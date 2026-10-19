"""
admin_api.py — Tara Astro Vision Admin Portal Backend API
══════════════════════════════════════════════════════════════
Authorized Admin: info@taraastrovision.com
Includes:
  - Strict authentication & PBKDF2 verification
  - Login rate limiting (5 attempts / 15 mins)
  - Dashboard metrics aggregation from real database
  - Separate booking management (Homam, Pooja, Consultation)
  - Booking Accept / Reject with automated Razorpay refund
  - Astrologer consultation scheduling with collision detection (Asia/Kolkata)
  - Refund tracking & manual retry
  - Audit logging for every admin action
"""

from fastapi import APIRouter, HTTPException, Depends, Request, status
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta, timezone
from typing import Optional, List
import sqlite3
import json
import logging
import secrets

from setup_admin import (
    AUTHORIZED_ADMIN_EMAIL,
    verify_admin_password,
    init_admin_tables,
)

log = logging.getLogger("tara-astro-admin")

admin_router = APIRouter(prefix="/api/admin", tags=["admin"])
public_consult_router = APIRouter(prefix="/api/consultation", tags=["consultation"])

# In-memory tracking for login rate limiting: ip -> list of timestamps
ADMIN_FAILED_LOGINS = {}


def check_admin_rate_limit(client_ip: str):
    """Enforce maximum 5 failed attempts in 15 minutes per IP."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=15)
    attempts = [t for t in ADMIN_FAILED_LOGINS.get(client_ip, []) if t > cutoff]
    ADMIN_FAILED_LOGINS[client_ip] = attempts
    if len(attempts) >= 5:
        log.warning(f"Rate limit exceeded for admin login from IP {client_ip}")
        raise HTTPException(
            status_code=429,
            detail="Too many failed login attempts. Please wait 15 minutes before trying again."
        )


def record_failed_login(client_ip: str):
    now = datetime.now(timezone.utc)
    attempts = ADMIN_FAILED_LOGINS.get(client_ip, [])
    attempts.append(now)
    ADMIN_FAILED_LOGINS[client_ip] = attempts


def clear_failed_logins(client_ip: str):
    ADMIN_FAILED_LOGINS.pop(client_ip, None)


# ─── Pydantic Request Models ─────────────────────────────────

class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


class BookingAcceptRequest(BaseModel):
    notes: Optional[str] = None
    admin_notes: Optional[str] = None


class BookingRejectRequest(BaseModel):
    reason: str
    admin_notes: Optional[str] = None


class ConsultationScheduleRequest(BaseModel):
    scheduled_date: Optional[str] = None       # YYYY-MM-DD
    scheduled_time: Optional[str] = None       # HH:MM (Asia/Kolkata)
    date: Optional[str] = None
    time: Optional[str] = None
    consultation_notes: Optional[str] = None
    admin_notes: Optional[str] = None
    meeting_link: Optional[str] = None


class ConsultationRescheduleRequest(BaseModel):
    scheduled_date: Optional[str] = None       # YYYY-MM-DD
    scheduled_time: Optional[str] = None       # HH:MM (Asia/Kolkata)
    date: Optional[str] = None
    time: Optional[str] = None
    new_date: Optional[str] = None
    new_time: Optional[str] = None
    reason: Optional[str] = None
    consultation_notes: Optional[str] = None
    admin_notes: Optional[str] = None


class PublicConsultationRequest(BaseModel):
    name: str
    email: EmailStr
    phone: str
    consultation_type: str       # 'phone' or 'personal'
    message: str


# ─── Audit Log Helper ────────────────────────────────────────

def log_admin_action(db, action: str, details: str, booking_id: Optional[str] = None, ip_address: Optional[str] = None):
    try:
        db.execute(
            """INSERT INTO admin_audit_logs (admin_email, action, booking_id, details, ip_address)
               VALUES (?, ?, ?, ?, ?)""",
            (AUTHORIZED_ADMIN_EMAIL, action, booking_id, details, ip_address)
        )
        db.commit()
    except Exception as e:
        log.error(f"Failed to record audit log: {e}")


# ─── Auth Dependency ─────────────────────────────────────────

def setup_admin_routes(app, get_db, oauth2_scheme, verify_token, create_token, _rzp_client, send_email, get_all_services_availability):
    """Factory to attach admin routes with shared backend services."""

    def _dispatch_send_email(*args, **kwargs):
        import sys
        main_mod = sys.modules.get("main")
        fn = getattr(main_mod, "send_email", send_email) if main_mod else send_email
        return fn(*args, **kwargs)

    def _dispatch_rzp_client():
        import sys
        main_mod = sys.modules.get("main")
        fn = getattr(main_mod, "_rzp_client", _rzp_client) if main_mod else _rzp_client
        return fn()

    def get_current_admin(token: str = Depends(oauth2_scheme), db=Depends(get_db)):
        payload = verify_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired admin session. Please log in.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if payload.get("role") != "admin" or payload.get("email") != AUTHORIZED_ADMIN_EMAIL:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Authorized administrator only."
            )
        admin = db.execute(
            "SELECT id, email, created_at, last_login_at FROM admin_users WHERE email = ?",
            (AUTHORIZED_ADMIN_EMAIL,)
        ).fetchone()
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Admin account not configured in database."
            )
        return dict(admin)

    # ─── Public Consultation Booking ─────────────────────────

    @public_consult_router.post("/book")
    async def book_consultation_endpoint(data: PublicConsultationRequest, db=Depends(get_db)):
        cid = f"TAV-CONSULT-{int(datetime.now().timestamp())}-{secrets.token_hex(2).upper()}"
        participants_data = [{
            "name": data.name,
            "email": data.email,
            "phone": data.phone,
            "type": data.consultation_type,
            "message": data.message,
        }]

        try:
            db.execute(
                """INSERT INTO bookings (
                    id, type, name, customer_name, price, persons, participants,
                    contact_email, contact_phone, status, booking_status, payment_status,
                    consultation_type, admin_notes
                ) VALUES (?, 'consultation', 'Astrologer Consultation', ?, 0.0, 1, ?, ?, ?, 'confirmed', 'pending', 'not_required', ?, ?)""",
                (cid, data.name, json.dumps(participants_data), data.email, data.phone, data.consultation_type, data.message)
            )
            db.commit()
        except Exception as e:
            log.error(f"Failed to record consultation booking: {e}")
            raise HTTPException(500, "Failed to submit consultation request.")

        # Notify admin via email
        admin_subject = f"[New Consultation] {data.name} — {data.consultation_type.title()} Consultation ({cid})"
        admin_body = f"""New Astrologer Consultation Request:

Booking ID: {cid}
Customer Name: {data.name}
Email: {data.email}
Phone: {data.phone}
Preferred Mode: {data.consultation_type.title()}

Inquiry / Guidance Topic:
{data.message}

Please log in to the Tara Astro Vision Admin Portal at https://www.taraastrovision.com/admin to accept, reject, or schedule this appointment.
"""
        _dispatch_send_email(to=AUTHORIZED_ADMIN_EMAIL, subject=admin_subject, body=admin_body)

        # Notify customer receipt
        cust_subject = f"Consultation Request Received — Tara Astro Vision ({cid})"
        cust_body = f"""Dear {data.name},

Namaste. We have received your astrologer consultation request.

Booking Reference: {cid}
Preferred Mode: {data.consultation_type.title()}
Guidance Topic: {data.message}

Our astrologer will review your inquiry and schedule your appointment shortly. You will receive a confirmation email with the confirmed date and time in IST.

Warm regards,
Tara Astro Vision
info@taraastrovision.com | +91 9908466610
https://www.taraastrovision.com/
"""
        _dispatch_send_email(to=data.email, subject=cust_subject, body=cust_body)

        return {
            "status": "ok",
            "message": "Consultation request submitted successfully. Our astrologer will contact you shortly.",
            "booking_id": cid,
        }

    # ─── Admin Login & Session ───────────────────────────────

    @admin_router.post("/login")
    async def admin_login_endpoint(data: AdminLoginRequest, request: Request, db=Depends(get_db)):
        client_ip = request.client.host if request.client else "127.0.0.1"
        check_admin_rate_limit(client_ip)

        # 1. Strictly enforce authorized email
        req_email = data.email.strip().lower()
        if req_email != AUTHORIZED_ADMIN_EMAIL:
            record_failed_login(client_ip)
            log_admin_action(db, "unauthorized_login_attempt", f"Attempted login with non-admin email: {data.email}", ip_address=client_ip)
            raise HTTPException(
                status_code=401,
                detail="Access denied. Only authorized administrator may access this portal."
            )

        # 2. Fetch admin record
        admin = db.execute(
            "SELECT id, email, password_hash, salt, last_login_at, created_at FROM admin_users WHERE email = ?",
            (AUTHORIZED_ADMIN_EMAIL,)
        ).fetchone()
        if not admin:
            record_failed_login(client_ip)
            log_admin_action(db, "unconfigured_admin_login", "Admin account not found in database", ip_address=client_ip)
            raise HTTPException(
                status_code=401,
                detail="Admin account not configured in database. Run setup_admin.py to set password."
            )

        if isinstance(admin, (sqlite3.Row, dict)):
            admin_id = admin["id"]
            pwd_hash = admin["password_hash"]
            salt = admin["salt"]
        else:
            admin_id = admin[0]
            pwd_hash = admin[2]
            salt = admin[3]

        # 3. Verify password hash using PBKDF2 with constant-time verification
        pwd_input = data.password
        matched = verify_admin_password(pwd_input, salt, pwd_hash)
        if not matched and pwd_input != pwd_input.strip():
            matched = verify_admin_password(pwd_input.strip(), salt, pwd_hash)

        if not matched:
            record_failed_login(client_ip)
            log_admin_action(db, "failed_login_password", "Incorrect password entered", ip_address=client_ip)
            raise HTTPException(
                status_code=401,
                detail="Invalid administrator credentials."
            )

        # Success
        clear_failed_logins(client_ip)
        now_str = datetime.now(timezone.utc).isoformat()
        db.execute("UPDATE admin_users SET last_login_at = ? WHERE id = ?", (now_str, admin_id))
        db.commit()
        log_admin_action(db, "admin_login_success", "Successful login", ip_address=client_ip)

        token = create_token({"email": AUTHORIZED_ADMIN_EMAIL, "role": "admin"}, expires_hours=12)
        return {
            "status": "ok",
            "token": token,
            "email": AUTHORIZED_ADMIN_EMAIL,
            "role": "admin",
            "message": "Login successful"
        }

    @admin_router.get("/me")
    async def admin_me_endpoint(admin=Depends(get_current_admin)):
        return {
            "email": admin["email"],
            "role": "admin",
            "last_login_at": admin.get("last_login_at"),
            "created_at": admin.get("created_at"),
        }

    @admin_router.post("/logout")
    async def admin_logout_endpoint(request: Request, admin=Depends(get_current_admin), db=Depends(get_db)):
        client_ip = request.client.host if request.client else "127.0.0.1"
        log_admin_action(db, "admin_logout", "Administrator logged out", ip_address=client_ip)
        return {"status": "ok", "message": "Logged out successfully"}

    # ─── Admin Dashboard ─────────────────────────────────────

    @admin_router.get("/dashboard")
    async def admin_dashboard_endpoint(admin=Depends(get_current_admin), db=Depends(get_db)):
        """Aggregate key metrics from real database records."""
        # Booking counts by service type
        homam_total = db.execute("SELECT COUNT(*) FROM bookings WHERE type = 'homam' AND status != 'pending_payment'").fetchone()[0]
        pooja_total = db.execute("SELECT COUNT(*) FROM bookings WHERE type = 'pooja' AND status != 'pending_payment'").fetchone()[0]
        consult_total = db.execute("SELECT COUNT(*) FROM bookings WHERE type = 'consultation' AND status != 'pending_payment'").fetchone()[0]
        total_bookings = homam_total + pooja_total + consult_total

        # Today's bookings (using current date)
        today_bookings = db.execute(
            "SELECT COUNT(*) FROM bookings WHERE status != 'pending_payment' AND date(created_at) = date('now')"
        ).fetchone()[0]

        # Status breakdown
        pending_count = db.execute(
            "SELECT COUNT(*) FROM bookings WHERE status != 'pending_payment' AND (booking_status = 'pending' OR booking_status IS NULL)"
        ).fetchone()[0]
        accepted_count = db.execute(
            "SELECT COUNT(*) FROM bookings WHERE status != 'pending_payment' AND booking_status IN ('accepted', 'confirmed', 'scheduled', 'rescheduled', 'completed')"
        ).fetchone()[0]
        rejected_count = db.execute(
            "SELECT COUNT(*) FROM bookings WHERE status != 'pending_payment' AND (booking_status = 'rejected' OR booking_status = 'cancelled')"
        ).fetchone()[0]

        # Payment metrics
        successful_payments = db.execute(
            "SELECT COUNT(*) FROM bookings WHERE payment_status = 'paid' OR (price > 0 AND razorpay_payment_id IS NOT NULL AND status IN ('paid', 'confirmed'))"
        ).fetchone()[0]

        # Gross amount
        gross_collected = db.execute(
            "SELECT COALESCE(SUM(price), 0.0) FROM bookings WHERE (payment_status IN ('paid', 'refunded', 'partially_refunded') OR status = 'paid') AND price > 0"
        ).fetchone()[0]

        # Refund counts & sums from payment_refunds
        refunds_pending = db.execute(
            "SELECT COUNT(*) FROM payment_refunds WHERE status IN ('refund_initiated', 'manual_refund_required', 'pending')"
        ).fetchone()[0]
        refunds_completed = db.execute(
            "SELECT COUNT(*) FROM payment_refunds WHERE status = 'processed'"
        ).fetchone()[0]
        refunds_failed = db.execute(
            "SELECT COUNT(*) FROM payment_refunds WHERE status = 'failed'"
        ).fetchone()[0]
        actual_refunds_amount = db.execute(
            "SELECT COALESCE(SUM(amount_paise)/100.0, 0.0) FROM payment_refunds WHERE status = 'processed'"
        ).fetchone()[0]

        net_collected = max(0.0, gross_collected - actual_refunds_amount)

        # Recent bookings
        recent_rows = db.execute(
            """SELECT id, type, name, customer_name, contact_email, contact_phone,
                      price, persons, booking_status, payment_status, created_at, scheduled_date
               FROM bookings
               WHERE status != 'pending_payment'
               ORDER BY created_at DESC
               LIMIT 12"""
        ).fetchall()

        recent_bookings = [dict(r) for r in recent_rows]

        # Daily booking trends for the last 7 days
        daily_trends = db.execute(
            """SELECT date(created_at) as day, COUNT(*) as count, COALESCE(SUM(price), 0.0) as revenue
               FROM bookings
               WHERE status != 'pending_payment' AND created_at >= date('now', '-7 days')
               GROUP BY date(created_at)
               ORDER BY day ASC"""
        ).fetchall()

        # Capacity preview
        capacity_preview = []
        try:
            avail_dict = get_all_services_availability(db)
            seen_canons = set()
            for info in avail_dict.values():
                canon = info.get("canonical_name", info.get("name"))
                if canon in seen_canons:
                    continue
                seen_canons.add(canon)
                capacity_preview.append({
                    "name": canon,
                    "type": info.get("type"),
                    "confirmed": info.get("booked", 0),
                    "available": info.get("remaining", 50),
                    "limit": info.get("max_limit", 50),
                    "is_full": info.get("sold_out", False),
                    "is_enabled": not info.get("coming_soon", False) if info.get("type") == "homam" else True,
                })
        except Exception as e:
            log.warning(f"Failed to generate capacity preview: {e}")

        # Map recent bookings for UI
        for r in recent_bookings:
            r["service_type"] = r.get("type")
            r["amount"] = r.get("price")
            r["service_name"] = r.get("name")
            r["customer_phone"] = r.get("contact_phone")
            r["customer_email"] = r.get("contact_email")

        return {
            "status": "ok",
            "summary": {
                "homam_bookings": homam_total,
                "pooja_bookings": pooja_total,
                "consultation_bookings": consult_total,
                "total_bookings": total_bookings,
                "today_bookings": today_bookings,
                "pending_bookings": pending_count,
                "accepted_bookings": accepted_count,
                "rejected_bookings": rejected_count,
                "successful_payments": successful_payments,
                "refunds_pending": refunds_pending,
                "refunds_completed": refunds_completed,
                "refunds_failed": refunds_failed,
                "gross_collected": gross_collected,
                "actual_refunds": actual_refunds_amount,
                "net_collected": net_collected,
            },
            "metrics": {
                "total_homams": homam_total,
                "total_poojas": pooja_total,
                "total_consultations": consult_total,
                "total_bookings": total_bookings,
                "today_bookings": today_bookings,
                "pending_bookings": pending_count,
                "accepted_bookings": accepted_count,
                "rejected_bookings": rejected_count,
            },
            "revenue": {
                "gross": gross_collected,
                "refunds": actual_refunds_amount,
                "net": net_collected,
            },
            "capacity": capacity_preview,
            "recent_bookings": recent_bookings,
            "daily_trends": [dict(r) for r in daily_trends],
        }

    # ─── Booking List & Search ───────────────────────────────

    @admin_router.get("/bookings")
    async def list_bookings_endpoint(
        type: Optional[str] = None,          # 'homam', 'pooja', 'consultation', or None
        service_type: Optional[str] = None,  # alias for type
        status: Optional[str] = None,        # 'pending', 'accepted', 'rejected', etc.
        search: Optional[str] = None,        # query string
        page: int = 1,
        page_size: int = 25,
        limit: Optional[int] = None,         # alias for page_size
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        admin=Depends(get_current_admin),
        db=Depends(get_db),
    ):
        page = max(1, page)
        effective_page_size = limit if limit is not None else page_size
        page_size = min(100, max(1, effective_page_size))
        offset = (page - 1) * page_size

        allowed_sort = {"created_at", "price", "name", "id", "customer_name", "scheduled_date"}
        if sort_by not in allowed_sort:
            sort_by = "created_at"
        direction = "ASC" if sort_dir.lower() == "asc" else "DESC"

        where_clauses = ["status != 'pending_payment'"]
        params = []

        effective_type = service_type or type
        if effective_type and effective_type.lower() != "all":
            where_clauses.append("type = ?")
            params.append(effective_type.lower())

        if status and status.lower() != "all":
            if status.lower() == "pending":
                where_clauses.append("(booking_status = 'pending' OR booking_status IS NULL)")
            elif status.lower() == "accepted":
                where_clauses.append("booking_status IN ('accepted', 'confirmed', 'scheduled', 'rescheduled')")
            else:
                where_clauses.append("booking_status = ?")
                params.append(status.lower())

        if search and search.strip():
            q = f"%{search.strip()}%"
            where_clauses.append(
                "(id LIKE ? OR name LIKE ? OR customer_name LIKE ? OR contact_email LIKE ? OR contact_phone LIKE ? OR razorpay_payment_id LIKE ?)"
            )
            params.extend([q, q, q, q, q, q])

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        total_count = db.execute(
            f"SELECT COUNT(*) FROM bookings {where_sql}",
            params
        ).fetchone()[0]

        query = f"""
            SELECT id, type, name, customer_name, price, persons, contact_email, contact_phone,
                   status, booking_status, payment_status, scheduled_date, scheduled_time,
                   scheduled_at, consultation_type, razorpay_order_id, razorpay_payment_id,
                   refund_id, refund_status, refund_amount, created_at, updated_at
            FROM bookings
            {where_sql}
            ORDER BY {sort_by} {direction}
            LIMIT ? OFFSET ?
        """
        rows = db.execute(query, params + [page_size, offset]).fetchall()

        booking_list = []
        for r in rows:
            b_dict = dict(r)
            b_dict["service_type"] = b_dict.get("type")
            b_dict["amount"] = b_dict.get("price")
            b_dict["service_name"] = b_dict.get("name")
            b_dict["customer_phone"] = b_dict.get("contact_phone")
            b_dict["customer_email"] = b_dict.get("contact_email")
            booking_list.append(b_dict)

        return {
            "bookings": booking_list,
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": (total_count + page_size - 1) // page_size if total_count > 0 else 1,
        }

    # ─── Booking Details ─────────────────────────────────────

    @admin_router.get("/bookings/{booking_id}")
    async def get_booking_detail_endpoint(
        booking_id: str,
        admin=Depends(get_current_admin),
        db=Depends(get_db),
    ):
        b = db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
        if not b:
            raise HTTPException(404, f"Booking not found: {booking_id}")

        booking = dict(b)
        booking["service_type"] = booking.get("type")
        booking["amount"] = booking.get("price")
        booking["service_name"] = booking.get("name")
        booking["customer_phone"] = booking.get("contact_phone")
        booking["customer_email"] = booking.get("contact_email")

        # Parse participants safely
        participants = []
        try:
            if booking.get("participants"):
                participants = json.loads(booking["participants"]) if isinstance(booking["participants"], str) else booking["participants"]
        except Exception:
            participants = []
        booking["participants_list"] = participants

        # Populate gotra, nakshatra, rasi from first participant if present
        if participants and isinstance(participants, list) and len(participants) > 0:
            first_p = participants[0]
            if isinstance(first_p, dict):
                booking["gotra"] = booking.get("gotra") or first_p.get("gotra")
                booking["nakshatra"] = booking.get("nakshatra") or first_p.get("nakshatra")
                booking["rasi"] = booking.get("rasi") or first_p.get("rasi")
                booking["sankalpam"] = booking.get("sankalpam") or first_p.get("sankalpam")

        # Fetch linked refund records
        refunds = db.execute(
            "SELECT * FROM payment_refunds WHERE booking_id = ? ORDER BY created_at DESC",
            (booking_id,)
        ).fetchall()
        booking["refunds"] = [dict(r) for r in refunds]

        # Fetch audit trail
        audit_logs = db.execute(
            "SELECT * FROM admin_audit_logs WHERE booking_id = ? ORDER BY created_at DESC",
            (booking_id,)
        ).fetchall()
        return {"status": "ok", "booking": booking, **booking}

    # ─── Accept Booking ──────────────────────────────────────

    @admin_router.post("/bookings/{booking_id}/accept")
    async def accept_booking_endpoint(
        booking_id: str,
        data: BookingAcceptRequest,
        request: Request,
        admin=Depends(get_current_admin),
        db=Depends(get_db),
    ):
        client_ip = request.client.host if request.client else "127.0.0.1"
        b = db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
        if not b:
            raise HTTPException(404, f"Booking not found: {booking_id}")

        booking = dict(b)

        if booking.get("status") not in ("paid", "confirmed") or booking.get("payment_status") != "paid":
            raise HTTPException(409, "Only paid bookings can be accepted")

        # Prevent duplicate acceptance
        if booking.get("booking_status") == "accepted":
            return {
                "status": "ok",
                "message": "Booking is already accepted.",
                "booking_id": booking_id,
                "email_sent": False,
            }

        now_str = datetime.now(timezone.utc).isoformat()
        notes_val = data.notes or data.admin_notes
        db.execute(
            """UPDATE bookings
               SET booking_status = 'accepted',
                   status = 'confirmed',
                   accepted_at = ?,
                   admin_notes = COALESCE(?, admin_notes),
                   updated_at = ?
               WHERE id = ?""",
            (now_str, notes_val, now_str, booking_id)
        )
        db.commit()

        log_admin_action(
            db,
            "booking_accepted",
            f"Accepted {booking['type']} booking: {booking['name']} (Total: ₹{booking['price']})",
            booking_id=booking_id,
            ip_address=client_ip,
        )

        # Send confirmation email to customer
        cust_email = booking.get("contact_email")
        email_sent = False
        if cust_email:
            subject = f"Booking Confirmed — {booking['name']} (ID: {booking_id})"
            body = f"""Dear {booking.get('customer_name') or 'Devotee'},

Namaste. We are pleased to confirm that your booking for {booking['name']} has been accepted and scheduled.

Booking Summary:
- Booking Reference: {booking_id}
- Service: {booking['name']} ({booking['type'].title()})
- Number of Persons: {booking.get('persons', 1)}
- Amount Paid: ₹{booking.get('price', 0.0):,.2f}
- Payment Status: Paid (Ref: {booking.get('razorpay_payment_id') or 'N/A'})
- Scheduled Date: {booking.get('scheduled_date') or 'As per tradition / sacred muhurtham'}

May the divine grace bring health, peace, and prosperity to you and your family.
If you have any questions, please contact us at info@taraastrovision.com or +91 9908466610.

Warm regards,
Tara Astro Vision
https://www.taraastrovision.com/
"""
            email_sent = _dispatch_send_email(to=cust_email, subject=subject, body=body)

        return {
            "status": "ok",
            "message": f"Booking {booking_id} accepted successfully.",
            "booking_id": booking_id,
            "email_sent": email_sent,
        }

    # ─── Reject Booking & Process Refund ─────────────────────

    @admin_router.post("/bookings/{booking_id}/reject")
    async def reject_booking_endpoint(
        booking_id: str,
        data: BookingRejectRequest,
        request: Request,
        admin=Depends(get_current_admin),
        db=Depends(get_db),
    ):
        client_ip = request.client.host if request.client else "127.0.0.1"
        if not data.reason or not data.reason.strip():
            raise HTTPException(400, "A valid rejection reason is required.")

        b = db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
        if not b:
            raise HTTPException(404, f"Booking not found: {booking_id}")

        booking = dict(b)

        if booking.get("status") not in ("paid", "confirmed") or booking.get("payment_status") != "paid":
            raise HTTPException(409, "Only paid bookings can be rejected")

        # Prevent duplicate rejection
        if booking.get("booking_status") == "rejected" and booking.get("refund_status") == "processed":
            return {
                "status": "ok",
                "message": "Booking is already rejected and refunded.",
                "booking_id": booking_id,
                "refund_status": "processed",
                "refund_id": booking.get("refund_id"),
            }

        now_str = datetime.now(timezone.utc).isoformat()
        reason = data.reason.strip()

        # Handle Razorpay refund if payment was captured
        refund_id = None
        refund_status = "none"
        refund_error = None
        amount_paise = int(round(booking.get("price", 0.0) * 100))
        payment_id = booking.get("razorpay_payment_id")

        if payment_id and amount_paise > 0:
            # Check if refund was already recorded
            existing_rf = db.execute(
                "SELECT * FROM payment_refunds WHERE booking_id = ? AND status = 'processed'",
                (booking_id,)
            ).fetchone()

            if existing_rf:
                refund_id = existing_rf["refund_id"]
                refund_status = "processed"
            else:
                try:
                    client = _dispatch_rzp_client()
                    refund_res = client.payment.refund(payment_id, {
                        "amount": amount_paise,
                        "notes": {
                            "booking_id": booking_id,
                            "service": booking.get("name"),
                            "reason": reason,
                            "admin": AUTHORIZED_ADMIN_EMAIL,
                        }
                    })
                    refund_id = refund_res.get("id") if isinstance(refund_res, dict) else str(refund_res)
                    refund_status = refund_res.get("status", "processed") if isinstance(refund_res, dict) else "processed"
                    log.info(f"Razorpay refund initiated: {refund_id} for booking {booking_id}")
                except Exception as e:
                    refund_error = str(e)
                    refund_status = "manual_refund_required"
                    log.error(f"Razorpay refund call failed for booking {booking_id}: {e}")

                # Record into payment_refunds table
                try:
                    db.execute(
                        """INSERT INTO payment_refunds (
                            booking_id, service_name, razorpay_order_id, razorpay_payment_id,
                            amount_paise, status, refund_id, reason, error_message
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (booking_id, booking.get("name"), booking.get("razorpay_order_id"),
                         payment_id, amount_paise, refund_status, refund_id, reason, refund_error)
                    )
                    db.commit()
                except Exception as db_err:
                    log.error(f"Failed to record refund in DB: {db_err}")

        # Update booking status
        payment_status = "refunded" if refund_status == "processed" else ("pending_refund" if refund_status == "refund_initiated" else ("refund_required" if refund_status == "manual_refund_required" else "not_applicable"))
        db.execute(
            """UPDATE bookings
               SET booking_status = 'rejected',
                   status = 'rejected',
                   payment_status = ?,
                   rejection_reason = ?,
                   rejected_at = ?,
                   admin_notes = COALESCE(?, admin_notes),
                   refund_id = COALESCE(?, refund_id),
                   refund_status = ?,
                   refund_amount = ?,
                   refund_initiated_at = ?,
                   refund_error = ?,
                   updated_at = ?
               WHERE id = ?""",
            (payment_status, reason, now_str, data.admin_notes, refund_id,
             refund_status, booking.get("price", 0.0), now_str, refund_error, now_str, booking_id)
        )
        db.commit()

        log_admin_action(
            db,
            "booking_rejected",
            f"Rejected {booking['type']} booking: {booking['name']} — Reason: {reason} | Refund: {refund_status} ({refund_id or 'none'})",
            booking_id=booking_id,
            ip_address=client_ip,
        )

        # Send rejection & refund notification email
        cust_email = booking.get("contact_email")
        email_sent = False
        if cust_email:
            refund_clause = ""
            if amount_paise > 0 and payment_id:
                ref_text = f"Refund ID: {refund_id}" if refund_id else "Refund Reference: In Process by Banking Team"
                refund_clause = f"""
Refund Information:
- Refund Amount: ₹{booking.get('price', 0.0):,.2f}
- {ref_text}
- Estimated Timeline: Refunds are typically credited back to your original payment method within 5 to 7 working days, subject to your bank and payment provider's processing schedule.
"""

            subject = f"Booking Update — {booking['name']} (ID: {booking_id})"
            body = f"""Dear {booking.get('customer_name') or 'Customer'},

Namaste. We regret to inform you that your booking for {booking['name']} (Reference: {booking_id}) could not be accommodated.

Reason for Cancellation:
{reason}
{refund_clause}
We sincerely apologize for any inconvenience caused. If you have questions regarding this cancellation or would like assistance in booking an alternative date or service, please reply directly to this email or contact us at:
info@taraastrovision.com | +91 9908466610

Warm regards,
Tara Astro Vision
https://www.taraastrovision.com/
"""
            email_sent = _dispatch_send_email(to=cust_email, subject=subject, body=body)

        return {
            "status": "ok",
            "message": f"Booking {booking_id} rejected.",
            "booking_id": booking_id,
            "refund_status": refund_status,
            "refund_id": refund_id,
            "email_sent": email_sent,
        }

    # ─── Consultation Scheduling ─────────────────────────────

    @admin_router.post("/bookings/{booking_id}/schedule")
    async def schedule_consultation_endpoint(
        booking_id: str,
        data: ConsultationScheduleRequest,
        request: Request,
        admin=Depends(get_current_admin),
        db=Depends(get_db),
    ):
        client_ip = request.client.host if request.client else "127.0.0.1"
        b = db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
        if not b:
            raise HTTPException(404, f"Booking not found: {booking_id}")
        booking = dict(b)

        date_val = (data.scheduled_date or data.date or "").strip()
        time_val = (data.scheduled_time or data.time or "").strip()
        notes_val = data.consultation_notes or data.admin_notes

        # Validate date and time format
        try:
            datetime.strptime(date_val, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(400, "Invalid date format. Expected YYYY-MM-DD.")
        try:
            datetime.strptime(time_val, "%H:%M")
        except ValueError:
            raise HTTPException(400, "Invalid time format. Expected HH:MM (24-hour).")

        # Collision check: Prevent double-booking same slot in Asia/Kolkata
        conflict = db.execute(
            """SELECT id, customer_name FROM bookings
               WHERE scheduled_date = ? AND scheduled_time = ?
                 AND id != ?
                 AND booking_status IN ('scheduled', 'rescheduled', 'accepted')""",
            (date_val, time_val, booking_id)
        ).fetchone()

        if conflict:
            raise HTTPException(
                status_code=409,
                detail=f"Time slot {date_val} at {time_val} IST is already booked for customer '{conflict['customer_name']}' (ID: {conflict['id']}). Please pick an alternative time slot."
            )

        combined_sched = f"{date_val} {time_val} IST"
        now_str = datetime.now(timezone.utc).isoformat()

        db.execute(
            """UPDATE bookings
               SET booking_status = 'scheduled',
                   status = 'confirmed',
                   scheduled_date = ?,
                   scheduled_time = ?,
                   scheduled_at = ?,
                   admin_notes = COALESCE(?, admin_notes),
                   accepted_at = COALESCE(accepted_at, ?),
                   updated_at = ?
               WHERE id = ?""",
            (date_val, time_val, combined_sched, notes_val, now_str, now_str, booking_id)
        )
        db.commit()

        log_admin_action(
            db,
            "consultation_scheduled",
            f"Scheduled consultation with {booking.get('customer_name')} for {combined_sched}",
            booking_id=booking_id,
            ip_address=client_ip,
        )

        # Send confirmation email to customer
        cust_email = booking.get("contact_email")
        email_sent = False
        if cust_email:
            mode_text = (booking.get("consultation_type") or "phone").title()
            meeting_info = f"\nMeeting Link / Call Instructions: {data.meeting_link}" if data.meeting_link else ""
            notes_info = f"\nAstrologer's Note: {data.consultation_notes}" if data.consultation_notes else ""

            subject = f"Consultation Confirmed — Tara Astro Vision ({combined_sched})"
            body = f"""Dear {booking.get('customer_name') or 'Client'},

Namaste. Your Vedic astrology consultation has been scheduled with our expert astrologer.

Appointment Details (Asia/Kolkata):
- Date: {date_val}
- Time: {time_val} IST
- Mode: {mode_text} Consultation{meeting_info}{notes_info}
- Booking Reference: {booking_id}

Preparation Guidelines:
1. Please ensure you are available in a quiet environment 5 minutes prior to the scheduled time.
2. If your birth details (exact date, time, and city of birth) were not previously provided, please have them ready.

If you need to reschedule or have any questions, please reach out to info@taraastrovision.com or call +91 9908466610.

Warm regards,
Tara Astro Vision
https://www.taraastrovision.com/
"""
            email_sent = _dispatch_send_email(to=cust_email, subject=subject, body=body)

        return {
            "status": "ok",
            "message": f"Consultation scheduled for {combined_sched}.",
            "booking_id": booking_id,
            "scheduled_at": combined_sched,
            "email_sent": email_sent,
        }

    # ─── Consultation Rescheduling ───────────────────────────

    @admin_router.post("/bookings/{booking_id}/reschedule")
    async def reschedule_consultation_endpoint(
        booking_id: str,
        data: ConsultationRescheduleRequest,
        request: Request,
        admin=Depends(get_current_admin),
        db=Depends(get_db),
    ):
        client_ip = request.client.host if request.client else "127.0.0.1"
        b = db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
        if not b:
            raise HTTPException(404, f"Booking not found: {booking_id}")
        booking = dict(b)

        date_val = (data.scheduled_date or data.new_date or data.date or "").strip()
        time_val = (data.scheduled_time or data.new_time or data.time or "").strip()
        notes_val = data.consultation_notes or data.admin_notes

        # Validate date and time format
        try:
            datetime.strptime(date_val, "%Y-%m-%d")
            datetime.strptime(time_val, "%H:%M")
        except ValueError:
            raise HTTPException(400, "Invalid date or time format. Expected YYYY-MM-DD and HH:MM.")

        # Collision check
        conflict = db.execute(
            """SELECT id, customer_name FROM bookings
               WHERE scheduled_date = ? AND scheduled_time = ?
                 AND id != ?
                 AND booking_status IN ('scheduled', 'rescheduled', 'accepted')""",
            (date_val, time_val, booking_id)
        ).fetchone()

        if conflict:
            raise HTTPException(
                status_code=409,
                detail=f"Time slot {date_val} at {time_val} IST is already booked for customer '{conflict['customer_name']}'. Please pick an alternative time slot."
            )

        old_sched = booking.get("scheduled_at") or f"{booking.get('scheduled_date')} {booking.get('scheduled_time')}"
        new_sched = f"{date_val} {time_val} IST"
        now_str = datetime.now(timezone.utc).isoformat()
        reason_text = data.reason or "Schedule adjustment"

        db.execute(
            """UPDATE bookings
               SET booking_status = 'rescheduled',
                   scheduled_date = ?,
                   scheduled_time = ?,
                   scheduled_at = ?,
                   admin_notes = COALESCE(?, admin_notes),
                   updated_at = ?
               WHERE id = ?""",
            (date_val, time_val, new_sched, notes_val, now_str, booking_id)
        )
        db.commit()

        log_admin_action(
            db,
            "consultation_rescheduled",
            f"Rescheduled consultation from '{old_sched}' to '{new_sched}' — Reason: {reason_text}",
            booking_id=booking_id,
            ip_address=client_ip,
        )

        cust_email = booking.get("contact_email")
        email_sent = False
        if cust_email:
            subject = f"Consultation Rescheduled — Tara Astro Vision ({new_sched})"
            body = f"""Dear {booking.get('customer_name') or 'Client'},

Namaste. Please note that your consultation appointment has been rescheduled.

Updated Appointment Details:
- Previous Schedule: {old_sched}
- New Confirmed Schedule: {new_sched}
- Booking Reference: {booking_id}
- Reason: {reason_text}

If this new schedule does not suit you, please let us know immediately by replying to info@taraastrovision.com or calling +91 9908466610.

Warm regards,
Tara Astro Vision
https://www.taraastrovision.com/
"""
            email_sent = _dispatch_send_email(to=cust_email, subject=subject, body=body)

        return {
            "status": "ok",
            "message": f"Consultation rescheduled to {new_sched}.",
            "booking_id": booking_id,
            "scheduled_at": new_sched,
            "email_sent": email_sent,
        }

    # ─── Retry Refund ────────────────────────────────────────

    @admin_router.post("/bookings/{booking_id}/retry-refund")
    async def retry_refund_endpoint(
        booking_id: str,
        request: Request,
        admin=Depends(get_current_admin),
        db=Depends(get_db),
    ):
        client_ip = request.client.host if request.client else "127.0.0.1"
        b = db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
        if not b:
            raise HTTPException(404, f"Booking not found: {booking_id}")
        booking = dict(b)

        if booking.get("refund_status") == "processed":
            return {"status": "ok", "message": "Refund already processed.", "refund_id": booking.get("refund_id")}

        payment_id = booking.get("razorpay_payment_id")
        amount_paise = int(round(booking.get("price", 0.0) * 100))
        if not payment_id or amount_paise <= 0:
            raise HTTPException(400, "Booking does not have a refundable payment ID or positive amount.")

        try:
            client = _dispatch_rzp_client()
            refund_res = client.payment.refund(payment_id, {
                "amount": amount_paise,
                "notes": {"booking_id": booking_id, "retry_by": AUTHORIZED_ADMIN_EMAIL}
            })
            rf_id = refund_res.get("id") if isinstance(refund_res, dict) else str(refund_res)
            rf_status = refund_res.get("status", "processed") if isinstance(refund_res, dict) else "processed"
            now_str = datetime.now(timezone.utc).isoformat()

            db.execute(
                """UPDATE bookings
                   SET refund_id = ?, refund_status = ?, payment_status = 'refunded', updated_at = ?
                   WHERE id = ?""",
                (rf_id, rf_status, now_str, booking_id)
            )
            db.execute(
                """INSERT INTO payment_refunds (
                    booking_id, service_name, razorpay_order_id, razorpay_payment_id,
                    amount_paise, status, refund_id, reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Admin retry')""",
                (booking_id, booking.get("name"), booking.get("razorpay_order_id"), payment_id, amount_paise, rf_status, rf_id)
            )
            db.commit()

            log_admin_action(db, "refund_retried_success", f"Refund successfully retried: {rf_id}", booking_id=booking_id, ip_address=client_ip)
            return {"status": "ok", "message": f"Refund successful: {rf_id}", "refund_id": rf_id}
        except Exception as e:
            log_admin_action(db, "refund_retried_failed", f"Refund retry failed: {e}", booking_id=booking_id, ip_address=client_ip)
            raise HTTPException(502, f"Razorpay refund retry failed: {e}")

    # ─── Capacity Metrics ────────────────────────────────────

    @admin_router.get("/capacity")
    async def get_capacity_endpoint(admin=Depends(get_current_admin), db=Depends(get_db)):
        """Live slot capacity for all Poojas and enabled Homams."""
        availability = get_all_services_availability(db)
        seen_canons = set()
        services_list = []
        for info in availability.values():
            canon = info.get("canonical_name", info.get("name"))
            if canon in seen_canons:
                continue
            seen_canons.add(canon)
            services_list.append({
                "name": canon,
                "type": info.get("type"),
                "confirmed": info.get("booked", 0),
                "available": info.get("remaining", 50),
                "limit": info.get("max_limit", 50),
                "is_full": info.get("sold_out", False),
                "is_enabled": not info.get("coming_soon", False) if info.get("type") == "homam" else True,
            })
        return {
            "services": services_list,
            "max_limit": 50,
            "availability": availability,
        }

    # ─── Refunds Log ─────────────────────────────────────────

    @admin_router.get("/refunds")
    async def get_refunds_endpoint(
        page: int = 1,
        page_size: int = 25,
        admin=Depends(get_current_admin),
        db=Depends(get_db),
    ):
        offset = (max(1, page) - 1) * page_size
        total = db.execute("SELECT COUNT(*) FROM payment_refunds").fetchone()[0]
        rows = db.execute(
            """SELECT id, booking_id, service_name, razorpay_order_id, razorpay_payment_id,
                      amount_paise, status, refund_id, reason, error_message, created_at
               FROM payment_refunds
               ORDER BY created_at DESC
               LIMIT ? OFFSET ?""",
            (page_size, offset)
        ).fetchall()
        return {
            "refunds": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    # ─── Audit Logs ──────────────────────────────────────────

    @admin_router.get("/audit-logs")
    async def get_audit_logs_endpoint(
        action: Optional[str] = None,
        booking_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
        admin=Depends(get_current_admin),
        db=Depends(get_db),
    ):
        offset = (max(1, page) - 1) * page_size
        where = []
        params = []
        if action:
            where.append("action = ?")
            params.append(action)
        if booking_id:
            where.append("booking_id = ?")
            params.append(booking_id)

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        total = db.execute(f"SELECT COUNT(*) FROM admin_audit_logs {where_sql}", params).fetchone()[0]

        rows = db.execute(
            f"""SELECT id, admin_email, action, booking_id, details, ip_address, created_at
               FROM admin_audit_logs
               {where_sql}
               ORDER BY created_at DESC
               LIMIT ? OFFSET ?""",
            params + [page_size, offset]
        ).fetchall()

        logs_list = []
        for r in rows:
            l_dict = dict(r)
            l_dict["timestamp"] = l_dict.get("created_at")
            logs_list.append(l_dict)

        return {
            "logs": logs_list,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    # Include routers into the app
    app.include_router(admin_router)
    app.include_router(public_consult_router)
