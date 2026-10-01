#!/usr/bin/env python3
"""Generate multi-page HTML files for Tara Astro Vision."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def nav(active: str) -> str:
    def cls(name: str) -> str:
        return 'nav-link active' if active == name else 'nav-link'
    def pcl(name: str) -> str:
        return 'nav-link nav-link-protected active' if active == name else 'nav-link nav-link-protected'
    return f"""  <nav class="navbar" id="navbar">
    <div class="nav-inner">
      <a href="index.html" class="nav-logo">
        <img src="logo.jpg" alt="Tara Astro Vision Logo" class="logo-om">
        <span class="logo-text" data-i18n="brand">Tara Astro Vision</span>
      </a>
      <div class="nav-links" id="navLinks">
        <a href="index.html" class="{cls('home')}" data-i18n="nav_home">Home</a>
        <a href="horoscope.html" class="{cls('horoscope')}" data-i18n="nav_horoscope">Horoscope</a>
        <a href="kundli.html" class="{pcl('kundli')}" data-i18n="nav_kundli">Kundli</a>
        <a href="dashboard.html" class="{pcl('dashboard')}" data-i18n="nav_dashboard">Dashboard</a>
        <a href="pooja.html" class="{cls('pooja')}">Poojas</a>
        <a href="homam.html" class="{cls('homam')}">Homams</a>
        <a href="consult.html" class="{cls('consult')}">Consult Astrologer</a>
        <a href="contact.html" class="{cls('contact')}">Contact</a>
      </div>
      <div class="nav-right">
        <div class="lang-switcher" id="langSwitcher">
          <button type="button" class="lang-btn" aria-expanded="false" aria-haspopup="true">
            <span id="currentLangFlag">🇮🇳</span>
            <span id="currentLangCode">EN</span>
            <svg width="10" height="6" viewBox="0 0 10 6" aria-hidden="true">
              <path d="M1 1l4 4 4-4" stroke="currentColor" stroke-width="1.5" fill="none" />
            </svg>
          </button>
          <div class="lang-menu hidden" id="langMenu">
            <button type="button" data-lang="en"><span>🇬🇧</span> English</button>
            <button type="button" data-lang="te"><span>🇮🇳</span> తెలుగు</button>
            <button type="button" data-lang="hi"><span>🇮🇳</span> हिंदी</button>
            <button type="button" data-lang="ta"><span>🇮🇳</span> தமிழ்</button>
            <button type="button" data-lang="ml"><span>🇮🇳</span> മലയാളം</button>
            <button type="button" data-lang="kn"><span>🇮🇳</span> ಕನ್ನಡ</button>
            <button type="button" data-lang="mr"><span>🇮🇳</span> मराठी</button>
          </div>
        </div>
        <div class="auth-buttons" id="authButtons">
          <button type="button" class="btn-login" data-i18n="login">Login</button>
          <button type="button" class="btn-register" data-i18n="register">Register</button>
        </div>
        <div class="user-menu hidden" id="userMenu">
          <button type="button" class="user-avatar-btn">
            <span class="avatar-circle" id="avatarInitial">A</span>
            <span id="userName">User</span>
          </button>
          <div class="user-dropdown hidden" id="userDropdown">
            <a href="dashboard.html">Dashboard</a>
            <a href="dashboard.html">Profile</a>
            <a href="#" id="logoutLink">Logout</a>
          </div>
        </div>
        <button type="button" class="cart-btn" id="cartBtn">
          🛒 <span class="cart-count" id="cartCount">0</span>
        </button>
        <button type="button" class="hamburger" id="hamburger" aria-label="Menu">
          <span></span><span></span><span></span>
        </button>
      </div>
    </div>
  </nav>"""

CART = """  <div class="cart-overlay hidden" id="cartOverlay"></div>
  <div class="cart-sidebar hidden" id="cartSidebar">
    <div class="cart-header">
      <h3>🛒 Your Cart</h3>
      <button type="button" class="cart-close-btn" id="cartCloseBtn" aria-label="Close cart">✕</button>
    </div>
    <div class="cart-items" id="cartItems">
      <div class="cart-empty" id="cartEmpty">
        <p>Your cart is empty</p>
        <p class="cart-empty-emoji" aria-hidden="true">🛒</p>
      </div>
    </div>
    <div class="cart-footer hidden" id="cartFooter">
      <div class="cart-total-row"><span>Total:</span><span id="cartTotal" class="cart-total-amt">₹0</span></div>
      <div class="cart-footer-inner">
        <button type="button" class="btn-primary full-width" id="btnProceedCartPay">Payment currently unavailable</button>
        <button type="button" class="btn-secondary full-width" id="btnProceedCartQuote">Request Quote (Email)</button>
        <button type="button" class="btn-secondary full-width" id="btnClearCart">Clear Cart</button>
      </div>
    </div>
  </div>"""

MODALS = """  <div class="modal-overlay hidden" id="modalOverlay"></div>
  <div class="modal hidden" id="modal-login">
    <button type="button" class="modal-close" aria-label="Close">×</button>
    <div class="modal-header">
      <img src="logo.jpg" alt="Tara Astro Vision Logo" class="modal-om">
      <h2 data-i18n="login_title">Welcome Back</h2>
      <p data-i18n="login_sub">Login to access your personal guidance</p>
    </div>
    <form class="modal-form" id="formLogin">
      <div class="form-group">
        <label data-i18n="email">Email</label>
        <input type="email" id="loginEmail" required class="form-input" placeholder="your@email.com" autocomplete="username" />
      </div>
      <div class="form-group">
        <label data-i18n="password">Password</label>
        <input type="password" id="loginPass" required class="form-input" placeholder="••••••••" autocomplete="current-password" />
      </div>
      <div class="modal-error hidden" id="loginError"></div>
      <button type="submit" class="btn-primary full-width" data-i18n="login">Login</button>
      <p class="modal-switch" data-i18n="no_account">Don't have an account?
        <a href="#" data-open-modal="register" data-i18n="register_link">Register</a>
      </p>
    </form>
  </div>
  <div class="modal hidden" id="modal-register">
    <button type="button" class="modal-close" aria-label="Close">×</button>
    <div class="modal-header">
      <img src="logo.jpg" alt="Tara Astro Vision Logo" class="modal-om">
      <h2 data-i18n="register_title">Begin Your Journey</h2>
      <p data-i18n="register_sub">Create your sacred account</p>
    </div>
    <form class="modal-form" id="formRegister">
      <div class="form-group">
        <label data-i18n="full_name">Full Name</label>
        <input type="text" id="regName" required class="form-input" placeholder="Your Name" autocomplete="name" />
      </div>
      <div class="form-group">
        <label data-i18n="email">Email</label>
        <input type="email" id="regEmail" required class="form-input" placeholder="your@email.com" autocomplete="email" />
      </div>
      <div class="form-group">
        <label data-i18n="password">Password</label>
        <input type="password" id="regPass" required class="form-input" placeholder="Min 8 characters" minlength="8" autocomplete="new-password" />
      </div>
      <div class="modal-error hidden" id="registerError"></div>
      <button type="submit" class="btn-primary full-width" data-i18n="register">Register</button>
      <p class="modal-switch">Already have an account?
        <a href="#" data-open-modal="login" data-i18n="login_link">Login</a>
      </p>
    </form>
  </div>
  <div class="modal hidden" id="modal-loginRequired">
    <button type="button" class="modal-close" aria-label="Close">×</button>
    <div class="modal-header">
      <img src="logo.jpg" alt="Tara Astro Vision Logo" class="modal-om">
      <h2 data-i18n="auth_required">Login Required</h2>
      <p data-i18n="auth_required_desc">Please login or register to access your personalized birth chart and predictions.</p>
    </div>
    <div class="modal-actions">
      <button type="button" class="btn-primary" data-open-modal="login" data-i18n="login">Login</button>
      <button type="button" class="btn-secondary" data-open-modal="register" data-i18n="register">Register</button>
    </div>
  </div>
  <div class="modal hidden" id="modal-loading">
    <div class="loading-inner">
      <div class="chakra-spinner">𑁍</div>
      <p data-i18n="calculating">Calculating your cosmic positions...</p>
    </div>
  </div>
  <div class="modal hidden" id="modal-paymentUnavailable">
    <button type="button" class="modal-close" aria-label="Close">×</button>
    <div class="modal-header">
      <h2 id="payment-modal-title">Payment unavailable</h2>
      <p id="payment-modal-sub">Your request is pending payment and has not been confirmed.</p>
    </div>
    <div class="modal-body">
      <p>Payment is not available yet. No payment has been made and this request is not confirmed.</p>
    </div>
  </div>"""

FOOTER = """  <footer class="site-footer">
    <div class="container">
      <div class="footer-contact">
        <h3>Contact Us</h3>
        <p>Email: <a href="mailto:taraastrovision123@gmail.com">taraastrovision123@gmail.com</a></p>
        <p>Phone: <a href="tel:9014308190">9014308190</a></p>
      </div>
    </div>
  </footer>"""

HEAD = """<!DOCTYPE html>
<html lang="en" data-lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;500;600;700&family=Crimson+Pro:ital,wght@0,300;0,400;0,500;1,300;1,400&family=Noto+Sans+Telugu:wght@300;400;500&family=Noto+Sans+Devanagari:wght@300;400;500&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="css/styles.css" />
  <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
</head>
<body data-page="{page}">
"""

SCRIPTS = """  <script src="js/main.js"></script>
</body>
</html>
"""


def write_page(filename: str, title: str, page: str, active: str, main_inner: str):
    html = (
        HEAD.format(title=title, page=page)
        + nav(active)
        + "\n"
        + CART
        + "\n"
        + main_inner
        + "\n"
        + FOOTER
        + "\n"
        + MODALS
        + "\n"
        + SCRIPTS
    )
    (ROOT / filename).write_text(html, encoding="utf-8")
    print("Wrote", filename)


def main():
    pooja_body = (ROOT / "_pooja_body.html").read_text(encoding="utf-8")
    homam_body = (ROOT / "_homam_body.html").read_text(encoding="utf-8")

    # index
    write_page(
        "index.html",
        "Tara Astro Vision — Home",
        "home",
        "home",
        """  <main class="site-main site-main--flush">
    <div class="nav-breadcrumb">
      <a href="index.html">Home</a> → <a href="kundli.html">Kundli</a> → <a href="pooja.html">Pooja</a> → <a href="contact.html">Contact</a>
    </div>
    <section class="hero">
      <div class="stars-bg" id="starsBg"></div>
      <div class="hero-content">
        <img src="logo.jpg" alt="Tara Astro Vision Logo" class="hero-om">
        <h1 class="hero-title" data-i18n="hero_title">Discover Your Cosmic Path</h1>
        <p class="hero-sub" data-i18n="hero_sub">Ancient Vedic wisdom. Authentic Jyotisha. Guidance rooted in dharma.</p>
        <div class="hero-cta">
          <a class="btn-primary nav-link-protected" href="kundli.html" id="heroKundliCta" data-i18n="cta_kundli">Generate Your Kundli</a>
          <a class="btn-secondary" href="horoscope.html" data-i18n="cta_horoscope">Today's Horoscope</a>
        </div>
      </div>
      <div class="hero-mandala" aria-hidden="true"></div>
    </section>
    <section class="features-section">
      <div class="container">
        <h2 class="section-title" data-i18n="feat_title">Sacred Offerings</h2>
        <div class="features-grid">
          <a class="feature-card nav-link-protected" href="kundli.html">
            <div class="feat-icon">𑁍</div>
            <h3 data-i18n="feat_kundli">Birth Chart</h3>
            <p data-i18n="feat_kundli_desc">Your South Indian Rasi chart with precise planetary positions and life guidance.</p>
          </a>
          <a class="feature-card" href="horoscope.html">
            <div class="feat-icon">☽</div>
            <h3 data-i18n="feat_horoscope">Daily Guidance</h3>
            <p data-i18n="feat_horoscope_desc">Moon-based daily, weekly, and monthly wisdom for your Rasi and Nakshatra.</p>
          </a>
          <a class="feature-card nav-link-protected" href="dashboard.html">
            <div class="feat-icon">𑁋</div>
            <h3 data-i18n="feat_dashboard">Personal Journey</h3>
            <p data-i18n="feat_dashboard_desc">Your saved charts, past readings, and life predictions in one place.</p>
          </a>
        </div>
      </div>
    </section>
    <section class="rasi-section">
      <div class="container">
        <h2 class="section-title" data-i18n="rasi_title">The Twelve Rasis</h2>
        <p class="section-sub" data-i18n="rasi_sub">Explore the nature of each Rasi according to Vedic tradition</p>
        <div class="rasi-grid" id="rasiGrid"></div>
      </div>
    </section>
    <section class="trust-section">
      <div class="container">
        <div class="trust-grid">
          <div class="trust-item">
            <span class="trust-num">100%</span>
            <span data-i18n="trust_vedic">Pure Vedic</span>
          </div>
          <div class="trust-item">
            <span class="trust-num">Sidereal</span>
            <span data-i18n="trust_calc">Astronomically Accurate</span>
          </div>
          <div class="trust-item">
            <span class="trust-num">7</span>
            <span data-i18n="trust_lang">Indian Languages</span>
          </div>
          <div class="trust-item">
            <span class="trust-num">South Indian</span>
            <span data-i18n="trust_chart">Rasi Chart Style</span>
          </div>
        </div>
      </div>
    </section>
  </main>""",
    )

    # horoscope
    write_page(
        "horoscope.html",
        "Horoscope — Tara Astro Vision",
        "horoscope",
        "horoscope",
        """  <main class="site-main">
    <div class="page-hero">
      <div class="container">
        <h1 data-i18n="horo_page_title">Vedic Horoscope</h1>
        <p data-i18n="horo_page_sub">Based on Moon Rasi, Nakshatra & Gochar transit</p>
      </div>
    </div>
    <div class="container page-body">
      <div class="tabs">
        <button type="button" class="tab active" data-period="daily" data-i18n="tab_daily">Daily</button>
        <button type="button" class="tab" data-period="weekly" data-i18n="tab_weekly">Weekly</button>
        <button type="button" class="tab" data-period="monthly" data-i18n="tab_monthly">Monthly</button>
      </div>
      <div class="rasi-selector" id="rasiSelector">
        <p class="selector-label" data-i18n="select_rasi">Select your Moon Rasi:</p>
        <div class="rasi-chips" id="rasiChips"></div>
      </div>
      <div class="horo-display" id="horoDisplay">
        <div class="horo-placeholder">
          <span class="placeholder-icon">☽</span>
          <p data-i18n="select_rasi_prompt">Please select your Rasi above to view your guidance</p>
        </div>
      </div>
    </div>
  </main>""",
    )

    # kundli
    write_page(
        "kundli.html",
        "Kundli — Tara Astro Vision",
        "kundli",
        "kundli",
        """  <main class="site-main">
    <div class="page-hero">
      <div class="container">
        <h1 data-i18n="kundli_page_title">Your Birth Chart</h1>
        <p data-i18n="kundli_page_sub">South Indian Rasi Chart with precise Vedic calculations</p>
      </div>
    </div>
    <div class="container page-body">
      <div class="kundli-layout">
        <div class="kundli-form-section" id="kundliFormSection">
          <h2 data-i18n="birth_details">Birth Details</h2>
          <form class="birth-form" id="birthForm">
            <div class="form-group">
              <label data-i18n="dob">Date of Birth</label>
              <input type="date" id="dob" required class="form-input" />
            </div>
            <div class="form-group">
              <label data-i18n="tob">Time of Birth</label>
              <input type="time" id="tob" required class="form-input" />
            </div>
            <div class="form-group">
              <label data-i18n="pob">Place of Birth</label>
              <input type="text" id="pob" required class="form-input" placeholder="City, Country" autocomplete="off" />
              <div class="city-dropdown hidden" id="cityDropdown"></div>
            </div>
            <div class="form-row">
              <div class="form-group half">
                <label data-i18n="lat">Latitude</label>
                <input type="number" id="lat" step="0.0001" class="form-input" readonly />
              </div>
              <div class="form-group half">
                <label data-i18n="lon">Longitude</label>
                <input type="number" id="lon" step="0.0001" class="form-input" readonly />
              </div>
            </div>
            <div class="form-group">
              <label data-i18n="timezone">Timezone</label>
              <select id="timezone" class="form-input">
                <option value="5.5">IST (UTC+5:30)</option>
                <option value="5.75">Nepal (UTC+5:45)</option>
                <option value="6">Bangladesh (UTC+6)</option>
                <option value="0">UTC</option>
              </select>
            </div>
            <div class="form-group">
              <label data-i18n="gender">Gender (Optional)</label>
              <select id="gender" class="form-input">
                <option value="">Prefer not to say</option>
                <option value="male" data-i18n="male">Male</option>
                <option value="female" data-i18n="female">Female</option>
                <option value="other" data-i18n="other">Other</option>
              </select>
            </div>
            <button type="submit" class="btn-primary full-width" data-i18n="generate_chart">Generate My Chart</button>
          </form>
        </div>
        <div class="kundli-result-section hidden" id="kundliResult">
          <div class="chart-header">
            <h2 data-i18n="your_chart">Your Vedic Birth Chart</h2>
            <div class="chart-style-toggle">
              <button type="button" class="style-btn active" id="btn-south">South Indian</button>
              <button type="button" class="style-btn" id="btn-north">North Indian</button>
            </div>
            <button type="button" class="btn-back" id="btnKundliRecalc" data-i18n="recalculate">↩ Recalculate</button>
          </div>
          <div class="charts-row">
            <div class="chart-box">
              <h3 class="chart-title" id="lagna-title">Lagna / Ascendant / Basic Birth Chart</h3>
              <div id="lagnaChartContainer"></div>
            </div>
            <div class="chart-box">
              <h3 class="chart-title" id="navamsa-title">Navamsa</h3>
              <div id="navamsaChartContainer"></div>
            </div>
          </div>
          <div class="planet-info" id="planetInfo"></div>
          <div class="life-overview" id="lifeOverview"></div>
        </div>
      </div>
    </div>
  </main>""",
    )

    # dashboard
    write_page(
        "dashboard.html",
        "Dashboard — Tara Astro Vision",
        "dashboard",
        "dashboard",
        """  <main class="site-main">
    <div class="page-hero">
      <div class="container">
        <h1 data-i18n="dash_title">My Dashboard</h1>
        <p data-i18n="dash_sub">Your personal cosmic journey</p>
      </div>
    </div>
    <div class="container page-body">
      <div class="dashboard-grid">
        <div class="dash-card" id="savedCharts">
          <h3 data-i18n="saved_charts">Saved Charts</h3>
          <div class="chart-list" id="chartList">
            <p class="empty-state" data-i18n="no_charts">No charts saved yet. Generate your Kundli first.</p>
          </div>
        </div>
        <div class="dash-card" id="recentReadings">
          <h3 data-i18n="recent_readings">Recent Readings</h3>
          <div id="readingsList">
            <p class="empty-state" data-i18n="no_readings">No readings yet.</p>
          </div>
        </div>
        <div class="dash-card" id="profileCard">
          <h3 data-i18n="my_profile">My Profile</h3>
          <div id="profileInfo"></div>
        </div>
      </div>
    </div>
  </main>""",
    )

    # pooja
    write_page(
        "pooja.html",
        "Poojas — Tara Astro Vision",
        "pooja",
        "pooja",
        "  <main class=\"site-main\">\n" + pooja_body + "\n  </main>",
    )

    # homam
    write_page(
        "homam.html",
        "Homams — Tara Astro Vision",
        "homam",
        "homam",
        "  <main class=\"site-main\">\n" + homam_body + "\n  </main>",
    )

    # consult
    write_page(
        "consult.html",
        "Consult — Tara Astro Vision",
        "consult",
        "consult",
        """  <main class="site-main">
    <div class="page-hero">
      <h1 class="page-hero-title">🔮 Personal Astrology Consultation</h1>
      <p class="page-hero-sub">Direct guidance from our expert Vedic astrologers</p>
    </div>
    <div class="container consult-container">
      <div class="consult-areas">
        <h2 class="section-heading">Areas of Guidance</h2>
        <div class="consult-topics-grid">
          <div class="consult-topic-card">
            <div class="topic-icon">💼</div>
            <div class="topic-name">Career &amp; Profession</div>
            <p>Understand your strengths, timing and planetary support for career growth.</p>
          </div>
          <div class="consult-topic-card">
            <div class="topic-icon">💍</div>
            <div class="topic-name">Marriage &amp; Relationships</div>
            <p>Compatibility analysis, auspicious timing and remedies for harmony.</p>
          </div>
          <div class="consult-topic-card">
            <div class="topic-icon">🏠</div>
            <div class="topic-name">Family &amp; Children</div>
            <p>Guidance on family matters, children's education and ancestral karma.</p>
          </div>
          <div class="consult-topic-card">
            <div class="topic-icon">🕉️</div>
            <div class="topic-name">Spiritual Growth</div>
            <p>Discover your dharmic path, ideal mantras and spiritual practices.</p>
          </div>
        </div>
      </div>
      <div class="consult-cta-banner">
        <div class="cta-text">
          <h3>Need Immediate Guidance?</h3>
          <p>Chat directly with our astrologer on WhatsApp for a quick consultation.</p>
        </div>
        <a href="https://wa.me/919999999999?text=Hello%2C%20I%20would%20like%20to%20consult%20an%20astrologer" target="_blank" rel="noopener noreferrer" class="btn-whatsapp">
          <span>💬</span> Chat with Astrologer
        </a>
      </div>
      <div class="consult-form-section">
        <h2 class="section-heading">Book a Consultation</h2>
        <form id="consultForm" novalidate>
          <div class="form-row">
            <div class="form-group">
              <label>Full Name <span class="required">*</span></label>
              <input type="text" id="c-name" class="form-input" placeholder="Your full name" required>
            </div>
            <div class="form-group">
              <label>Email Address <span class="required">*</span></label>
              <input type="email" id="c-email" class="form-input" placeholder="your@email.com" required>
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>Phone Number <span class="required">*</span></label>
              <input type="tel" id="c-phone" class="form-input" placeholder="+91 XXXXX XXXXX" required>
            </div>
            <div class="form-group">
              <label>Preferred Consultation Type <span class="required">*</span></label>
              <select id="c-type" class="form-input" required>
                <option value="">Select type</option>
                <option value="phone">📞 Phone Call</option>
                <option value="personal">🤝 Personal Visit</option>
              </select>
            </div>
          </div>
          <div class="form-group">
            <label>Your Message <span class="required">*</span></label>
            <textarea id="c-message" class="form-input consult-textarea" placeholder="Briefly describe what you would like guidance on..." required></textarea>
          </div>
          <div id="consult-error" class="form-error hidden">Please fill in all required fields.</div>
          <button type="submit" class="btn-primary full-width">Pay &amp; Book Consultation</button>
        </form>
        <div id="consult-success" class="jathakam-success hidden">
          <div class="success-icon">✅</div>
          <h3>Consultation Booked!</h3>
          <p>Thank you! Our astrologer will contact you within 24 hours at your preferred mode.</p>
          <button type="button" class="btn-secondary" id="btnConsultReset">Book Another</button>
        </div>
      </div>
    </div>
  </main>""",
    )

    # contact
    write_page(
        "contact.html",
        "Contact — Tara Astro Vision",
        "contact",
        "contact",
        """  <main class="site-main">
    <div class="page-hero">
      <div class="container">
        <h1>Contact Tara Astro Vision</h1>
        <p>We are here to support your spiritual and astrological journey</p>
      </div>
    </div>
    <div class="container page-body contact-page-wrap">
      <div class="dash-card contact-card">
        <h2 class="section-heading contact-card-title">Get in touch</h2>
        <p class="contact-intro">Reach us by email or phone for bookings, questions, or guidance.</p>
        <p><strong>Email:</strong> <a href="mailto:taraastrovision123@gmail.com">taraastrovision123@gmail.com</a></p>
        <p><strong>Phone:</strong> <a href="tel:9014308190">9014308190</a></p>
        <p class="contact-cta-wrap"><a class="btn-secondary" href="consult.html">Book a consultation</a></p>
      </div>
    </div>
  </main>""",
    )

    # booking
    write_page(
        "booking.html",
        "Booking — Tara Astro Vision",
        "booking",
        "pooja",
        """  <main class="site-main">
    <div class="page-hero">
      <h1 class="page-hero-title">📋 Participant Details</h1>
      <p class="page-hero-sub">Please fill in the details of all participants. The person making the booking must be Participant 1.</p>
    </div>
    <div class="container booking-form-container">
      <div id="bookingSummary" class="booking-summary"></div>
      <form id="bookingParticipantForm" class="booking-form">
        <div id="bookingFormContainer"></div>
        <div id="addParticipantContainer" class="add-participant-container"></div>
        <div id="bookingFormError" class="form-error hidden"></div>
        <button type="submit" class="btn-primary btn-submit-details full-width">Submit Details &amp; Continue to Payment</button>
      </form>
    </div>
  </main>""",
    )

    # payment
    write_page(
        "payment.html",
        "Payment — Tara Astro Vision",
        "payment",
        "pooja",
        """  <main class="site-main">
    <div class="page-hero">
      <h1 class="page-hero-title" id="paymentPageTitle">Secure Payment</h1>
      <p class="page-hero-sub" id="paymentPageSub">Complete your booking</p>
    </div>
    <div class="container payment-page-container">
      <div id="paymentPageContent"></div>
    </div>
  </main>""",
    )

    # confirmation
    write_page(
        "confirmation.html",
        "Booking Confirmed — Tara Astro Vision",
        "confirmation",
        "pooja",
        """  <main class="site-main">
    <div class="page-hero">
      <h1 class="page-hero-title">Booking status</h1>
      <p class="page-hero-sub">Payment has not been completed, so your booking is not confirmed.</p>
    </div>
    <div class="container confirmation-container">
      <div id="confirmationContent"></div>
    </div>
  </main>""",
    )


if __name__ == "__main__":
    main()
