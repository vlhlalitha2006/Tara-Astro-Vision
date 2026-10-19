"""
test_admin_portal.py — Comprehensive Test Suite for Tara Astro Vision Admin Portal
══════════════════════════════════════════════════════════════════════════════════
Coverage:
  1. Admin URL routing (/admin, /admin/, /admin/{subpath})
  2. Strict Email Authentication (ONLY info@taraastrovision.com allowed)
  3. PBKDF2 Password Verification & JWT Token Issuance
  4. Login Rate Limiting (5 failed attempts -> 429 Too Many Requests)
  5. Protected Endpoint Access Control (401 without valid token)
  6. Dashboard Metrics & Revenue Aggregation from real Database
  7. Booking Views & Filtering (Homams, Poojas, Consultations)
  8. Booking Acceptance with Email Notification
  9. Booking Rejection with Razorpay Refund & Capacity Release
  10. Astrologer Consultation Public Submission & Admin Scheduling with IST Collision Detection
  11. Consultation Rescheduling
  12. Capacity Tracking (Strict 50 Booking Limit & 4 Approved Homams)
  13. Audit Trail Logging & Security Event Recording
══════════════════════════════════════════════════════════════════════════════════
Run with:
    .venv/bin/pytest test_admin_portal.py -v
"""

import os
import sqlite3
import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

import main
from setup_admin import (
    AUTHORIZED_ADMIN_EMAIL,
    setup_admin_user,
    hash_admin_password,
    verify_admin_password,
)
from admin_api import (
    ADMIN_FAILED_LOGINS,
    clear_failed_logins,
)
from main import (
    create_token,
    verify_token,
    SECRET_KEY,
)
from service_catalogue import get_confirmed_booking_count

client = TestClient(main.app)

TEST_ADMIN_PASSWORD = "TaraAstroTest2026!Secure"


@pytest.fixture(scope="session", autouse=True)
def setup_test_admin():
    """Ensure admin account is configured for testing, preserving any existing admin."""
    conn = sqlite3.connect(main.DATABASE_URL)
    row = conn.execute(
        "SELECT email, password_hash, salt, created_at, last_login_at FROM admin_users WHERE email = ?",
        (AUTHORIZED_ADMIN_EMAIL,)
    ).fetchone()
    conn.close()

    setup_admin_user(TEST_ADMIN_PASSWORD, main.DATABASE_URL)
    yield
    if row:
        conn = sqlite3.connect(main.DATABASE_URL)
        conn.execute(
            "UPDATE admin_users SET password_hash = ?, salt = ?, created_at = ?, last_login_at = ? WHERE email = ?",
            (row[1], row[2], row[3], row[4], row[0])
        )
        conn.commit()
        conn.close()



@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Reset rate limiting and clean up temporary test records."""
    ADMIN_FAILED_LOGINS.clear()
    yield
    ADMIN_FAILED_LOGINS.clear()
    try:
        conn = sqlite3.connect(main.DATABASE_URL, timeout=10.0)
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("DELETE FROM bookings WHERE id LIKE 'ADMTEST-%'")
        conn.execute("DELETE FROM payment_refunds WHERE booking_id LIKE 'ADMTEST-%'")
        conn.execute("DELETE FROM admin_audit_logs WHERE booking_id LIKE 'ADMTEST-%'")
        conn.commit()
    finally:
        conn.close()


def get_admin_token() -> str:
    """Helper to obtain a valid token for info@taraastrovision.com."""
    return create_token({"email": AUTHORIZED_ADMIN_EMAIL, "role": "admin"})


def auth_headers(token: str = None) -> dict:
    t = token or get_admin_token()
    return {"Authorization": f"Bearer {t}"}


# ══════════════════════════════════════════════════════════════════════════════
# 1. ADMIN URL & STATIC ASSETS ROUTING
# ══════════════════════════════════════════════════════════════════════════════

class TestAdminRouting:
    def test_admin_root_serves_admin_html(self):
        r = client.get("/admin")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "Tara Astro Vision — Admin Portal" in r.text
        assert "info@taraastrovision.com" in r.text

    def test_admin_slash_serves_admin_html(self):
        r = client.get("/admin/")
        assert r.status_code == 200
        assert "Tara Astro Vision — Admin Portal" in r.text

    def test_admin_subpath_serves_admin_html(self):
        r = client.get("/admin/dashboard")
        assert r.status_code == 200
        assert "Tara Astro Vision — Admin Portal" in r.text

    def test_admin_css_and_js_served(self):
        r_css = client.get("/admin.css")
        assert r_css.status_code == 200
        assert "admin-body" in r_css.text

        r_js = client.get("/admin.js")
        assert r_js.status_code == 200
        assert "handleAdminLogin" in r_js.text


# ══════════════════════════════════════════════════════════════════════════════
# 2. STRICT AUTHENTICATION & RATE LIMITING
# ══════════════════════════════════════════════════════════════════════════════

class TestAdminAuthentication:
    def test_login_success_for_authorized_email(self):
        r = client.post("/api/admin/login", json={
            "email": AUTHORIZED_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASSWORD
        })
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "ok"
        assert "token" in data
        assert data["email"] == AUTHORIZED_ADMIN_EMAIL

        # Verify token contents
        payload = verify_token(data["token"])
        assert payload is not None
        assert payload["email"] == AUTHORIZED_ADMIN_EMAIL
        assert payload["role"] == "admin"

    def test_login_rejected_for_unauthorized_email(self):
        """Any email other than info@taraastrovision.com must be strictly rejected."""
        unauthorized_emails = [
            "admin@taraastrovision.com",
            "support@taraastrovision.com",
            "hacker@gmail.com",
            "owner@gmail.com",
            "info@gmail.com"
        ]
        for email in unauthorized_emails:
            r = client.post("/api/admin/login", json={
                "email": email,
                "password": TEST_ADMIN_PASSWORD
            })
            assert r.status_code == 401
            assert "Access denied" in r.json()["detail"]

    def test_login_rejected_for_wrong_password(self):
        r = client.post("/api/admin/login", json={
            "email": AUTHORIZED_ADMIN_EMAIL,
            "password": "WrongPassword123!"
        })
        assert r.status_code == 401
        assert "Invalid" in r.json()["detail"]

    def test_login_rate_limiting_after_five_failed_attempts(self):
        """6th failed attempt must trigger 429 Too Many Requests."""
        ADMIN_FAILED_LOGINS.clear()

        # 5 failed attempts
        for _ in range(5):
            r = client.post("/api/admin/login", json={
                "email": AUTHORIZED_ADMIN_EMAIL,
                "password": "IncorrectPassword"
            })
            assert r.status_code == 401

        # 6th attempt must be blocked by rate limiter
        r6 = client.post("/api/admin/login", json={
            "email": AUTHORIZED_ADMIN_EMAIL,
            "password": "IncorrectPassword"
        })
        assert r6.status_code == 429
        assert "Too many failed login attempts" in r6.json()["detail"]

        # Even with correct password, blocked until rate limit window resets
        r7 = client.post("/api/admin/login", json={
            "email": AUTHORIZED_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASSWORD
        })
        assert r7.status_code == 429

    def test_me_endpoint_requires_auth(self):
        r_unauth = client.get("/api/admin/me")
        assert r_unauth.status_code == 401

        token = get_admin_token()
        r_auth = client.get("/api/admin/me", headers=auth_headers(token))
        assert r_auth.status_code == 200
        assert r_auth.json()["email"] == AUTHORIZED_ADMIN_EMAIL

    def test_logout_endpoint(self):
        token = get_admin_token()
        r = client.post("/api/admin/logout", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ══════════════════════════════════════════════════════════════════════════════
# 3. PROTECTED ADMIN API ACCESS CONTROL
# ══════════════════════════════════════════════════════════════════════════════

class TestProtectedAdminEndpoints:
    def test_endpoints_reject_unauthenticated_requests(self):
        protected_endpoints = [
            ("GET", "/api/admin/dashboard"),
            ("GET", "/api/admin/bookings"),
            ("GET", "/api/admin/bookings/ADMTEST-1"),
            ("POST", "/api/admin/bookings/ADMTEST-1/accept"),
            ("POST", "/api/admin/bookings/ADMTEST-1/reject"),
            ("POST", "/api/admin/bookings/ADMTEST-1/schedule"),
            ("GET", "/api/admin/capacity"),
            ("GET", "/api/admin/refunds"),
            ("GET", "/api/admin/audit-logs"),
        ]

        for method, endpoint in protected_endpoints:
            if method == "GET":
                r = client.get(endpoint)
            else:
                r = client.post(endpoint, json={})
            assert r.status_code == 401, f"Expected 401 for unauthenticated {method} {endpoint}, got {r.status_code}"

    def test_endpoints_reject_tampered_token(self):
        bad_headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature"}
        r = client.get("/api/admin/dashboard", headers=bad_headers)
        assert r.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# 4. DASHBOARD METRICS & REVENUE AGGREGATION
# ══════════════════════════════════════════════════════════════════════════════

class TestAdminDashboard:
    def test_dashboard_metrics_calculation(self):
        conn = sqlite3.connect(main.DATABASE_URL, timeout=10.0)
        conn.execute("PRAGMA busy_timeout = 5000")
        now_iso = datetime.now(timezone.utc).isoformat()
        empty_p = json.dumps([])

        try:
            # Seed specific test bookings
            conn.execute("""
                INSERT INTO bookings (
                    id, type, name, customer_name, price, persons, participants, contact_email, contact_phone,
                    status, booking_status, payment_status, created_at, scheduled_date
                ) VALUES
                ('ADMTEST-HOMAM-1', 'homam', 'Pratyangira Homam', 'Devotee A', 2500.0, 1, ?, 'devoteea@example.com', '9876543210', 'paid', 'pending', 'paid', ?, '2026-11-01'),
                ('ADMTEST-HOMAM-2', 'homam', 'Kala Bhairava Homam', 'Devotee B', 3000.0, 1, ?, 'devoteeb@example.com', '9876543211', 'paid', 'accepted', 'paid', ?, '2026-11-02'),
                ('ADMTEST-POOJA-1', 'pooja', 'Siva Abhishekam', 'Devotee C', 1116.0, 1, ?, 'devoteec@example.com', '9876543212', 'paid', 'pending', 'paid', ?, '2026-11-03'),
                ('ADMTEST-CONSULT-1', 'consultation', 'Vedic Astrology Consultation', 'Devotee D', 1000.0, 1, ?, 'devoteed@example.com', '9876543213', 'pending', 'pending', 'unpaid', ?, '2026-11-04')
            """, (empty_p, now_iso, empty_p, now_iso, empty_p, now_iso, empty_p, now_iso))
            conn.commit()
        finally:
            conn.close()

        r = client.get("/api/admin/dashboard", headers=auth_headers())
        assert r.status_code == 200
        data = r.json()

        assert "metrics" in data
        assert "revenue" in data
        assert "capacity" in data
        assert "recent_bookings" in data

        m = data["metrics"]
        assert m["total_homams"] >= 2
        assert m["total_poojas"] >= 1
        assert m["total_consultations"] >= 1
        assert m["pending_bookings"] >= 3
        assert m["accepted_bookings"] >= 1

        rev = data["revenue"]
        assert rev["gross"] >= 6616.0
        assert rev["net"] <= rev["gross"]


# ══════════════════════════════════════════════════════════════════════════════
# 5. BOOKING LISTING & DETAILS
# ══════════════════════════════════════════════════════════════════════════════

class TestBookingManagement:
    def test_list_bookings_filtered_by_type(self):
        conn = sqlite3.connect(main.DATABASE_URL, timeout=10.0)
        conn.execute("PRAGMA busy_timeout = 5000")
        empty_p = json.dumps([])
        try:
            conn.execute("""
                INSERT INTO bookings (
                    id, type, name, customer_name, price, persons, participants, contact_email, contact_phone,
                    status, booking_status, payment_status, created_at
                ) VALUES
                ('ADMTEST-H1', 'homam', 'Lakshmi Ganapathi Homam', 'Devotee Ganapathi', 2000.0, 1, ?, 'lg@example.com', '9000000001', 'paid', 'pending', 'paid', '2026-10-18T10:00:00Z'),
                ('ADMTEST-P1', 'pooja', 'Navagraha Pooja', 'Devotee Navagraha', 1500.0, 1, ?, 'nv@example.com', '9000000002', 'paid', 'pending', 'paid', '2026-10-18T10:00:00Z')
            """, (empty_p, empty_p))
            conn.commit()
        finally:
            conn.close()

        # Filter homams
        r_h = client.get("/api/admin/bookings?service_type=homam", headers=auth_headers())
        assert r_h.status_code == 200
        h_data = r_h.json()
        assert all(b["service_type"] == "homam" for b in h_data["bookings"])
        assert any(b["id"] == "ADMTEST-H1" for b in h_data["bookings"])

        # Filter poojas
        r_p = client.get("/api/admin/bookings?service_type=pooja", headers=auth_headers())
        assert r_p.status_code == 200
        p_data = r_p.json()
        assert all(b["service_type"] == "pooja" for b in p_data["bookings"])
        assert any(b["id"] == "ADMTEST-P1" for b in p_data["bookings"])

    def test_booking_details_endpoint(self):
        conn = sqlite3.connect(main.DATABASE_URL, timeout=10.0)
        conn.execute("PRAGMA busy_timeout = 5000")
        participants_json = json.dumps([
            {"name": "Devotee Chandi", "gotra": "Bharadwaja", "nakshatra": "Mrigashira", "rasi": "Mithuna", "sankalpam": "Family Prosperity"}
        ])
        try:
            conn.execute("""
                INSERT INTO bookings (
                    id, type, name, customer_name, price, persons, participants,
                    contact_email, contact_phone,
                    status, booking_status, payment_status, razorpay_order_id, razorpay_payment_id
                ) VALUES (
                    'ADMTEST-DETAIL-1', 'homam', 'Chandi Mula Mantra Homam', 'Devotee Chandi', 5000.0, 1, ?,
                    'chandi@example.com', '9111222333',
                    'paid', 'pending', 'paid', 'order_CHANDI_999', 'pay_CHANDI_999'
                )
            """, (participants_json,))
            conn.commit()
        finally:
            conn.close()

        r = client.get("/api/admin/bookings/ADMTEST-DETAIL-1", headers=auth_headers())
        assert r.status_code == 200
        data = r.json()
        b = data["booking"]
        assert b["id"] == "ADMTEST-DETAIL-1"
        assert b["customer_name"] == "Devotee Chandi"
        assert b["gotra"] == "Bharadwaja"
        assert b["sankalpam"] == "Family Prosperity"
        assert b["razorpay_payment_id"] == "pay_CHANDI_999"


# ══════════════════════════════════════════════════════════════════════════════
# 6. ACCEPT BOOKING ACTION
# ══════════════════════════════════════════════════════════════════════════════

class TestBookingAcceptAction:
    @patch("main.send_email", return_value=True)
    def test_accept_booking_updates_status_and_sends_email(self, mock_email):
        conn = sqlite3.connect(main.DATABASE_URL, timeout=10.0)
        conn.execute("PRAGMA busy_timeout = 5000")
        empty_p = json.dumps([])
        try:
            conn.execute("""
                INSERT INTO bookings (
                    id, type, name, customer_name, price, persons, participants, contact_email, contact_phone,
                    status, booking_status, payment_status
                ) VALUES (
                    'ADMTEST-ACCEPT-1', 'homam', 'Pratyangira Homam', 'Devotee Accept', 2000.0, 1, ?,
                    'accept@example.com', '9988776655', 'paid', 'pending', 'paid'
                )
            """, (empty_p,))
            conn.commit()
        finally:
            conn.close()

        r = client.post(
            "/api/admin/bookings/ADMTEST-ACCEPT-1/accept",
            headers=auth_headers(),
            json={"admin_notes": "Priests assigned for ritual"}
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["email_sent"] is True

        # Verify database update
        conn = sqlite3.connect(main.DATABASE_URL, timeout=10.0)
        try:
            row = conn.execute("SELECT booking_status, status, accepted_at, admin_notes FROM bookings WHERE id = 'ADMTEST-ACCEPT-1'").fetchone()
            assert row[0] == "accepted"
            assert row[1] == "confirmed"
            assert row[2] is not None
            assert row[3] == "Priests assigned for ritual"

            # Verify audit log was created
            audit = conn.execute("SELECT action, booking_id FROM admin_audit_logs WHERE booking_id = 'ADMTEST-ACCEPT-1'").fetchone()
            assert audit is not None
            assert audit[0] == "booking_accepted"
        finally:
            conn.close()

    @patch("main.send_email", return_value=True)
    def test_accept_booking_idempotency(self, mock_email):
        """Accepting an already accepted booking is idempotent and does not duplicate emails."""
        conn = sqlite3.connect(main.DATABASE_URL, timeout=10.0)
        conn.execute("PRAGMA busy_timeout = 5000")
        empty_p = json.dumps([])
        try:
            conn.execute("""
                INSERT INTO bookings (
                    id, type, name, customer_name, price, persons, participants, contact_email, contact_phone,
                    status, booking_status, payment_status
                ) VALUES (
                    'ADMTEST-ACCEPT-IDEM', 'homam', 'Pratyangira Homam', 'Devotee', 2000.0, 1, ?,
                    'idem@example.com', '9988776655', 'confirmed', 'accepted', 'paid'
                )
            """, (empty_p,))
            conn.commit()
        finally:
            conn.close()

        r = client.post(
            "/api/admin/bookings/ADMTEST-ACCEPT-IDEM/accept",
            headers=auth_headers(),
            json={"admin_notes": "Again"}
        )
        assert r.status_code == 200
        assert r.json()["message"] == "Booking is already accepted."
        assert r.json()["email_sent"] is False


# ══════════════════════════════════════════════════════════════════════════════
# 7. REJECT BOOKING ACTION & RAZORPAY REFUND
# ══════════════════════════════════════════════════════════════════════════════

class TestBookingRejectAction:
    def test_reject_booking_requires_reason(self):
        r = client.post(
            "/api/admin/bookings/ADMTEST-REJECT-NO-REASON/reject",
            headers=auth_headers(),
            json={"reason": ""}
        )
        assert r.status_code == 400
        assert "reason is required" in r.json()["detail"]

    @patch("main.send_email", return_value=True)
    def test_reject_booking_triggers_razorpay_refund_and_releases_capacity(self, mock_email):
        # 1. Insert a confirmed paid booking
        conn = sqlite3.connect(main.DATABASE_URL, timeout=10.0)
        conn.execute("PRAGMA busy_timeout = 5000")
        empty_p = json.dumps([])
        try:
            conn.execute("""
                INSERT INTO bookings (
                    id, type, name, customer_name, price, persons, participants, contact_email, contact_phone,
                    status, booking_status, payment_status, razorpay_payment_id
                ) VALUES (
                    'ADMTEST-REJECT-1', 'homam', 'Pratyangira Homam', 'Devotee Reject', 2500.0, 1, ?,
                    'reject@example.com', '9876543210', 'paid', 'pending', 'paid', 'pay_TEST_REFUND_1'
                )
            """, (empty_p,))
            conn.commit()

            # Check capacity before reject
            count_before = get_confirmed_booking_count(conn, "Pratyangira Homam")
        finally:
            conn.close()

        # 2. Mock Razorpay client refund call
        mock_rzp = MagicMock()
        mock_rzp.payment.refund.return_value = {
            "id": "rfnd_RZP_SUCCESS_789",
            "status": "processed",
            "amount": 250000
        }

        with patch("main._rzp_client", return_value=mock_rzp):
            r = client.post(
                "/api/admin/bookings/ADMTEST-REJECT-1/reject",
                headers=auth_headers(),
                json={
                    "reason": "Temple priest scheduling emergency on selected muhurtham.",
                    "admin_notes": "Customer requested full refund."
                }
            )

        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["refund_id"] == "rfnd_RZP_SUCCESS_789"
        assert data["refund_status"] == "processed"
        assert data["email_sent"] is True

        # 3. Verify database updates
        conn = sqlite3.connect(main.DATABASE_URL, timeout=10.0)
        try:
            row = conn.execute("""
                SELECT booking_status, status, payment_status, refund_id, refund_status,
                       rejection_reason, refund_amount
                FROM bookings WHERE id = 'ADMTEST-REJECT-1'
            """).fetchone()

            assert row[0] == "rejected"
            assert row[1] == "rejected"
            assert row[2] == "refunded"
            assert row[3] == "rfnd_RZP_SUCCESS_789"
            assert row[4] == "processed"
            assert "Temple priest scheduling" in row[5]
            assert row[6] == 2500.0

            # 4. Verify capacity is released
            count_after = get_confirmed_booking_count(conn, "Pratyangira Homam")
            assert count_after == count_before - 1

            # 5. Verify refund record logged in payment_refunds table
            refund_record = conn.execute(
                "SELECT * FROM payment_refunds WHERE booking_id = 'ADMTEST-REJECT-1'"
            ).fetchone()
            assert refund_record is not None

            # 6. Verify audit log entry
            audit = conn.execute(
                "SELECT action FROM admin_audit_logs WHERE booking_id = 'ADMTEST-REJECT-1'"
            ).fetchone()
            assert audit[0] == "booking_rejected"
        finally:
            conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# 8. ASTROLOGER CONSULTATION: PUBLIC BOOKING & SCHEDULING
# ══════════════════════════════════════════════════════════════════════════════

class TestConsultationManagement:
    def test_public_consultation_submission(self):
        """Devotees can request a consultation via POST /api/consultation/book."""
        r = client.post("/api/consultation/book", json={
            "name": "Devotee Ananya",
            "email": "ananya@example.com",
            "phone": "9876543210",
            "consultation_type": "phone",
            "message": "Guidance on career change and marriage matching."
        })
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        booking_id = data["booking_id"]
        assert booking_id.startswith("TAV-CONSULT-")

        # Verify stored in DB
        conn = sqlite3.connect(main.DATABASE_URL, timeout=10.0)
        try:
            b = conn.execute("SELECT customer_name, type, booking_status FROM bookings WHERE id = ?", (booking_id,)).fetchone()
            assert b is not None
            assert b[0] == "Devotee Ananya"
            assert b[1] == "consultation"
            assert b[2] == "pending"
            conn.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
            conn.commit()
        finally:
            conn.close()

    @patch("main.send_email", return_value=True)
    def test_schedule_consultation_and_collision_detection(self, mock_email):
        """Admin schedules consultation; duplicate slot on same date & time must raise 409 Conflict."""
        conn = sqlite3.connect(main.DATABASE_URL, timeout=10.0)
        conn.execute("PRAGMA busy_timeout = 5000")
        empty_p = json.dumps([])
        try:
            conn.execute("""
                INSERT INTO bookings (
                    id, type, name, customer_name, price, persons, participants, contact_email, contact_phone,
                    status, booking_status
                ) VALUES
                ('ADMTEST-CONS-1', 'consultation', 'Vedic Astrology Consultation', 'Devotee First', 0.0, 1, ?, 'first@example.com', '9001', 'pending', 'pending'),
                ('ADMTEST-CONS-2', 'consultation', 'Vedic Astrology Consultation', 'Devotee Second', 0.0, 1, ?, 'second@example.com', '9002', 'pending', 'pending')
            """, (empty_p, empty_p))
            conn.commit()
        finally:
            conn.close()

        # 1. Schedule first consultation for 2026-11-15 at 10:30 IST
        r1 = client.post(
            "/api/admin/bookings/ADMTEST-CONS-1/schedule",
            headers=auth_headers(),
            json={
                "scheduled_date": "2026-11-15",
                "scheduled_time": "10:30",
                "meeting_link": "Phone Call from +91 9908466610",
                "consultation_notes": "Keep birth time ready."
            }
        )
        assert r1.status_code == 200
        assert r1.json()["status"] == "ok"

        # 2. Attempt to schedule second consultation at the SAME date and time -> 409 Conflict
        r2 = client.post(
            "/api/admin/bookings/ADMTEST-CONS-2/schedule",
            headers=auth_headers(),
            json={
                "scheduled_date": "2026-11-15",
                "scheduled_time": "10:30",
                "meeting_link": "Google Meet",
                "consultation_notes": "Duplicate test."
            }
        )
        assert r2.status_code == 409
        assert "already booked" in r2.json()["detail"]

        # 3. Scheduling second consultation at a DIFFERENT time succeeds
        r3 = client.post(
            "/api/admin/bookings/ADMTEST-CONS-2/schedule",
            headers=auth_headers(),
            json={
                "scheduled_date": "2026-11-15",
                "scheduled_time": "11:30",
                "meeting_link": "Google Meet",
                "consultation_notes": "Different time slot."
            }
        )
        assert r3.status_code == 200
        assert r3.json()["status"] == "ok"

    @patch("main.send_email", return_value=True)
    def test_reschedule_consultation(self, mock_email):
        conn = sqlite3.connect(main.DATABASE_URL, timeout=10.0)
        conn.execute("PRAGMA busy_timeout = 5000")
        empty_p = json.dumps([])
        try:
            conn.execute("""
                INSERT INTO bookings (
                    id, type, name, customer_name, price, persons, participants, contact_email, contact_phone,
                    status, booking_status, scheduled_date, scheduled_time, scheduled_at
                ) VALUES (
                    'ADMTEST-RESCHED-1', 'consultation', 'Vedic Astrology Consultation', 'Devotee Resched', 0.0, 1, ?,
                    'resched@example.com', '9003', 'confirmed', 'scheduled', '2026-11-20', '14:00', '2026-11-20 14:00 IST'
                )
            """, (empty_p,))
            conn.commit()
        finally:
            conn.close()

        r = client.post(
            "/api/admin/bookings/ADMTEST-RESCHED-1/reschedule",
            headers=auth_headers(),
            json={
                "scheduled_date": "2026-11-21",
                "scheduled_time": "16:00",
                "reason": "Devotee requested evening slot.",
                "consultation_notes": "Updated timing."
            }
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "2026-11-21 16:00 IST" in data["scheduled_at"]

        # Verify DB
        conn = sqlite3.connect(main.DATABASE_URL, timeout=10.0)
        try:
            row = conn.execute("SELECT booking_status, scheduled_date, scheduled_time FROM bookings WHERE id = 'ADMTEST-RESCHED-1'").fetchone()
            assert row[0] == "rescheduled"
            assert row[1] == "2026-11-21"
            assert row[2] == "16:00"
        finally:
            conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# 9. CAPACITY TRACKER & 4 ENABLED HOMAMS
# ══════════════════════════════════════════════════════════════════════════════

class TestAdminCapacity:
    def test_capacity_endpoint_enforces_50_limit_and_4_enabled_homams(self):
        r = client.get("/api/admin/capacity", headers=auth_headers())
        assert r.status_code == 200
        data = r.json()
        assert data["max_limit"] == 50
        services = data["services"]
        assert isinstance(services, list)

        # 4 Approved Homams
        approved_homams = [
            "Pratyangira Homam",
            "Lakshmi Ganapathi Homam",
            "Kala Bhairava Homam",
            "Chandi Mula Mantra Homam"
        ]

        for s in services:
            assert s["limit"] == 50
            if s["type"] == "homam":
                if s["name"] in approved_homams:
                    assert s["is_enabled"] is True, f"{s['name']} must be enabled"
                else:
                    assert s["is_enabled"] is False, f"{s['name']} must be disabled (Coming Soon)"


# ══════════════════════════════════════════════════════════════════════════════
# 10. AUDIT TRAIL LOGGING
# ══════════════════════════════════════════════════════════════════════════════

class TestAdminAuditLogs:
    def test_audit_logs_record_and_retrieve(self):
        # Trigger an action
        token = get_admin_token()
        client.get("/api/admin/me", headers=auth_headers(token))

        r = client.get("/api/admin/audit-logs?page=1&limit=20", headers=auth_headers(token))
        assert r.status_code == 200
        data = r.json()
        assert "logs" in data
        assert "total" in data
        assert data["total"] > 0

        # Check fields of audit logs
        first_log = data["logs"][0]
        assert "id" in first_log
        assert "admin_email" in first_log
        assert "action" in first_log
        assert "timestamp" in first_log
        assert first_log["admin_email"] == AUTHORIZED_ADMIN_EMAIL
