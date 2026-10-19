"""
══════════════════════════════════════════════════════════════════
Tara Astro Vision — Automated Payment & Booking Test Suite
══════════════════════════════════════════════════════════════════

Tests use mocked Razorpay responses — NO real charges are made.
Run with:
    .venv/bin/python -m pytest test_payments.py -v

Coverage:
  Phase 3 — Razorpay order creation (25 scenarios)
  Phase 4 — Frontend API URL logic (2 scenarios)
  Phase 5 — Payment signature verification (9 scenarios)
  Phase 6 — Booking confirmation (8 scenarios)
  Phase 7 — Error / edge-case handling (7 scenarios)
  Phase 9 — Health endpoint (1 scenario)
══════════════════════════════════════════════════════════════════
"""

import os, sys, json, hmac, hashlib, importlib, sqlite3, time, types, tempfile, itertools
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# ── Ensure main.py can be imported ────────────────────────────
SRC = Path(__file__).parent
sys.path.insert(0, str(SRC))

# ── Set test env vars BEFORE importing main ───────────────────
os.environ.setdefault("JWT_SECRET", "test_secret_do_not_use_in_production")
os.environ["RAZORPAY_KEY_ID"] = "rzp_test_TESTKEY"
os.environ["RAZORPAY_KEY_SECRET"] = "test_secret_key"
os.environ["RAZORPAY_WEBHOOK_SECRET"] = "webhook_secret"

# Use a temporary SQLite DB for tests
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["DATABASE_URL"] = _tmp_db.name

# ── CORS must allow test client ────────────────────────────────
os.environ["CORS_ORIGINS"] = (
    "https://www.taraastrovision.com,http://testserver,http://localhost:8000"
)

import main  # noqa: E402 — import after env setup
from main import app  # noqa: E402

main.DATABASE_URL = _tmp_db.name
main.init_db()

client = TestClient(app, raise_server_exceptions=False)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _sign(order_id: str, payment_id: str, secret: str = "test_secret_key") -> str:
    """Compute HMAC-SHA256 signature identical to Razorpay's algorithm."""
    msg = f"{order_id}|{payment_id}"
    return hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()


_order_ids = itertools.count(1)


def _mock_rzp_order(order_id=None, amount=11600, currency="INR"):
    """Return a mock Razorpay order dict."""
    return {
        "id": order_id or f"order_TEST_{next(_order_ids)}",
        "amount": amount,
        "currency": currency,
        "receipt": "tav_test",
        "status": "created",
    }


def _rzp_client_patch(order_id=None, amount=11600, status="captured", currency="INR"):
    """Context-manager: patches razorpay.Client so tests don't hit the API."""
    mock_client = MagicMock()
    order = _mock_rzp_order(order_id, amount, currency)
    mock_client.order.create.return_value = order
    mock_client.order.fetch.return_value = {
        "id": order["id"], "amount": amount, "currency": currency,
    }
    mock_client.payment.fetch.return_value = {
        "id": "pay_TEST456", "order_id": order["id"], "amount": amount,
        "currency": currency, "status": status,
    }
    mock_client.utility.verify_payment_signature.return_value = None  # no exception = valid
    return patch("main._rzp_client", return_value=mock_client)


def _make_booking_payload(
    booking_id="TAV-TEST-001",
    rzp_order=None,
    rzp_payment=None,
    price=3.0,
    status="paid",
):
    """Build a minimal valid /api/booking/confirm payload."""
    rzp_order = rzp_order or f"order_{booking_id}"
    rzp_payment = rzp_payment or f"pay_{booking_id}"
    _, total = main.validate_and_price("Siva Abhishekam", "pooja", 1)
    amount_paise = int(round(total * 100))
    with sqlite3.connect(main.DATABASE_URL) as conn:
        conn.execute(
            """INSERT OR REPLACE INTO payment_orders (
                   order_id, booking_id, service_name, service_type, persons,
                   amount_paise, currency, status, payment_id
               ) VALUES (?, ?, ?, ?, ?, ?, 'INR', 'created', ?)""",
            (rzp_order, booking_id, "Siva Abhishekam", "pooja", 1, amount_paise, rzp_payment),
        )
    return {
        "id": booking_id,
        "type": "pooja",
        "name": "Siva Abhishekam",
        "price": price,
        "persons": 1,
        "participants": [{"name": "Test User", "gotra": "Bharadwaja", "relation": "Self"}],
        "contactEmail": "test@example.com",
        "contactPhone": "9999999999",
        "status": status,
        "paidAt": "2026-10-09T08:00:00.000Z",
        "razorpayOrderId": rzp_order,
        "razorpayPaymentId": rzp_payment,
        "razorpaySignature": "test-signature",
        "scheduledDate": "2026-10-15",
    }


def _confirm_rzp_client(payload):
    _, total = main.validate_and_price(payload["name"], payload["type"], payload["persons"])
    amount_paise = int(round(total * 100))
    mock = MagicMock()
    mock.order.fetch.return_value = {
        "id": payload["razorpayOrderId"],
        "amount": amount_paise,
        "currency": "INR",
    }
    mock.payment.fetch.return_value = {
        "id": payload["razorpayPaymentId"],
        "order_id": payload["razorpayOrderId"],
        "amount": amount_paise,
        "currency": "INR",
        "status": "captured",
    }
    mock.utility.verify_payment_signature.return_value = None
    return mock


# ═══════════════════════════════════════════════════════════════
# PHASE 9 — Health endpoint
# ═══════════════════════════════════════════════════════════════

class TestHealth:
    def test_health_returns_200(self):
        r = client.get("/api/health")
        assert r.status_code == 200

    def test_health_body_safe(self):
        r = client.get("/api/health")
        body = r.json()
        assert body["status"] == "healthy"
        # Must not expose secrets or file paths
        text = json.dumps(body)
        assert "secret" not in text.lower()
        assert "/" not in text or body.get("system")  # system value may contain "/"

    def test_health_shows_razorpay_configured(self):
        """Health endpoint must report razorpay_configured=True when env vars are set."""
        # Ensure module-level vars match env (in case a prior test blanked them)
        main.RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "rzp_test_TESTKEY")
        main.RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "test_secret_key")
        r = client.get("/api/health")
        body = r.json()
        # Health checks os.getenv which IS set — must be True
        assert body.get("razorpay_configured") is True


# ═══════════════════════════════════════════════════════════════
# PHASE 3 — Razorpay order creation
# ═══════════════════════════════════════════════════════════════

class TestOrderCreation:
    def test_valid_order_returns_key_and_order_id(self):
        with _rzp_client_patch("order_ABC", 31600):
            r = client.post("/api/payment/order", json={
                "name": "Kumkum Archana",
                "serviceType": "pooja",
                "bookingId": "TAV-001"
            })
        assert r.status_code == 200
        body = r.json()
        assert body["order_id"] == "order_ABC"
        assert body["key_id"] == "rzp_test_TESTKEY"
        assert body["amount"] == 31600
        assert body["currency"] == "INR"

    def test_key_secret_not_in_response(self):
        with _rzp_client_patch():
            r = client.post("/api/payment/order", json={"name": "Siva Astottara Pooja"})
        assert "key_secret" not in r.text
        assert "test_secret_key" not in r.text

    def test_amount_converted_to_paise(self):
        with _rzp_client_patch("order_X", 51600) as m:
            client.post("/api/payment/order", json={"name": "Ekadasa Rudrabhishekam"})
            call_kwargs = m.return_value.order.create.call_args[0][0]
            assert call_kwargs["amount"] == 51600

    def test_currency_is_inr(self):
        with _rzp_client_patch() as m:
            client.post("/api/payment/order", json={"name": "Siva Astottara Pooja"})
            assert m.return_value.order.create.call_args[0][0]["currency"] == "INR"

    def test_amount_below_minimum_rejected(self):
        # Unknown or invalid service name produces 400
        r = client.post("/api/payment/order", json={"name": "Invalid Service Free"})
        assert r.status_code == 400

    def test_zero_amount_rejected(self):
        r = client.post("/api/payment/order", json={"name": ""})
        assert r.status_code == 400

    def test_negative_amount_rejected(self):
        r = client.post("/api/payment/order", json={"name": "Fake Pooja -100"})
        assert r.status_code == 400

    def test_missing_credentials_returns_500(self):
        """Missing Razorpay credentials must produce 500, not 200 or crash."""
        saved_id = main.RAZORPAY_KEY_ID
        saved_secret = main.RAZORPAY_KEY_SECRET
        try:
            main.RAZORPAY_KEY_ID = ""
            main.RAZORPAY_KEY_SECRET = ""
            # Patch _rzp_client to read the now-empty module vars
            with patch("main.RAZORPAY_KEY_ID", ""), patch("main.RAZORPAY_KEY_SECRET", ""):
                r = client.post("/api/payment/order", json={"name": "Siva Astottara Pooja"})
            assert r.status_code == 500
        finally:
            main.RAZORPAY_KEY_ID = saved_id
            main.RAZORPAY_KEY_SECRET = saved_secret

    def test_razorpay_api_error_returns_502(self):
        mock_client = MagicMock()
        mock_client.order.create.side_effect = Exception("Network timeout")
        with patch("main._rzp_client", return_value=mock_client):
            r = client.post("/api/payment/order", json={"name": "Siva Astottara Pooja"})
        assert r.status_code == 502

    def test_invalid_amount_string_rejected(self):
        r = client.post("/api/payment/order", json={"name": "Unknown"})
        assert r.status_code in (400, 422)

    def test_receipt_truncated_to_40_chars(self):
        long_id = "TAV-" + "X" * 60
        with _rzp_client_patch() as m:
            client.post("/api/payment/order", json={"name": "Siva Astottara Pooja", "bookingId": long_id})
            receipt = m.return_value.order.create.call_args[0][0]["receipt"]
            assert len(receipt) <= 40

    def test_optional_booking_id_accepted(self):
        with _rzp_client_patch():
            r = client.post("/api/payment/order", json={"name": "Siva Astottara Pooja"})
        assert r.status_code == 200

    def test_contact_email_in_notes(self):
        with _rzp_client_patch() as m:
            client.post("/api/payment/order", json={
                "name": "Siva Astottara Pooja", "contactEmail": "user@example.com"
            })
            notes = m.return_value.order.create.call_args[0][0]["notes"]
            assert notes.get("email") == "user@example.com"


# ═══════════════════════════════════════════════════════════════
# PHASE 5 — Payment signature verification
# ═══════════════════════════════════════════════════════════════

class TestPaymentVerification:
    @pytest.fixture(autouse=True)
    def register_order(self):
        with sqlite3.connect(main.DATABASE_URL) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO payment_orders (
                       order_id, booking_id, service_name, service_type, persons,
                       amount_paise, currency, status
                   ) VALUES ('order_TEST123', NULL, 'Siva Abhishekam', 'pooja', 1, 30000, 'INR', 'created')"""
            )

    def test_valid_signature_returns_200(self):
        sig = _sign("order_TEST123", "pay_TEST456")
        mock_client = MagicMock()
        mock_client.utility.verify_payment_signature.return_value = None  # no exception
        mock_client.order.fetch.return_value = {"id": "order_TEST123", "amount": 30000, "currency": "INR"}
        mock_client.payment.fetch.return_value = {"id": "pay_TEST456", "order_id": "order_TEST123", "amount": 30000, "currency": "INR", "status": "captured"}
        with patch("main._rzp_client", return_value=mock_client):
            r = client.post("/api/payment/verify", json={
                "razorpay_order_id":  "order_TEST123",
                "razorpay_payment_id": "pay_TEST456",
                "razorpay_signature": sig,
            })
        assert r.status_code == 200
        assert r.json()["verified"] is True

    def test_invalid_signature_returns_400(self):
        mock_client = MagicMock()
        mock_client.utility.verify_payment_signature.side_effect = Exception("SignatureVerificationError")
        with patch("main._rzp_client", return_value=mock_client):
            r = client.post("/api/payment/verify", json={
                "razorpay_order_id":  "order_TEST123",
                "razorpay_payment_id": "pay_TEST456",
                "razorpay_signature": "bad_signature",
            })
        assert r.status_code == 400

    def test_missing_signature_field_rejected(self):
        r = client.post("/api/payment/verify", json={
            "razorpay_order_id": "order_TEST123",
            "razorpay_payment_id": "pay_TEST456",
            # razorpay_signature omitted
        })
        assert r.status_code == 422  # Pydantic validation error

    def test_empty_signature_rejected(self):
        mock_client = MagicMock()
        mock_client.utility.verify_payment_signature.side_effect = Exception("Bad sig")
        with patch("main._rzp_client", return_value=mock_client):
            r = client.post("/api/payment/verify", json={
                "razorpay_order_id":  "order_TEST123",
                "razorpay_payment_id": "pay_TEST456",
                "razorpay_signature": "",
            })
        # Empty string must be caught — either 400 from our guard or from SDK
        assert r.status_code in (400, 422)

    def test_missing_order_id_rejected(self):
        r = client.post("/api/payment/verify", json={
            "razorpay_payment_id": "pay_TEST456",
            "razorpay_signature": "some_sig",
        })
        assert r.status_code == 422

    def test_response_does_not_contain_key_secret(self):
        mock_client = MagicMock()
        mock_client.utility.verify_payment_signature.return_value = None
        mock_client.order.fetch.return_value = {"id": "order_TEST123", "amount": 30000, "currency": "INR"}
        mock_client.payment.fetch.return_value = {"id": "pay_TEST456", "order_id": "order_TEST123", "amount": 30000, "currency": "INR", "status": "captured"}
        with patch("main._rzp_client", return_value=mock_client):
            r = client.post("/api/payment/verify", json={
                "razorpay_order_id":  "order_TEST123",
                "razorpay_payment_id": "pay_TEST456",
                "razorpay_signature": "sig",
            })
        assert "test_secret_key" not in r.text

    def test_verify_returns_order_and_payment_ids(self):
        mock_client = MagicMock()
        mock_client.utility.verify_payment_signature.return_value = None
        mock_client.order.fetch.return_value = {"id": "order_TEST123", "amount": 30000, "currency": "INR"}
        mock_client.payment.fetch.return_value = {"id": "pay_TEST456", "order_id": "order_TEST123", "amount": 30000, "currency": "INR", "status": "captured"}
        with patch("main._rzp_client", return_value=mock_client):
            r = client.post("/api/payment/verify", json={
                "razorpay_order_id":  "order_TEST123",
                "razorpay_payment_id": "pay_TEST456",
                "razorpay_signature": "sig",
            })
        body = r.json()
        assert body["razorpay_order_id"] == "order_TEST123"
        assert body["razorpay_payment_id"] == "pay_TEST456"


# ═══════════════════════════════════════════════════════════════
# PHASE 6 — Booking confirmation
# ═══════════════════════════════════════════════════════════════

class TestBookingConfirmation:
    def test_valid_booking_saved(self):
        payload = _make_booking_payload("TAV-CONF-001")
        with patch("main._rzp_client", return_value=_confirm_rzp_client(payload)), \
             patch("main.send_email", return_value=True):
            r = client.post("/api/booking/confirm", json=payload)
        assert r.status_code == 200
        assert r.json()["id"] == "TAV-CONF-001"

    def test_booking_without_payment_id_rejected(self):
        payload = _make_booking_payload("TAV-CONF-002")
        payload["razorpayPaymentId"] = None
        r = client.post("/api/booking/confirm", json=payload)
        assert r.status_code == 400

    def test_booking_without_order_id_rejected(self):
        payload = _make_booking_payload("TAV-CONF-003")
        payload["razorpayOrderId"] = None
        r = client.post("/api/booking/confirm", json=payload)
        assert r.status_code == 400

    def test_duplicate_booking_idempotent(self):
        """Second confirm with same ID must NOT create duplicate; returns 200."""
        payload = _make_booking_payload("TAV-CONF-DUP")
        with patch("main._rzp_client", return_value=_confirm_rzp_client(payload)), \
             patch("main.send_email", return_value=True):
            r1 = client.post("/api/booking/confirm", json=payload)
            r2 = client.post("/api/booking/confirm", json=payload)
        assert r1.status_code == 200
        assert r2.status_code == 200
        # Verify database has exactly ONE row for this booking
        conn = sqlite3.connect(main.DATABASE_URL)
        rows = conn.execute(
            "SELECT COUNT(*) FROM bookings WHERE id = ?", ("TAV-CONF-DUP",)
        ).fetchone()[0]
        conn.close()
        assert rows == 1, f"Expected 1 booking row, got {rows}"

    def test_booking_status_set_to_paid(self):
        """Booking must be stored with status='paid' regardless of what frontend sends."""
        payload = _make_booking_payload("TAV-CONF-STATUS")
        payload["status"] = "pending_payment"  # frontend may send wrong value
        with patch("main._rzp_client", return_value=_confirm_rzp_client(payload)), \
             patch("main.send_email", return_value=True):
            r = client.post("/api/booking/confirm", json=payload)
        assert r.status_code == 200
        conn = sqlite3.connect(main.DATABASE_URL)
        row = conn.execute(
            "SELECT status FROM bookings WHERE id = ?", ("TAV-CONF-STATUS",)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "paid"

    def test_email_failure_does_not_lose_booking(self):
        """Email failure after DB save must still return 200; booking must be in DB."""
        payload = _make_booking_payload("TAV-CONF-NOEMAIL")
        with patch("main._rzp_client", return_value=_confirm_rzp_client(payload)), \
             patch("main.send_email", return_value=False):
            r = client.post("/api/booking/confirm", json=payload)
        assert r.status_code == 200
        conn = sqlite3.connect(main.DATABASE_URL)
        row = conn.execute(
            "SELECT id FROM bookings WHERE id = ?", ("TAV-CONF-NOEMAIL",)
        ).fetchone()
        conn.close()
        assert row is not None

    def test_missing_participants_rejected(self):
        payload = _make_booking_payload("TAV-CONF-NOPT")
        payload["participants"] = []  # empty list
        with patch("main._rzp_client", return_value=_confirm_rzp_client(payload)), \
             patch("main.send_email", return_value=True):
            r = client.post("/api/booking/confirm", json=payload)
        # Empty list is rejected with 400
        assert r.status_code in (400, 422)

    def test_missing_signature_rejected(self):
        payload = _make_booking_payload("TAV-CONF-NOSIG")
        payload.pop("razorpaySignature")
        r = client.post("/api/booking/confirm", json=payload)
        assert r.status_code == 400

    def test_confirm_rejects_order_amount_mismatch(self):
        payload = _make_booking_payload("TAV-CONF-WRONG-AMOUNT")
        mock = _confirm_rzp_client(payload)
        mock.order.fetch.return_value["amount"] += 1
        with patch("main._rzp_client", return_value=mock):
            r = client.post("/api/booking/confirm", json=payload)
        assert r.status_code == 400

    def test_confirm_rejects_authorized_not_captured_payment(self):
        payload = _make_booking_payload("TAV-CONF-AUTHORIZED")
        mock = _confirm_rzp_client(payload)
        mock.payment.fetch.return_value["status"] = "authorized"
        with patch("main._rzp_client", return_value=mock):
            r = client.post("/api/booking/confirm", json=payload)
        assert r.status_code == 400


# ═══════════════════════════════════════════════════════════════
# PHASE 7 — Error / edge-case handling
# ═══════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_health_endpoint_reachable(self):
        r = client.get("/api/health")
        assert r.status_code == 200

    def test_root_returns_200(self):
        """Root path must return 200 (serves index.html or JSON fallback)."""
        r = client.get("/")
        assert r.status_code == 200

    def test_large_amount_rejected(self):
        """Amount exceeding MAX_ORDER_PAISE cap must be rejected."""
        os.environ["MAX_ORDER_PAISE"] = "100"  # cap at ₹1 for this test
        with _rzp_client_patch():
            r = client.post("/api/payment/order", json={"name": "Siva Astottara Pooja"})
        # Restore
        os.environ.pop("MAX_ORDER_PAISE", None)
        assert r.status_code == 400

    def test_payment_verify_network_error_safe(self):
        """SDK raising a non-signature exception must still return 400, not 500."""
        with sqlite3.connect(main.DATABASE_URL) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO payment_orders (
                       order_id, service_name, service_type, persons, amount_paise, currency
                   ) VALUES ('order_TEST123', 'Siva Abhishekam', 'pooja', 1, 30000, 'INR')"""
            )
        mock_client = MagicMock()
        mock_client.utility.verify_payment_signature.side_effect = ConnectionError("timeout")
        with patch("main._rzp_client", return_value=mock_client):
            r = client.post("/api/payment/verify", json={
                "razorpay_order_id":  "order_TEST123",
                "razorpay_payment_id": "pay_TEST456",
                "razorpay_signature": "sig",
            })
        assert r.status_code in (400, 502)

    def test_confirm_wrong_payment_id_rejected(self):
        """Booking without a razorpayPaymentId must fail before DB write."""
        payload = _make_booking_payload("TAV-WRONGPAY")
        payload["razorpayPaymentId"] = ""
        r = client.post("/api/booking/confirm", json=payload)
        assert r.status_code == 400

    def test_webhook_bad_signature_rejected(self):
        """Webhook with wrong signature must return 400."""
        body = json.dumps({"event": "payment.captured"}).encode()
        r = client.post(
            "/api/payment/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": "badsig",
            },
        )
        assert r.status_code == 400

    def test_webhook_valid_signature_accepted(self):
        """Webhook with correct HMAC-SHA256 signature must return 200."""
        body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_WH1", "order_id": "order_WH1", "status": "captured"}}}}).encode()
        sig = hmac.new(b"webhook_secret", body, hashlib.sha256).hexdigest()
        r = client.post(
            "/api/payment/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": sig,
            },
        )
        assert r.status_code == 200

    def test_webhook_reconciles_captured_payment_once(self):
        payload = _make_booking_payload("TAV-WEBHOOK-CAPTURE")
        order, payment = payload["razorpayOrderId"], payload["razorpayPaymentId"]
        _, total = main.validate_and_price(payload["name"], payload["type"], payload["persons"])
        amount = int(round(total * 100))
        with sqlite3.connect(main.DATABASE_URL) as conn:
            conn.execute(
                """INSERT INTO bookings (
                       id, type, name, customer_name, price, persons, participants,
                       contact_email, contact_phone, status, razorpay_order_id
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_payment', ?)""",
                (
                    payload["id"], payload["type"], payload["name"], "Webhook User",
                    total, 1, json.dumps(payload["participants"]), payload["contactEmail"],
                    payload["contactPhone"], order,
                ),
            )
        event = {
            "event": "payment.captured",
            "payload": {"payment": {"entity": {
                "id": payment, "order_id": order, "status": "captured",
                "amount": amount, "currency": "INR",
            }}},
        }
        body = json.dumps(event).encode()
        signature = hmac.new(b"webhook_secret", body, hashlib.sha256).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
            "X-Razorpay-Event-Id": "event-webhook-capture-once",
        }
        first = client.post("/api/payment/webhook", content=body, headers=headers)
        duplicate = client.post("/api/payment/webhook", content=body, headers=headers)
        assert first.status_code == 200
        assert duplicate.json()["status"] == "duplicate"
        with sqlite3.connect(main.DATABASE_URL) as conn:
            saved = conn.execute(
                "SELECT status, payment_status, razorpay_payment_id FROM bookings WHERE id=?",
                (payload["id"],),
            ).fetchone()
            order_state = conn.execute(
                "SELECT status, payment_id FROM payment_orders WHERE order_id=?",
                (order,),
            ).fetchone()
        assert saved == ("paid", "paid", payment)
        assert order_state == ("captured", payment)

    def test_webhook_failure_keeps_booking_unpaid(self):
        payload = _make_booking_payload("TAV-WEBHOOK-FAILED")
        event = {
            "event": "payment.failed",
            "payload": {"payment": {"entity": {
                "id": payload["razorpayPaymentId"],
                "order_id": payload["razorpayOrderId"],
                "status": "failed",
            }}},
        }
        body = json.dumps(event).encode()
        signature = hmac.new(b"webhook_secret", body, hashlib.sha256).hexdigest()
        response = client.post(
            "/api/payment/webhook",
            content=body,
            headers={"X-Razorpay-Signature": signature},
        )
        assert response.status_code == 200
        with sqlite3.connect(main.DATABASE_URL) as conn:
            order_state = conn.execute(
                "SELECT status FROM payment_orders WHERE order_id=?",
                (payload["razorpayOrderId"],),
            ).fetchone()
        assert order_state == ("failed",)

    def test_public_static_mount_hides_database_and_environment_files(self):
        for path in ("/jyotisha.db", "/.env", "/main.py", "/.jwt_secret"):
            assert client.get(path).status_code == 404


# ═══════════════════════════════════════════════════════════════
# Frontend API URL logic (static inspection)
# ═══════════════════════════════════════════════════════════════

class TestFrontendApiUrl:
    """Verify the frontend API-base configuration is present and configurable."""

    def test_production_api_base_is_configurable_and_https_ready(self):
        config = (SRC / "api-config.js").read_text(encoding="utf-8")
        assert "productionApiBase" in config
        assert "window.TAV_API_BASE" in config
        assert "replace(/\\/+$/, '')" in config

    def test_localhost_uses_absolute_url(self):
        config = (SRC / "api-config.js").read_text(encoding="utf-8")
        assert "localhost" in config
        assert "8000" in config
        html = (SRC / "index.html").read_text(encoding="utf-8")
        assert 'src="/api-config.js"' in html

    def test_booking_js_uses_api_base(self):
        with open(SRC / "booking.js", encoding="utf-8") as f:
            js = f.read()
        assert "TAV_API_BASE" in js
        assert "/api/payment/order" in js
        assert "/api/payment/verify" in js
        assert "/api/booking/confirm" in js


# ═══════════════════════════════════════════════════════════════
# Cleanup
# ═══════════════════════════════════════════════════════════════

def pytest_sessionfinish(session, exitstatus):
    """Remove temp test database."""
    try:
        Path(_tmp_db.name).unlink(missing_ok=True)
    except Exception:
        pass
