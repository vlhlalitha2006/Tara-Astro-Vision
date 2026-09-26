/* ══════════════════════════════════════════
   JYOTISHA — Application Controller
   Page routing, UI interactions, Kundli flow
   ══════════════════════════════════════════ */

// ────────────────────────────────────────────
// PAGE ROUTING
// ────────────────────────────────────────────
function showPage(pageId) {
  document.querySelectorAll('.page').forEach(p => {
    p.classList.remove('active');
    p.classList.add('hidden');
  });

  const target = document.getElementById(`page-${pageId}`);
  if (target) {
    target.classList.remove('hidden');
    target.classList.add('active');
    window.scrollTo(0, 0);
  }

  // Update nav active states
  document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));

  // Close mobile nav
  document.getElementById('navLinks').classList.remove('open');

  // Page-specific init
  if (pageId === 'dashboard') {
    const user = AUTH.getUser();
    if (user) loadDashboard(user);
  }
}

function toggleNav() {
  document.getElementById('navLinks').classList.toggle('open');
}

// ────────────────────────────────────────────
// MODAL MANAGEMENT
// ────────────────────────────────────────────
let activeModal = null;

function showModal(id) {
  if (activeModal) {
    const prev = document.getElementById(`modal-${activeModal}`);
    if (prev) prev.classList.add('hidden');
  }

  const overlay = document.getElementById('modalOverlay');
  const modal = document.getElementById(`modal-${id}`);

  if (!modal) return;

  overlay.classList.remove('hidden');
  modal.classList.remove('hidden');
  activeModal = id;

  // Clear errors
  const err = modal.querySelector('.modal-error');
  if (err) err.classList.add('hidden');
}

function closeModal() {
  const overlay = document.getElementById('modalOverlay');
  overlay.classList.add('hidden');
  if (activeModal) {
    const modal = document.getElementById(`modal-${activeModal}`);
    if (modal) modal.classList.add('hidden');
    activeModal = null;
  }
}

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeModal();
});

// ────────────────────────────────────────────
// RASI GRID (Home page)
// ────────────────────────────────────────────
function renderRasiGrid() {
  const grid = document.getElementById('rasiGrid');
  if (!grid) return;

  const langKey = `name_${currentLang}`;
  const descriptions = {
    1: 'Courageous & bold', 2: 'Steadfast & sensual', 3: 'Curious & communicative',
    4: 'Nurturing & intuitive', 5: 'Creative & generous', 6: 'Analytical & service-oriented',
    7: 'Harmonious & diplomatic', 8: 'Intense & transformative', 9: 'Philosophical & expansive',
    10: 'Disciplined & ambitious', 11: 'Innovative & humanitarian', 12: 'Mystical & compassionate'
  };

  grid.innerHTML = RASIS.map(r => `
    <div class="rasi-card" onclick="window.scrollTo(0,0); showPage('horoscope'); setTimeout(()=>selectRasi(${r.num}), 300)">
      <span class="rasi-symbol">${r.symbol}</span>
      <span class="rasi-name">${r[langKey] || r.name_en}</span>
      <span class="rasi-sanskrit" style="font-size:11px;color:var(--text-muted)">${descriptions[r.num]}</span>
    </div>
  `).join('');
}

// ────────────────────────────────────────────
// HOROSCOPE PAGE
// ────────────────────────────────────────────
let selectedRasi = null;
let selectedPeriod = 'daily';

function renderRasiChips() {
  const chips = document.getElementById('rasiChips');
  if (!chips) return;

  const langKey = `name_${currentLang}`;
  chips.innerHTML = RASIS.map(r => `
    <div class="rasi-chip ${selectedRasi === r.num ? 'active' : ''}" onclick="selectRasi(${r.num})">
      <span>${r.symbol}</span>
      <span>${r[langKey] || r.name_en}</span>
    </div>
  `).join('');
}

function selectRasi(num) {
  selectedRasi = num;
  renderRasiChips();
  renderHoroscopeCard(selectedRasi, selectedPeriod);
}

function switchTab(period, btn) {
  selectedPeriod = period;
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  if (selectedRasi) renderHoroscopeCard(selectedRasi, selectedPeriod);
}

// ────────────────────────────────────────────
// KUNDLI PAGE
// ────────────────────────────────────────────
let currentChartData = null;
let currentChartStyle = 'south'; // 'south' | 'north'

function setChartStyle(style) {
  currentChartStyle = style;
  document.querySelectorAll('.style-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(`btn-${style}`).classList.add('active');

  if (currentChartData) {
    renderAllCharts();
  }
}

function renderAllCharts() {
  if (!currentChartData) return;

  const lagnaContainer = 'lagnaChartContainer';
  const navamsaContainer = 'navamsaChartContainer';

  if (currentChartStyle === 'south') {
    renderSouthIndianChart(currentChartData, lagnaContainer, 'lagna');
    renderSouthIndianChart(currentChartData, navamsaContainer, 'navamsa');
  } else {
    renderNorthIndianChart(currentChartData, lagnaContainer, 'lagna');
    renderNorthIndianChart(currentChartData, navamsaContainer, 'navamsa');
  }
}

async function generateKundli(e) {
  e.preventDefault();

  const dob = document.getElementById('dob').value;
  const tob = document.getElementById('tob').value;
  const lat = parseFloat(document.getElementById('lat').value);
  const lon = parseFloat(document.getElementById('lon').value);
  const tz = parseFloat(document.getElementById('timezone').value);

  if (!dob || !tob) {
    alert('Please enter date and time of birth');
    return;
  }

  if (isNaN(lat) || isNaN(lon)) {
    alert('Please select a valid place of birth from the suggestions');
    return;
  }

  showModal('loading');

  // Calculate UTC time
  const [year, month, day] = dob.split('-').map(Number);
  const [h, m] = tob.split(':').map(Number);
  const hourUTC = h + m / 60 - tz;

  // Small delay for UX feedback, then calculate
  await new Promise(r => setTimeout(r, 1400));

  try {
    const chartData = VedicEngine.calculate(year, month, day, hourUTC, lat, lon);
    currentChartData = chartData;

    closeModal();
    showKundliResult();
    renderAllCharts();
    renderPlanetTable(chartData);
    renderLifeOverview(chartData);

    // Save chart for logged-in user
    const pob = document.getElementById('pob').value;
    const user = AUTH.getUser();
    if (user) {
      saveChart({
        name: `${pob} — ${dob}`,
        dob, tob, lat, lon,
        lagna: chartData.lagna_rasi,
        moon: chartData.moon_rasi,
      });
    }

  } catch (err) {
    closeModal();
    console.error('Kundli error:', err);
    alert('An error occurred during calculation. Please try again.');
  }
}

function showKundliResult() {
  document.getElementById('kundliFormSection').classList.remove('hidden');
  document.getElementById('kundliResult').classList.remove('hidden');
}

function showKundliForm() {
  document.getElementById('kundliResult').classList.add('hidden');
}

// ────────────────────────────────────────────
// CITY AUTOCOMPLETE
// Uses OpenStreetMap Nominatim (free, no key)
// ────────────────────────────────────────────
let cityTimeout = null;

// South Indian grid positions (row, col) for each Rasi number 1–12
const SI_POSITIONS = {
  1: [0, 1], 2: [0, 2], 3: [0, 3], 4: [1, 3], 5: [2, 3], 6: [3, 3],
  7: [3, 2], 8: [3, 1], 9: [3, 0], 10: [2, 0], 11: [1, 0], 12: [0, 0],
};

const PLANET_COLORS = {
  Surya: '#FF9800', Chandra: '#3F51B5', Kuja: '#F44336', Budha: '#4CAF50',
  Guru: '#C9962B', Shukra: '#E91E63', Shani: '#000000', Rahu: '#000000',
  Ketu: '#000000', Lagna: '#9C27B0'
};

function renderSouthIndianChart(chartData, containerId, type = 'lagna') {
  const container = document.getElementById(containerId);
  if (!container) return;

  const grid = Array.from({ length: 4 }, () => Array(4).fill(null));
  const planetsKey = type === 'lagna' ? 'rasi' : 'navamsa_rasi';

  for (let rasi = 1; rasi <= 12; rasi++) {
    const [row, col] = SI_POSITIONS[rasi];
    const rasiObj = RASIS[rasi - 1];
    const planets = [];

    for (const [planet, data] of Object.entries(chartData.planets)) {
      if (data[planetsKey] === rasi) {
        let label = PLANET_ABBR[planet] || planet.slice(0, 2);
        if (planet === 'Rahu' || planet === 'Ketu') label += '(R)';
        planets.push({
          name: planet,
          label: `${label}-${data.rasiDeg}°`,
          color: PLANET_COLORS[planet] || 'var(--gold-light)'
        });
      }
    }
    grid[row][col] = { rasi, rasiObj, planets };
  }

  const chartLagna = type === 'lagna' ? chartData.lagna_rasi : chartData.lagna_navamsa;
  const langKey = `name_${currentLang}`;

  let html = '<div class="si-grid">';
  for (let row = 0; row < 4; row++) {
    for (let col = 0; col < 4; col++) {
      if ((row === 1 || row === 2) && (col === 1 || col === 2)) {
        html += '<div class="si-cell center"></div>';
        continue;
      }
      const cell = grid[row][col];
      if (!cell) {
        html += '<div class="si-cell"></div>';
        continue;
      }
      const { rasi, rasiObj, planets } = cell;
      const isLagna = rasi === chartLagna;
      const rasiName = rasiObj[langKey] || rasiObj.name_en;

      const planetsHtml = planets.length
        ? `<div class="si-planets">${planets.map(p =>
          `<span class="si-planet${p.name === 'Lagna' ? ' lagna-tag' : ''}" style="color:${p.color}; border-color:${p.color}33; background:${p.color}11">${p.label}</span>`
        ).join('')}</div>`
        : '';

      html += `
        <div class="si-cell${isLagna ? ' lagna-cell' : ''}">
          <span class="si-rasi-num">${rasi}</span>
          <span class="si-rasi-name">${rasiName}</span>
          ${planetsHtml}
        </div>`;
    }
  }
  html += '</div>';
  container.innerHTML = html;
}

// ────────────────────────────────────────────
// NORTH INDIAN CHART RENDERER (Diamond Style)
// ────────────────────────────────────────────
function renderNorthIndianChart(chartData, containerId, type = 'lagna') {
  const container = document.getElementById(containerId);
  if (!container) return;

  const lagnaRasi = type === 'lagna' ? chartData.lagna_rasi : chartData.lagna_navamsa;
  const planetsKey = type === 'lagna' ? 'rasi' : 'navamsa_rasi';

  // Map planets to rasis
  const rasiToPlanets = {};
  for (const [planet, data] of Object.entries(chartData.planets)) {
    const r = data[planetsKey];
    if (!rasiToPlanets[r]) rasiToPlanets[r] = [];
    let label = PLANET_ABBR[planet];
    if (planet === 'Rahu' || planet === 'Ketu') label += '(R)';
    rasiToPlanets[r].push({
      name: planet,
      label: `${label}-${data.rasiDeg}°`,
      color: PLANET_COLORS[planet] || 'var(--gold-light)'
    });
  }

  // House vertices and text labels (Anti-clockwise)
  // Square size: 400x400
  const S = 400;
  const M = S / 2;

  // Paths for 12 houses (not used in this specific rendering, but kept for context if needed)
  const houses = [
    { id: 1, path: `M ${M},${M} L ${M / 2},${M / 2} L ${M},0 L ${3 * M / 2},${M / 2} Z` }, // Top diamond
    { id: 2, path: `M 0,0 L ${M},0 L ${M / 2},${M / 2} Z` },                        // Top left tri
    { id: 3, path: `M 0,0 L 0,${M} L ${M / 2},${M / 2} Z` },                        // Left top tri
    { id: 4, path: `M ${M},${M} L ${M / 2},${M / 2} L 0,${M} L ${M / 2},${3 * M / 2} Z` }, // Left diamond
    { id: 5, path: `M 0,${S} L 0,${M} L ${M / 2},${3 * M / 2} Z` },                      // Left bot tri
    { id: 6, path: `M 0,${S} L ${M},${S} L ${M / 2},${3 * M / 2} Z` },                   // Bot left tri
    { id: 7, path: `M ${M},${M} L ${M / 2},${3 * M / 2} L ${M},${S} L ${3 * M / 2},${3 * M / 2} Z` }, // Bot diamond
    { id: 8, path: `M ${S},${S} L ${M},${S} L ${3 * M / 2},${3 * M / 2} Z` },               // Bot right tri
    { id: 9, path: `M ${S},${S} L ${S},${M} L ${3 * M / 2},${3 * M / 2} Z` },               // Right bot tri
    { id: 10, path: `M ${M},${M} L ${3 * M / 2},${3 * M / 2} L ${S},${M} L ${3 * M / 2},${M / 2} Z` }, // Right diamond
    { id: 11, path: `M ${S},0 L ${S},${M} L ${3 * M / 2},${M / 2} Z` },                    // Right top tri
    { id: 12, path: `M ${S},0 L ${M},0 L ${3 * M / 2},${M / 2} Z` },                       // Top right tri
  ];

  // Helper for text positioning (House number labels)
  const labels = [
    { x: M, y: M / 2 - 55 },  // 1
    { x: M / 2 + 30, y: 55 },  // 2
    { x: 30, y: M / 2 + 30 },  // 3
    { x: M / 2 - 55, y: M },   // 4
    { x: 30, y: 3 * M / 2 - 30 },// 5
    { x: M / 2 + 30, y: S - 55 },// 6
    { x: M, y: 3 * M / 2 + 55 }, // 7
    { x: 3 * M / 2 - 30, y: S - 55 }, // 8
    { x: S - 30, y: 3 * M / 2 - 30 }, // 9
    { x: 3 * M / 2 + 55, y: M },      // 10
    { x: S - 30, y: M / 2 + 30 },   // 11
    { x: 3 * M / 2 - 30, y: 55 },     // 12
  ];

  // Planet display offset within house center
  const pOffsets = [
    { x: M, y: M / 2 },
    { x: M / 2, y: M / 4 },
    { x: M / 4, y: M / 2 },
    { x: M / 2, y: M },
    { x: M / 4, y: 3 * M / 2 },
    { x: M / 2, y: S - M / 4 },
    { x: M, y: 3 * M / 2 },
    { x: 3 * M / 2, y: S - M / 4 },
    { x: S - M / 4, y: 3 * M / 2 },
    { x: 3 * M / 2, y: M },
    { x: S - M / 4, y: M / 2 },
    { x: 3 * M / 2, y: M / 4 },
  ];

  let svg = `<svg viewBox="0 0 ${S} ${S}" class="ni-svg" xmlns="http://www.w3.org/2000/svg">
    <rect x="0" y="0" width="${S}" height="${S}" fill="none" stroke="currentColor" stroke-width="2"/>
    <line x1="0" y1="0" x2="${S}" y2="${S}" stroke="currentColor" />
    <line x1="${S}" y1="0" x2="0" y2="${S}" stroke="currentColor" />
    <path d="M ${M},0 L 0,${M} L ${M},${S} L ${S},${M} Z" stroke="currentColor" />`;

  for (let i = 0; i < 12; i++) {
    const houseNum = i + 1;
    const rasi = (lagnaRasi + houseNum - 2) % 12 + 1;
    const planets = rasiToPlanets[rasi] || [];

    // Rasi Label (House Number in NI style)
    svg += `<text x="${labels[i].x}" y="${labels[i].y}" text-anchor="middle" class="ni-house-num">${rasi}</text>`;

    if (planets.length > 0) {
      const px = pOffsets[i].x;
      const py = pOffsets[i].y;
      planets.forEach((p, idx) => {
        const offset = idx * 14 - (planets.length - 1) * 7;
        svg += `<text x="${px}" y="${py + offset}" text-anchor="middle" class="ni-planet ${p.name === 'Lagna' ? 'ni-lagna' : ''}" style="fill:${p.color}">${p.label}</text>`;
      });
    }
  }

  svg += '</svg>';
  container.innerHTML = svg;
}

function renderPlanetTable(chartData) {
  const container = document.getElementById('planetInfo');
  if (!container) return;

  const langKey = `name_${currentLang}`;

  let html = `<h3>${t('planet_positions')}</h3>
  <table class="planet-table">
    <thead>
      <tr>
        <th>${t('planet')}</th>
        <th>${t('rasi')}</th>
        <th>${t('nakshatra')}</th>
        <th>${t('degree')}</th>
      </tr>
    </thead>
    <tbody>`;

  const planetOrder = ['Lagna', 'Surya', 'Chandra', 'Kuja', 'Budha', 'Guru', 'Shukra', 'Shani', 'Rahu', 'Ketu'];
  for (const planet of planetOrder) {
    const data = chartData.planets[planet];
    if (!data) continue;
    const rasiName = data.rasi_data[langKey] || data.rasi_data.name_en;
    html += `<tr>
      <td>${planet}</td>
      <td>${rasiName}</td>
      <td>${data.nakshatra}</td>
      <td>${data.rasiDeg}°</td>
    </tr>`;
  }

  html += '</tbody></table>';
  container.innerHTML = html;
}

function renderLifeOverview(chartData) {
  const container = document.getElementById('lifeOverview');
  if (!container) return;

  const overview = GuidanceEngine.generateOverview(chartData);
  const langKey = `name_${currentLang}`;

  const areas = [
    { key: 'career', icon: '✦', label: t('career_area') },
    { key: 'family', icon: '⚘', label: t('family_area') },
    { key: 'finance', icon: '❈', label: t('finance_area') },
    { key: 'peace', icon: '☽', label: t('peace_area') },
    { key: 'spirituality', icon: 'ॐ', label: t('spirituality_area') },
  ];

  let html = `
    <h3>${t('life_overview')}</h3>
    <div class="asc-banner">
      <div class="asc-label">Lagna — Ascendant</div>
      <div class="asc-value">${overview.ascendant_name}</div>
      <div class="asc-sub">Moon in ${overview.moon_rasi_name} · ${overview.nakshatra_name} Nakshatra</div>
    </div>
    ${overview.nakshatra_coloring ? `<div class="horo-nakshatra">${overview.nakshatra_coloring}</div>` : ''}
    <div class="overview-grid">`;

  for (const area of areas) {
    html += `
      <div class="overview-item">
        <div class="overview-area">${area.icon} ${area.label}</div>
        <div class="overview-text">${overview[area.key]}</div>
      </div>`;
  }

  html += '</div>';
  container.innerHTML = html;
}

function renderHoroscopeCard(rasiNum, period) {
  const horo = GuidanceEngine.generateHoroscope(rasiNum, period);
  const container = document.getElementById('horoDisplay');
  if (!container) return;

  const today = new Date();
  let dateRange;
  if (period === 'daily') {
    dateRange = today.toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  } else if (period === 'weekly') {
    const end = new Date(today); end.setDate(today.getDate() + 6);
    dateRange = `${today.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })} – ${end.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}`;
  } else {
    dateRange = today.toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });
  }

  const areas = [
    { key: 'career', icon: '✦', label: t('career_area') },
    { key: 'family', icon: '⚘', label: t('family_area') },
    { key: 'finance', icon: '❈', label: t('finance_area') },
    { key: 'peace', icon: '☽', label: t('peace_area') },
    { key: 'spirituality', icon: 'ॐ', label: t('spirituality_area') },
  ];

  let html = `
    <div class="horo-card">
      <div class="horo-header">
        <span class="horo-rasi-symbol">${horo.rasi_symbol}</span>
        <div class="horo-rasi-info">
          <h2>${horo.rasi_name}</h2>
          <p>${period.charAt(0).toUpperCase() + period.slice(1)} Guidance — Vedic</p>
        </div>
        <div class="horo-date-range">${dateRange}</div>
      </div>
      <div class="guidance-grid">`;

  for (const area of areas) {
    html += `
      <div class="guidance-card">
        <div class="guidance-area">${area.icon} ${area.label}</div>
        <div class="guidance-text">${horo[area.key]}</div>
      </div>`;
  }

  html += `</div>
      <div class="horo-nakshatra">${horo.nakshatra_note}</div>
    </div>`;

  container.innerHTML = html;
}

async function searchCity(query) {
  clearTimeout(cityTimeout);
  const dropdown = document.getElementById('cityDropdown');

  if (!query || query.length < 3) {
    dropdown.classList.add('hidden');
    return;
  }

  cityTimeout = setTimeout(async () => {
    try {
      const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}&format=json&limit=6&addressdetails=1`;
      const res = await fetch(url, {
        headers: { 'Accept-Language': 'en' }
      });
      const data = await res.json();

      if (!data.length) {
        dropdown.classList.add('hidden');
        return;
      }

      dropdown.innerHTML = data.map(item => {
        const display = item.display_name.split(',').slice(0, 3).join(',');
        return `<div class="city-option" onclick="selectCity('${escapeStr(display)}', ${item.lat}, ${item.lon})">
          ${display}
        </div>`;
      }).join('');

      dropdown.classList.remove('hidden');
    } catch (err) {
      console.warn('City search error:', err);
      dropdown.classList.add('hidden');
    }
  }, 350);
}

function selectCity(name, lat, lon) {
  document.getElementById('pob').value = name;
  document.getElementById('lat').value = parseFloat(lat).toFixed(4);
  document.getElementById('lon').value = parseFloat(lon).toFixed(4);
  document.getElementById('cityDropdown').classList.add('hidden');

  // Auto-detect timezone from longitude
  const tzOffset = Math.round(lon / 15 * 2) / 2;
  const tzSelect = document.getElementById('timezone');
  // Try to match common Indian timezones
  if (lon > 65 && lon < 100) {
    setSelectByValue(tzSelect, '5.5'); // IST
  } else {
    setSelectByValue(tzSelect, tzOffset.toString());
  }
}

function setSelectByValue(select, value) {
  for (const opt of select.options) {
    if (opt.value === value) {
      select.value = value;
      return;
    }
  }
}

function escapeStr(s) {
  return s.replace(/'/g, "\\'").replace(/"/g, '\\"');
}

// Close city dropdown on outside click
document.addEventListener('click', e => {
  const pob = document.getElementById('pob');
  const dd = document.getElementById('cityDropdown');
  if (pob && dd && !pob.contains(e.target) && !dd.contains(e.target)) {
    dd.classList.add('hidden');
  }
});

// ────────────────────────────────────────────
// STARS BACKGROUND
// ────────────────────────────────────────────
function renderStars() {
  const bg = document.getElementById('starsBg');
  if (!bg) return;

  let html = '';
  for (let i = 0; i < 180; i++) {
    const x = Math.random() * 100;
    const y = Math.random() * 100;
    const size = Math.random() * 2.5 + 0.5;
    const dur = (Math.random() * 4 + 2).toFixed(1);
    const del = (Math.random() * 5).toFixed(1);
    const minOp = (Math.random() * 0.3 + 0.1).toFixed(2);

    html += `<div class="star" style="
      left:${x}%; top:${y}%;
      width:${size}px; height:${size}px;
      --dur:${dur}s; --delay:${del}s; --min-op:${minOp};
    "></div>`;
  }
  bg.innerHTML = html;
}

// ────────────────────────────────────────────
// INIT
// ────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  renderStars();
  renderRasiGrid();
  renderRasiChips();
  setLanguage(currentLang);
  if (window.location.hash === '#homams') {
    showPage('homams');
  }
});

window.renderRasiGrid = renderRasiGrid;
window.renderRasiChips = renderRasiChips;

// Make functions globally accessible for HTML onclick handlers
window.showPage = showPage;
window.toggleNav = toggleNav;
window.showModal = showModal;
window.closeModal = closeModal;
window.selectRasi = selectRasi;
window.switchTab = switchTab;
window.setChartStyle = setChartStyle;
window.generateKundli = generateKundli;
window.showKundliForm = showKundliForm;
window.searchCity = searchCity;
window.selectCity = selectCity;

window.renderPlanetTable = renderPlanetTable;
window.renderLifeOverview = renderLifeOverview;
window.renderHoroscopeCard = renderHoroscopeCard;


// ────────────────────────────────────────────
// CONSULT ASTROLOGER PAGE
// ────────────────────────────────────────────
function submitConsult(e) {
  e.preventDefault();

  const name = document.getElementById('c-name').value.trim();
  const email = document.getElementById('c-email').value.trim();
  const phone = document.getElementById('c-phone').value.trim();
  const type = document.getElementById('c-type').value;
  const message = document.getElementById('c-message').value.trim();
  const errEl = document.getElementById('consult-error');

  if (!name || !email || !phone || !type || !message) {
    errEl.classList.remove('hidden');
    return;
  }

  // Basic email format check
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    errEl.textContent = 'Please enter a valid email address.';
    errEl.classList.remove('hidden');
    return;
  }

  errEl.classList.add('hidden');

  // Launch payment flow instead of immediate email
  showPaymentModal('Consultation Booking', 'Fee: ₹501 (Personal Guidance)');
}

function resetConsultForm() {
  document.getElementById('consultForm').reset();
  document.getElementById('consultForm').classList.remove('hidden');
  document.getElementById('consult-success').classList.add('hidden');
  document.getElementById('consult-error').textContent = 'Please fill in all required fields.';
}

window.submitConsult = submitConsult;
window.resetConsultForm = resetConsultForm;

// ────────────────────────────────────────────
// SHOPPING CART SYSTEM
// ────────────────────────────────────────────

let cart = []; // Array of { id, name, basePrice, qty }

function addToCart(name, price) {
  const existing = cart.find(i => i.id === name);
  if (existing) {
    existing.qty++;
  } else {
    cart.push({ id: name, name, basePrice: price, qty: 1 });
  }
  renderCart();
  showCartFeedback();
}

function addHomamToCart(btn, name, basePrice) {
  const card = btn.closest('.homam-card');
  const qtyInput = card ? card.querySelector('.homam-qty') : null;
  const persons = qtyInput ? Math.max(1, parseInt(qtyInput.value) || 1) : 1;
  const totalPrice = basePrice * persons;
  const id = name + '_homam';

  const existing = cart.find(i => i.id === id);
  if (existing) {
    existing.qty += persons;
  } else {
    cart.push({ id, name: `${name} (${persons} person${persons > 1 ? 's' : ''})`, basePrice, qty: persons });
  }
  renderCart();
  showCartFeedback();
}

function removeFromCart(id) {
  cart = cart.filter(i => i.id !== id);
  renderCart();
}

function updateQty(id, delta) {
  const item = cart.find(i => i.id === id);
  if (!item) return;
  item.qty = Math.max(1, item.qty + delta);
  renderCart();
}

function clearCart() {
  cart = [];
  renderCart();
}

function renderCart() {
  const itemsEl = document.getElementById('cartItems');
  const emptyEl = document.getElementById('cartEmpty');
  const footerEl = document.getElementById('cartFooter');
  const countEl = document.getElementById('cartCount');
  const totalEl = document.getElementById('cartTotal');

  if (!itemsEl) return;

  // Clear existing items (not the empty placeholder)
  Array.from(itemsEl.children).forEach(c => {
    if (c.id !== 'cartEmpty') c.remove();
  });

  if (cart.length === 0) {
    emptyEl.style.display = '';
    footerEl.style.display = 'none';
    countEl.textContent = '0';
    return;
  }

  emptyEl.style.display = 'none';
  footerEl.style.display = 'flex';
  footerEl.style.flexDirection = 'column';

  let total = 0;
  cart.forEach(item => {
    const subtotal = item.basePrice * item.qty;
    total += subtotal;

    const div = document.createElement('div');
    div.className = 'cart-item';
    div.innerHTML = `
      <div class="cart-item-name">${item.name}</div>
      <div class="cart-item-row">
        <div class="cart-item-controls">
          <button class="cart-qty-btn" onclick="updateQty('${item.id}',-1)">−</button>
          <span class="cart-qty-num">${item.qty}</span>
          <button class="cart-qty-btn" onclick="updateQty('${item.id}',1)">+</button>
          <span style="font-size:12px;color:var(--text-secondary);margin-left:4px">× ₹${item.basePrice.toLocaleString('en-IN')}</span>
        </div>
        <button class="cart-item-remove" onclick="removeFromCart('${item.id}')">🗑</button>
      </div>
      <div class="cart-item-subtotal">Subtotal: ₹${subtotal.toLocaleString('en-IN')}</div>
    `;
    itemsEl.appendChild(div);
  });

  totalEl.textContent = '₹' + total.toLocaleString('en-IN');

  const totalItems = cart.reduce((s, i) => s + i.qty, 0);
  countEl.textContent = totalItems;
}

function toggleCart() {
  const sidebar = document.getElementById('cartSidebar');
  const overlay = document.getElementById('cartOverlay');
  if (!sidebar) return;
  sidebar.classList.toggle('hidden');
  overlay.classList.toggle('hidden');
}

function showCartFeedback() {
  // Open cart automatically so user sees the item was added
  const sidebar = document.getElementById('cartSidebar');
  const overlay = document.getElementById('cartOverlay');
  if (sidebar && sidebar.classList.contains('hidden')) {
    sidebar.classList.remove('hidden');
    overlay.classList.remove('hidden');
  }
}

function proceedCheckout() {
  if (cart.length === 0) return;
  const total = cart.reduce((s, i) => s + i.basePrice * i.qty, 0);
  const lines = cart.map(i => `${i.name} x${i.qty} = ₹${(i.basePrice * i.qty).toLocaleString('en-IN')}`).join('%0A');
  const body = encodeURIComponent(
    `I would like to book the following:\n${cart.map(i => `${i.name} x${i.qty} = ₹${i.basePrice * i.qty}`).join('\n')}\n\nTotal: ₹${total}`
  );
  window.open(`mailto:taraastrovision123@gmail.com?subject=Poojas%20%2F%20Homam%20Booking%20Request&body=${body}`, '_blank');
}

window.addToCart = addToCart;
window.addHomamToCart = addHomamToCart;
window.removeFromCart = removeFromCart;
window.updateQty = updateQty;
window.clearCart = clearCart;
window.toggleCart = toggleCart;
window.proceedCheckout = proceedCheckout;

// ────────────────────────────────────────────
// PAYMENT SYSTEM
// ────────────────────────────────────────────
let paymentContext = null;

function showPaymentModal(title, sub) {
  paymentContext = title.toLowerCase().includes('consult') ? 'consult' : 'cart';
  
  document.getElementById('payment-modal-title').textContent = title;
  document.getElementById('payment-modal-sub').textContent = sub;
  
  // Reset views
  document.getElementById('payment-options-view').classList.remove('hidden');
  document.getElementById('payment-processing-view').classList.add('hidden');
  document.getElementById('payment-success-view').classList.add('hidden');
  
  showModal('payment');
}

function processMethod(method) {
  document.getElementById('payment-options-view').classList.add('hidden');
  document.getElementById('payment-processing-view').classList.remove('hidden');
  
  // Simulate payment processing for UX
  setTimeout(() => {
    document.getElementById('payment-processing-view').classList.add('hidden');
    document.getElementById('payment-success-view').classList.remove('hidden');
    
    if (paymentContext === 'consult') {
       document.getElementById('payment-success-msg').textContent = "Consultation Fee Paid. Your booking is confirmed.";
    } else {
       document.getElementById('payment-success-msg').textContent = "Order payment successful. Your items are booked.";
    }
  }, 2200);
}

function finalizePayment() {
  closeModal();
  if (paymentContext === 'cart') {
    const total = cart.reduce((s, i) => s + i.basePrice * i.qty, 0);
    const body = encodeURIComponent(
      `I have PAID for the following items:\n${cart.map(i => `${i.name} x${i.qty} = ₹${i.basePrice * i.qty}`).join('\n')}\n\nTotal: ₹${total}\n\nPlease process my request.`
    );
    window.open(`mailto:taraastrovision123@gmail.com?subject=Paid Order Confirmation&body=${body}`, '_blank');
    
    clearCart();
    if (!document.getElementById('cartSidebar').classList.contains('hidden')) {
      toggleCart();
    }
    showPage('home');
  } else {
    // Show the consultation success message div
    const name = document.getElementById('c-name').value;
    const body = encodeURIComponent(`Consultation Paid by ${name}. Details shared in form.`);
    window.open(`mailto:taraastrovision123@gmail.com?subject=Paid Consultation - ${name}&body=${body}`, '_blank');
    
    document.getElementById('consultForm').classList.add('hidden');
    document.getElementById('consult-success').classList.remove('hidden');
  }
}

function proceedPayment() {
  if (cart.length === 0) return;
  const total = cart.reduce((s, i) => s + i.basePrice * i.qty, 0);
  showPaymentModal('Cart Checkout', `Total Amount: ₹${total.toLocaleString('en-IN')}`);
}

window.processMethod = processMethod;
window.finalizePayment = finalizePayment;
window.proceedPayment = proceedPayment;
window.showPaymentModal = showPaymentModal;