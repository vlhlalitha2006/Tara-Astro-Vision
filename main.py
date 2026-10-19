"""
══════════════════════════════════════════════════════════
JYOTISHA — FastAPI Backend
Vedic Astrology Platform
Author: Birthday Gift Project
══════════════════════════════════════════════════════════
Backend Stack:
  - FastAPI (async REST API)
  - Swiss Ephemeris (pyswisseph) for real planetary calculations
  - SQLite (dev) / PostgreSQL (production)
  - JWT authentication (jose / python-jose)
  - Lahiri Ayanamsha (standard GoI / Vedic)
══════════════════════════════════════════════════════════
"""

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, timedelta, timezone
from typing import Optional, List
import sqlite3, hashlib, os, math, logging, threading, json
import pathlib
from service_catalogue import (
    validate_and_price,
    all_services,
    get_all_services_availability,
    get_confirmed_booking_count,
    SERVICE_BOOKING_LIMIT,
    canonical_service_name,
    is_homam_enabled,
)
from razorpay_service import RazorpayClient, RazorpayAPIError, SignatureVerificationError

booking_lock = threading.Lock()

# Root directory of backend and project
ROOT_DIR = pathlib.Path(__file__).parent.resolve()

# Load .env from project directory (where main.py lives)
_env_path = ROOT_DIR / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_env_path)
except ImportError:
    pass

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("tara-astro")

# Optional: import swisseph for production
# import swisseph as swe
# swe.set_ephe_path('/path/to/ephe')   # Set ephemeris data path

# ─── Configuration ───────────────────────────────────────────
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
SECRET_KEY = os.environ.get("JWT_SECRET") or os.getenv("JWT_SECRET", "")
if not SECRET_KEY:
    if APP_ENV == "production":
        raise RuntimeError("JWT_SECRET must be configured in production")
    _secret_file = ROOT_DIR / ".jwt_secret"
    if _secret_file.is_file():
        try:
            SECRET_KEY = _secret_file.read_text().strip()
        except Exception:
            SECRET_KEY = ""
    if not SECRET_KEY:
        import secrets as _secrets
        SECRET_KEY = _secrets.token_hex(32)
        try:
            _secret_file.write_text(SECRET_KEY)
        except Exception:
            pass
        log.warning("JWT_SECRET not set — generated persistent secret in .jwt_secret. Set JWT_SECRET in .env for production.")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

_db_env = os.environ.get("DATABASE_URL") or os.getenv("DATABASE_URL", "")
if _db_env:
    if _db_env.startswith("sqlite:///") or _db_env.startswith("postgresql://") or os.path.isabs(_db_env):
        DATABASE_URL = _db_env
    else:
        DATABASE_URL = str((ROOT_DIR / _db_env).resolve())
else:
    if APP_ENV == "production":
        raise RuntimeError("DATABASE_URL must point to a persistent database path in production")
    DATABASE_URL = str((ROOT_DIR / "jyotisha.db").resolve())
if APP_ENV == "production" and not os.path.isabs(DATABASE_URL):
    raise RuntimeError("DATABASE_URL must be an absolute path on persistent storage in production")


# ─── FastAPI App ─────────────────────────────────────────────
app = FastAPI(
    title="Jyotisha API",
    description="Pure Vedic Astrology Platform — South Indian Kundli & Guidance",
    version="1.0.0",
)

_cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5500,http://127.0.0.1:5500",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ─── Site Index & Homam SPA ──────────────────────────────────
HOMAM_DIST = ROOT_DIR / "homam"


def _site_index():
    idx = ROOT_DIR / "index.html"
    if idx.is_file():
        return FileResponse(idx)
    return {"message": "Jyotisha API — Vedic Astrology Platform", "status": "running"}


def _homam_index():
    idx = HOMAM_DIST / "index.html"
    if not idx.is_file():
        raise HTTPException(404, "Homam pages not built (run: cd homam-app && npm run build)")
    return FileResponse(idx)


@app.get("/homam")
@app.get("/homam/")
async def homam_root():
    """Serve main website SPA with Homams section active."""
    return _site_index()


@app.get("/homam/{full_path:path}")
async def homam_spa(full_path: str):
    """Serve built assets under /homam/assets/*; otherwise SPA index for client routes."""
    if not HOMAM_DIST.is_dir():
        raise HTTPException(404, "Homam pages not built (run: cd homam-app && npm run build)")
    candidate = (HOMAM_DIST / full_path).resolve()
    try:
        candidate.relative_to(HOMAM_DIST.resolve())
    except ValueError:
        raise HTTPException(404, "Invalid path")
    if candidate.is_file():
        return FileResponse(candidate)
    nested_index = candidate / "index.html"
    if candidate.is_dir() and nested_index.is_file():
        return FileResponse(nested_index)
    return _homam_index()


def _admin_index():
    idx = ROOT_DIR / "admin.html"
    if not idx.is_file():
        raise HTTPException(404, "Admin portal file not found")
    return FileResponse(idx)


@app.get("/admin")
@app.get("/admin/")
async def admin_root():
    """Serve Admin Portal interface."""
    return _admin_index()


@app.get("/admin/{full_path:path}")
async def admin_spa_subroute(full_path: str):
    """Serve Admin Portal for any subpath."""
    return _admin_index()


# ─── Database Setup ──────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DATABASE_URL, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    conn = sqlite3.connect(DATABASE_URL)
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            email       TEXT    UNIQUE NOT NULL,
            password    TEXT    NOT NULL,
            lang        TEXT    DEFAULT 'en',
            created_at  TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS birth_charts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            label       TEXT,
            dob         TEXT    NOT NULL,
            tob         TEXT    NOT NULL,
            city        TEXT    NOT NULL,
            lat         REAL    NOT NULL,
            lon         REAL    NOT NULL,
            timezone_offset REAL NOT NULL DEFAULT 5.5,
            gender      TEXT,
            chart_json  TEXT,
            created_at  TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS readings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            chart_id    INTEGER REFERENCES birth_charts(id),
            period      TEXT    NOT NULL,
            rasi        INTEGER,
            guidance    TEXT,
            created_at  TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS bookings (
            id              TEXT    PRIMARY KEY,
            type            TEXT    NOT NULL,
            name            TEXT    NOT NULL,
            customer_name   TEXT,
            price           REAL    NOT NULL,
            persons         INTEGER DEFAULT 1,
            participants    TEXT    NOT NULL,
            contact_email   TEXT    NOT NULL,
            contact_phone   TEXT    NOT NULL,
            status          TEXT    DEFAULT 'pending_payment',
            paid_at         TEXT,
            created_at      TEXT    DEFAULT (datetime('now')),
            razorpay_order_id TEXT,
            razorpay_payment_id TEXT
        );

        CREATE TABLE IF NOT EXISTS payment_refunds (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id          TEXT,
            service_name        TEXT NOT NULL,
            razorpay_order_id   TEXT,
            razorpay_payment_id TEXT NOT NULL,
            amount_paise        INTEGER NOT NULL,
            status              TEXT NOT NULL,
            refund_id           TEXT,
            reason              TEXT,
            error_message       TEXT,
            created_at          TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS payment_orders (
            order_id            TEXT PRIMARY KEY,
            booking_id          TEXT,
            service_name        TEXT NOT NULL,
            service_type        TEXT NOT NULL,
            persons             INTEGER NOT NULL,
            amount_paise        INTEGER NOT NULL,
            currency            TEXT NOT NULL,
            status              TEXT NOT NULL DEFAULT 'created',
            payment_id          TEXT,
            created_at          TEXT DEFAULT (datetime('now')),
            updated_at          TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS payment_webhook_events (
            event_id            TEXT PRIMARY KEY,
            event               TEXT NOT NULL,
            order_id            TEXT,
            payment_id          TEXT,
            received_at         TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_bookings_name_status ON bookings(name, status);
        CREATE INDEX IF NOT EXISTS idx_bookings_rzp_payment ON bookings(razorpay_payment_id);
        CREATE INDEX IF NOT EXISTS idx_payment_orders_booking ON payment_orders(booking_id);
    """)
    conn.commit()

    # Admin tables & migrations
    from setup_admin import init_admin_tables, auto_seed_admin_if_needed
    init_admin_tables(conn)
    auto_seed_admin_if_needed(DATABASE_URL)

    booking_columns = {row[1] for row in c.execute("PRAGMA table_info(bookings)")}
    admin_columns = [
        ("scheduled_date", "TEXT"),
        ("customer_name", "TEXT"),
        ("razorpay_order_id", "TEXT"),
        ("razorpay_payment_id", "TEXT"),
        ("booking_status", "TEXT DEFAULT 'pending'"),
        ("payment_status", "TEXT DEFAULT 'paid'"),
        ("admin_notes", "TEXT"),
        ("rejection_reason", "TEXT"),
        ("accepted_at", "TEXT"),
        ("rejected_at", "TEXT"),
        ("scheduled_time", "TEXT"),
        ("scheduled_at", "TEXT"),
        ("consultation_type", "TEXT"),
        ("refund_id", "TEXT"),
        ("refund_status", "TEXT DEFAULT 'none'"),
        ("refund_amount", "REAL DEFAULT 0.0"),
        ("refund_initiated_at", "TEXT"),
        ("refund_error", "TEXT"),
        ("updated_at", "TEXT"),
    ]
    for column, column_type in admin_columns:
        if column not in booking_columns:
            c.execute(f"ALTER TABLE bookings ADD COLUMN {column} {column_type}")
    c.execute("""
        UPDATE bookings
        SET booking_status = 'pending',
            payment_status = 'paid'
        WHERE booking_status IS NULL OR booking_status = ''
    """)
    conn.commit()
    conn.close()

init_db()

# ─── Pydantic Models ─────────────────────────────────────────
class UserRegister(BaseModel):
    name:     str
    email:    EmailStr
    password: str
    lang:     Optional[str] = "en"

class UserLogin(BaseModel):
    email:    EmailStr
    password: str

class BirthInput(BaseModel):
    dob:              str       # YYYY-MM-DD
    tob:              str       # HH:MM
    city:             str
    lat:              float
    lon:              float
    timezone_offset:  float = 5.5
    gender:           Optional[str] = None
    label:            Optional[str] = None

class HoroscopeRequest(BaseModel):
    rasi:   int       # 1–12
    period: str       # daily | weekly | monthly

class LangUpdate(BaseModel):
    lang: str

class Participant(BaseModel):
    name: str
    gotra: str
    relation: str

class BookingConfirm(BaseModel):
    id: str
    type: str
    name: str
    price: float
    persons: Optional[int] = 1
    participants: List[dict]
    contactEmail: str
    contactPhone: str
    status: Optional[str] = "pending_payment"
    paidAt: Optional[str] = None
    razorpayOrderId: Optional[str] = None
    razorpayPaymentId: Optional[str] = None
    razorpaySignature: Optional[str] = None       # for defence-in-depth re-verification
    expectedAmountPaise: Optional[int] = None     # from order-creation response
    pdfBase64: Optional[str] = None  # PDF receipt for email attachment
    scheduledDate: Optional[str] = None  # YYYY-MM-DD; same for all participants

class RazorpayOrderRequest(BaseModel):
    name: str                              # service name — required for catalogue lookup
    serviceType: Optional[str] = "pooja"   # "pooja" | "homam" | "consultation"
    persons: Optional[int] = 1             # persons (homam only; ignored for poojas and consultations)
    bookingId: Optional[str] = None
    contactEmail: Optional[str] = None
    contactPhone: Optional[str] = None
    participants: List[dict] = Field(default_factory=list)
    scheduledDate: Optional[str] = None
    # Legacy: amount from browser is IGNORED — price is always from the catalogue
    amount: Optional[float] = None

class RazorpayVerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    expected_amount_paise: Optional[int] = None  # echoed back from order-creation response
    booking_id: Optional[str] = None

# ─── Auth Utilities ──────────────────────────────────────────
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_token(data: dict, expires_hours: int = ACCESS_TOKEN_EXPIRE_HOURS) -> str:
    """Simple JWT-like token (use python-jose in production)"""
    import base64, json, hmac
    payload = {**data, "exp": (datetime.now(timezone.utc) + timedelta(hours=expires_hours)).isoformat()}
    header  = base64.b64encode(b'{"alg":"HS256"}').decode()
    body    = base64.b64encode(json.dumps(payload).encode()).decode()
    sig     = hmac.new(SECRET_KEY.encode(), f"{header}.{body}".encode(), "sha256").hexdigest()
    return f"{header}.{body}.{sig}"

def verify_token(token: str) -> Optional[dict]:
    import base64, json, hmac
    try:
        parts = token.split(".")
        if len(parts) != 3: return None
        header, body, sig = parts
        expected = hmac.new(SECRET_KEY.encode(), f"{header}.{body}".encode(), "sha256").hexdigest()
        if sig != expected: return None
        payload = json.loads(base64.b64decode(body + "==").decode())
        exp_dt = datetime.fromisoformat(payload["exp"])
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        if exp_dt < datetime.now(timezone.utc): return None
        return payload
    except Exception:
        return None

def get_current_user(token: str = Depends(oauth2_scheme), db=Depends(get_db)):
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.execute("SELECT * FROM users WHERE id = ?", (payload.get("user_id"),)).fetchone()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return dict(user)

# ─── Vedic Calculation Engine ────────────────────────────────
# Production: Use pyswisseph with real ephemeris data
# This provides the calculation backbone
# pip install pyswisseph

class VedicCalculator:
    """
    Vedic sidereal planetary calculations.
    Production implementation uses pyswisseph.
    """

    LAHIRI_AYANAMSHA = 0   # swe.SIDM_LAHIRI in pyswisseph

    # Rasi data (Vedic, 1–12)
    RASIS = [
        {"num":1,  "en":"Mesha",     "te":"మేష",     "hi":"मेष",    "ta":"மேஷம்",   "symbol":"♈", "lord":"Kuja"},
        {"num":2,  "en":"Vrishabha", "te":"వృషభ",    "hi":"वृषभ",   "ta":"ரிஷபம்",  "symbol":"♉", "lord":"Shukra"},
        {"num":3,  "en":"Mithuna",   "te":"మిథున",   "hi":"मिथुन",  "ta":"மிதுனம்", "symbol":"♊", "lord":"Budha"},
        {"num":4,  "en":"Kataka",    "te":"కటక",     "hi":"कर्क",   "ta":"கடகம்",   "symbol":"♋", "lord":"Chandra"},
        {"num":5,  "en":"Simha",     "te":"సింహ",    "hi":"सिंह",   "ta":"சிம்மம்", "symbol":"♌", "lord":"Surya"},
        {"num":6,  "en":"Kanya",     "te":"కన్య",    "hi":"कन्या",  "ta":"கன்னி",   "symbol":"♍", "lord":"Budha"},
        {"num":7,  "en":"Tula",      "te":"తుల",     "hi":"तुला",   "ta":"துலாம்",  "symbol":"♎", "lord":"Shukra"},
        {"num":8,  "en":"Vrishchika","te":"వృశ్చిక",  "hi":"वृश्चिक","ta":"விருச்சிகம்","symbol":"♏", "lord":"Kuja"},
        {"num":9,  "en":"Dhanu",     "te":"ధనుస్",   "hi":"धनु",    "ta":"தனுசு",   "symbol":"♐", "lord":"Guru"},
        {"num":10, "en":"Makara",    "te":"మకర",     "hi":"मकर",    "ta":"மகரம்",   "symbol":"♑", "lord":"Shani"},
        {"num":11, "en":"Kumbha",    "te":"కుంభ",    "hi":"कुंभ",   "ta":"கும்பம்", "symbol":"♒", "lord":"Shani"},
        {"num":12, "en":"Meena",     "te":"మీన",     "hi":"मीन",    "ta":"மீனம்",   "symbol":"♓", "lord":"Guru"},
    ]

    NAKSHATRAS = [
        'Ashwini','Bharani','Krittika','Rohini','Mrigashira','Ardra',
        'Punarvasu','Pushya','Ashlesha','Magha','Purva Phalguni','Uttara Phalguni',
        'Hasta','Chitra','Swati','Vishakha','Anuradha','Jyeshtha',
        'Mula','Purva Ashadha','Uttara Ashadha','Shravana','Dhanishtha','Shatabhisha',
        'Purva Bhadrapada','Uttara Bhadrapada','Revati'
    ]

    def julian_day(self, year, month, day, hour=12.0):
        if month <= 2:
            year -= 1; month += 12
        A = int(year / 100)
        B = 2 - A + int(A / 4)
        return int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + hour / 24 + B - 1524.5

    def lahiri_ayanamsha(self, jd):
        """Lahiri ayanamsha approximation. pyswisseph gives exact value."""
        return 23.85 + (50.27 / 3600) * (jd - 2415020.0) / 365.25

    def norm360(self, deg):
        return ((deg % 360) + 360) % 360

    def sun_tropical(self, jd):
        T  = (jd - 2451545.0) / 36525
        L0 = 280.46646 + 36000.76983 * T
        M  = (357.52911 + 35999.05029 * T) * math.pi / 180
        C  = (1.914602 - 0.004817 * T) * math.sin(M) + 0.019993 * math.sin(2 * M)
        return self.norm360(L0 + C)

    def moon_tropical(self, jd):
        T  = (jd - 2451545.0) / 36525
        L  = 218.3165 + 481267.8813 * T
        Mp = (134.9634 + 477198.8676 * T) * math.pi / 180
        D  = (297.8502 + 445267.1115 * T) * math.pi / 180
        M  = (357.5291 + 35999.0503  * T) * math.pi / 180
        F  = (93.2720  + 483202.0175 * T) * math.pi / 180
        corr = (6.2888 * math.sin(Mp) + 1.2740 * math.sin(2*D - Mp)
               + 0.6583 * math.sin(2*D) + 0.2136 * math.sin(2*Mp)
               - 0.1851 * math.sin(M)  - 0.1143 * math.sin(2*F))
        return self.norm360(L + corr)

    def planet_tropical(self, jd, planet):
        T = (jd - 2451545.0) / 36525
        configs = {
            'Kuja':   (355.433, 19140.299, 10.691, 0.623),
            'Budha':  (252.251, 149472.675, 11.068, 0.603),
            'Guru':   (34.351,  3034.906,   5.557, 0.168),
            'Shukra': (181.979, 58517.815,  0.779, 0.020),
            'Shani':  (50.078,  1222.114,   6.394, 0.180),
        }
        if planet not in configs: return 0
        L0, rate, c1, c2 = configs[planet]
        L = L0 + rate * T
        M = (L0 + rate * T) * math.pi / 180
        return self.norm360(L + c1 * math.sin(M) + c2 * math.sin(2 * M))

    def rahu_tropical(self, jd):
        T = (jd - 2451545.0) / 36525
        return self.norm360(125.0445 - 1934.1363 * T)

    def lagna(self, jd, lat, lon, ayan):
        T = (jd - 2451545.0) / 36525
        GMST = 280.46061837 + 360.98564736629 * (jd - 2451545) + 0.000387933 * T * T
        LST  = self.norm360(GMST + lon)
        eps  = (23.439291 - 0.013004 * T) * math.pi / 180
        lst_rad = LST * math.pi / 180
        lat_rad = lat * math.pi / 180
        asc_trop = math.atan2(
            math.cos(lst_rad),
            -(math.sin(lst_rad) * math.cos(eps) + math.tan(lat_rad) * math.sin(eps))
        ) * 180 / math.pi
        return self.norm360(asc_trop - ayan)

    def get_rasi(self, deg):
        rasi = int(deg / 30) + 1
        return (rasi - 1) % 12 + 1, round(deg % 30, 4)

    def get_nakshatra(self, deg):
        idx  = int(deg / (360 / 27))
        pada = int((deg % (360 / 27)) / (360 / 108)) + 1
        return self.NAKSHATRAS[idx % 27], pada

    def calculate(self, year, month, day, tob_str, lat, lon, tz_offset=5.5):
        """
        Main calculation entry point.
        
        For production accuracy, replace with:
            import swisseph as swe
            swe.set_sid_mode(swe.SIDM_LAHIRI)
            jd = swe.julday(year, month, day, hour_ut)
            flags = swe.FLG_SIDEREAL | swe.FLG_SPEED
            lon, lat_ecl, dist, lon_s, lat_s, dist_s = swe.calc_ut(jd, swe.SUN, flags)[0]
        """
        h, m = map(int, tob_str.split(':'))
        hour_local = h + m / 60
        hour_ut    = hour_local - tz_offset

        jd   = self.julian_day(year, month, day, hour_ut)
        ayan = self.lahiri_ayanamsha(jd)

        raw = {
            'Surya':   self.norm360(self.sun_tropical(jd)        - ayan),
            'Chandra': self.norm360(self.moon_tropical(jd)       - ayan),
            'Kuja':    self.norm360(self.planet_tropical(jd,'Kuja')   - ayan),
            'Budha':   self.norm360(self.planet_tropical(jd,'Budha')  - ayan),
            'Guru':    self.norm360(self.planet_tropical(jd,'Guru')   - ayan),
            'Shukra':  self.norm360(self.planet_tropical(jd,'Shukra') - ayan),
            'Shani':   self.norm360(self.planet_tropical(jd,'Shani')  - ayan),
            'Rahu':    self.norm360(self.rahu_tropical(jd)       - ayan),
            'Ketu':    self.norm360(self.rahu_tropical(jd) + 180 - ayan),
            'Lagna':   self.lagna(jd, lat, lon, ayan),
        }

        planets = {}
        for name, deg in raw.items():
            rasi_num, rasi_deg = self.get_rasi(deg)
            nakshatra, pada    = self.get_nakshatra(deg)
            rasi_data          = self.RASIS[rasi_num - 1]
            planets[name] = {
                "degree":    round(deg, 4),
                "rasi":      rasi_num,
                "rasi_deg":  rasi_deg,
                "rasi_name": rasi_data["en"],
                "nakshatra": nakshatra,
                "pada":      pada,
                "lord":      rasi_data["lord"],
            }

        return {
            "planets":    planets,
            "lagna_rasi": planets["Lagna"]["rasi"],
            "moon_rasi":  planets["Chandra"]["rasi"],
            "ayanamsha":  round(ayan, 4),
            "jd":         round(jd, 4),
            "system":     "Lahiri Sidereal (Vedic)",
        }

calc = VedicCalculator()

# ─── API & SPA Routes ────────────────────────────────────────

SPA_PATHS = [
    "/",
    "/home",
    "/horoscope",
    "/horoscopes",
    "/kundli",
    "/kundali",
    "/dashboard",
    "/pooja",
    "/poojas",
    "/homams",
    "/consult",
    "/consultation",
    "/consult-astrologer",
    "/booking",
    "/booking-form",
    "/payment",
    "/confirmation",
]

for _path in SPA_PATHS:
    app.add_api_route(_path, _site_index, methods=["GET"], include_in_schema=False)
    if _path != "/":
        app.add_api_route(f"{_path}/", _site_index, methods=["GET"], include_in_schema=False)

@app.get("/api/health")
async def health():
    email_configured = bool(
        os.getenv("RESEND_API_KEY", "").strip() or
        os.getenv("SMTP_PASS", "").strip()
    )
    razorpay_configured = bool(
        os.getenv("RAZORPAY_KEY_ID", "").strip() and
        os.getenv("RAZORPAY_KEY_SECRET", "").strip()
    )
    return {
        "status": "healthy",
        "system": "Lahiri Sidereal Vedic",
        "version": "1.0.0",
        "email_configured": email_configured,
        "razorpay_configured": razorpay_configured,
    }

# ── Auth ──────────────────────────────────────────────────────

@app.post("/api/auth/register")
async def register(data: UserRegister, db=Depends(get_db)):
    existing = db.execute("SELECT id FROM users WHERE email = ?", (data.email,)).fetchone()
    if existing:
        raise HTTPException(400, "Email already registered")

    db.execute(
        "INSERT INTO users (name, email, password, lang) VALUES (?, ?, ?, ?)",
        (data.name, data.email, hash_password(data.password), data.lang)
    )
    db.commit()

    user = db.execute("SELECT id, name, email, lang, created_at FROM users WHERE email = ?", (data.email,)).fetchone()
    token = create_token({"user_id": user["id"], "email": user["email"]})
    return {"token": token, "user": dict(user)}

@app.post("/api/auth/login")
async def login(data: UserLogin, db=Depends(get_db)):
    user = db.execute(
        "SELECT * FROM users WHERE email = ? AND password = ?",
        (data.email, hash_password(data.password))
    ).fetchone()
    if not user:
        raise HTTPException(401, "Invalid email or password")

    token = create_token({"user_id": user["id"], "email": user["email"]})
    return {"token": token, "user": {"id":user["id"],"name":user["name"],"email":user["email"],"lang":user["lang"]}}

@app.get("/api/auth/me")
async def me(user=Depends(get_current_user)):
    return user

# ── Kundli / Birth Chart ──────────────────────────────────────

@app.post("/api/kundli/calculate")
async def calculate_kundli(data: BirthInput, user=Depends(get_current_user), db=Depends(get_db)):
    """
    Calculate Vedic birth chart using Lahiri ayanamsha.
    Returns South Indian Rasi chart data and life guidance.
    Does NOT expose doshas, yogas, or technical jargon to client.
    """
    try:
        year, month, day = map(int, data.dob.split('-'))
        chart = calc.calculate(year, month, day, data.tob, data.lat, data.lon, data.timezone_offset)
    except Exception as e:
        raise HTTPException(500, f"Calculation error: {str(e)}")

    import json
    db.execute(
        "INSERT INTO birth_charts (user_id, label, dob, tob, city, lat, lon, timezone_offset, gender, chart_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (user["id"], data.label or f"{data.city} — {data.dob}", data.dob, data.tob,
         data.city, data.lat, data.lon, data.timezone_offset, data.gender, json.dumps(chart))
    )
    db.commit()

    return {"chart": chart, "message": "Chart calculated successfully"}

@app.get("/api/kundli/charts")
async def get_charts(user=Depends(get_current_user), db=Depends(get_db)):
    charts = db.execute(
        "SELECT id, label, dob, tob, city, created_at FROM birth_charts WHERE user_id = ? ORDER BY created_at DESC",
        (user["id"],)
    ).fetchall()
    return {"charts": [dict(c) for c in charts]}

# ── Horoscope ────────────────────────────────────────────────

@app.post("/api/horoscope")
async def get_horoscope(data: HoroscopeRequest):
    """
    Returns life guidance for given rasi and period.
    Based on Moon rasi, nakshatra & gochar.
    Output: life guidance only — career, family, finance, peace, spirituality.
    """
    if not (1 <= data.rasi <= 12):
        raise HTTPException(400, "Rasi must be between 1 and 12")
    if data.period not in ["daily", "weekly", "monthly"]:
        raise HTTPException(400, "Period must be daily, weekly, or monthly")

    # In production: incorporate real-time gochar (transit) positions
    # For MVP: guidance is rasi-based with date variations
    guidance = _generate_guidance(data.rasi, data.period)
    return guidance

def _generate_guidance(rasi: int, period: str) -> dict:
    """
    Pure life guidance — no technical astrological jargon.
    Based on rasi characteristics and seasonal patterns.
    """
    from datetime import date
    today = date.today()

    rasi_guidance = {
        1:  {"career":"Your leadership instincts are sharp. Bold, decisive action in professional matters will open new doors this period.", "family":"Patience and warmth toward loved ones creates harmony at home.", "finance":"Calculated risks now can yield strong returns. Avoid impulsive spending.", "peace":"Morning practice — even five minutes of stillness — anchors your energy.", "spirituality":"Brave, dharmic action is your highest worship. Let your courage serve others."},
        2:  {"career":"Steady, methodical effort brings lasting recognition. Your eye for quality sets you apart.", "family":"Your reliability is deeply loved. Make space for spontaneous joy in relationships.", "finance":"Long-term investments and savings compound quietly in your favor.", "peace":"Beauty in daily life — food, nature, music — is sacred nourishment.", "spirituality":"Gratitude for physical blessings deepens your connection to the divine."},
        3:  {"career":"Communication skills are your asset. Speak, write, and share your ideas with confidence.", "family":"Stay present emotionally, not just mentally. Deep listening strengthens bonds.", "finance":"Multiple income paths are possible. Focus your energy on the most promising.", "peace":"Movement and creative expression channel your brilliant restless mind.", "spirituality":"Sacred texts and learning open spiritual doorways for you this period."},
        4:  {"career":"Roles that involve care, building, and community align with your deeper purpose now.", "family":"Home life calls for your loving attention. Small rituals of togetherness matter greatly.", "finance":"Steady savings and real assets build the security your heart needs.", "peace":"Time near water, and in familiar, comforting spaces restores your spirit.", "spirituality":"Family worship and ancestral reverence deepen your sacred connection."},
        5:  {"career":"Creative leadership brings you to the fore. Your warmth attracts collaboration and success.", "family":"Be the generous, playful heart of your circle. Let others reciprocate.", "finance":"Confidence attracts abundance. Generosity with wisdom multiplies prosperity.", "peace":"Creative expression — art, music, play — is spiritual practice for you.", "spirituality":"Pure-hearted devotion and heartfelt bhakti are your natural path."},
        6:  {"career":"Precision, service, and mastery of craft bring you recognition and deep satisfaction.", "family":"Your helpfulness is boundless. Remember your own needs are equally sacred.", "finance":"Methodical budgeting and practical financial habits build lasting security.", "peace":"Daily routines of health and cleanliness create profound inner order.", "spirituality":"Selfless service — seva — is your deepest prayer and highest act."},
        7:  {"career":"Partnership ventures and harmonious collaborations bring professional success this period.", "family":"Fairness and mutual respect deepen your relationships. Express appreciation often.", "finance":"Balanced financial decisions and collaborative ventures prove fruitful.", "peace":"Harmony in surroundings and the company of uplifting people restore you.", "spirituality":"Seeing the divine in others — your partner, friend, stranger — is your sadhana."},
        8:  {"career":"Deep research, strategic thinking, and willingness to transform situations bring success.", "family":"Honest, vulnerable conversations deepen intimacy and trust profoundly.", "finance":"Patient, long-term financial strategy yields the substantial results you seek.", "peace":"Meditation and honest self-examination create your genuine, lasting peace.", "spirituality":"Transformation and inner depth are your spiritual calling this period."},
        9:  {"career":"Teaching, advising, and expansive thinking open new professional horizons.", "family":"Your wisdom and optimism inspire loved ones. Allow them to guide you too.", "finance":"Ethical financial conduct and patience with growth brings fortunate results.", "peace":"Time in nature, near large trees or sacred places, profoundly restores you.", "spirituality":"Study, pilgrimage, and guru-devotion are your most powerful practices now."},
        10: {"career":"Disciplined effort and structured ambition bring the recognition and authority you deserve.", "family":"Lead your family through example. Show vulnerability — it deepens love.", "finance":"Conservative, goal-aligned financial planning builds lasting stability.", "peace":"Accomplishment through honest, disciplined effort creates deep satisfaction.", "spirituality":"Karma yoga — action without attachment to outcomes — is your path now."},
        11: {"career":"Innovation and community-focused vision bring breakthrough professional opportunities.", "family":"Balance your love of freedom with genuine emotional presence for those you love.", "finance":"Group endeavors and forward-thinking investments can bring unexpected abundance.", "peace":"Contributing to collective upliftment brings your deepest personal fulfillment.", "spirituality":"Service to humanity and meditation on universal consciousness expand your soul."},
        12: {"career":"Healing, creative retreat, and compassionate service carry your highest purpose.", "family":"Your sensitivity is a profound spiritual gift. Honor it with loving boundaries.", "finance":"Clarity and structure in financial matters protects your generous nature.", "peace":"Solitude, meditation, and time near water deeply restore your being.", "spirituality":"Surrender, devotion, and silence are your most transformative practices now."},
    }

    g = rasi_guidance.get(rasi, rasi_guidance[1])
    rasi_data = VedicCalculator.RASIS[rasi - 1]

    period_label = {"daily":"Today","weekly":"This week","monthly":"This month"}[period]

    return {
        "rasi":         rasi,
        "rasi_name":    rasi_data["en"],
        "rasi_symbol":  rasi_data["symbol"],
        "period":       period,
        "period_label": period_label,
        "guidance": {
            "career":       g["career"],
            "family":       g["family"],
            "finance":      g["finance"],
            "peace":        g["peace"],
            "spirituality": g["spirituality"],
        }
    }

# ── Booking Confirmation & Email ─────────────────────────────────

ADMIN_EMAIL = "taraastrovision123@gmail.com"
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", ADMIN_EMAIL).strip()
SMTP_PASS = os.getenv("SMTP_PASS", "").strip()

def send_email(to: str, subject: str, body: str, attachment: Optional[tuple] = None) -> bool:
    """
    Send email via Resend or SMTP.
    attachment: (filename, base64_content[, content_type])
    """
    # Resend (supports attachments)
    if RESEND_API_KEY:
        try:
            import resend
            import base64
            resend.api_key = RESEND_API_KEY
            params = {
                "from": "Tara Astro Vision <onboarding@resend.dev>",
                "to": [to],
                "subject": subject,
                "text": body,
            }
            if attachment:
                filename, b64_content, *metadata = attachment
                params["attachments"] = [{
                    "content": b64_content,
                    "filename": filename,
                    "content_type": metadata[0] if metadata else "application/pdf",
                }]
            resend.Emails.send(params)
            log.info(f"Email sent via Resend to {to}: {subject}")
            return True
        except Exception as e:
            log.error(f"Resend failed: {e}", exc_info=True)
            return False

    # SMTP (Gmail, etc.) with optional PDF attachment
    if SMTP_USER and SMTP_PASS:
        try:
            import smtplib
            import base64
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            from email.mime.base import MIMEBase
            from email import encoders

            msg = MIMEMultipart()
            msg["Subject"] = subject
            msg["From"] = f"Tara Astro Vision <{SMTP_USER}>"
            msg["To"] = to
            msg.attach(MIMEText(body, "plain"))

            if attachment:
                filename, b64_content, *metadata = attachment
                content_type = metadata[0] if metadata else "application/pdf"
                maintype, subtype = content_type.split("/", 1)
                part = MIMEBase(maintype, subtype)
                part.set_payload(base64.b64decode(b64_content))
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename={filename}")
                msg.attach(part)

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(SMTP_USER, to, msg.as_string())
            log.info(f"Email sent via SMTP to {to}: {subject}")
            return True
        except Exception as e:
            log.error(f"SMTP failed: {e}", exc_info=True)
            return False

    log.warning("Email not configured. Set RESEND_API_KEY or SMTP_PASS in .env")
    return False

# ── Razorpay REST Integration ───────────────────────────────────
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

def _rzp_client() -> RazorpayClient:
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        raise HTTPException(500, "Razorpay not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in .env")
    return RazorpayClient(
        key_id=RAZORPAY_KEY_ID,
        key_secret=RAZORPAY_KEY_SECRET,
        webhook_secret=RAZORPAY_WEBHOOK_SECRET or os.getenv("RAZORPAY_WEBHOOK_SECRET", ""),
    )


def _verify_razorpay_payment(
    client: RazorpayClient,
    order_id: str,
    payment_id: str,
    signature: str,
    expected_amount_paise: Optional[int] = None,
) -> tuple[dict, dict]:
    """Verify the checkout signature and authoritative captured order/payment details."""
    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        })
    except Exception as e:
        log.warning("Payment signature verification failed for order=%s", order_id)
        raise HTTPException(400, "Payment verification failed — invalid signature") from e

    try:
        rzp_order = client.order.fetch(order_id)
        rzp_payment = client.payment.fetch(payment_id)
    except Exception as e:
        log.error("Could not retrieve Razorpay payment details for order=%s: %s", order_id, e)
        raise HTTPException(502, "Could not verify payment details with Razorpay") from e

    if rzp_order.get("id") != order_id:
        raise HTTPException(400, "Payment does not match the expected order")
    if rzp_order.get("currency") != "INR" or rzp_payment.get("currency", "INR") != "INR":
        raise HTTPException(400, "Invalid currency in payment")
    try:
        order_amount = int(rzp_order.get("amount", 0))
        payment_amount = int(rzp_payment.get("amount", 0))
    except (TypeError, ValueError) as e:
        raise HTTPException(400, "Invalid amount in payment details") from e
    if order_amount <= 0 or payment_amount != order_amount:
        raise HTTPException(400, "Payment amount does not match the Razorpay order")
    if expected_amount_paise is not None and order_amount != expected_amount_paise:
        raise HTTPException(400, "Payment amount does not match the expected booking amount")
    if rzp_payment.get("id") not in (None, payment_id):
        raise HTTPException(400, "Razorpay returned a different payment")
    if rzp_payment.get("order_id") != order_id:
        raise HTTPException(400, "Payment does not match the expected order")
    if rzp_payment.get("status") != "captured":
        raise HTTPException(400, "Payment has not been captured")
    return rzp_order, rzp_payment


def handle_overbooked_refund(
    db,
    booking_id: str,
    service_name: str,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    amount_paise: int,
    reason: str = "Booking capacity exceeded (50/50 limit reached)",
) -> dict:
    """
    Safely initiates refund via Razorpay for an overbooked customer,
    logs the event to payment_refunds table, and notifies admin.
    """
    refund_id = None
    status = "manual_refund_required"
    error_msg = None

    try:
        client = _rzp_client()
        refund = client.payment.refund(razorpay_payment_id, {
            "amount": amount_paise,
            "notes": {
                "reason": reason,
                "booking_id": booking_id,
                "service": service_name,
            }
        })
        refund_id = refund.get("id") if isinstance(refund, dict) else str(refund)
        status = "refund_initiated"
        log.info(f"Automatic refund initiated: {refund_id} for payment={razorpay_payment_id} booking={booking_id}")
    except Exception as e:
        error_msg = str(e)
        log.error(f"Automatic refund failed for payment={razorpay_payment_id}: {e}. Flagging for manual refund.")

    try:
        db.execute(
            """INSERT INTO payment_refunds (
                booking_id, service_name, razorpay_order_id, razorpay_payment_id,
                amount_paise, status, refund_id, reason, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (booking_id, service_name, razorpay_order_id, razorpay_payment_id,
             amount_paise, status, refund_id, reason, error_msg)
        )
        db.commit()
    except Exception as db_err:
        log.error(f"Failed to record refund in database: {db_err}")

    admin_subject = f"[ACTION REQUIRED] Overbooking Refund for {service_name} ({booking_id})"
    admin_body = f"""Overbooking alert:
A customer payment was received after the capacity limit was reached:
Service: {service_name}
Booking ID: {booking_id}
Order ID: {razorpay_order_id}
Payment ID: {razorpay_payment_id}
Amount: ₹{amount_paise / 100:.2f}
Refund Status: {status}
Refund ID: {refund_id or 'None'}
Error: {error_msg or 'None'}

Please verify this in the Razorpay dashboard immediately.
"""
    try:
        send_email(ADMIN_EMAIL, admin_subject, admin_body)
    except Exception as mail_err:
        log.error(f"Failed to send admin refund alert: {mail_err}")

    return {
        "status": status,
        "refund_id": refund_id,
        "error_message": error_msg,
    }

# ── Admin Portal APIs ─────────────────────────────────────────
from admin_api import setup_admin_routes
setup_admin_routes(
    app=app,
    get_db=get_db,
    oauth2_scheme=oauth2_scheme,
    verify_token=verify_token,
    create_token=create_token,
    _rzp_client=_rzp_client,
    send_email=send_email,
    get_all_services_availability=get_all_services_availability,
)

@app.get("/api/services")
async def list_services(db=Depends(get_db)):
    """Authoritative service catalogue — names, types, and server-calculated prices."""
    return {"services": all_services(db)}

@app.get("/api/services/availability")
async def get_services_availability(db=Depends(get_db)):
    """Live slot availability for all poojas and homams (limit 50 per individual service)."""
    return {
        "max_limit": SERVICE_BOOKING_LIMIT,
        "availability": get_all_services_availability(db),
    }

@app.post("/api/payment/order")
async def create_payment_order(data: RazorpayOrderRequest, db=Depends(get_db)):
    """
    Step 1: Create a Razorpay order.
    Price is ALWAYS calculated server-side from the service catalogue.
    Browser-supplied amounts are completely ignored.
    Enforces the strict 50-booking limit per service.
    """
    if not data.name or not data.name.strip():
        raise HTTPException(400, "Service name is required")

    service_type = (data.serviceType or "pooja").strip().lower()
    persons = max(1, int(data.persons or 1))

    try:
        svc, authoritative_total = validate_and_price(data.name, service_type, persons, db=db)
    except ValueError as e:
        raise HTTPException(400, str(e))

    confirmed_count = get_confirmed_booking_count(db, svc.name)
    if confirmed_count >= SERVICE_BOOKING_LIMIT:
        raise HTTPException(
            400,
            f"Bookings Closed — Maximum Capacity Reached ({SERVICE_BOOKING_LIMIT}/{SERVICE_BOOKING_LIMIT}) for '{svc.name}'."
        )

    amount_paise = int(round(authoritative_total * 100))
    MAX_PAISE = int(os.getenv("MAX_ORDER_PAISE", "100000000"))
    if amount_paise > MAX_PAISE:
        raise HTTPException(400, "Amount exceeds maximum allowed")

    client = _rzp_client()
    if data.bookingId:
        existing_booking = db.execute(
            "SELECT name, type, status FROM bookings WHERE id = ?",
            (data.bookingId,),
        ).fetchone()
        if existing_booking:
            if existing_booking["status"] in ("paid", "confirmed"):
                raise HTTPException(409, "This booking has already been paid")
            if (
                canonical_service_name(existing_booking["name"]) != canonical_service_name(svc.name)
                or existing_booking["type"] != svc.type
            ):
                raise HTTPException(409, "Booking ID is already associated with a different service")

    receipt = (data.bookingId or f"tav_{int(datetime.now(timezone.utc).timestamp())}")[:40]
    notes = {
        "booking_id": data.bookingId or "",
        "service": svc.name,
        "persons": str(persons),
        "server_amount_paise": str(amount_paise),
    }
    if data.contactEmail:
        notes["email"] = data.contactEmail
    try:
        order = client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt,
            "notes": notes,
        })
    except Exception as e:
        log.error(f"Razorpay order.create failed: {e}")
        raise HTTPException(502, "Could not create payment order. Please try again.")
    if (
        order.get("currency") != "INR"
        or int(order.get("amount", 0)) != amount_paise
        or not order.get("id")
    ):
        log.error("Razorpay returned an unexpected order response for booking=%s", data.bookingId)
        raise HTTPException(502, "Razorpay returned invalid order details")

    try:
        db.execute(
            """INSERT INTO payment_orders (
                   order_id, booking_id, service_name, service_type, persons,
                   amount_paise, currency, status
               ) VALUES (?, ?, ?, ?, ?, ?, 'INR', 'created')""",
            (order["id"], data.bookingId, svc.name, svc.type, persons, amount_paise),
        )
        if data.bookingId:
            participants_json = __import__("json").dumps(data.participants)
            existing = db.execute(
                "SELECT id FROM bookings WHERE id = ?", (data.bookingId,)
            ).fetchone()
            if existing:
                db.execute(
                    """UPDATE bookings SET
                           name=?, type=?, price=?, persons=?, participants=?,
                           contact_email=?, contact_phone=?, status='pending_payment',
                           paid_at=NULL, scheduled_date=?, razorpay_order_id=?,
                           razorpay_payment_id=NULL, booking_status='pending',
                           payment_status='pending', updated_at=datetime('now')
                       WHERE id=?""",
                    (
                        svc.name, svc.type, authoritative_total, persons, participants_json,
                        data.contactEmail or "", data.contactPhone or "", data.scheduledDate,
                        order["id"], data.bookingId,
                    ),
                )
            else:
                db.execute(
                    """INSERT INTO bookings (
                           id, type, name, customer_name, price, persons, participants,
                           contact_email, contact_phone, status, scheduled_date,
                           razorpay_order_id, booking_status, payment_status
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_payment', ?, ?, 'pending', 'pending')""",
                    (
                        data.bookingId, svc.type, svc.name,
                        (data.participants[0].get("name") if data.participants else ""),
                        authoritative_total, persons, participants_json,
                        data.contactEmail or "", data.contactPhone or "",
                        data.scheduledDate, order["id"],
                    ),
                )
        db.commit()
    except Exception as e:
        db.rollback()
        log.error("Could not persist payment order %s: %s", order["id"], e)
        raise HTTPException(500, "Could not save payment order details") from e

    log.info(
        f"Order created: {order['id']} service={svc.name!r} "
        f"persons={persons} amount={amount_paise}p booking={data.bookingId}"
    )
    return {
        "key_id": RAZORPAY_KEY_ID,
        "order_id": order["id"],
        "amount": order["amount"],       # paise confirmed by Razorpay
        "currency": order["currency"],
        "service_name": svc.name,
        "service_type": svc.type,
        "persons": persons,
        "unit_price": svc.price,
    }

@app.post("/api/payment/verify")
async def verify_payment(data: RazorpayVerifyRequest, db=Depends(get_db)):
    """
    Step 2: Verify HMAC-SHA256 signature AND fetch the order from Razorpay
    to cross-check amount, currency, and captured payment status.
    Rejects: bad signature, wrong currency, wrong amount, non-captured status.
    """
    if not data.razorpay_order_id or not data.razorpay_payment_id or not data.razorpay_signature:
        raise HTTPException(400, "Missing required payment verification fields")

    client = _rzp_client()

    rzp_order, rzp_payment = _verify_razorpay_payment(
        client,
        data.razorpay_order_id,
        data.razorpay_payment_id,
        data.razorpay_signature,
        data.expected_amount_paise,
    )
    order_record = db.execute(
        "SELECT booking_id, amount_paise FROM payment_orders WHERE order_id = ?",
        (data.razorpay_order_id,),
    ).fetchone()
    if not order_record:
        raise HTTPException(400, "Payment order was not created by this server")
    if data.booking_id and order_record["booking_id"] != data.booking_id:
        raise HTTPException(400, "Payment order does not match this booking")
    if int(order_record["amount_paise"]) != int(rzp_order["amount"]):
        raise HTTPException(400, "Payment amount does not match the saved order")
    db.execute(
        """UPDATE payment_orders SET status='captured', payment_id=?, updated_at=datetime('now')
           WHERE order_id=? AND status != 'captured'""",
        (data.razorpay_payment_id, data.razorpay_order_id),
    )
    db.commit()

    log.info(
        f"Payment verified order={data.razorpay_order_id} "
        f"payment={data.razorpay_payment_id} amount={rzp_order.get('amount')}p"
    )
    return {
        "verified": True,
        "razorpay_order_id": data.razorpay_order_id,
        "razorpay_payment_id": data.razorpay_payment_id,
        "amount_paise": rzp_order.get("amount"),
        "currency": rzp_order.get("currency"),
    }


@app.post("/api/booking/confirm")
async def confirm_booking(data: BookingConfirm, db=Depends(get_db)):
    """
    Step 3: Save booking linked to a verified Razorpay payment.
    - Re-verifies the payment signature server-side.
    - Validates the service name against the catalogue and calculates
      the authoritative price (ignores any price sent by the browser).
    - Idempotent: safely handles retries and page refreshes.
    """
    import json
    log.info(f"Booking confirm received: id={data.id} service={data.name!r}")

    # ── Guard 1: payment IDs must be present ────────────────────────────────
    if not data.razorpayPaymentId or not data.razorpayOrderId or not data.razorpaySignature:
        raise HTTPException(400, "A verified Razorpay payment is required to confirm a booking")

    # ── Guard 2: validate persisted order ownership and authoritative amount ─
    order_record = db.execute(
        """SELECT booking_id, service_name, service_type, persons, amount_paise, status
           FROM payment_orders WHERE order_id = ?""",
        (data.razorpayOrderId,),
    ).fetchone()
    if not order_record or order_record["booking_id"] != data.id:
        raise HTTPException(400, "Payment order is not associated with this booking")

    # ── Guard 3: validate service and calculate authoritative price ──────────
    service_type = (data.type or "pooja").strip().lower()
    persons = max(1, int(data.persons or 1))
    try:
        svc, authoritative_price = validate_and_price(data.name, service_type, persons)
    except ValueError as e:
        raise HTTPException(400, f"Invalid service: {e}")
    expected_amount_paise = int(round(authoritative_price * 100))
    if (
        canonical_service_name(order_record["service_name"]) != canonical_service_name(svc.name)
        or order_record["service_type"] != svc.type
        or int(order_record["persons"]) != persons
        or int(order_record["amount_paise"]) != expected_amount_paise
    ):
        raise HTTPException(400, "Payment order does not match this booking's service or amount")

    client = _rzp_client()
    rzp_order, _ = _verify_razorpay_payment(
        client,
        data.razorpayOrderId,
        data.razorpayPaymentId,
        data.razorpaySignature,
        expected_amount_paise,
    )
    if int(rzp_order["amount"]) != int(order_record["amount_paise"]):
        raise HTTPException(400, "Payment amount does not match the saved order")

    # ── Guard 4: participants required ──────────────────────────────────────
    if not data.participants:
        raise HTTPException(400, "At least one participant is required")

    # ── Concurrency-safe capacity check and DB save ─────────────────────────
    with booking_lock:
        # Idempotent check 1: by booking ID
        try:
            existing = db.execute(
                """SELECT id, status, razorpay_order_id, razorpay_payment_id
                   FROM bookings WHERE id = ?""",
                (data.id,),
            ).fetchone()
        except Exception as e:
            log.error(f"DB lookup failed: {e}")
            raise HTTPException(500, "Database error")

        if existing and existing["status"] in ("paid", "confirmed"):
            if (
                existing["razorpay_order_id"] == data.razorpayOrderId
                and existing["razorpay_payment_id"] == data.razorpayPaymentId
            ):
                log.info("Booking %s already confirmed — idempotent retry", data.id)
                return {
                    "message": "Booking already confirmed",
                    "id": data.id,
                    "emails_sent": {"admin": False, "user": False},
                }
            refund_res = handle_overbooked_refund(
                db=db,
                booking_id=data.id,
                service_name=svc.name,
                razorpay_order_id=data.razorpayOrderId,
                razorpay_payment_id=data.razorpayPaymentId,
                amount_paise=expected_amount_paise,
                reason="A second captured payment was received for an already-paid booking",
            )
            ref_id = refund_res.get("refund_id") or "manual-review"
            raise HTTPException(
                409,
                f"This booking was already paid. The additional payment is being refunded "
                f"(Reference: {ref_id}).",
            )

        # Idempotent check 2: by razorpay_payment_id (prevent duplicate booking for same payment in production)
        if data.razorpayPaymentId:
            try:
                existing_pay = db.execute(
                    "SELECT id, status FROM bookings WHERE razorpay_payment_id = ? AND id != ?",
                    (data.razorpayPaymentId, data.id)
                ).fetchone()
                if existing_pay:
                    log.info(
                        f"Payment {data.razorpayPaymentId} already used for booking {existing_pay['id']} — idempotent"
                    )
                    return {
                        "message": "Booking already confirmed for this payment",
                        "id": existing_pay["id"],
                        "emails_sent": {"admin": False, "user": False},
                    }
            except Exception as e:
                log.error(f"DB payment lookup failed: {e}")
                raise HTTPException(500, "Database error")

        # Capacity check right before recording booking
        confirmed_count = get_confirmed_booking_count(db, svc.name)
        if confirmed_count >= SERVICE_BOOKING_LIMIT:
            log.warning(
                f"Booking capacity reached for '{svc.name}' ({confirmed_count}/{SERVICE_BOOKING_LIMIT})! "
                f"Initiating refund for payment={data.razorpayPaymentId} booking={data.id}"
            )
            amount_paise = int(round(authoritative_price * 100))
            refund_res = handle_overbooked_refund(
                db=db,
                booking_id=data.id,
                service_name=svc.name,
                razorpay_order_id=data.razorpayOrderId or "",
                razorpay_payment_id=data.razorpayPaymentId,
                amount_paise=amount_paise,
                reason=f"Capacity limit reached ({SERVICE_BOOKING_LIMIT}/{SERVICE_BOOKING_LIMIT})",
            )
            ref_id = refund_res.get("refund_id") or "manual-review"
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Bookings Closed — Maximum Capacity Reached ({SERVICE_BOOKING_LIMIT}/{SERVICE_BOOKING_LIMIT}) "
                    f"for '{svc.name}'. Your payment has been received and a refund "
                    f"({refund_res.get('status')}) has been initiated (Reference: {ref_id}). "
                    f"Customer support has been notified."
                ),
            )

        try:
            if existing:
                db.execute(
                    """UPDATE bookings SET
                           type=?, name=?, customer_name=?, price=?, persons=?, participants=?,
                           contact_email=?, contact_phone=?, status='paid', paid_at=?,
                           scheduled_date=?, razorpay_order_id=?, razorpay_payment_id=?,
                           booking_status='pending', payment_status='paid', updated_at=datetime('now')
                       WHERE id=?""",
                    (
                        svc.type, svc.name,
                        data.participants[0].get("name") if data.participants else None,
                        authoritative_price, persons, json.dumps(data.participants),
                        data.contactEmail, data.contactPhone, data.paidAt, data.scheduledDate,
                        data.razorpayOrderId, data.razorpayPaymentId, data.id,
                    ),
                )
            else:
                db.execute(
                    """INSERT INTO bookings (
                             id, type, name, customer_name, price, persons, participants,
                             contact_email, contact_phone, status, paid_at, scheduled_date,
                             razorpay_order_id, razorpay_payment_id, booking_status, payment_status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'paid', ?, ?, ?, ?, 'pending', 'paid')""",
                    (
                        data.id, svc.type, svc.name,
                        data.participants[0].get("name") if data.participants else None,
                        authoritative_price, persons, json.dumps(data.participants),
                        data.contactEmail, data.contactPhone, data.paidAt,
                        data.scheduledDate, data.razorpayOrderId, data.razorpayPaymentId,
                    ),
                )
            db.execute(
                """UPDATE payment_orders SET status='captured', payment_id=?, updated_at=datetime('now')
                   WHERE order_id=?""",
                (data.razorpayPaymentId, data.razorpayOrderId),
            )
            db.commit()

        except Exception as e:
            log.error(f"DB insert failed: {e}")
            raise HTTPException(500, "Failed to save booking")

    # Admin email - full booking details
    parts_text = "\n".join(
        f"  {i+1}. {p.get('name','')} — Gotra: {p.get('gotra','')}, Relation: {p.get('relation','')}"
        for i, p in enumerate(data.participants)
    )
    sched_str = data.scheduledDate or "—"
    admin_body = f"""New Booking: {data.name}
Booking ID: {data.id}
Type: {data.type}
Scheduled Pooja/Homam Date: {sched_str}
Amount: ₹{data.price:,.0f}
Date: {data.paidAt or 'N/A'}
Payment Status: Paid

Participants:
{parts_text}

Contact: {data.contactEmail} | {data.contactPhone}
"""
    admin_sent = send_email(ADMIN_EMAIL, f"Tara Astro Vision — New Booking {data.id}", admin_body)

    # User confirmation email - with PDF attachment
    date_str = data.paidAt[:19] if data.paidAt else "N/A"
    user_body = f"""Dear Customer,

Thank you for your booking with Tara Astro Vision.

Booking ID: {data.id}
Pooja/Homam: {data.name}
Scheduled date: {data.scheduledDate or "—"}
Amount Paid: ₹{data.price:,.0f}
Date: {date_str}

Your PDF receipt is attached to this email.

Contact us: {ADMIN_EMAIL} | 9014308190

With divine blessings,
Tara Astro Vision
"""
    pdf_attachment = None
    if data.pdfBase64:
        pdf_attachment = (f"Tara-Astro-Vision-Receipt-{data.id}.pdf", data.pdfBase64)
    user_sent = send_email(
        data.contactEmail,
        f"Tara Astro Vision — Booking Confirmed {data.id}",
        user_body,
        attachment=pdf_attachment
    )

    if not admin_sent or not user_sent:
        log.warning(f"Emails sent: admin={admin_sent}, user={user_sent}")

    return {
        "message": "Booking confirmed",
        "id": data.id,
        "emails_sent": {"admin": admin_sent, "user": user_sent}
    }


# ── Razorpay Webhook ─────────────────────────────────────────────────────────

@app.post("/api/payment/webhook")
async def razorpay_webhook(request: Request, db=Depends(get_db)):
    """
    Razorpay webhook for payment reconciliation.
    Verifies X-Razorpay-Signature using HMAC-SHA256 + RAZORPAY_WEBHOOK_SECRET.

    Configure in Razorpay Dashboard → Settings → Webhooks:
      URL:    https://www.taraastrovision.com/api/payment/webhook
      Events: payment.captured, payment.failed
    """
    import hmac as _hmac, hashlib as _hashlib, json as _json

    body_bytes = await request.body()

    _webhook_secret = (RAZORPAY_WEBHOOK_SECRET or os.getenv("RAZORPAY_WEBHOOK_SECRET", "")).strip()
    if not _webhook_secret:
        log.error("Rejecting Razorpay webhook because RAZORPAY_WEBHOOK_SECRET is not configured")
        raise HTTPException(503, "Webhook verification is not configured")
    signature = request.headers.get("X-Razorpay-Signature", "")
    expected = _hmac.new(
        _webhook_secret.encode(), body_bytes, _hashlib.sha256
    ).hexdigest()
    if not _hmac.compare_digest(expected, signature):
        log.warning("Webhook signature verification failed")
        raise HTTPException(400, "Invalid webhook signature")

    try:
        payload = _json.loads(body_bytes)
    except (ValueError, TypeError):
        raise HTTPException(400, "Invalid JSON payload")

    event = payload.get("event", "")
    entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    order_entity = payload.get("payload", {}).get("order", {}).get("entity", {})
    order_id = entity.get("order_id") or order_entity.get("id") or ""
    payment_id = entity.get("id", "")
    event_id = request.headers.get("x-razorpay-event-id") or _hashlib.sha256(body_bytes).hexdigest()

    if event not in ("payment.captured", "payment.failed"):
        return {"status": "ignored", "event": event}

    try:
        inserted = db.execute(
            """INSERT OR IGNORE INTO payment_webhook_events (event_id, event, order_id, payment_id)
               VALUES (?, ?, ?, ?)""",
            (event_id, event, order_id or None, payment_id or None),
        ).rowcount
        if not inserted:
            return {"status": "duplicate", "event": event}

        if event == "payment.captured":
            payment_order = db.execute(
                "SELECT * FROM payment_orders WHERE order_id = ?", (order_id,)
            ).fetchone()
            if not payment_order:
                log.warning("Captured webhook references an unknown payment order")
            elif (
                entity.get("status") != "captured"
                or entity.get("currency") != payment_order["currency"]
                or int(entity.get("amount", 0)) != int(payment_order["amount_paise"])
            ):
                raise HTTPException(400, "Captured payment details do not match the saved order")
            else:
                with booking_lock:
                    payment_order = db.execute(
                        "SELECT * FROM payment_orders WHERE order_id = ?", (order_id,)
                    ).fetchone()
                    if (
                        payment_order["status"] == "captured"
                        and payment_order["payment_id"] not in (None, payment_id)
                    ):
                        refund = handle_overbooked_refund(
                            db,
                            payment_order["booking_id"] or "",
                            payment_order["service_name"],
                            order_id,
                            payment_id,
                            int(payment_order["amount_paise"]),
                            reason="A second payment was captured for the same Razorpay order",
                        )
                        log.warning("Duplicate capture for order=%s; refund status=%s", order_id, refund["status"])
                    else:
                        db.execute(
                            """UPDATE payment_orders SET status='captured', payment_id=?,
                                   updated_at=datetime('now') WHERE order_id=?""",
                            (payment_id, order_id),
                        )
                    booking = db.execute(
                        "SELECT * FROM bookings WHERE razorpay_order_id = ?", (order_id,)
                    ).fetchone()
                    if booking and not (
                        payment_order["status"] == "captured"
                        and payment_order["payment_id"] not in (None, payment_id)
                    ):
                        if booking["status"] in ("paid", "confirmed"):
                            if booking["razorpay_payment_id"] != payment_id:
                                refund = handle_overbooked_refund(
                                    db,
                                    booking["id"],
                                    booking["name"],
                                    order_id,
                                    payment_id,
                                    int(payment_order["amount_paise"]),
                                    reason="A second captured payment was received for an already-paid booking",
                                )
                                log.warning(
                                    "Duplicate payment captured for booking=%s; refund status=%s",
                                    booking["id"],
                                    refund["status"],
                                )
                        else:
                            confirmed_count = get_confirmed_booking_count(db, booking["name"])
                            if confirmed_count >= SERVICE_BOOKING_LIMIT:
                                refund = handle_overbooked_refund(
                                    db,
                                    booking["id"],
                                    booking["name"],
                                    order_id,
                                    payment_id,
                                    int(payment_order["amount_paise"]),
                                )
                                db.execute(
                                    """UPDATE bookings SET status='refund_pending', payment_status=?,
                                           booking_status='rejected', rejection_reason=?, updated_at=datetime('now')
                                       WHERE id=?""",
                                    (
                                        refund["status"],
                                        "Capacity limit reached; refund initiated or requires manual review",
                                        booking["id"],
                                    ),
                                )
                            else:
                                db.execute(
                                    """UPDATE bookings SET status='paid', payment_status='paid',
                                           booking_status='pending', paid_at=datetime('now'),
                                           razorpay_payment_id=?, updated_at=datetime('now')
                                       WHERE id=?""",
                                    (payment_id, booking["id"]),
                                )
                                booking_data = dict(booking)
                                booking_data["razorpay_payment_id"] = payment_id
                                booking_data["paid_at"] = datetime.now(timezone.utc).isoformat()
                                db.commit()
                                details = "\n".join(
                                    f"  {i + 1}. {p.get('name', '')} — Gotra: {p.get('gotra', '')}, "
                                    f"Relation: {p.get('relation', '')}"
                                    for i, p in enumerate(_json.loads(booking_data["participants"] or "[]"))
                                )
                                message = (
                                    f"Booking ID: {booking_data['id']}\n"
                                    f"Service: {booking_data['name']}\n"
                                    f"Amount Paid: ₹{booking_data['price']:,.0f}\n"
                                    f"Participants:\n{details}\n"
                                    f"Contact: {booking_data['contact_email']} | {booking_data['contact_phone']}"
                                )
                                send_email(ADMIN_EMAIL, f"Tara Astro Vision — New Booking {booking_data['id']}", message)
                                send_email(
                                    booking_data["contact_email"],
                                    f"Tara Astro Vision — Booking Confirmed {booking_data['id']}",
                                    message,
                                )

        elif event == "payment.failed" and order_id:
            db.execute(
                """UPDATE payment_orders SET status='failed', payment_id=?,
                       updated_at=datetime('now') WHERE order_id=? AND status != 'captured'""",
                (payment_id or None, order_id),
            )
            db.execute(
                """UPDATE bookings SET status='pending_payment', payment_status='failed',
                       updated_at=datetime('now')
                   WHERE razorpay_order_id=? AND status NOT IN ('paid', 'confirmed')""",
                (order_id,),
            )

        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        log.error("Razorpay webhook processing failed for event=%s: %s", event, e, exc_info=True)
        raise HTTPException(500, "Webhook processing failed") from e

    return {"status": "ok", "event": event}

# ── Language Preference ──────────────────────────────────────


@app.put("/api/user/language")
async def update_language(data: LangUpdate, user=Depends(get_current_user), db=Depends(get_db)):
    valid_langs = {"en","te","hi","ta","ml","kn","mr"}
    if data.lang not in valid_langs:
        raise HTTPException(400, "Unsupported language")
    db.execute("UPDATE users SET lang = ? WHERE id = ?", (data.lang, user["id"]))
    db.commit()
    return {"message": "Language updated", "lang": data.lang}

# ─── Root site static assets ─────────────────────────────────
class PublicSiteFiles(StaticFiles):
    """Serve frontend assets without exposing backend, database, or secret files."""

    PUBLIC_SUFFIXES = {
        ".html", ".js", ".css", ".jpg", ".jpeg", ".png", ".svg", ".ico",
        ".webp", ".avif", ".woff", ".woff2", ".ttf",
    }

    async def get_response(self, path: str, scope):
        parts = pathlib.PurePosixPath(path).parts
        candidate = (ROOT_DIR / path).resolve()
        try:
            candidate.relative_to(ROOT_DIR)
        except ValueError:
            raise HTTPException(404, "Not found")
        if any(part.startswith(".") for part in parts):
            raise HTTPException(404, "Not found")
        if candidate.is_dir() and path:
            raise HTTPException(404, "Not found")
        if candidate.is_file() and candidate.suffix.lower() not in self.PUBLIC_SUFFIXES:
            raise HTTPException(404, "Not found")
        return await super().get_response(path, scope)


# Mounted after API and SPA routes so API paths keep their intended handlers.
app.mount("/", PublicSiteFiles(directory=str(ROOT_DIR), html=True), name="site")

# ─── Entry Point ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
