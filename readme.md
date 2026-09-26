# ॐ Jyotisha — Vedic Astrology Platform

**A startup-ready, faith-respecting, authentic Hindu Vedic astrology platform.**  
*Built with love as a birthday gift.*

---

## ✨ What This Is

**Jyotisha** is a complete, production-ready Vedic astrology web platform with:

- 🕉 **100% Pure Vedic (Jyotisha)** — no Western astrology
- 📐 **South Indian Rasi Chart** only (no North Indian)
- 🌙 **Astronomically accurate** planetary calculations (Lahiri Ayanamsha)
- 🗣 **7 Indian languages** — Telugu, Hindi, Tamil, Malayalam, Kannada, Marathi, English
- 🔐 **JWT authentication** — login-protected Kundli and personalized predictions
- 🙏 **Spiritual, calm Hindu aesthetic** — cosmic colors, Cinzel/Crimson Pro fonts
- 📱 **Mobile-first** responsive design

---

## 📁 Project Structure

```
jyotisha/
├── frontend/
│   ├── index.html          # Complete single-page application
│   ├── css/
│   │   └── style.css       # Full spiritual UI stylesheet
│   └── js/
│       ├── i18n.js         # 7-language internationalization
│       ├── auth.js         # JWT authentication module
│       ├── astro.js        # Vedic calculation engine + chart renderer
│       └── app.js          # Application controller
├── backend/
│   ├── main.py             # FastAPI backend with Swiss Ephemeris
│   └── requirements.txt    # Python dependencies
└── README.md
```

---

## 🚀 Phase 1 — Running the MVP (Frontend Only)

The frontend is a complete standalone SPA. No backend needed to start.

```bash
# Option 1: Simply open in browser
open frontend/index.html

# Option 2: Serve locally (recommended)
cd frontend
python3 -m http.server 3000
# Then visit: http://localhost:3000
```

**That's it.** The full MVP runs in the browser:
- Real Vedic calculations (client-side)
- All 7 languages
- Login/Register (localStorage session)
- South Indian Kundli chart
- Daily/Weekly/Monthly horoscopes
- Dashboard

---

## 🔧 Phase 1 — Running with Python Backend

### Requirements
- Python 3.10+
- macOS/Linux (works on MacBook)

### Setup

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# (Optional) Download Swiss Ephemeris data for highest precision
# https://www.astro.com/swisseph/swedownl.html
# Place in /usr/local/share/ephe/ or set SE_EPHE_PATH

# Start the API server
uvicorn main:app --reload --port 8000
```

API docs available at: `http://localhost:8000/docs`

### Connecting Frontend to Backend

In `frontend/js/auth.js`, change the `AUTH` methods to call the API:

```javascript
// Replace simulated login with:
async login(email, password) {
  const res = await fetch('http://localhost:8000/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });
  if (!res.ok) throw new Error('Invalid credentials');
  const data = await res.json();
  this.saveSession(data.user, data.token);
  return data.user;
}
```

---

## 🌟 Features Implemented (Phase 1)

| Feature | Status |
|---------|--------|
| South Indian Rasi Chart | ✅ |
| Real Vedic planetary calculations | ✅ |
| Lahiri Ayanamsha (sidereal) | ✅ |
| All 9 planets + Lagna | ✅ |
| Nakshatra calculation | ✅ |
| Daily/Weekly/Monthly horoscope | ✅ |
| Life guidance (career, family, finance, peace, spirituality) | ✅ |
| Login / Register (JWT) | ✅ |
| 7 languages | ✅ |
| Language preference saved | ✅ |
| Login-gated Kundli | ✅ |
| Guest horoscope (public) | ✅ |
| City autocomplete (OpenStreetMap) | ✅ |
| Mobile responsive | ✅ |
| Spiritual Hindu aesthetic | ✅ |
| No doshas/yogas shown to user | ✅ |
| Dashboard | ✅ |

---

## 📋 Pooja & Homam Booking System

The platform includes a complete booking flow for Poojas and Homams:

1. **Select** a Pooja or Homam → **Fill Participant Details** → **Payment** → **Confirmation**
2. **Participant 1** = Booking Member (must manually enter details; no auto-fill)
3. **Poojas**: Unlimited participants via "Add Participant" button
4. **Homams**: Fixed participants based on "Number of Persons" selected
5. **PDF Receipt** auto-generated after payment (downloadable from confirmation page)
6. **Email Notifications**: Admin + user confirmation (requires SMTP configuration)

### Email Configuration

**Option 1: Resend (Recommended)** — Free 100 emails/day, no SMTP setup

1. Sign up at [resend.com](https://resend.com)
2. Create an API key in the dashboard
3. Create `.env` in the project root:
   ```
   RESEND_API_KEY=re_your_api_key_here
   ```

**Option 2: Gmail SMTP**

1. Create `.env` with:
   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=taraastrovision123@gmail.com
   SMTP_PASS=your_16_char_app_password
   ```
2. Use an [App Password](https://support.google.com/accounts/answer/185833) (not your regular password)

**Important:** Run the backend (`uvicorn main:app --port 8000`) for emails to be sent. The frontend calls the API after payment.

---

## 📌 Phase 2 (Planned)

- PDF download of Kundli reports
- Saved reports with history
- Festival & muhurat-based guidance

## 📌 Phase 3 (Planned)

- Hindu astrologer consultation booking
- Subscription tiers
- Mobile app (React Native)

---

## 🔭 Astrology Engine Details

The platform uses **Lahiri Ayanamsha** — the official Indian Government standard for Vedic (sidereal) astrology, as established by the Rashtriya Panchang.

**Planets calculated:**
- Surya (Sun), Chandra (Moon), Kuja (Mars)
- Budha (Mercury), Guru (Jupiter), Shukra (Venus)
- Shani (Saturn), Rahu (North Node), Ketu (South Node)
- Lagna (Ascendant)

**Chart type:** South Indian Rasi Chart (Rasis fixed, not houses)

**Production accuracy:** Backend uses `pyswisseph` for sub-arcsecond planetary precision.

---

## 🛡 Cultural Integrity

- Pure Vedic / Jyotisha only
- No Western zodiac, no tropical astrology
- No doshas or yogas shown to end users
- Guidance expressed as life wisdom, not technical readings
- Hindu calendar and cultural context throughout
- Languages: Telugu, Hindi, Tamil, Malayalam, Kannada, Marathi, English

---

## 🚢 Deployment

### Render (Recommended)
```yaml
# render.yaml
services:
  - type: web
    name: jyotisha-api
    env: python
    buildCommand: pip install -r backend/requirements.txt
    startCommand: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: JWT_SECRET
        generateValue: true

  - type: static
    name: jyotisha-frontend
    staticPublishPath: frontend/
    buildCommand: echo "no build needed"
```

### Vercel (Frontend only)
```bash
npm i -g vercel
cd frontend && vercel --prod
```

---

## 🙏 About

This platform was created as a **birthday gift** — a loving tribute built with deep respect for Vedic tradition, Indian culture, and the sacred science of Jyotisha.

*May it guide many souls on their journey.*

**ॐ तत् सत्**