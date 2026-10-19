"""
══════════════════════════════════════════════════════════════════
razorpay_service.py — Direct REST API Client for Razorpay
Tara Astro Vision
══════════════════════════════════════════════════════════════════
Replaces the official python `razorpay` SDK with direct, secure
HTTP requests (using httpx) and standard library hmac/hashlib.

Endpoints implemented:
  - POST /v1/orders               (Create Order)
  - GET  /v1/orders/{id}          (Fetch Order)
  - GET  /v1/payments/{id}        (Fetch Payment)
  - POST /v1/payments/{id}/refund (Create Refund)

Security:
  - Key secret NEVER leaves backend environment variables.
  - Uses HTTP Basic Authentication (key_id, key_secret).
  - Payment signature verified via HMAC-SHA256 with constant-time comparison.
  - Webhook signature verified via HMAC-SHA256 on raw request body.
══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Any, Dict, Optional

import httpx

log = logging.getLogger("taraastrovision.razorpay")

RAZORPAY_API_BASE = "https://api.razorpay.com/v1"


class RazorpayAPIError(Exception):
    """Raised when Razorpay REST API returns an error or cannot be reached."""

    def __init__(self, message: str, status_code: int = 502, error_data: Optional[dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_data = error_data or {}


class SignatureVerificationError(Exception):
    """Raised when payment or webhook HMAC-SHA256 signature verification fails."""
    pass


class _OrderNamespace:
    """Namespace mimic for backward compatibility with SDK's client.order.*"""

    def __init__(self, client: "RazorpayClient"):
        self._c = client

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._c.create_order(
            amount=data.get("amount", 0),
            currency=data.get("currency", "INR"),
            receipt=data.get("receipt", ""),
            notes=data.get("notes") or {},
        )

    def fetch(self, order_id: str) -> Dict[str, Any]:
        return self._c.fetch_order(order_id)


class _PaymentNamespace:
    """Namespace mimic for backward compatibility with SDK's client.payment.*"""

    def __init__(self, client: "RazorpayClient"):
        self._c = client

    def fetch(self, payment_id: str) -> Dict[str, Any]:
        return self._c.fetch_payment(payment_id)

    def refund(self, payment_id: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        data = data or {}
        return self._c.create_refund(
            payment_id=payment_id,
            amount=data.get("amount"),
            notes=data.get("notes") or {},
        )


class _UtilityNamespace:
    """Namespace mimic for backward compatibility with SDK's client.utility.*"""

    def __init__(self, client: "RazorpayClient"):
        self._c = client

    def verify_payment_signature(self, parameters: Dict[str, str]) -> bool:
        order_id = parameters.get("razorpay_order_id", "")
        payment_id = parameters.get("razorpay_payment_id", "")
        signature = parameters.get("razorpay_signature", "")
        return self._c.verify_payment_signature(order_id, payment_id, signature)

    def verify_webhook_signature(
        self, body: bytes | str, signature: str, secret: Optional[str] = None
    ) -> bool:
        return self._c.verify_webhook_signature(body, signature, secret)


class RazorpayClient:
    """
    Direct REST API Client for Razorpay.
    Makes authenticated server-to-server requests without requiring the python razorpay SDK.
    """

    def __init__(
        self,
        key_id: Optional[str] = None,
        key_secret: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        timeout: float = 15.0,
    ):
        self.key_id = (key_id or os.getenv("RAZORPAY_KEY_ID", "")).strip()
        self.key_secret = (key_secret or os.getenv("RAZORPAY_KEY_SECRET", "")).strip()
        self.webhook_secret = (webhook_secret or os.getenv("RAZORPAY_WEBHOOK_SECRET", "")).strip()
        self.timeout = timeout

        # Namespaced helpers matching old SDK structure
        self.order = _OrderNamespace(self)
        self.payment = _PaymentNamespace(self)
        self.utility = _UtilityNamespace(self)

    @property
    def is_configured(self) -> bool:
        return bool(self.key_id and self.key_secret)

    def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute authenticated request against Razorpay REST API."""
        if not self.is_configured:
            raise RazorpayAPIError(
                "Razorpay credentials not configured. Please set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET.",
                status_code=500,
            )

        url = f"{RAZORPAY_API_BASE}/{path.lstrip('/')}"
        auth = (self.key_id, self.key_secret)

        try:
            with httpx.Client(timeout=self.timeout) as http:
                res = http.request(
                    method=method.upper(),
                    url=url,
                    auth=auth,
                    json=json_data,
                    headers={"Accept": "application/json", "User-Agent": "TaraAstroVision/1.0"},
                )
        except Exception as exc:
            log.error(f"Network error communicating with Razorpay ({method} {url}): {exc}")
            raise RazorpayAPIError(f"Could not connect to Razorpay API: {exc}", status_code=502)

        try:
            data = res.json()
        except Exception:
            data = {"error": {"description": res.text}}

        if not res.is_success:
            err_msg = ""
            if isinstance(data, dict) and "error" in data:
                err_info = data["error"]
                if isinstance(err_info, dict):
                    err_msg = err_info.get("description") or err_info.get("message") or str(err_info)
                else:
                    err_msg = str(err_info)
            if not err_msg:
                err_msg = f"Razorpay API returned HTTP {res.status_code}"
            log.error(f"Razorpay API returned {res.status_code}: {err_msg}")
            raise RazorpayAPIError(err_msg, status_code=res.status_code, error_data=data)

        return data

    # ── Orders API ───────────────────────────────────────────────

    def create_order(
        self,
        amount: int,
        currency: str = "INR",
        receipt: str = "",
        notes: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a Razorpay order via POST /v1/orders.
        amount: integer amount in paise (e.g. 300 for ₹3.00)
        """
        payload: Dict[str, Any] = {
            "amount": int(amount),
            "currency": currency or "INR",
            "receipt": (receipt or "")[:40],
            "notes": notes or {},
        }
        return self._request("POST", "/orders", json_data=payload)

    def fetch_order(self, order_id: str) -> Dict[str, Any]:
        """Fetch order details via GET /v1/orders/{order_id}."""
        if not order_id:
            raise RazorpayAPIError("order_id is required", status_code=400)
        return self._request("GET", f"/orders/{order_id}")

    # ── Payments API ─────────────────────────────────────────────

    def fetch_payment(self, payment_id: str) -> Dict[str, Any]:
        """Fetch payment details via GET /v1/payments/{payment_id}."""
        if not payment_id:
            raise RazorpayAPIError("payment_id is required", status_code=400)
        return self._request("GET", f"/payments/{payment_id}")

    # ── Refunds API ──────────────────────────────────────────────

    def create_refund(
        self,
        payment_id: str,
        amount: Optional[int] = None,
        notes: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Initiate a refund via POST /v1/payments/{payment_id}/refund.
        amount: Optional integer in paise. If omitted, Razorpay refunds the full amount.
        """
        if not payment_id:
            raise RazorpayAPIError("payment_id is required for refund", status_code=400)
        payload: Dict[str, Any] = {"notes": notes or {}}
        if amount is not None:
            payload["amount"] = int(amount)
        return self._request("POST", f"/payments/{payment_id}/refund", json_data=payload)

    # ── Signature Verification ───────────────────────────────────

    def verify_payment_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        """
        Verify payment signature using HMAC-SHA256 with constant-time comparison.
        Payload format required by Razorpay: f"{order_id}|{payment_id}"
        """
        if not order_id or not payment_id or not signature:
            raise SignatureVerificationError("Missing required parameters for payment signature verification")

        if not self.key_secret:
            raise SignatureVerificationError("RAZORPAY_KEY_SECRET is not configured")

        msg = f"{order_id}|{payment_id}"
        expected = hmac.new(
            self.key_secret.encode("utf-8"),
            msg.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            raise SignatureVerificationError("Invalid Razorpay payment signature")

        return True

    def verify_webhook_signature(
        self, body: bytes | str, signature: str, secret: Optional[str] = None
    ) -> bool:
        """
        Verify webhook payload signature using HMAC-SHA256 with constant-time comparison.
        """
        key = (secret or self.webhook_secret or "").strip()
        if not key:
            raise SignatureVerificationError("RAZORPAY_WEBHOOK_SECRET is not configured")
        if not signature:
            raise SignatureVerificationError("Missing webhook signature")

        body_bytes = body.encode("utf-8") if isinstance(body, str) else body
        expected = hmac.new(
            key.encode("utf-8"),
            body_bytes,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            raise SignatureVerificationError("Invalid Razorpay webhook signature")

        return True
