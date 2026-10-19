"""
test_booking_limits.py — Comprehensive Tests for 50-Booking Limit per Service
Tara Astro Vision
══════════════════════════════════════════════════════════════════════════════
Coverage:
  1. Service availability API endpoint (/api/services/availability)
  2. Independent 50-booking quota per service (Poojas and Homams)
  3. Pre-order capacity validation (/api/payment/order rejects 51st booking)
  4. Concurrency-safe confirmation limit enforcement (/api/booking/confirm)
  5. Automated refund initiation & recording in payment_refunds for overbooking race condition
  6. Status filtering: only confirmed/paid bookings take slots; pending/cancelled do not
  7. Duplicate payment idempotency: re-verification does not double count
  8. Concurrent booking attempts via multithreading
══════════════════════════════════════════════════════════════════════════════
Run with:
    .venv/bin/pytest test_booking_limits.py -v
"""

import os, sqlite3, json, concurrent.futures, itertools
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

import main
from service_catalogue import (
    SERVICE_BOOKING_LIMIT,
    get_confirmed_booking_count,
    get_all_services_availability,
    validate_and_price,
    canonical_service_name,
)

client = TestClient(main.app)
_mock_order_ids = itertools.count(1)


def _mock_rzp_client():
    mock = MagicMock()

    def create_order(data):
        return {
            "id": f"order_MOCK_{next(_mock_order_ids)}",
            "amount": data["amount"],
            "currency": data["currency"],
            "status": "created",
        }

    def fetch_order(order_id):
        with sqlite3.connect(main.DATABASE_URL) as conn:
            row = conn.execute(
                "SELECT amount_paise, currency FROM payment_orders WHERE order_id = ?",
                (order_id,),
            ).fetchone()
        return {
            "id": order_id,
            "amount": row[0] if row else 0,
            "currency": row[1] if row else "INR",
        }

    def fetch_payment(payment_id):
        with sqlite3.connect(main.DATABASE_URL) as conn:
            row = conn.execute(
                """SELECT order_id, amount_paise, currency FROM payment_orders
                   WHERE payment_id = ? ORDER BY created_at LIMIT 1""",
                (payment_id,),
            ).fetchone()
        return {
            "id": payment_id,
            "order_id": row[0] if row else "",
            "amount": row[1] if row else 0,
            "currency": row[2] if row else "INR",
            "status": "captured",
        }

    mock.order.create.side_effect = create_order
    mock.order.fetch.side_effect = fetch_order
    mock.payment.fetch.side_effect = fetch_payment
    mock.utility.verify_payment_signature.return_value = None
    mock.payment.refund.return_value = {"id": "rfnd_MOCK_999", "status": "processed"}
    return mock


@pytest.fixture(autouse=True)
def clean_test_bookings():
    yield
    # Clean up any test seed bookings inserted during test runs
    conn = sqlite3.connect(main.DATABASE_URL)
    conn.execute("DELETE FROM bookings WHERE id LIKE 'TEST-%' OR id LIKE 'TAV-ORDER-%' OR id LIKE 'TAV-CHANDI-%' OR id LIKE 'TAV-CONCURR-%' OR id LIKE 'TAV-SAI-%' OR id LIKE 'IGN-%'")
    conn.execute("DELETE FROM payment_refunds WHERE booking_id LIKE 'TAV-%' OR booking_id LIKE 'TEST-%'")
    conn.execute("DELETE FROM payment_orders WHERE booking_id LIKE 'TAV-%' OR booking_id LIKE 'TEST-%'")
    conn.commit()
    conn.close()


def _register_payment_order(payload):
    _, total = validate_and_price(payload["name"], payload["type"], payload["persons"])
    amount_paise = int(round(total * 100))
    payload.setdefault("razorpaySignature", "unit-test-signature")
    with sqlite3.connect(main.DATABASE_URL) as conn:
        conn.execute(
            """INSERT OR REPLACE INTO payment_orders (
                   order_id, booking_id, service_name, service_type, persons,
                   amount_paise, currency, status, payment_id
               ) VALUES (?, ?, ?, ?, ?, ?, 'INR', 'created', ?)""",
            (
                payload["razorpayOrderId"], payload["id"], payload["name"],
                payload["type"], payload["persons"], amount_paise,
                payload["razorpayPaymentId"],
            ),
        )


def _insert_confirmed_bookings(conn, service_name: str, count: int, service_type: str = "homam", price: float = 2000.0):
    """Directly insert *count* confirmed bookings for testing capacity limits."""
    for i in range(count):
        b_id = f"TEST-SEED-{service_name[:4]}-{i+1:03d}"
        pay_id = f"pay_seed_{service_name[:4]}_{i+1:03d}"
        conn.execute(
            """INSERT OR REPLACE INTO bookings (
                id, type, name, customer_name, price, persons, participants,
                contact_email, contact_phone, status, paid_at, scheduled_date,
                razorpay_order_id, razorpay_payment_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                b_id, service_type, service_name, f"Customer {i+1}", price, 1,
                json.dumps([{"name": f"Person {i+1}", "gotra": "Kashyap", "relation": "Self"}]),
                f"customer{i+1}@example.com", "9014308190", "paid",
                "2026-10-10T10:00:00Z", "2026-10-25", f"order_seed_{i+1}", pay_id
            )
        )
    conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
# 1. Availability API Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestAvailabilityAPI:
    def test_availability_endpoint_structure(self):
        r = client.get("/api/services/availability")
        assert r.status_code == 200
        data = r.json()
        assert data["max_limit"] == 50
        avail = data["availability"]
        assert isinstance(avail, dict)

        # Check key services exist
        assert "Pratyangira Homam" in avail
        assert "Prathyangira Homam" in avail  # alias included
        assert "Siva Abhishekam" in avail

        # Check structure of each entry
        entry = avail["Pratyangira Homam"]
        assert "name" in entry
        assert "booked" in entry
        assert "remaining" in entry
        assert "max_limit" in entry
        assert "sold_out" in entry
        assert "available" in entry
        assert "coming_soon" in entry
        assert entry["max_limit"] == 50

    def test_disabled_homams_marked_coming_soon(self):
        r = client.get("/api/services/availability")
        assert r.status_code == 200
        avail = r.json()["availability"]
        # Kali Homam is disabled
        kali = avail["Kali Homam"]
        assert kali["available"] is False
        assert kali["coming_soon"] is True

        # Prathyangira is enabled
        prath = avail["Prathyangira Homam"]
        assert prath["coming_soon"] is False


# ══════════════════════════════════════════════════════════════════════════════
# 2. Pre-Order Capacity Validation
# ══════════════════════════════════════════════════════════════════════════════

class TestPreOrderCapacityValidation:
    def test_order_creation_allowed_below_limit(self):
        with patch("main._rzp_client", return_value=_mock_rzp_client()):
            r = client.post("/api/payment/order", json={
                "name": "Lakshmi Ganapathi Homam",
                "serviceType": "homam",
                "persons": 1,
                "bookingId": "TAV-ORDER-OK",
            })
        assert r.status_code == 200
        assert r.json()["service_name"] == "Lakshmi Ganapathi Homam"

    def test_order_creation_blocked_when_50_reached(self):
        svc_name = "Kala Bhairava Homam"
        conn = sqlite3.connect(main.DATABASE_URL)
        _insert_confirmed_bookings(conn, svc_name, 50, "homam", 2000.0)
        conn.close()

        with patch("main._rzp_client", return_value=_mock_rzp_client()):
            r = client.post("/api/payment/order", json={
                "name": svc_name,
                "serviceType": "homam",
                "persons": 1,
                "bookingId": "TAV-ORDER-FULL",
            })
        assert r.status_code == 400
        detail = r.json().get("detail", "")
        assert "Bookings Closed — Maximum Capacity Reached" in detail
        assert "50/50" in detail


# ══════════════════════════════════════════════════════════════════════════════
# 3. Confirmation Limit Enforcement & Overbooking Refund Safety
# ══════════════════════════════════════════════════════════════════════════════

class TestBookingConfirmationLimit:
    def test_confirmation_succeeds_up_to_50(self):
        svc_name = "Chandi Mula Mantra Homam"
        conn = sqlite3.connect(main.DATABASE_URL)
        _insert_confirmed_bookings(conn, svc_name, 49, "homam", 2000.0)
        conn.close()

        # The 50th booking must succeed
        payload_50 = {
            "id": "TAV-CHANDI-050",
            "type": "homam",
            "name": svc_name,
            "price": 2000.0,
            "persons": 1,
            "participants": [{"name": "Pooja Member", "gotra": "Atri", "relation": "Self"}],
            "contactEmail": "customer50@example.com",
            "contactPhone": "9014308190",
            "paidAt": "2026-10-11T10:00:00Z",
            "razorpayOrderId": "order_chandi_050",
            "razorpayPaymentId": "pay_chandi_050",
        }
        _register_payment_order(payload_50)
        with patch("main._rzp_client", return_value=_mock_rzp_client()), \
             patch("main.send_email", return_value=True):
            r = client.post("/api/booking/confirm", json=payload_50)
        assert r.status_code == 200
        assert r.json()["id"] == "TAV-CHANDI-050"

        # Verify availability now reports 0 remaining and sold_out = True
        conn = sqlite3.connect(main.DATABASE_URL)
        cnt = get_confirmed_booking_count(conn, svc_name)
        assert cnt == 50
        conn.close()

    def test_51st_confirmation_triggers_refund_and_blocks(self):
        svc_name = "Chandi Mula Mantra Homam"
        conn = sqlite3.connect(main.DATABASE_URL)
        _insert_confirmed_bookings(conn, svc_name, 50, "homam", 2000.0)
        conn.close()

        payload_51 = {
            "id": "TAV-CHANDI-051",
            "type": "homam",
            "name": svc_name,
            "price": 2000.0,
            "persons": 1,
            "participants": [{"name": "Overbooked Person", "gotra": "Atri", "relation": "Self"}],
            "contactEmail": "customer51@example.com",
            "contactPhone": "9014308190",
            "paidAt": "2026-10-11T10:05:00Z",
            "razorpayOrderId": "order_chandi_051",
            "razorpayPaymentId": "pay_chandi_051",
        }
        _register_payment_order(payload_51)

        mock_rzp = _mock_rzp_client()
        with patch("main._rzp_client", return_value=mock_rzp), \
             patch("main.send_email", return_value=True):
            r = client.post("/api/booking/confirm", json=payload_51)

        # Must reject with 400
        assert r.status_code == 400
        detail = r.json().get("detail", "")
        assert "Bookings Closed — Maximum Capacity Reached (50/50)" in detail
        assert "refund" in detail.lower()

        # Must have initiated refund via Razorpay client
        mock_rzp.payment.refund.assert_called_once()
        refund_call_args = mock_rzp.payment.refund.call_args
        assert refund_call_args[0][0] == "pay_chandi_051"
        assert refund_call_args[0][1]["amount"] == 200000  # 2000 * 100 paise

        # Must be logged in payment_refunds table
        conn = sqlite3.connect(main.DATABASE_URL)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM payment_refunds WHERE booking_id = ?", ("TAV-CHANDI-051",)
        ).fetchone()
        assert row is not None
        assert row["amount_paise"] == 200000  # 2000 INR = 200,000 paise
        assert row["status"] == "refund_initiated"
        assert row["razorpay_payment_id"] == "pay_chandi_051"

        # Count in bookings must remain exactly 50 (never 51)
        cnt = get_confirmed_booking_count(conn, svc_name)
        assert cnt == 50
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# 4. Independent Limits Between Services
# ══════════════════════════════════════════════════════════════════════════════

class TestIndependentLimits:
    def test_service_limits_are_independent(self):
        conn = sqlite3.connect(main.DATABASE_URL)
        _insert_confirmed_bookings(conn, "Chandi Mula Mantra Homam", 50, "homam", 2000.0)
        cnt_chandi = get_confirmed_booking_count(conn, "Chandi Mula Mantra Homam")
        cnt_praty = get_confirmed_booking_count(conn, "Pratyangira Homam")
        conn.close()

        assert cnt_chandi == 50
        assert cnt_praty < 50

        # Pratyangira order can still be created
        with patch("main._rzp_client", return_value=_mock_rzp_client()):
            r = client.post("/api/payment/order", json={
                "name": "Prathyangira Homam",
                "serviceType": "homam",
                "persons": 1,
                "bookingId": "TAV-PRATY-OK",
            })
        assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# 5. Non-Paid Bookings Do Not Consume Slots
# ══════════════════════════════════════════════════════════════════════════════

class TestNonPaidBookingsDoNotConsumeSlots:
    def test_pending_cancelled_failed_status_ignored(self):
        svc_name = "108 Aaku Pooja"
        conn = sqlite3.connect(main.DATABASE_URL)
        for st in ("pending_payment", "cancelled", "failed", "draft"):
            conn.execute(
                """INSERT OR REPLACE INTO bookings (
                    id, type, name, price, persons, participants,
                    contact_email, contact_phone, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (f"IGN-{st}", "pooja", svc_name, 216.0, 1, "[]", "t@ex.com", "999", st)
            )
        conn.commit()

        # Confirmed count should still be 0
        cnt = get_confirmed_booking_count(conn, svc_name)
        assert cnt == 0
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# 6. Duplicate Payment Idempotency
# ══════════════════════════════════════════════════════════════════════════════

class TestDuplicatePaymentDeduplication:
    def test_same_real_payment_id_cannot_create_second_booking(self):
        svc_name = "Sai Abhishekam"
        pay_id = "pay_real_unique_tx_8899"
        payload1 = {
            "id": "TAV-SAI-001",
            "type": "pooja",
            "name": svc_name,
            "price": 216.0,
            "persons": 1,
            "participants": [{"name": "User 1", "gotra": "G1", "relation": "Self"}],
            "contactEmail": "u1@example.com",
            "contactPhone": "9014308190",
            "paidAt": "2026-10-12T10:00:00Z",
            "razorpayOrderId": "order_sai_001",
            "razorpayPaymentId": pay_id,
        }
        _register_payment_order(payload1)

        with patch("main._rzp_client", return_value=_mock_rzp_client()), \
             patch("main.send_email", return_value=True):
            r1 = client.post("/api/booking/confirm", json=payload1)
        assert r1.status_code == 200

        # Attempt to confirm another booking with the exact same payment ID
        payload2 = {
            "id": "TAV-SAI-002",
            "type": "pooja",
            "name": svc_name,
            "price": 216.0,
            "persons": 1,
            "participants": [{"name": "User 2", "gotra": "G2", "relation": "Self"}],
            "contactEmail": "u2@example.com",
            "contactPhone": "9014308190",
            "paidAt": "2026-10-12T10:00:00Z",
            "razorpayOrderId": "order_sai_002",
            "razorpayPaymentId": pay_id,
        }
        _register_payment_order(payload2)
        with patch("main._rzp_client", return_value=_mock_rzp_client()), \
             patch("main.send_email", return_value=True):
            r2 = client.post("/api/booking/confirm", json=payload2)

        # A payment associated with another order cannot be reused.
        assert r2.status_code == 400

        conn = sqlite3.connect(main.DATABASE_URL)
        rows = conn.execute("SELECT id FROM bookings WHERE razorpay_payment_id = ?", (pay_id,)).fetchall()
        assert len(rows) == 1
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# 7. Concurrency Safety Test
# ══════════════════════════════════════════════════════════════════════════════

class TestConcurrencySafety:
    def test_concurrent_confirmations_do_not_exceed_50(self):
        svc_name = "Sri Chakra Pooja"
        conn = sqlite3.connect(main.DATABASE_URL)
        _insert_confirmed_bookings(conn, svc_name, 48, "pooja", 516.0)
        conn.close()

        def attempt_confirm(idx):
            payload = {
                "id": f"TAV-CONCURR-{idx}",
                "type": "pooja",
                "name": svc_name,
                "price": 516.0,
                "persons": 1,
                "participants": [{"name": f"Concurrent User {idx}", "gotra": "Kashyap", "relation": "Self"}],
                "contactEmail": f"concurr{idx}@example.com",
                "contactPhone": "9014308190",
                "paidAt": "2026-10-12T12:00:00Z",
                "razorpayOrderId": f"order_concurr_{idx}",
                "razorpayPaymentId": f"pay_concurr_{idx}",
            }
            _register_payment_order(payload)
            return client.post("/api/booking/confirm", json=payload)

        mock_rzp = _mock_rzp_client()
        with patch("main._rzp_client", return_value=mock_rzp), \
             patch("main.send_email", return_value=True):
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(attempt_confirm, i) for i in range(1, 6)]
                results = [f.result() for f in futures]

        status_codes = [r.status_code for r in results]
        # Exactly 2 should succeed (200), and 3 should be rejected with 400 (capacity full)
        successes = status_codes.count(200)
        rejections = status_codes.count(400)

        assert successes == 2
        assert rejections == 3

        conn = sqlite3.connect(main.DATABASE_URL)
        total_confirmed = get_confirmed_booking_count(conn, svc_name)
        conn.close()

        # The total count can NEVER exceed 50
        assert total_confirmed == 50
