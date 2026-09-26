/* ══════════════════════════════════════════
   JYOTISHA — Authentication Module
   JWT-compatible, client-side session management
   Production: swap fetch() calls to backend API
   ══════════════════════════════════════════ */

const AUTH = {
  TOKEN_KEY: 'jyotisha_token',
  USER_KEY:  'jyotisha_user',

  // ── Get stored session ──
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
    return !!this.getUser() && !!this.getToken();
  },

  // ── Save session ──
  saveSession(user, token) {
    localStorage.setItem(this.USER_KEY, JSON.stringify(user));
    localStorage.setItem(this.TOKEN_KEY, token);
  },

  // ── Clear session ──
  clearSession() {
    localStorage.removeItem(this.USER_KEY);
    localStorage.removeItem(this.TOKEN_KEY);
  },

  // ── Register ──
  async register(name, email, password) {
    // In production: POST /api/auth/register
    // Simulating backend response for MVP demo
    const existing = getRegisteredUsers().find(u => u.email === email);
    if (existing) throw new Error('Email already registered');

    const user = {
      id: Date.now().toString(),
      name,
      email,
      created: new Date().toISOString(),
      lang: currentLang || 'en'
    };

    const users = getRegisteredUsers();
    users.push({ ...user, password: btoa(password) });
    localStorage.setItem('jyotisha_users', JSON.stringify(users));

    const token = generateToken(user);
    this.saveSession(user, token);
    return user;
  },

  // ── Login ──
  async login(email, password) {
    // In production: POST /api/auth/login
    const users = getRegisteredUsers();
    const found = users.find(u => u.email === email && u.password === btoa(password));
    if (!found) throw new Error('Invalid email or password');

    const user = { id: found.id, name: found.name, email: found.email, created: found.created };
    const token = generateToken(user);
    this.saveSession(user, token);
    return user;
  },

  // ── Logout ──
  logout() {
    this.clearSession();
  }
};

// ── Helpers ──
function getRegisteredUsers() {
  try {
    return JSON.parse(localStorage.getItem('jyotisha_users') || '[]');
  } catch { return []; }
}

function generateToken(user) {
  // Minimal JWT-like structure for demo
  // Production: real JWT from backend
  const header  = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const payload = btoa(JSON.stringify({ ...user, exp: Date.now() + 86400000 }));
  const sig     = btoa(`${header}.${payload}.jyotisha_secret`);
  return `${header}.${payload}.${sig}`;
}

// ── UI Integration ──
function handleLogin(e) {
  e.preventDefault();
  const email = document.getElementById('loginEmail').value.trim();
  const pass  = document.getElementById('loginPass').value;
  const err   = document.getElementById('loginError');

  AUTH.login(email, pass)
    .then(user => {
      err.classList.add('hidden');
      closeModal();
      updateAuthUI(user);
      // If pending page, navigate there
      if (window._pendingPage) {
        showPage(window._pendingPage);
        window._pendingPage = null;
      }
    })
    .catch(ex => {
      err.textContent = ex.message;
      err.classList.remove('hidden');
    });
}

function handleRegister(e) {
  e.preventDefault();
  const name  = document.getElementById('regName').value.trim();
  const email = document.getElementById('regEmail').value.trim();
  const pass  = document.getElementById('regPass').value;
  const err   = document.getElementById('registerError');

  AUTH.register(name, email, pass)
    .then(user => {
      err.classList.add('hidden');
      closeModal();
      updateAuthUI(user);
      if (window._pendingPage) {
        showPage(window._pendingPage);
        window._pendingPage = null;
      }
    })
    .catch(ex => {
      err.textContent = ex.message;
      err.classList.remove('hidden');
    });
}

function logout() {
  AUTH.logout();
  updateAuthUI(null);
  showPage('home');
  document.getElementById('userDropdown').classList.add('hidden');
}

function updateAuthUI(user) {
  const authButtons = document.getElementById('authButtons');
  const userMenu    = document.getElementById('userMenu');
  const avatarEl    = document.getElementById('avatarInitial');
  const nameEl      = document.getElementById('userName');

  if (user) {
    authButtons.classList.add('hidden');
    userMenu.classList.remove('hidden');
    avatarEl.textContent = user.name.charAt(0).toUpperCase();
    nameEl.textContent   = user.name.split(' ')[0];
    loadDashboard(user);
  } else {
    authButtons.classList.remove('hidden');
    userMenu.classList.add('hidden');
  }
}

function toggleUserMenu() {
  document.getElementById('userDropdown').classList.toggle('hidden');
}

document.addEventListener('click', e => {
  const um = document.getElementById('userMenu');
  if (um && !um.contains(e.target)) {
    const dd = document.getElementById('userDropdown');
    if (dd) dd.classList.add('hidden');
  }
});

function requireLogin(page) {
  if (AUTH.isLoggedIn()) {
    showPage(page);
  } else {
    window._pendingPage = page;
    showModal('loginRequired');
  }
}

function loadDashboard(user) {
  const profileInfo = document.getElementById('profileInfo');
  if (!profileInfo) return;

  const charts = getSavedCharts();
  const chartList = document.getElementById('chartList');
  if (chartList) {
    if (charts.length === 0) {
      chartList.innerHTML = `<p class="empty-state">${t('no_charts')}</p>`;
    } else {
      chartList.innerHTML = charts.map(c => `
        <div class="profile-row">
          <span class="profile-label">${c.name}</span>
          <span class="profile-value" style="font-size:13px;color:var(--text-muted)">${new Date(c.date).toLocaleDateString()}</span>
        </div>
      `).join('');
    }
  }

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
      <span class="profile-label">Member Since</span>
      <span class="profile-value">${new Date(user.created).toLocaleDateString()}</span>
    </div>
    <div class="profile-row">
      <span class="profile-label">Language</span>
      <span class="profile-value">${currentLang.toUpperCase()}</span>
    </div>
  `;
}

function getSavedCharts() {
  const user = AUTH.getUser();
  if (!user) return [];
  try {
    const all = JSON.parse(localStorage.getItem('jyotisha_charts') || '[]');
    return all.filter(c => c.userId === user.id);
  } catch { return []; }
}

function saveChart(chartData) {
  const user = AUTH.getUser();
  if (!user) return;
  const all = JSON.parse(localStorage.getItem('jyotisha_charts') || '[]');
  all.push({ ...chartData, userId: user.id, date: new Date().toISOString() });
  localStorage.setItem('jyotisha_charts', JSON.stringify(all));
}

// Init auth state on load
document.addEventListener('DOMContentLoaded', () => {
  const user = AUTH.getUser();
  if (user) updateAuthUI(user);
});

// Make functions globally accessible for HTML onclick handlers
window.handleLogin = handleLogin;
window.handleRegister = handleRegister;
window.logout = logout;
window.requireLogin = requireLogin;
window.toggleUserMenu = toggleUserMenu;