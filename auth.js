/* ══════════════════════════════════════════
   JYOTISHA — Authentication & Session Module
   Updated for direct, open access without login
   ══════════════════════════════════════════ */

const AUTH = {
  TOKEN_KEY: 'jyotisha_token',
  USER_KEY:  'jyotisha_user',

  getUser() {
    try {
      const raw = localStorage.getItem(this.USER_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch { return null; }
  },

  getToken() {
    return localStorage.getItem(this.TOKEN_KEY);
  },

  isLoggedIn() {
    return true; // Direct access enabled
  },

  saveSession(user, token) {
    try {
      localStorage.setItem(this.USER_KEY, JSON.stringify(user));
      localStorage.setItem(this.TOKEN_KEY, token);
    } catch {}
  },

  clearSession() {
    try {
      localStorage.removeItem(this.USER_KEY);
      localStorage.removeItem(this.TOKEN_KEY);
    } catch {}
  },

  async register() {
    return null;
  },

  async login() {
    return null;
  },

  logout() {
    this.clearSession();
  }
};

function getRegisteredUsers() {
  try {
    return JSON.parse(localStorage.getItem('jyotisha_users') || '[]');
  } catch { return []; }
}

function handleLogin(e) {
  if (e && e.preventDefault) e.preventDefault();
  if (typeof closeModal === 'function') closeModal();
}

function handleRegister(e) {
  if (e && e.preventDefault) e.preventDefault();
  if (typeof closeModal === 'function') closeModal();
}

function logout() {
  AUTH.logout();
  if (typeof showPage === 'function') showPage('home');
}

function updateAuthUI(user) {
  const authButtons = document.getElementById('authButtons');
  const userMenu    = document.getElementById('userMenu');
  if (authButtons) authButtons.classList.add('hidden');
  if (userMenu) userMenu.classList.add('hidden');
}

function toggleUserMenu() {}

function requireLogin(page) {
  if (typeof showPage === 'function') {
    showPage(page);
  } else if (typeof page === 'string' && page.endsWith('.html')) {
    window.location.href = page;
  }
}

function loadDashboard(user) {
  const profileInfo = document.getElementById('profileInfo');
  const charts = getSavedCharts();
  const chartList = document.getElementById('chartList');
  if (chartList) {
    if (charts.length === 0) {
      chartList.innerHTML = `<p class="empty-state">${typeof t === 'function' ? t('no_charts') : 'No charts saved yet. Generate your Kundli first.'}</p>`;
    } else {
      chartList.innerHTML = charts.map(c => `
        <div class="profile-row">
          <span class="profile-label">${c.name || 'Birth Chart'}</span>
          <span class="profile-value" style="font-size:13px;color:var(--text-muted)">${new Date(c.date).toLocaleDateString()}</span>
        </div>
      `).join('');
    }
  }

  if (profileInfo) {
    if (user) {
      profileInfo.innerHTML = `
        <div class="profile-row">
          <span class="profile-label">Name</span>
          <span class="profile-value">${user.name}</span>
        </div>
        <div class="profile-row">
          <span class="profile-label">Email</span>
          <span class="profile-value">${user.email}</span>
        </div>
        <div class="profile-row">
          <span class="profile-label">Language</span>
          <span class="profile-value">${(typeof currentLang !== 'undefined' ? currentLang : 'EN').toUpperCase()}</span>
        </div>
      `;
    } else {
      profileInfo.innerHTML = `
        <div class="profile-row">
          <span class="profile-label">Access</span>
          <span class="profile-value">Direct Access</span>
        </div>
        <div class="profile-row">
          <span class="profile-label">Language</span>
          <span class="profile-value">${(typeof currentLang !== 'undefined' ? currentLang : 'EN').toUpperCase()}</span>
        </div>
        <div class="profile-row">
          <span class="profile-label">Saved Charts</span>
          <span class="profile-value">${charts.length}</span>
        </div>
      `;
    }
  }
}

function getSavedCharts() {
  try {
    return JSON.parse(localStorage.getItem('jyotisha_charts') || '[]');
  } catch { return []; }
}

function saveChart(chartData) {
  try {
    const all = JSON.parse(localStorage.getItem('jyotisha_charts') || '[]');
    all.push({ ...chartData, date: new Date().toISOString() });
    localStorage.setItem('jyotisha_charts', JSON.stringify(all));
  } catch (e) {
    console.error('Could not save chart:', e);
  }
}

// Init auth state on load
document.addEventListener('DOMContentLoaded', () => {
  updateAuthUI();
});

// Make functions globally accessible
window.handleLogin = handleLogin;
window.handleRegister = handleRegister;
window.logout = logout;
window.requireLogin = requireLogin;
window.toggleUserMenu = toggleUserMenu;
window.loadDashboard = loadDashboard;
window.getSavedCharts = getSavedCharts;
window.saveChart = saveChart;
window.AUTH = AUTH;