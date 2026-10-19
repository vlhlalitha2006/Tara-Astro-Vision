"""
test_booking_and_report.py
══════════════════════════════════════════════════════════════════
Automated tests for:
  1. Service catalogue price validation
  2. Razorpay order creation (mocked)
  3. Payment signature verification (mocked)
  4. Booking confirmation (mocked Razorpay, temp DB)
  5. Duplicate booking prevention
  6. Daily report generation and email
  7. IST timezone filtering
  8. Empty-report and failure handling
  9. Scheduler configuration existence
══════════════════════════════════════════════════════════════════
Run: .venv/bin/python -m pytest test_booking_and_report.py -v
"""
from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import os
import sqlite3
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# ── Set env vars BEFORE importing main ────────────────────────────
os.environ.setdefault("RAZORPAY_KEY_ID",     "rzp_test_TESTKEY")
os.environ.setdefault("RAZORPAY_KEY_SECRET", "test_secret_key_32chars_exactly_ok")
os.environ.setdefault("JWT_SECRET",          "test_jwt_secret_for_tests_only")
os.environ.setdefault("ADMIN_EMAIL",         "admin@test.example")
os.environ.setdefault("RAZORPAY_WEBHOOK_SECRET", "test_webhook_secret")

from fastapi.testclient import TestClient
import main
import daily_report
from service_catalogue import validate_and_price, get_service, all_services

# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def tmp_db(tmp_path_factory):
    """Fresh isolated SQLite DB for the test session."""
    db_path = str(tmp_path_factory.mktemp("data") / "test.db")
    return db_path


@pytest.fixture(scope="session", autouse=True)
def patch_database(tmp_db):
    """Point main.py and daily_report to the temp DB for the entire session."""
    with patch.object(main, "DATABASE_URL", tmp_db), \
         patch.object(daily_report, "DATABASE_URL", tmp_db):
        main.init_db()
        yield


@pytest.fixture(scope="session")
def client():
    return TestClient(main.app)


# ─────────────────────────────────────────────────────────────────
# 1. SERVICE CATALOGUE VALIDATION
# ─────────────────────────────────────────────────────────────────

class TestServiceCatalogue:
    def test_known_pooja_has_correct_price(self):
        svc, total = validate_and_price("Siva Abhishekam", "pooja", 1)
        assert svc.name == "Siva Abhishekam"
        assert svc.price == 3.0
        assert total == 3.0

    def test_known_homam_price_per_person(self):
        svc, total = validate_and_price("Kala Bhairava Homam", "homam", 2)
        assert svc.price == 2000.0
        assert total == 4000.0

    def test_unknown_service_raises(self):
        with pytest.raises(ValueError, match="Unknown service"):
            validate_and_price("Fake Pooja That Doesnt Exist", "pooja", 1)

    def test_wrong_type_raises(self):
        with pytest.raises(ValueError, match="is a pooja, not a homam"):
            validate_and_price("Siva Abhishekam", "homam", 1)

    def test_homam_as_pooja_raises(self):
        with pytest.raises(ValueError, match="is a homam, not a pooja"):
            validate_and_price("Kala Bhairava Homam", "pooja", 1)

    def test_all_services_returns_list(self):
        services = all_services()
        assert isinstance(services, list)
        assert len(services) >= 30  # poojas + homams

    def test_get_service_returns_none_for_unknown(self):
        assert get_service("nonexistent") is None

    def test_every_pooja_price_is_positive(self):
        for svc in all_services():
            assert svc["price"] > 0, f"{svc['name']} has non-positive price"

    def test_homam_max_persons_enforced(self):
        svc = get_service("Kala Bhairava Homam")
        with pytest.raises(ValueError, match="Maximum"):
            validate_and_price(svc.name, "homam", svc.max_persons + 1)

    def test_price_for_all_catalogue_services(self):
        """Smoke test: every service in the catalogue returns a positive total."""
        for entry in all_services():
            _, total = validate_and_price(entry["name"], entry["type"], 1, check_availability=False)
            assert total > 0
            if entry.get("available"):
                _, total_avail = validate_and_price(entry["name"], entry["type"], 1)
                assert total_avail > 0
            else:
                with pytest.raises(ValueError, match="Coming Soon"):
                    validate_and_price(entry["name"], entry["type"], 1)


# ─────────────────────────────────────────────────────────────────
# 2. ORDER CREATION — SERVER CALCULATES PRICE
# ─────────────────────────────────────────────────────────────────

MOCK_ORDER = {"id": "order_TEST001", "amount": 300, "currency": "INR"}


class TestOrderCreation:
    def test_valid_pooja_returns_server_price(self, client):
        with patch("main._rzp_client") as mock_rzp:
            mock_rzp.return_value.order.create.return_value = MOCK_ORDER
            r = client.post("/api/payment/order", json={
                "name": "Siva Abhishekam",
                "serviceType": "pooja",
                "persons": 1,
                "bookingId": "TEST-001",
            })
        assert r.status_code == 200
        body = r.json()
        assert body["order_id"] == "order_TEST001"
        assert body["service_name"] == "Siva Abhishekam"
        assert body["unit_price"] == 3.0

    def test_browser_amount_is_ignored(self, client):
        """Even if browser sends a tampered amount, server uses catalogue price."""
        with patch("main._rzp_client") as mock_rzp:
            mock_rzp.return_value.order.create.return_value = {
                **MOCK_ORDER, "id": "order_TEST002"
            }
            r = client.post("/api/payment/order", json={
                "name": "Siva Abhishekam",
                "serviceType": "pooja",
                "amount": 1.0,   # tampered — should be ignored
                "persons": 1,
            })
        assert r.status_code == 200
        # Server should have used 3.0 (catalogue price), not 1.0
        assert r.json()["unit_price"] == 3.0

    def test_unknown_service_rejected(self, client):
        r = client.post("/api/payment/order", json={
            "name": "Hacker Pooja 0.01",
            "serviceType": "pooja",
        })
        assert r.status_code == 400
        assert "Unknown service" in r.json()["detail"]

    def test_missing_name_rejected(self, client):
        r = client.post("/api/payment/order", json={"serviceType": "pooja"})
        assert r.status_code in (400, 422)

    def test_wrong_type_rejected(self, client):
        r = client.post("/api/payment/order", json={
            "name": "Siva Abhishekam",
            "serviceType": "homam",  # wrong — it's a pooja
        })
        assert r.status_code == 400

    def test_homam_price_multiplied_by_persons(self, client):
        expected_paise = int(2000 * 3 * 100)
        mock_order = {"id": "order_HOM001", "amount": expected_paise, "currency": "INR"}
        with patch("main._rzp_client") as mock_rzp:
            mock_rzp.return_value.order.create.return_value = mock_order
            r = client.post("/api/payment/order", json={
                "name": "Kala Bhairava Homam",
                "serviceType": "homam",
                "persons": 3,
            })
        assert r.status_code == 200
        body = r.json()
        assert body["persons"] == 3
        assert body["unit_price"] == 2000.0

    def test_disabled_homam_order_rejected(self, client):
        """Disabled homams cannot be booked through API."""
        r = client.post("/api/payment/order", json={
            "name": "Kali Homam",
            "serviceType": "homam",
            "persons": 1,
        })
        assert r.status_code == 400
        assert "Coming Soon" in r.json()["detail"]

    def test_services_endpoint_returns_catalogue(self, client):
        r = client.get("/api/services")
        assert r.status_code == 200
        services = r.json()["services"]
        names = [s["name"] for s in services]
        assert "Siva Abhishekam" in names
        assert "Maha Mrityunjaya Homam" in names

    def test_key_id_in_response_not_secret(self, client):
        with patch("main._rzp_client") as mock_rzp:
            mock_rzp.return_value.order.create.return_value = {
                "id": "order_TEST003", "amount": 21600, "currency": "INR"
            }
            r = client.post("/api/payment/order", json={
                "name": "Ganesh Abhishekam",
                "serviceType": "pooja",
            })
        body = r.json()
        assert "key_id" in body
        secret = os.environ["RAZORPAY_KEY_SECRET"]
        assert secret not in str(body)


# ─────────────────────────────────────────────────────────────────
# 3. PAYMENT VERIFICATION — SIGNATURE + AMOUNT + STATUS
# ─────────────────────────────────────────────────────────────────

def _make_signature(order_id: str, payment_id: str, secret: str) -> str:
    msg = f"{order_id}|{payment_id}".encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


class TestPaymentVerification:
    ORDER_ID   = "order_VER001"
    PAYMENT_ID = "pay_VER001"

    @pytest.fixture(autouse=True)
    def register_order(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO payment_orders (
                       order_id, booking_id, service_name, service_type, persons,
                       amount_paise, currency, status
                   ) VALUES (?, NULL, 'Siva Abhishekam', 'pooja', 1, 11600, 'INR', 'created')""",
                (self.ORDER_ID,),
            )

    def _mock_rzp(self, status="captured", currency="INR", amount=11600):
        mock = MagicMock()
        mock.utility.verify_payment_signature.return_value = None
        mock.order.fetch.return_value  = {
            "id": self.ORDER_ID,
            "amount": amount,
            "currency": currency,
        }
        mock.payment.fetch.return_value = {
            "id": self.PAYMENT_ID,
            "status": status,
            "order_id": self.ORDER_ID,
            "amount": amount,
            "currency": currency,
        }
        return mock

    def test_valid_signature_returns_200(self, client):
        sig = _make_signature(self.ORDER_ID, self.PAYMENT_ID, os.environ["RAZORPAY_KEY_SECRET"])
        with patch("main._rzp_client", return_value=self._mock_rzp()):
            r = client.post("/api/payment/verify", json={
                "razorpay_order_id":   self.ORDER_ID,
                "razorpay_payment_id": self.PAYMENT_ID,
                "razorpay_signature":  sig,
            })
        assert r.status_code == 200
        assert r.json()["verified"] is True

    def test_invalid_signature_rejected(self, client):
        mock = MagicMock()
        mock.utility.verify_payment_signature.side_effect = Exception("Invalid")
        with patch("main._rzp_client", return_value=mock):
            r = client.post("/api/payment/verify", json={
                "razorpay_order_id":   self.ORDER_ID,
                "razorpay_payment_id": self.PAYMENT_ID,
                "razorpay_signature":  "bad_signature_value",
            })
        assert r.status_code == 400
        assert "invalid signature" in r.json()["detail"].lower()

    def test_non_inr_currency_rejected(self, client):
        with patch("main._rzp_client", return_value=self._mock_rzp(currency="USD")):
            r = client.post("/api/payment/verify", json={
                "razorpay_order_id":   self.ORDER_ID,
                "razorpay_payment_id": self.PAYMENT_ID,
                "razorpay_signature":  "sig",
            })
        assert r.status_code == 400
        assert "currency" in r.json()["detail"].lower()

    def test_amount_mismatch_rejected(self, client):
        with patch("main._rzp_client", return_value=self._mock_rzp(amount=9999)):
            r = client.post("/api/payment/verify", json={
                "razorpay_order_id":    self.ORDER_ID,
                "razorpay_payment_id":  self.PAYMENT_ID,
                "razorpay_signature":   "sig",
                "expected_amount_paise": 11600,  # doesn't match 9999
            })
        assert r.status_code == 400
        assert "amount" in r.json()["detail"].lower()

    def test_non_captured_payment_rejected(self, client):
        with patch("main._rzp_client", return_value=self._mock_rzp(status="failed")):
            r = client.post("/api/payment/verify", json={
                "razorpay_order_id":   self.ORDER_ID,
                "razorpay_payment_id": self.PAYMENT_ID,
                "razorpay_signature":  "sig",
            })
        assert r.status_code == 400
        assert "not been captured" in r.json()["detail"].lower()

    def test_mismatched_order_id_rejected(self, client):
        mock = self._mock_rzp()
        mock.payment.fetch.return_value = {"status": "captured", "order_id": "order_OTHER"}
        with patch("main._rzp_client", return_value=mock):
            r = client.post("/api/payment/verify", json={
                "razorpay_order_id":   self.ORDER_ID,
                "razorpay_payment_id": self.PAYMENT_ID,
                "razorpay_signature":  "sig",
            })
        assert r.status_code == 400

    def test_missing_fields_rejected(self, client):
        r = client.post("/api/payment/verify", json={
            "razorpay_order_id": self.ORDER_ID,
        })
        assert r.status_code in (400, 422)

    def test_response_does_not_expose_secret(self, client):
        with patch("main._rzp_client", return_value=self._mock_rzp()):
            r = client.post("/api/payment/verify", json={
                "razorpay_order_id":   self.ORDER_ID,
                "razorpay_payment_id": self.PAYMENT_ID,
                "razorpay_signature":  "sig",
            })
        assert os.environ["RAZORPAY_KEY_SECRET"] not in r.text


# ─────────────────────────────────────────────────────────────────
# 4. BOOKING CONFIRMATION
# ─────────────────────────────────────────────────────────────────

VALID_BOOKING = {
    "id": "TEST-BK-001",
    "type": "pooja",
    "name": "Siva Abhishekam",
    "price": 3.0,
    "persons": 1,
    "participants": [{"name": "Ravi Kumar", "gotra": "Kashyap", "relation": "Self"}],
    "contactEmail": "ravi@example.com",
    "contactPhone": "9876543210",
    "paidAt": "2026-10-09T10:00:00Z",
    "razorpayOrderId": "order_CONF001",
    "razorpayPaymentId": "pay_CONF001",
    "razorpaySignature": "test-signature",
}


def _prepare_booking_payment(booking):
    if booking["id"] != VALID_BOOKING["id"] and booking["razorpayOrderId"] == VALID_BOOKING["razorpayOrderId"]:
        booking["razorpayOrderId"] = f"order_{booking['id']}"
        booking["razorpayPaymentId"] = f"pay_{booking['id']}"
    if not booking.get("razorpaySignature"):
        booking["razorpaySignature"] = "test-signature"
    _, total = validate_and_price(booking["name"], booking["type"], booking["persons"])
    with sqlite3.connect(main.DATABASE_URL) as conn:
        conn.execute(
            """INSERT OR REPLACE INTO payment_orders (
                   order_id, booking_id, service_name, service_type, persons,
                   amount_paise, currency, status, payment_id
               ) VALUES (?, ?, ?, ?, ?, ?, 'INR', 'created', ?)""",
            (
                booking["razorpayOrderId"], booking["id"], booking["name"],
                booking["type"], booking["persons"], int(round(total * 100)),
                booking["razorpayPaymentId"],
            ),
        )


def _mock_rzp_confirm(booking):
    _, total = validate_and_price(booking["name"], booking["type"], booking["persons"])
    amount_paise = int(round(total * 100))
    mock = MagicMock()
    mock.utility.verify_payment_signature.return_value = None
    mock.order.fetch.return_value = {
        "id": booking["razorpayOrderId"],
        "amount": amount_paise,
        "currency": "INR",
    }
    mock.payment.fetch.return_value = {
        "id": booking["razorpayPaymentId"],
        "order_id": booking["razorpayOrderId"],
        "amount": amount_paise,
        "currency": "INR",
        "status": "captured",
    }
    return mock


class TestBookingConfirmation:
    def test_valid_booking_saved_with_catalogue_price(self, client, tmp_db):
        _prepare_booking_payment(VALID_BOOKING)
        with patch("main._rzp_client", return_value=_mock_rzp_confirm(VALID_BOOKING)):
            r = client.post("/api/booking/confirm", json=VALID_BOOKING)
        assert r.status_code == 200
        # Verify the price stored is the catalogue price, not the browser price
        conn = sqlite3.connect(tmp_db)
        row = conn.execute(
            "SELECT price, status FROM bookings WHERE id = ?", ("TEST-BK-001",)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == 3.0         # catalogue price
        assert row[1] == "paid"

    def test_duplicate_booking_returns_200_not_error(self, client):
        """Second identical confirm must succeed idempotently, not 500."""
        _prepare_booking_payment(VALID_BOOKING)
        with patch("main._rzp_client", return_value=_mock_rzp_confirm(VALID_BOOKING)):
            r = client.post("/api/booking/confirm", json=VALID_BOOKING)
        assert r.status_code == 200
        assert "already confirmed" in r.json().get("message", "").lower()

    def test_booking_status_is_always_paid(self, client, tmp_db):
        booking = {**VALID_BOOKING, "id": "TEST-BK-002", "status": "pending_payment"}
        _prepare_booking_payment(booking)
        with patch("main._rzp_client", return_value=_mock_rzp_confirm(booking)):
            r = client.post("/api/booking/confirm", json=booking)
        assert r.status_code == 200
        conn = sqlite3.connect(tmp_db)
        status = conn.execute(
            "SELECT status FROM bookings WHERE id = ?", ("TEST-BK-002",)
        ).fetchone()[0]
        conn.close()
        assert status == "paid"

    def test_tampered_price_stored_as_catalogue_price(self, client, tmp_db):
        booking = {**VALID_BOOKING, "id": "TEST-BK-003", "price": 0.01}  # tampered!
        _prepare_booking_payment(booking)
        with patch("main._rzp_client", return_value=_mock_rzp_confirm(booking)):
            r = client.post("/api/booking/confirm", json=booking)
        assert r.status_code == 200
        conn = sqlite3.connect(tmp_db)
        price = conn.execute(
            "SELECT price FROM bookings WHERE id = ?", ("TEST-BK-003",)
        ).fetchone()[0]
        conn.close()
        assert price == 3.0   # catalogue price, not 0.01

    def test_missing_payment_id_rejected(self, client):
        booking = {**VALID_BOOKING, "id": "TEST-BK-NO-PAY", "razorpayPaymentId": None}
        r = client.post("/api/booking/confirm", json=booking)
        assert r.status_code == 400

    def test_missing_participants_rejected(self, client):
        booking = {**VALID_BOOKING, "id": "TEST-BK-NO-PART", "participants": []}
        _prepare_booking_payment(booking)
        with patch("main._rzp_client", return_value=_mock_rzp_confirm(booking)):
            r = client.post("/api/booking/confirm", json=booking)
        assert r.status_code == 400

    def test_invalid_service_name_rejected(self, client):
        booking = {**VALID_BOOKING, "id": "TEST-BK-INV", "name": "Fraud Pooja Free"}
        r = client.post("/api/booking/confirm", json=booking)
        assert r.status_code == 400

    def test_bad_signature_on_confirm_rejected(self, client):
        mock = MagicMock()
        mock.utility.verify_payment_signature.side_effect = Exception("bad")
        booking = {**VALID_BOOKING, "id": "TEST-BK-BADSIG",
                   "razorpaySignature": "bad_sig_here"}
        _prepare_booking_payment(booking)
        with patch("main._rzp_client", return_value=mock):
            r = client.post("/api/booking/confirm", json=booking)
        assert r.status_code == 400


# ─────────────────────────────────────────────────────────────────
# 5. DAILY REPORT
# ─────────────────────────────────────────────────────────────────

def _insert_booking(db_path, booking_id, status, created_at_utc, price=116.0):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT OR IGNORE INTO bookings
           (id, type, name, price, persons, participants, contact_email,
            contact_phone, status, paid_at, created_at,
            razorpay_order_id, razorpay_payment_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (booking_id, "pooja", "Siva Astottara Pooja", price, 1,
         '[{"name":"Test User","gotra":"Kashyap","relation":"Self"}]',
         "test@example.com", "9999999999", status,
         "2026-10-09T04:30:00Z", created_at_utc,
         "order_RPT001", "pay_RPT001")
    )
    conn.commit()
    conn.close()


class TestDailyReport:
    def test_report_generated_from_db(self, tmp_db):
        """Report runs against actual DB records, not hard-coded data."""
        # Insert a paid booking created at IST 2026-10-09 09:00 = UTC 03:30
        _insert_booking(tmp_db, "RPT-001", "paid", "2026-10-09 03:30:00")
        with patch("daily_report.send_email", return_value=True) as mock_email:
            result = daily_report.generate_daily_report("2026-10-09")
        assert result is True
        mock_email.assert_called_once()
        # Check email subject
        _, kwargs = mock_email.call_args
        assert "2026-10-09" in kwargs.get("subject", "")

    def test_email_contains_customer_name(self, tmp_db):
        _insert_booking(tmp_db, "RPT-002", "paid", "2026-10-09 04:00:00")
        with patch("daily_report.send_email", return_value=True) as mock_email:
            daily_report.generate_daily_report("2026-10-09")
        body = mock_email.call_args[1]["body"]
        assert "test@example.com" in body

    def test_email_contains_payment_status(self, tmp_db):
        _insert_booking(tmp_db, "RPT-003", "paid", "2026-10-09 04:30:00")
        with patch("daily_report.send_email", return_value=True) as mock_email:
            daily_report.generate_daily_report("2026-10-09")
        body = mock_email.call_args[1]["body"]
        assert "Successful" in body

    def test_report_excludes_other_days(self, tmp_db):
        """Bookings from a different IST day must NOT appear in today's report."""
        # Created at UTC 2026-10-08 20:00 = IST 2026-10-09 01:30 — belongs to Oct 9
        _insert_booking(tmp_db, "RPT-EXCL-001", "paid", "2026-10-07 10:00:00")
        with patch("daily_report.send_email", return_value=True) as mock_email:
            daily_report.generate_daily_report("2026-10-09")
        body = mock_email.call_args[1]["body"]
        assert "RPT-EXCL-001" not in body

    def test_empty_report_handled_gracefully(self, tmp_db):
        """Report for a date with no bookings must send an email without crashing."""
        with patch("daily_report.send_email", return_value=True) as mock_email:
            result = daily_report.generate_daily_report("2000-01-01")
        assert result is True
        body = mock_email.call_args[1]["body"]
        assert "No bookings" in body

    def test_failed_bookings_distinguished(self, tmp_db):
        _insert_booking(tmp_db, "RPT-FAIL-001", "failed", "2026-10-09 05:00:00")
        with patch("daily_report.send_email", return_value=True) as mock_email:
            daily_report.generate_daily_report("2026-10-09")
        body = mock_email.call_args[1]["body"]
        assert "Failed" in body or "Cancelled" in body

    def test_email_failure_returns_false(self, tmp_db):
        _insert_booking(tmp_db, "RPT-EFLAIL", "paid", "2026-10-09 06:00:00")
        with patch("daily_report.send_email", return_value=False):
            result = daily_report.generate_daily_report("2026-10-09")
        assert result is False

    def test_db_error_returns_false(self, tmp_db):
        with patch("daily_report.DATABASE_URL", "/nonexistent/path/db.sqlite"):
            result = daily_report.generate_daily_report("2026-10-09")
        assert result is False

    def test_excel_attachment_included(self, tmp_db):
        _insert_booking(tmp_db, "RPT-XLS-001", "paid", "2026-10-09 07:00:00")
        with patch("daily_report.send_email", return_value=True) as mock_email:
            daily_report.generate_daily_report("2026-10-09")
        call_kwargs = mock_email.call_args[1]
        assert "attachment" in call_kwargs
        name, data, mime = call_kwargs["attachment"]
        assert name.endswith(".xlsx")
        assert "spreadsheet" in mime

    def test_ist_timezone_boundary_included(self, tmp_db):
        """
        Booking created at UTC 18:30 on Oct 8 = IST 00:00 Oct 9 (day start).
        Must appear in the Oct 9 IST report.
        """
        _insert_booking(tmp_db, "RPT-IST-BOUND", "paid", "2026-10-08 18:30:00")
        with patch("daily_report.send_email", return_value=True) as mock_email:
            daily_report.generate_daily_report("2026-10-09")
        body = mock_email.call_args[1]["body"]
        assert "RPT-IST-BOUND" in body

    def test_ist_timezone_boundary_excluded(self, tmp_db):
        """
        Booking at UTC 18:29 on Oct 8 = IST 23:59 Oct 8.
        Must NOT appear in the Oct 9 IST report.
        """
        _insert_booking(tmp_db, "RPT-IST-BEFORE", "paid", "2026-10-08 18:29:00")
        with patch("daily_report.send_email", return_value=True) as mock_email:
            daily_report.generate_daily_report("2026-10-09")
        body = mock_email.call_args[1]["body"]
        assert "RPT-IST-BEFORE" not in body


# ─────────────────────────────────────────────────────────────────
# 6. SCHEDULER FILES EXIST AND ARE VALID
# ─────────────────────────────────────────────────────────────────

import pathlib
PROJECT_DIR = pathlib.Path(__file__).parent


class TestSchedulerConfiguration:
    def test_shell_wrapper_exists(self):
        assert (PROJECT_DIR / "send_daily_report.sh").is_file(), \
            "send_daily_report.sh not found"

    def test_shell_wrapper_is_executable_or_contains_shebang(self):
        content = (PROJECT_DIR / "send_daily_report.sh").read_text()
        assert content.startswith("#!/")

    def test_systemd_service_file_exists(self):
        assert (PROJECT_DIR / "tav-daily-report.service").is_file(), \
            "tav-daily-report.service not found"

    def test_systemd_timer_file_exists(self):
        assert (PROJECT_DIR / "tav-daily-report.timer").is_file(), \
            "tav-daily-report.timer not found"

    def test_timer_fires_at_correct_utc_time(self):
        content = (PROJECT_DIR / "tav-daily-report.timer").read_text()
        # 08:00 IST = 02:30 UTC
        assert "02:30" in content

    def test_timer_has_persistent_flag(self):
        content = (PROJECT_DIR / "tav-daily-report.timer").read_text()
        assert "Persistent=true" in content

    def test_shell_script_references_daily_report_py(self):
        content = (PROJECT_DIR / "send_daily_report.sh").read_text()
        assert "daily_report.py" in content

    def test_shell_script_loads_env_file(self):
        content = (PROJECT_DIR / "send_daily_report.sh").read_text()
        assert ".env" in content

    def test_cron_instruction_documented_in_script(self):
        content = (PROJECT_DIR / "send_daily_report.sh").read_text()
        assert "cron" in content.lower() or "crontab" in content.lower()
