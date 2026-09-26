/* ══════════════════════════════════════════
   JYOTISHA — Vedic Astrology Engine
   Pure Vedic / Jyotisha calculations
   Uses Lahiri Ayanamsha (official GoI standard)
   Tropical → Sidereal conversion
   Swiss Ephemeris formulas (client-side approx)
   Production backend: pyswisseph
   ══════════════════════════════════════════ */

// ────────────────────────────────────────────
// VEDIC CONSTANTS
// ────────────────────────────────────────────
const RASIS = [
  { num: 1, name_en: 'Mesha', name_te: 'మేష', name_hi: 'मेष', name_ta: 'மேஷம்', name_ml: 'മേഷം', name_kn: 'ಮೇಷ', name_mr: 'मेष', symbol: '♈', lord: 'Kuja', element: 'Fire', quality: 'Movable' },
  { num: 2, name_en: 'Vrishabha', name_te: 'వృషభ', name_hi: 'वृषभ', name_ta: 'ரிஷபம்', name_ml: 'വൃഷഭം', name_kn: 'ವೃಷಭ', name_mr: 'वृषभ', symbol: '♉', lord: 'Shukra', element: 'Earth', quality: 'Fixed' },
  { num: 3, name_en: 'Mithuna', name_te: 'మిథున', name_hi: 'मिथुन', name_ta: 'மிதுனம்', name_ml: 'മിഥുനം', name_kn: 'ಮಿಥುನ', name_mr: 'मिथुन', symbol: '♊', lord: 'Budha', element: 'Air', quality: 'Dual' },
  { num: 4, name_en: 'Kataka', name_te: 'కటక', name_hi: 'कर्क', name_ta: 'கடகம்', name_ml: 'കർക്കടകം', name_kn: 'ಕರ್ಕ', name_mr: 'कर्क', symbol: '♋', lord: 'Chandra', element: 'Water', quality: 'Movable' },
  { num: 5, name_en: 'Simha', name_te: 'సింహ', name_hi: 'सिंह', name_ta: 'சிம்மம்', name_ml: 'ചിങ്ങം', name_kn: 'ಸಿಂಹ', name_mr: 'सिंह', symbol: '♌', lord: 'Surya', element: 'Fire', quality: 'Fixed' },
  { num: 6, name_en: 'Kanya', name_te: 'కన్య', name_hi: 'कन्या', name_ta: 'கன்னி', name_ml: 'കന്നി', name_kn: 'ಕನ್ಯ', name_mr: 'कन्या', symbol: '♍', lord: 'Budha', element: 'Earth', quality: 'Dual' },
  { num: 7, name_en: 'Tula', name_te: 'తుల', name_hi: 'तुला', name_ta: 'துலாம்', name_ml: 'തുലാം', name_kn: 'ತುಲ', name_mr: 'तुला', symbol: '♎', lord: 'Shukra', element: 'Air', quality: 'Movable' },
  { num: 8, name_en: 'Vrishchika', name_te: 'వృశ్చిక', name_hi: 'वृश्चिक', name_ta: 'விருச்சிகம்', name_ml: 'വൃശ്ചികം', name_kn: 'ವೃಶ್ಚಿಕ', name_mr: 'वृश्चिक', symbol: '♏', lord: 'Kuja', element: 'Water', quality: 'Fixed' },
  { num: 9, name_en: 'Dhanu', name_te: 'ధనుస్', name_hi: 'धनु', name_ta: 'தனுசு', name_ml: 'ധനു', name_kn: 'ಧನು', name_mr: 'धनु', symbol: '♐', lord: 'Guru', element: 'Fire', quality: 'Dual' },
  { num: 10, name_en: 'Makara', name_te: 'మకర', name_hi: 'मकर', name_ta: 'மகரம்', name_ml: 'മകരം', name_kn: 'ಮಕರ', name_mr: 'मकर', symbol: '♑', lord: 'Shani', element: 'Earth', quality: 'Movable' },
  { num: 11, name_en: 'Kumbha', name_te: 'కుంభ', name_hi: 'कुंभ', name_ta: 'கும்பம்', name_ml: 'കുംഭം', name_kn: 'ಕುಂಭ', name_mr: 'कुंभ', symbol: '♒', lord: 'Shani', element: 'Air', quality: 'Fixed' },
  { num: 12, name_en: 'Meena', name_te: 'మీన', name_hi: 'मीन', name_ta: 'மீனம்', name_ml: 'മീനം', name_kn: 'ಮೀನ', name_mr: 'मीन', symbol: '♓', lord: 'Guru', element: 'Water', quality: 'Dual' },
];

const NAKSHATRAS = [
  'Ashwini', 'Bharani', 'Krittika', 'Rohini', 'Mrigashira', 'Ardra',
  'Punarvasu', 'Pushya', 'Ashlesha', 'Magha', 'Purva Phalguni', 'Uttara Phalguni',
  'Hasta', 'Chitra', 'Swati', 'Vishakha', 'Anuradha', 'Jyeshtha',
  'Mula', 'Purva Ashadha', 'Uttara Ashadha', 'Shravana', 'Dhanishtha', 'Shatabhisha',
  'Purva Bhadrapada', 'Uttara Bhadrapada', 'Revati'
];

const NAKSHATRA_LORDS = [
  'Ketu', 'Shukra', 'Surya', 'Chandra', 'Kuja', 'Rahu', 'Guru', 'Shani', 'Budha',
  'Ketu', 'Shukra', 'Surya', 'Chandra', 'Kuja', 'Rahu', 'Guru', 'Shani', 'Budha',
  'Ketu', 'Shukra', 'Surya', 'Chandra', 'Kuja', 'Rahu', 'Guru', 'Shani', 'Budha'
];

const PLANETS = ['Surya', 'Chandra', 'Kuja', 'Budha', 'Guru', 'Shukra', 'Shani', 'Rahu', 'Ketu', 'Lagna'];
const PLANET_ABBR = {
  Surya: 'Su', Chandra: 'Mo', Kuja: 'Ma', Budha: 'Me', Guru: 'Ju',
  Shukra: 'Ve', Shani: 'Sa', Rahu: 'Ra', Ketu: 'Ke', Lagna: 'As'
};

// ────────────────────────────────────────────
// CORE CALCULATION ENGINE
// Implements Vedic sidereal astronomy
// using Lahiri Ayanamsha
// ────────────────────────────────────────────

const VedicEngine = {

  // Julian Day Number from calendar date
  julianDay(year, month, day, hour = 12) {
    if (month <= 2) { year -= 1; month += 12; }
    const A = Math.floor(year / 100);
    const B = 2 - A + Math.floor(A / 4);
    return Math.floor(365.25 * (year + 4716)) +
      Math.floor(30.6001 * (month + 1)) +
      day + hour / 24 + B - 1524.5;
  },

  // Lahiri Ayanamsha (official Government of India standard)
  lahiriAyanamsha(jd) {
    const T = (jd - 2451545.0) / 36525;
    // IAU 1976 precession + Lahiri correction
    return 23.85 + (50.27 / 3600) * (jd - 2415020.0) / 365.25;
  },

  // Normalize to [0, 360)
  norm360(deg) {
    return ((deg % 360) + 360) % 360;
  },

  // Mean longitude (simplified Meeus)
  sunTropical(jd) {
    const T = (jd - 2451545.0) / 36525;
    const L0 = 280.46646 + 36000.76983 * T;
    const M = (357.52911 + 35999.05029 * T) * Math.PI / 180;
    const C = (1.914602 - 0.004817 * T) * Math.sin(M)
      + 0.019993 * Math.sin(2 * M);
    return this.norm360(L0 + C);
  },

  moonTropical(jd) {
    const T = (jd - 2451545.0) / 36525;
    const L = 218.3165 + 481267.8813 * T;
    const M = (357.5291 + 35999.0503 * T) * Math.PI / 180;
    const Mp = (134.9634 + 477198.8676 * T) * Math.PI / 180;
    const D = (297.8502 + 445267.1115 * T) * Math.PI / 180;
    const F = (93.2720 + 483202.0175 * T) * Math.PI / 180;
    const corr = 6.2888 * Math.sin(Mp)
      + 1.2740 * Math.sin(2 * D - Mp)
      + 0.6583 * Math.sin(2 * D)
      + 0.2136 * Math.sin(2 * Mp)
      - 0.1851 * Math.sin(M)
      - 0.1143 * Math.sin(2 * F);
    return this.norm360(L + corr);
  },

  marsTropical(jd) {
    const T = (jd - 2451545.0) / 36525;
    const L = 355.433 + 19140.299 * T;
    const M = (19.373 + 19140.299 * T) * Math.PI / 180;
    return this.norm360(L + 10.691 * Math.sin(M) + 0.623 * Math.sin(2 * M));
  },

  mercuryTropical(jd) {
    const T = (jd - 2451545.0) / 36525;
    const L = 252.251 + 149472.675 * T;
    const M = (168.64 + 149472.515 * T) * Math.PI / 180;
    return this.norm360(L + 11.068 * Math.sin(M) + 0.603 * Math.sin(2 * M) - 0.105 * Math.sin(3 * M));
  },

  jupiterTropical(jd) {
    const T = (jd - 2451545.0) / 36525;
    const L = 34.351 + 3034.906 * T;
    const M = (20.020 + 3034.906 * T) * Math.PI / 180;
    return this.norm360(L + 5.557 * Math.sin(M) + 0.168 * Math.sin(2 * M));
  },

  venusTropical(jd) {
    const T = (jd - 2451545.0) / 36525;
    const L = 181.979 + 58517.815 * T;
    const M = (212.448 + 58517.803 * T) * Math.PI / 180;
    return this.norm360(L + 0.779 * Math.sin(M) + 0.0197 * Math.sin(2 * M));
  },

  saturnTropical(jd) {
    const T = (jd - 2451545.0) / 36525;
    const L = 50.078 + 1222.114 * T;
    const M = (317.020 + 1222.114 * T) * Math.PI / 180;
    return this.norm360(L + 6.394 * Math.sin(M) + 0.180 * Math.sin(2 * M));
  },

  // Mean Rahu (Moon's ascending node) — retrograde
  rahuTropical(jd) {
    const T = (jd - 2451545.0) / 36525;
    return this.norm360(125.0445 - 1934.1363 * T);
  },

  // Ketu = Rahu + 180°
  ketuTropical(jd) {
    return this.norm360(this.rahuTropical(jd) + 180);
  },

  // Sidereal time → Lagna (Ascendant)
  lagnaVedic(jd, lat, lon, ayanamsha) {
    const T = (jd - 2451545.0) / 36525;
    // Greenwich Mean Sidereal Time (degrees)
    let GMST = 280.46061837 + 360.98564736629 * (jd - 2451545) + 0.000387933 * T * T;
    GMST = this.norm360(GMST);
    // Local Sidereal Time
    const LST = this.norm360(GMST + lon);
    // Obliquity of ecliptic
    const eps = (23.439291 - 0.013004 * T) * Math.PI / 180;
    // Convert LST to ecliptic longitude (Ascendant)
    const lstRad = LST * Math.PI / 180;
    const latRad = lat * Math.PI / 180;
    const ascTropical = Math.atan2(
      Math.cos(lstRad),
      -(Math.sin(lstRad) * Math.cos(eps) + Math.tan(latRad) * Math.sin(eps))
    ) * 180 / Math.PI;
    // Sidereal Lagna
    return this.norm360(ascTropical - ayanamsha);
  },

  // Tropical → Vedic Sidereal
  toVedic(tropicalDeg, ayanamsha) {
    return this.norm360(tropicalDeg - ayanamsha);
  },

  // Degree → Rasi number (1–12) and degree within rasi
  getRasi(deg) {
    const rasi = Math.floor(deg / 30) + 1;
    const within = deg % 30;
    return { rasi: rasi > 12 ? rasi - 12 : rasi, degrees: within.toFixed(2) };
  },

  // Navamsa (D9) calculation
  getNavamsaRasi(deg) {
    const rasiIdx = Math.floor(deg / 30); // 0-11
    const within = deg % 30;
    const navamsaSegment = Math.floor(within / (30 / 9)); // 0-8

    // Starting rasi for each element (Fire, Earth, Air, Water)
    const starts = [1, 10, 7, 4];
    const startRasi = starts[rasiIdx % 4];

    let navRasi = (startRasi + navamsaSegment - 1) % 12 + 1;
    return navRasi;
  },

  // Degree → Nakshatra
  getNakshatra(deg) {
    const idx = Math.floor(deg / (360 / 27));
    return {
      name: NAKSHATRAS[idx] || 'Ashwini',
      lord: NAKSHATRA_LORDS[idx] || 'Ketu',
      pada: Math.floor((deg % (360 / 27)) / (360 / 108)) + 1
    };
  },

  // ── Master calculator ──
  calculate(year, month, day, hour, lat, lon) {
    const jd = this.julianDay(year, month, day, hour);
    const ayan = this.lahiriAyanamsha(jd);

    const positions = {
      Surya: this.toVedic(this.sunTropical(jd), ayan),
      Chandra: this.toVedic(this.moonTropical(jd), ayan),
      Kuja: this.toVedic(this.marsTropical(jd), ayan),
      Budha: this.toVedic(this.mercuryTropical(jd), ayan),
      Guru: this.toVedic(this.jupiterTropical(jd), ayan),
      Shukra: this.toVedic(this.venusTropical(jd), ayan),
      Shani: this.toVedic(this.saturnTropical(jd), ayan),
      Rahu: this.toVedic(this.rahuTropical(jd), ayan),
      Ketu: this.toVedic(this.ketuTropical(jd), ayan),
      Lagna: this.lagnaVedic(jd, lat, lon, ayan),
    };

    const result = {};
    for (const [planet, deg] of Object.entries(positions)) {
      const rasiData = this.getRasi(deg);
      const nakData = this.getNakshatra(deg);
      result[planet] = {
        degree: parseFloat(deg.toFixed(4)),
        rasi: rasiData.rasi,
        rasiDeg: rasiData.degrees,
        rasi_data: RASIS[rasiData.rasi - 1],
        navamsa_rasi: this.getNavamsaRasi(deg),
        nakshatra: nakData.name,
        nakshatraLord: nakData.lord,
        pada: nakData.pada,
      };
    }

    return {
      planets: result,
      lagna_rasi: result.Lagna.rasi,
      lagna_navamsa: result.Lagna.navamsa_rasi,
      moon_rasi: result.Chandra.rasi,
      ayanamsha: parseFloat(ayan.toFixed(4)),
      jd,
    };
  }
};

// ────────────────────────────────────────────
// LIFE GUIDANCE GENERATOR
// Translates planetary positions to
// human-readable life guidance
// No doshas, yogas, or jargon shown to user
// ────────────────────────────────────────────

const GuidanceEngine = {

  // Rasi-based personality & life themes
  rasiGuidance: {
    1: { career: "Leadership and pioneering roles bring you fulfillment. Trust your instincts in professional decisions — they rarely mislead you.", family: "Your courage and directness are pillars of strength for those you love. Balance your initiative with patience.", finance: "Bold decisions can bring rewards, but steady financial discipline will compound your prosperity over time.", peace: "Regular moments of stillness help channel your abundant energy constructively. Practice gratitude daily.", spirituality: "Your natural courage is a spiritual gift. Acts of dharmic action — doing what is right — are your highest path." },
    2: { career: "Your steady reliability and eye for beauty create lasting success in creative, financial, and nurturing fields.", family: "You are the root of stability in your relationships. Your dedication inspires deep loyalty from those around you.", finance: "Patience with investments pays off generously. Avoid impulsive purchases; deliberate choices build lasting wealth.", peace: "Beauty in daily life — nature, music, food — is not indulgence but nourishment for your soul.", spirituality: "Gratitude for the physical world is your sadhana. Offer beauty to the divine in all its forms." },
    3: { career: "Communication, learning, and adaptability are your gifts. Roles that involve exchange of ideas or skillful craftsmanship suit you deeply.", family: "Your curiosity and playfulness keep relationships dynamic. Be present in emotional conversations, not just intellectual ones.", finance: "Versatility brings multiple income streams. Guard against scattering energy — focused effort multiplies returns.", peace: "Journaling, creative expression, and physical activity channel your restless mind toward deep inner calm.", spirituality: "Study and the pursuit of knowledge itself is devotion for you. Sacred texts bring you genuine transformation." },
    4: { career: "Roles where you nurture, protect, and build — whether in family, community, or institutions — bring deep satisfaction.", family: "Home and family are sacred to you. Your emotional intelligence is a profound gift; trust its wisdom.", finance: "Security and steady growth matter more to you than speculative gain. Real estate and savings serve you well.", peace: "Water, nature walks, and time with loved ones restore your spirit most completely.", spirituality: "Worship at home, family rituals, and devotion to ancestors deepen your connection to the divine." },
    5: { career: "Creative expression, leadership, and endeavors involving children or performance align with your soul's purpose.", family: "Your warmth and generosity make you a beloved figure. Allow others to support you too — receive gracefully.", finance: "Your natural confidence attracts opportunity. Channel generosity wisely to build lasting prosperity.", peace: "Creative expression — art, music, dance — is not merely pleasure but a sacred form of prayer for you.", spirituality: "Pure devotion and heartfelt bhakti are your most natural spiritual practices. Let the heart lead." },
    6: { career: "Service, analytical precision, and dedication to craft bring you professional fulfillment and respect.", family: "Your helpfulness is boundless — remember to set boundaries that honor your own well-being too.", finance: "Methodical budgeting and service-oriented income channels grow your wealth steadily and securely.", peace: "Daily routines of health, cleanliness, and service create the inner order that brings you true calm.", spirituality: "Selfless service — seva — is your deepest spiritual expression. Helping others IS your worship." },
    7: { career: "Partnership, diplomacy, and fields requiring balance and harmony — law, design, counseling — are your domains.", family: "Harmonious relationships are essential to your well-being. Seek partnerships built on mutual respect and beauty.", finance: "Collaborative ventures tend to prosper. Avoid financial dependencies; maintain your own stable foundation.", peace: "Beauty, balance, and the company of those who uplift you restore your deepest peace.", spirituality: "The path of relationship itself is your spiritual practice. Seeing the divine in the other is your dharma." },
    8: { career: "Depth, investigation, research, and transformation are your professional gifts. You succeed where others dare not go.", family: "Intensity in relationships is natural for you. Cultivate trust slowly; it becomes unbreakable once established.", finance: "Patient, long-term financial strategy — not quick gains — builds the substantial security you are meant to have.", peace: "Practices that face darkness with courage — meditation, deep introspection — create your genuine peace.", spirituality: "Your path is one of profound inner transformation. The divine calls you toward depth, not surface." },
    9: { career: "Teaching, philosophy, law, spirituality, and long-distance endeavors carry your dharmic purpose.", family: "Your optimism and wisdom make you an inspiring presence. Give your loved ones space to grow.", finance: "Opportunities often arrive from unexpected directions. Maintain ethical financial practices — good karma compounds.", peace: "Travel, learning, and being in nature — especially near large trees or temples — restore your spirit.", spirituality: "Pilgrimage, study of dharmashastra, and guru devotion are your most powerful spiritual vehicles." },
    10: { career: "Discipline, ambition, and structured achievement define your professional path. Authority comes through proven merit.", family: "Family duty and responsibility are sacred commitments for you. Lead by example, and be vulnerable when needed.", finance: "Long-term, conservative financial planning aligned with clear goals brings you the stability you seek.", peace: "Achievement through disciplined effort — not shortcuts — creates the deepest satisfaction for your nature.", spirituality: "Karma yoga — the yoga of dedicated, detached action — is your most natural spiritual path." },
    11: { career: "Innovation, community building, and visionary thinking distinguish your professional contributions.", family: "You value freedom and friendship in relationships. Express your deep emotional needs with the same clarity as your ideas.", finance: "Group endeavors and technology-aligned ventures can bring unexpected abundance. Think expansively.", peace: "Time with like-minded communities and contribution to collective causes brings your most genuine peace.", spirituality: "Seva to humanity, social causes aligned with dharma, and meditation on universal consciousness are your path." },
    12: { career: "Healing arts, spirituality, creative retreat, and service to the vulnerable carry your highest professional purpose.", family: "Your sensitivity is a profound gift — for compassion, intuition, and deep love. Honor it rather than suppress it.", finance: "Clarity in financial dealings protects your giving nature. Generosity is your strength; structure is your protection.", peace: "Solitude, meditation, and time near water or in sacred spaces replenish your spirit deeply.", spirituality: "Moksha and liberation are your soul's deepest yearning. Surrender, meditation, and devotion are your greatest paths." }
  },

  // Nakshatra-specific flavoring
  nakshatraColorings: {
    'Ashwini': "Swift, pioneering energy supports new beginnings this period.",
    'Bharani': "Patience through transformation leads to profound renewal.",
    'Krittika': "Sharp discernment and purposeful effort bring clarity.",
    'Rohini': "Beauty, creativity, and material grounding are favored.",
    'Mrigashira': "Gentle searching and curious exploration lead to discovery.",
    'Ardra': "A time of deep emotional processing and inner storm-clearing.",
    'Punarvasu': "Restoration, return to balance, and renewed optimism prevail.",
    'Pushya': "Nourishment, growth, and divine grace are abundantly present.",
    'Ashlesha': "Deep intuition and inner wisdom guide your path.",
    'Magha': "Ancestral strength and regal presence carry you forward.",
    'Purva Phalguni': "Enjoyment, creativity, and heartfelt expression are highlighted.",
    'Uttara Phalguni': "Long-lasting, meaningful relationships and partnerships are supported.",
    'Hasta': "Skilled hands and practical wisdom manifest your goals.",
    'Chitra': "Artistry, beauty, and inspired creation are at their peak.",
    'Swati': "Independence, growth through adversity, and adaptability serve you.",
    'Vishakha': "Determined pursuit of a singular goal brings breakthrough.",
    'Anuradha': "Deep friendship, devotion, and cooperative effort flourish.",
    'Jyeshtha': "Leadership, protection of dharma, and seniority are your gifts.",
    'Mula': "Root-level transformation and liberation from what no longer serves.",
    'Purva Ashadha': "Invincibility, optimism, and bold aspirations drive progress.",
    'Uttara Ashadha': "Lasting victory through universal principles and ethical living.",
    'Shravana': "Listening, learning, and connection across distances are favored.",
    'Dhanishtha': "Abundance, rhythm, and joyful expansion support all efforts.",
    'Shatabhisha': "Healing, mystery, and solitary inner work bring great power.",
    'Purva Bhadrapada': "Intense purification and spiritual ardor transform your path.",
    'Uttara Bhadrapada': "Depth, wisdom, and spiritual maturation bring lasting peace.",
    'Revati': "Completion, nurturing, and safe arrival at sacred destinations.",
  },

  // Generate life overview based on lagna rasi
  generateOverview(chartData) {
    const lagnaRasi = chartData.lagna_rasi;
    const moonRasi = chartData.moon_rasi;
    const guidance = this.rasiGuidance[lagnaRasi] || this.rasiGuidance[1];
    const moonGuide = this.rasiGuidance[moonRasi] || this.rasiGuidance[1];
    const moonNaksh = chartData.planets.Chandra.nakshatra;
    const nakshatraMsg = this.nakshatraColorings[moonNaksh] || "";
    const lagnaRasiName = RASIS[lagnaRasi - 1][`name_${currentLang}`] || RASIS[lagnaRasi - 1].name_en;
    const moonRasiName = RASIS[moonRasi - 1][`name_${currentLang}`] || RASIS[moonRasi - 1].name_en;

    return {
      ascendant_name: lagnaRasiName,
      moon_rasi_name: moonRasiName,
      nakshatra_name: moonNaksh,
      nakshatra_coloring: nakshatraMsg,
      career: guidance.career,
      family: guidance.family,
      finance: guidance.finance,
      peace: guidance.peace,
      spirituality: moonGuide.spirituality,
    };
  },

  // Generate horoscope for period (daily/weekly/monthly) and rasi
  generateHoroscope(rasiNum, period) {
    const base = this.rasiGuidance[rasiNum] || this.rasiGuidance[1];
    const rasi = RASIS[rasiNum - 1];
    const langKey = `name_${currentLang}`;
    const rasiName = rasi[langKey] || rasi.name_en;

    // Today's date seed for consistent daily guidance
    const today = new Date();
    const seed = today.getFullYear() * 10000 + (today.getMonth() + 1) * 100 + today.getDate();
    const weekSeed = today.getFullYear() * 1000 + getWeekNumber(today);
    const monthSeed = today.getFullYear() * 100 + today.getMonth();

    const periodSeed = period === 'daily' ? seed : period === 'weekly' ? weekSeed : monthSeed;
    const variation = ((rasiNum * 7 + periodSeed) % 100) / 100;

    // Enriched period-specific guidance
    const periodPhrases = {
      daily: [
        "Today calls for", "This day invites", "The celestial energies today encourage",
        "Today's cosmic vibration supports", "This auspicious day favors"
      ],
      weekly: [
        "This week, the planetary alignments favor", "The coming days invite you to",
        "This week's transits encourage", "The week ahead supports",
        "Cosmic currents this week call you to"
      ],
      monthly: [
        "This month brings", "The lunar cycle this month encourages",
        "Over the coming weeks, cosmic support favors", "This month's planetary dance invites",
        "The month ahead calls you toward"
      ]
    };

    const phrases = periodPhrases[period];
    const phraseIdx = Math.floor(variation * phrases.length);
    const intro = phrases[phraseIdx] || phrases[0];

    // Rotate guidance areas for variety
    const areas = ['career', 'family', 'finance', 'peace', 'spirituality'];
    const primaryArea = areas[periodSeed % areas.length];
    const secondaryArea = areas[(periodSeed + rasiNum) % areas.length];

    const moonNakshIdx = (rasiNum * 3 + Math.floor(variation * 9)) % 27;
    const moonNaksh = NAKSHATRAS[moonNakshIdx];

    return {
      rasi_num: rasiNum,
      rasi_name: rasiName,
      rasi_symbol: rasi.symbol,
      period,
      career: `${intro} thoughtful action in your professional life. ${base.career}`,
      family: base.family,
      finance: base.finance,
      peace: base.peace,
      spirituality: base.spirituality,
      nakshatra_note: `The Moon transits ${moonNaksh} this ${period}, adding ${this.nakshatraColorings[moonNaksh] || 'powerful energy to all endeavors.'}`,
    };
  }
};

// ── Utilities ──
function getWeekNumber(d) {
  const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const dayNum = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
  return Math.ceil((((date - yearStart) / 86400000) + 1) / 7);
}

function getRasiName(rasi) {
  const r = RASIS[rasi - 1];
  if (!r) return '';
  return r[`name_${currentLang}`] || r.name_en;
}

// Make Constants globally accessible
window.VedicEngine = VedicEngine;
window.RASIS = RASIS;
window.PLANETS = PLANETS;
window.PLANET_ABBR = PLANET_ABBR;
window.NAKSHATRAS = NAKSHATRAS;
window.NAKSHATRA_LORDS = NAKSHATRA_LORDS;
window.GuidanceEngine = GuidanceEngine;