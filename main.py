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

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from typing import Optional, List
import sqlite3, hashlib, os, math, logging
import pathlib

# Load .env from project directory (where main.py lives)
_env_path = pathlib.Path(__file__).parent / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_env_path)
except ImportError:
    pass

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("tara-astro")

# Optional: import swisseph for production
# import swisseph as swe
# swe.set_ephe_path('/path/to/ephe')   # Set ephemeris data path

# ─── Configuration ───────────────────────────────────────────
SECRET_KEY    = os.getenv("JWT_SECRET", "jyotisha_secret_change_in_production")
ALGORITHM     = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
DATABASE_URL  = os.getenv("DATABASE_URL", "jyotisha.db")

# ─── FastAPI App ─────────────────────────────────────────────
app = FastAPI(
    title="Jyotisha API",
    description="Pure Vedic Astrology Platform — South Indian Kundli & Guidance",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ─── Homam SPA (Vite + React Router build in ./homam) ─────────
ROOT_DIR = pathlib.Path(__file__).parent.resolve()
HOMAM_DIST = ROOT_DIR / "homam"


def _homam_index():
    idx = HOMAM_DIST / "index.html"
    if not idx.is_file():
        raise HTTPException(404, "Homam pages not built (run: cd homam-app && npm run build)")
    return FileResponse(idx)


@app.get("/homam")
@app.get("/homam/")
async def homam_root():
    """Serve React shell for /homam (redirect or empty path)."""
    return _homam_index()


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
    return _homam_index()

# ─── Database Setup ──────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DATABASE_URL)
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
            price           REAL    NOT NULL,
            persons         INTEGER DEFAULT 1,
            participants    TEXT    NOT NULL,
            contact_email   TEXT    NOT NULL,
            contact_phone   TEXT    NOT NULL,
            status          TEXT    DEFAULT 'confirmed',
            paid_at         TEXT,
            created_at      TEXT    DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    try:
        c.execute("ALTER TABLE bookings ADD COLUMN scheduled_date TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass
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
    status: Optional[str] = "confirmed"
    paidAt: Optional[str] = None
    pdfBase64: Optional[str] = None  # PDF receipt for email attachment
    scheduledDate: Optional[str] = None  # YYYY-MM-DD; same for all participants

# ─── Auth Utilities ──────────────────────────────────────────
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_token(data: dict, expires_hours: int = ACCESS_TOKEN_EXPIRE_HOURS) -> str:
    """Simple JWT-like token (use python-jose in production)"""
    import base64, json, hmac
    payload = {**data, "exp": (datetime.utcnow() + timedelta(hours=expires_hours)).isoformat()}
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
        if datetime.fromisoformat(payload["exp"]) < datetime.utcnow(): return None
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

# ─── API Routes ──────────────────────────────────────────────

@app.get("/")
async def root():
    return {"message": "Jyotisha API — Vedic Astrology Platform", "status": "running"}

@app.get("/api/health")
async def health():
    email_configured = bool(RESEND_API_KEY or (SMTP_USER and SMTP_PASS))
    return {
        "status": "healthy",
        "system": "Lahiri Sidereal Vedic",
        "version": "1.0.0",
        "email_configured": email_configured,
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
    attachment: (filename, base64_content) for PDF
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
                filename, b64_content = attachment
                params["attachments"] = [{
                    "content": b64_content,
                    "filename": filename,
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
                filename, b64_content = attachment
                part = MIMEBase("application", "pdf")
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

@app.post("/api/booking/confirm")
async def confirm_booking(data: BookingConfirm, db=Depends(get_db)):
    """
    Save booking and send admin + user confirmation emails.
    Triggered only after successful payment (frontend calls this after payment completion).
    """
    import json
    log.info(f"Booking confirm received: {data.id} {data.name}")

    try:
        db.execute(
            """INSERT INTO bookings (id, type, name, price, persons, participants, contact_email, contact_phone, status, paid_at, scheduled_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data.id, data.type, data.name, data.price, data.persons or 1,
             json.dumps(data.participants), data.contactEmail, data.contactPhone,
             data.status or "confirmed", data.paidAt, data.scheduledDate)
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

# ── Language Preference ──────────────────────────────────────

@app.put("/api/user/language")
async def update_language(data: LangUpdate, user=Depends(get_current_user), db=Depends(get_db)):
    valid_langs = {"en","te","hi","ta","ml","kn","mr"}
    if data.lang not in valid_langs:
        raise HTTPException(400, "Unsupported language")
    db.execute("UPDATE users SET lang = ? WHERE id = ?", (data.lang, user["id"]))
    db.commit()
    return {"message": "Language updated", "lang": data.lang}

# ─── Entry Point ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)