"""
══════════════════════════════════════════════════════════════
service_catalogue.py — Authoritative Backend Service Catalogue
Tara Astro Vision
══════════════════════════════════════════════════════════════
This file is the SINGLE SOURCE OF TRUTH for all service names
and prices. The frontend only selects services; the backend
validates names AND calculates the price.

Rules:
  - Never trust prices sent by the browser.
  - Validate every service name against this catalogue before
    creating a Razorpay order or confirming a booking.
  - Homam price is per-person; total = price_per_person * persons.
  - Pooja price is flat (persons=1 always for poojas).
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Optional


ServiceType = Literal["pooja", "homam", "consultation"]


@dataclass(frozen=True)
class Service:
    name: str
    type: ServiceType
    price: float            # flat price for poojas/consultations; price-per-person for homams
    min_persons: int = 1
    max_persons: int = 1    # homams: set to a large number like 20


# ─── Consultation Catalogue ──────────────────────────────────
_CONSULTATIONS: list[Service] = [
    Service("Astrologer Consultation",        "consultation", 1000.0),
    Service("Vedic Astrology Consultation",  "consultation", 1000.0),
]


# ─── Pooja Catalogue ─────────────────────────────────────────
_POOJAS: list[Service] = [
    # Monday – Shiva Poojas
    Service("Siva Abhishekam",          "pooja", 3.0),
    Service("Siva Astottara Pooja",     "pooja", 116.0),
    Service("Ekadasa Rudrabhishekam",   "pooja", 516.0),
    Service("Gotra Nama Pooja (Mon)",   "pooja", 116.0),
    # Tuesday – Anjaneya Poojas
    Service("108 Aaku Pooja",           "pooja", 216.0),
    Service("Anjaneya Abhishekam",      "pooja", 216.0),
    Service("Anjaneya Astottaram",      "pooja", 116.0),
    Service("Gotra Nama Pooja (Tue)",   "pooja", 116.0),
    # Wednesday – Ganesh Poojas
    Service("Ganesh Abhishekam",        "pooja", 216.0),
    Service("Ganesh Astottaram",        "pooja", 116.0),
    Service("Gotra Nama Pooja (Wed)",   "pooja", 116.0),
    # Thursday – Sai Poojas
    Service("Sai Astottara Pooja",      "pooja", 116.0),
    Service("Sai Abhishekam",           "pooja", 216.0),
    Service("Gotra Nama Pooja (Thu)",   "pooja", 116.0),
    # Friday – Devi Poojas
    Service("Kumkum Archana",           "pooja", 316.0),
    Service("Lalitha Devi Abhishekam",  "pooja", 216.0),
    Service("Lalitha Devi Astottaram",  "pooja", 116.0),
    Service("Sri Chakra Pooja",         "pooja", 516.0),
    # Saturday – Venkateswara Poojas
    Service("Venkateswara Abhishekam",  "pooja", 216.0),
    Service("Venkateswara Astottaram",  "pooja", 116.0),
    Service("Gotra Nama Pooja (Sat)",   "pooja", 116.0),
    # Sunday – Surya Poojas
    Service("Surya Astottaram",         "pooja", 116.0),
    Service("Aditya Hrudayam Parayana", "pooja", 116.0),
    Service("Gotra Nama Pooja (Sun)",   "pooja", 116.0),
]

# ─── Homam Catalogue (samuhika / group; price is per-person) ─
_HOMAMS: list[Service] = [
    Service("Pratyangira Homam",            "homam", 2000.0, max_persons=100),
    Service("Kali Homam",                   "homam", 2000.0, max_persons=100),
    Service("Tara Homam",                   "homam", 2000.0, max_persons=100),
    Service("Chinnamasta Homam",            "homam", 2000.0, max_persons=100),
    Service("Tripura Bhairavi Homam",       "homam", 2000.0, max_persons=100),
    Service("Bagalamukhi Homam",            "homam", 2000.0, max_persons=100),
    Service("Shodashi Homam",               "homam", 2000.0, max_persons=100),
    Service("Matangi Homam",                "homam", 2000.0, max_persons=100),
    Service("Dhoomavathi Homam",            "homam", 2000.0, max_persons=100),
    Service("Bhuvaneswari Homam",           "homam", 2000.0, max_persons=100),
    Service("Kamalatmika Homam",            "homam", 2000.0, max_persons=100),
    Service("Kala Bhairava Homam",          "homam", 2000.0, max_persons=100),
    Service("Lakshmi Ganapathi Homam",      "homam", 2000.0, max_persons=100),
    Service("Navagraha Homam",              "homam", 2000.0, max_persons=100),
    Service("Maha Mrityunjaya Homam",       "homam", 2000.0, max_persons=100),
    Service("Lakshmi Narasimha Homam",      "homam", 2000.0, max_persons=100),
    Service("Chandi Mula Mantra Homam",     "homam", 2000.0, max_persons=100),
    Service("Dattatreya Mula Mantra Homam", "homam", 2000.0, max_persons=100),
    Service("Sudarshana Homam",             "homam", 2000.0, max_persons=100),
    Service("Rudra Homam",                  "homam", 2000.0, max_persons=100),
    Service("Medha Dakshina Murthy Homam",  "homam", 2000.0, max_persons=100),
    Service("Varahi Homam",                 "homam", 2000.0, max_persons=100),
]

# Aliases mapping alternative spelling / button labels to canonical service objects
_ALIASES: dict[str, Service] = {
    "Prathyangira Homam": Service("Prathyangira Homam", "homam", 2000.0, max_persons=100),
    "Bhagalamukhi Homam": Service("Bhagalamukhi Homam", "homam", 2000.0, max_persons=100),
    "Bhairavi Homam": Service("Bhairavi Homam", "homam", 2000.0, max_persons=100),
    "Shodasi Homam": Service("Shodasi Homam", "homam", 2000.0, max_persons=100),
    "Kalabhairava Homam": Service("Kalabhairava Homam", "homam", 2000.0, max_persons=100),
    "Sudarsana Homam": Service("Sudarsana Homam", "homam", 2000.0, max_persons=100),
    "Vaarahi Homam": Service("Vaarahi Homam", "homam", 2000.0, max_persons=100),
}

# ─── Internal lookup maps ─────────────────────────────────────
_ALL: dict[str, Service] = {s.name: s for s in _POOJAS + _HOMAMS + _CONSULTATIONS}
_ALL.update(_ALIASES)


# ─── Booking Limit (50 max confirmed bookings per individual service) ──
import os
SERVICE_BOOKING_LIMIT: int = int(os.getenv("MAX_BOOKINGS_PER_SERVICE", "50"))

# Map alias / alternative spellings to canonical service names
CANONICAL_NAME_MAP: dict[str, str] = {
    "Prathyangira Homam": "Pratyangira Homam",
    "Pratyangira Homam": "Pratyangira Homam",
    "Bhagalamukhi Homam": "Bagalamukhi Homam",
    "Bagalamukhi Homam": "Bagalamukhi Homam",
    "Bhairavi Homam": "Tripura Bhairavi Homam",
    "Tripura Bhairavi Homam": "Tripura Bhairavi Homam",
    "Shodasi Homam": "Shodashi Homam",
    "Shodashi Homam": "Shodashi Homam",
    "Kalabhairava Homam": "Kala Bhairava Homam",
    "Kala Bhairava Homam": "Kala Bhairava Homam",
    "Sudarsana Homam": "Sudarshana Homam",
    "Sudarshana Homam": "Sudarshana Homam",
    "Vaarahi Homam": "Varahi Homam",
    "Varahi Homam": "Varahi Homam",
}


def canonical_service_name(name: str) -> str:
    """Return the primary canonical name for *name*."""
    n = (name or "").strip()
    return CANONICAL_NAME_MAP.get(n, n)


def service_name_variants(name: str) -> list[str]:
    """Return all known spelling variants/aliases for a service name."""
    canon = canonical_service_name(name)
    variants = {canon}
    if (name or "").strip():
        variants.add(name.strip())
    for k, v in CANONICAL_NAME_MAP.items():
        if v == canon:
            variants.add(k)
    return sorted(list(variants))


# ─── Enabled Homams (only these 4 are active for booking) ────
ENABLED_HOMAMS: set[str] = {
    "Pratyangira Homam",
    "Prathyangira Homam",
    "Lakshmi Ganapathi Homam",
    "Kala Bhairava Homam",
    "Kalabhairava Homam",
    "Chandi Mula Mantra Homam",
}


def is_homam_enabled(name: str) -> bool:
    """Return True if the homam is currently enabled for booking."""
    return (name or "").strip() in ENABLED_HOMAMS


# ─── Booking Counts & Slot Availability ───────────────────────

def get_confirmed_booking_count(conn_or_cursor, name: str) -> int:
    """
    Count confirmed/paid bookings for *name* (or any alias).
    Excludes cancelled, failed, or pending payments.
    """
    if conn_or_cursor is None or not name:
        return 0
    variants = service_name_variants(name)
    placeholders = ",".join("?" for _ in variants)
    query = f"""
        SELECT COUNT(*)
        FROM bookings
        WHERE name IN ({placeholders})
          AND status IN ('paid', 'confirmed')
    """
    row = conn_or_cursor.execute(query, variants).fetchone()
    return int(row[0]) if row else 0


def get_all_services_availability(conn_or_cursor=None, max_limit: int = SERVICE_BOOKING_LIMIT) -> dict[str, dict]:
    """
    Return a mapping of service name -> live slot availability info.
    Keys include canonical service names as well as all aliases.
    """
    counts_by_canon: dict[str, int] = {}
    if conn_or_cursor is not None:
        query = """
            SELECT name, COUNT(*) as cnt
            FROM bookings
            WHERE status IN ('paid', 'confirmed')
            GROUP BY name
        """
        rows = conn_or_cursor.execute(query).fetchall()
        for row in rows:
            c_name = canonical_service_name(row[0])
            counts_by_canon[c_name] = counts_by_canon.get(c_name, 0) + int(row[1])

    avail: dict[str, dict] = {}
    for s in _POOJAS + _HOMAMS:
        c_name = canonical_service_name(s.name)
        booked = counts_by_canon.get(c_name, 0)
        remaining = max(0, max_limit - booked)
        sold_out = (booked >= max_limit)
        is_homam = (s.type == "homam")
        enabled = is_homam_enabled(s.name) if is_homam else True

        info = {
            "name": s.name,
            "canonical_name": c_name,
            "type": s.type,
            "booked": booked,
            "remaining": remaining,
            "max_limit": max_limit,
            "sold_out": sold_out,
            "available": enabled and not sold_out,
            "coming_soon": is_homam and not enabled,
        }
        avail[s.name] = info
        avail[c_name] = info
        for v in service_name_variants(s.name):
            avail[v] = info

    return avail


# ─── Public API ───────────────────────────────────────────────

def get_service(name: str) -> Optional[Service]:
    """Return the Service for *name*, or None if not found."""
    if not name:
        return None
    return _ALL.get(name.strip())


def validate_and_price(
    name: str,
    service_type: str,
    persons: int = 1,
    check_availability: bool = True,
    db=None,
    max_limit: int = SERVICE_BOOKING_LIMIT,
) -> tuple[Service, float]:
    """
    Validate *name* + *service_type* against the catalogue and
    return (service, authoritative_total_price).

    Raises ValueError with a human-readable message on any
    validation failure.
    """
    svc = get_service(name)
    if svc is None:
        raise ValueError(f"Unknown service: '{name}'")

    norm_type = service_type.strip().lower()
    if svc.type != norm_type:
        raise ValueError(
            f"Service '{name}' is a {svc.type}, not a {norm_type}"
        )

    if norm_type == "homam":
        if check_availability and not is_homam_enabled(svc.name):
            raise ValueError(
                f"Booking for '{name}' is currently unavailable (Coming Soon). Only Prathyangira Homam, Lakshmi Ganapathi Homam, Kala Bhairava Homam, and Chandi Mula Mantra Homam are available for booking."
            )
        if persons < svc.min_persons:
            raise ValueError(
                f"Minimum {svc.min_persons} person(s) required for '{name}'"
            )
        if persons > svc.max_persons:
            raise ValueError(
                f"Maximum {svc.max_persons} person(s) allowed for '{name}'"
            )
        total = svc.price * persons
    else:
        # Poojas are flat-price; ignore persons > 1 from frontend
        total = svc.price

    # Capacity check if db connection provided
    if db is not None and check_availability:
        confirmed_count = get_confirmed_booking_count(db, svc.name)
        if confirmed_count >= max_limit:
            raise ValueError(
                f"Bookings Closed — Maximum Capacity Reached ({max_limit}/{max_limit}) for '{svc.name}'."
            )

    return svc, total


def all_services(conn_or_cursor=None, max_limit: int = SERVICE_BOOKING_LIMIT) -> list[dict]:
    """Return the full catalogue as a list of dicts (for /api/services endpoint)."""
    avail_map = get_all_services_availability(conn_or_cursor, max_limit=max_limit)
    result = []
    for s in _POOJAS + _HOMAMS:
        info = avail_map.get(s.name, {})
        booked = info.get("booked", 0)
        remaining = info.get("remaining", max_limit - booked)
        sold_out = info.get("sold_out", booked >= max_limit)
        is_homam = (s.type == "homam")
        enabled = is_homam_enabled(s.name) if is_homam else True

        result.append({
            "name": s.name,
            "type": s.type,
            "price": s.price,
            "min_persons": s.min_persons,
            "max_persons": s.max_persons,
            "available": enabled and not sold_out,
            "max_limit": max_limit,
            "booked": booked,
            "remaining": remaining,
            "sold_out": sold_out,
        })
    return result
