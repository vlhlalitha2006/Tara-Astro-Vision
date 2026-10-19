/**
 * Tara Astro Vision — Production Admin Portal Frontend Controller
 * Strictly authenticated to info@taraastrovision.com.
 * Communicates with FastAPI Admin Endpoints with JWT Bearer Authentication.
 * Timezone: Asia/Kolkata (IST).
 */

// Retrieve stored token from session or local storage
let adminToken = (typeof sessionStorage !== 'undefined' && sessionStorage.getItem('tara_admin_token')) ||
                 (typeof localStorage !== 'undefined' && localStorage.getItem('tara_admin_token')) ||
                 null;
let currentView = 'dashboard';
let bookingsCache = {};
let capacityCache = [];
let searchDebounceTimer = null;

/**
 * Determine the API base URL.
 * Automatically targets http://localhost:8000 when frontend runs on a dev server (e.g. 3000, 5173, 5500)
 * or file:, while using same-origin relative URLs on port 8000 or production domains.
 */
function getApiBase() {
  if (typeof window !== 'undefined' && window.TAV_API_BASE) {
    return window.TAV_API_BASE.replace(/\/+$/, '');
  }
  if (typeof localStorage !== 'undefined' && localStorage.getItem('tara_api_base')) {
    return localStorage.getItem('tara_api_base').replace(/\/+$/, '');
  }
  if (typeof window !== 'undefined' && window.location) {
    const protocol = window.location.protocol;
    const hostname = window.location.hostname;
    const port = window.location.port;

    if (protocol === 'file:') {
      return 'http://localhost:8000';
    }
    if ((hostname === 'localhost' || hostname === '127.0.0.1') && port && port !== '8000') {
      return `${protocol}//${hostname}:8000`;
    }
  }
  return '';
}

// =========================================================================
// ROUTING & NAVIGATION HELPERS
// =========================================================================

const VALID_ADMIN_VIEWS = ['dashboard', 'homams', 'poojas', 'consultations', 'payments', 'capacity', 'audit'];

function getViewFromUrl() {
  if (typeof window === 'undefined' || !window.location) return 'dashboard';

  // 1. Check hash first (e.g. #homams, #/homams)
  const hash = (window.location.hash || '').replace(/^#\/?/, '').toLowerCase().trim();
  if (VALID_ADMIN_VIEWS.includes(hash)) {
    return hash;
  }

  // 2. Check pathname (e.g. /admin/homams, /admin/poojas)
  const pathname = (window.location.pathname || '').replace(/\/+$/, '').toLowerCase();
  const segments = pathname.split('/').filter(Boolean);
  if (segments.length > 0) {
    const last = segments[segments.length - 1];
    if (VALID_ADMIN_VIEWS.includes(last)) {
      return last;
    }
  }

  return 'dashboard';
}

function getUrlForView(viewName) {
  if (typeof window === 'undefined' || !window.location) return '/admin';
  if (window.location.protocol === 'file:') {
    return `#/${viewName}`;
  }
  return viewName === 'dashboard' ? '/admin' : `/admin/${viewName}`;
}

// Browser navigation history support (Back/Forward)
if (typeof window !== 'undefined') {
  window.addEventListener('popstate', (e) => {
    if (!adminToken) return;
    const v = (e.state && e.state.view) || getViewFromUrl();
    switchAdminView(v, false);
  });

  window.addEventListener('hashchange', () => {
    if (!adminToken) return;
    const v = getViewFromUrl();
    switchAdminView(v, false);
  });
}

// =========================================================================
// INITIALIZATION
// =========================================================================

document.addEventListener('DOMContentLoaded', () => {
  const initialView = getViewFromUrl();
  if (adminToken) {
    showPortalView();
    switchAdminView(initialView, false);
    verifySession(initialView);
  } else {
    showLoginView();
  }

  // Setup ESC key listener for modals
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      ['modalDetail', 'modalReject', 'modalSchedule', 'modalReschedule'].forEach(closeModal);
    }
  });
});

// =========================================================================
// AUTHENTICATION & SESSION
// =========================================================================

async function verifySession(initialView) {
  if (!adminToken) {
    showLoginView();
    return;
  }

  const targetView = initialView || getViewFromUrl();

  try {
    const apiBase = getApiBase();
    const res = await fetch(`${apiBase}/api/admin/me`, {
      headers: {
        'Authorization': `Bearer ${adminToken}`,
        'Accept': 'application/json'
      }
    });

    if (res.ok) {
      const data = await res.json().catch(() => ({}));
      if (data.email === 'info@taraastrovision.com') {
        showPortalView();
        if (currentView !== targetView) {
          switchAdminView(targetView, false);
        }
        return;
      }
    }

    if (res.status === 401 || res.status === 403) {
      // Explicit unauthorized/expired session
      handleAuthExpired();
      showLoginError('Session expired or unauthorized. Please sign in again.');
    } else {
      // Transient server/backend restart response (e.g. 500, 502, 503, 404):
      // Keep portal visible and do not destroy the session token
      console.warn('Session verification server status:', res.status);
      showPortalView();
      if (currentView !== targetView) {
        switchAdminView(targetView, false);
      }
      showToast(`Admin backend returned status ${res.status}. Session active.`, 'warn');
    }
  } catch (err) {
    console.error('Session check network error:', err);
    // Network failure (server reload): keep token so refresh doesn't log the admin out
    showPortalView();
    if (currentView !== targetView) {
      switchAdminView(targetView, false);
    }
    showToast('Cannot connect to admin backend. Please verify server is running on port 8000.', 'warn');
  }
}

function handleAuthExpired() {
  adminToken = null;
  if (typeof sessionStorage !== 'undefined') sessionStorage.removeItem('tara_admin_token');
  if (typeof localStorage !== 'undefined') localStorage.removeItem('tara_admin_token');
  showLoginView();
}

function showLoginView() {
  const loginView = document.getElementById('loginView');
  const portalView = document.getElementById('portalView');
  if (loginView) loginView.classList.remove('hidden');
  if (portalView) portalView.classList.add('hidden');
}

function showPortalView() {
  const loginView = document.getElementById('loginView');
  const portalView = document.getElementById('portalView');
  if (loginView) loginView.classList.add('hidden');
  if (portalView) portalView.classList.remove('hidden');
}

async function handleAdminLogin(event) {
  event.preventDefault();
  const emailInput = document.getElementById('adminEmail');
  const pwdInput = document.getElementById('adminPassword');
  const btn = document.getElementById('btnLogin');

  const email = (emailInput && emailInput.value.trim()) ? emailInput.value.trim() : 'info@taraastrovision.com';
  const password = pwdInput ? pwdInput.value : '';

  if (!password) {
    showLoginError('Please enter the admin password.');
    return;
  }

  setButtonLoading(btn, true, 'Verifying credentials...');
  hideLoginError();

  try {
    const apiBase = getApiBase();
    const res = await fetch(`${apiBase}/api/admin/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });

    let data = {};
    try {
      data = await res.json();
    } catch (parseErr) {
      data = {};
    }

    if (res.ok && data.token) {
      adminToken = data.token;
      if (typeof sessionStorage !== 'undefined') sessionStorage.setItem('tara_admin_token', adminToken);
      if (typeof localStorage !== 'undefined') localStorage.setItem('tara_admin_token', adminToken);
      showToast('Logged in successfully', 'success');
      showPortalView();
      const targetView = getViewFromUrl();
      switchAdminView(targetView, true);
      if (pwdInput) pwdInput.value = '';
    } else if (res.status === 429) {
      showLoginError('Too many failed login attempts. Please wait 15 minutes before trying again.');
    } else if (res.status === 401 || res.status === 403) {
      const msg = (typeof data.detail === 'string' && data.detail)
        ? data.detail
        : 'Invalid email or password. Access is restricted.';
      showLoginError(msg);
    } else if (res.status === 404) {
      showLoginError('Admin login endpoint not found (404). Please ensure the FastAPI backend is running on port 8000.');
    } else if (res.status === 501) {
      showLoginError('Backend service unavailable (501). Frontend is connected to a static file server instead of FastAPI. Please run ./start.sh or uvicorn on port 8000.');
    } else if (res.status >= 500) {
      showLoginError(`Backend server error (${res.status}). Please check backend terminal logs.`);
    } else {
      const msg = (typeof data.detail === 'string' && data.detail)
        ? data.detail
        : `Unable to log in (HTTP ${res.status}). Please verify the backend service is running.`;
      showLoginError(msg);
    }
  } catch (err) {
    console.error('Login network error:', err);
    showLoginError('Cannot connect to admin backend server. Please verify FastAPI is running at http://localhost:8000.');
  } finally {
    setButtonLoading(btn, false, 'Sign In to Dashboard');
  }
}

async function handleAdminLogout() {
  if (adminToken) {
    try {
      const apiBase = getApiBase();
      await fetch(`${apiBase}/api/admin/logout`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${adminToken}` }
      });
    } catch (e) {
      // Ignore network errors during logout
    }
  }
  handleAuthExpired();
  showToast('Logged out successfully', 'info');
}

function togglePasswordVisibility() {
  const pwdInput = document.getElementById('adminPassword');
  if (!pwdInput) return;
  pwdInput.type = pwdInput.type === 'password' ? 'text' : 'password';
}

function showLoginError(msg) {
  const errBox = document.getElementById('loginError');
  if (errBox) {
    errBox.textContent = msg;
    errBox.classList.remove('hidden');
  }
}

function hideLoginError() {
  const errBox = document.getElementById('loginError');
  if (errBox) {
    errBox.textContent = '';
    errBox.classList.add('hidden');
  }
}

// =========================================================================
// API HELPER
// =========================================================================

async function adminApi(endpoint, options = {}) {
  if (!adminToken) {
    handleAuthExpired();
    throw new Error('Unauthenticated');
  }

  const defaultHeaders = {
    'Authorization': `Bearer ${adminToken}`,
    'Accept': 'application/json'
  };

  if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
    defaultHeaders['Content-Type'] = 'application/json';
    options.body = JSON.stringify(options.body);
  }

  options.headers = { ...defaultHeaders, ...(options.headers || {}) };

  const apiBase = getApiBase();
  const url = endpoint.startsWith('http') ? endpoint : `${apiBase}${endpoint}`;
  const res = await fetch(url, options);

  if (res.status === 401) {
    handleAuthExpired();
    showToast('Admin session expired. Please sign in again.', 'warn');
    throw new Error('Session expired');
  }

  return res;
}

// =========================================================================
// VIEW NAVIGATION
// =========================================================================

function switchAdminView(viewName, updateHistory = true) {
  if (!VALID_ADMIN_VIEWS.includes(viewName)) {
    viewName = 'dashboard';
  }
  currentView = viewName;

  // Ensure portal layout is visible
  showPortalView();

  // Update browser URL and history
  if (updateHistory && typeof window !== 'undefined' && window.history && window.history.pushState) {
    const targetUrl = getUrlForView(viewName);
    const currentLoc = window.location.pathname + (window.location.hash || '');
    if (currentLoc !== targetUrl && window.location.pathname !== targetUrl) {
      window.history.pushState({ view: viewName }, '', targetUrl);
    }
  }

  // Update navigation item active state
  document.querySelectorAll('.sidebar-nav .nav-item').forEach(item => {
    if (item.getAttribute('data-view') === viewName) {
      item.classList.add('active');
    } else {
      item.classList.remove('active');
    }
  });

  // Update view title in topbar
  const titleMap = {
    'dashboard': 'Executive Dashboard',
    'homams': 'Homam Bookings Management',
    'poojas': 'Weekly Pooja Bookings Management',
    'consultations': 'Astrologer Consultations & Scheduling',
    'payments': 'Payments & Real Razorpay Refunds',
    'capacity': 'Strict 50 Booking Capacity Tracker',
    'audit': 'System Audit Log & Security Events'
  };
  const titleEl = document.getElementById('currentViewTitle');
  if (titleEl) {
    titleEl.textContent = titleMap[viewName] || 'Admin Console';
  }

  // Toggle views
  const views = [
    { name: 'dashboard', id: 'viewDashboard' },
    { name: 'homams', id: 'viewHomams' },
    { name: 'poojas', id: 'viewPoojas' },
    { name: 'consultations', id: 'viewConsultations' },
    { name: 'payments', id: 'viewPayments' },
    { name: 'capacity', id: 'viewCapacity' },
    { name: 'audit', id: 'viewAudit' }
  ];

  views.forEach(v => {
    const el = document.getElementById(v.id);
    if (el) {
      if (v.name === viewName) {
        el.classList.add('active');
      } else {
        el.classList.remove('active');
      }
    }
  });

  // Close sidebar on mobile after clicking
  const sidebar = document.getElementById('adminSidebar');
  if (sidebar && sidebar.classList.contains('open')) {
    sidebar.classList.remove('open');
  }

  // Fetch view data
  loadCurrentViewData();
}

function refreshCurrentView() {
  loadCurrentViewData();
  showToast('Refreshing records...', 'info');
}

function loadCurrentViewData() {
  switch (currentView) {
    case 'dashboard':
      loadDashboard();
      break;
    case 'homams':
      loadHomamBookings();
      break;
    case 'poojas':
      loadPoojaBookings();
      break;
    case 'consultations':
      loadConsultationBookings();
      break;
    case 'payments':
      loadPayments();
      break;
    case 'capacity':
      loadCapacity();
      break;
    case 'audit':
      loadAuditLogs();
      break;
  }
}

function toggleSidebar() {
  const sidebar = document.getElementById('adminSidebar');
  if (sidebar) {
    sidebar.classList.toggle('open');
  }
}

// =========================================================================
// VIEW 1: DASHBOARD
// =========================================================================

async function loadDashboard() {
  try {
    const res = await adminApi('/api/admin/dashboard');
    if (!res.ok) throw new Error('Failed to fetch dashboard metrics');
    const data = await res.json();

    const m = data.metrics || {};
    const rev = data.revenue || {};

    // Update Top Stat Cards
    setText('statHomamTotal', m.total_homams || 0);
    setText('statPoojaTotal', m.total_poojas || 0);
    setText('statConsultTotal', m.total_consultations || 0);
    setText('statTodayTotal', m.today_bookings || 0);
    setText('statPendingTotal', m.pending_bookings || 0);
    setText('statAcceptedTotal', m.accepted_bookings || 0);
    setText('statRejectedTotal', m.rejected_bookings || 0);

    // Update Net Revenue Cards
    setText('statNetRevenue', formatCurrency(rev.net || 0));
    setText('statGrossRevenue', formatCurrency(rev.gross || 0));
    setText('statRefundsAmount', formatCurrency(rev.refunds || 0));

    // Update Sidebar Badges
    setText('badgeHomamCount', m.total_homams || 0);
    setText('badgePoojaCount', m.total_poojas || 0);
    setText('badgeConsultCount', m.total_consultations || 0);

    // Render 4 Enabled Homams Capacity Cards on Dashboard
    renderDashboardCapacityCards(data.capacity || []);

    // Render Recent Bookings Table
    renderRecentBookings(data.recent_bookings || []);

  } catch (err) {
    console.error('Error loading dashboard:', err);
    showToast('Error loading dashboard: ' + err.message, 'error');
  }
}

function renderDashboardCapacityCards(capacityList) {
  const container = document.getElementById('dashboardCapacityCards');
  if (!container) return;

  // Filter the 4 enabled homams for the dashboard preview
  const enabledHomams = capacityList.filter(c => c.is_enabled);

  if (!enabledHomams.length) {
    container.innerHTML = '<div class="table-empty">No enabled services configured</div>';
    return;
  }

  container.innerHTML = enabledHomams.map(c => {
    const pct = Math.min(100, Math.round((c.confirmed / c.limit) * 100));
    const isFull = c.is_full;
    return `
      <div class="capacity-card ${isFull ? 'full' : ''}">
        <div class="cap-header">
          <span class="cap-title">${escapeHtml(c.name)}</span>
          <span class="badge ${isFull ? 'badge-rejected' : 'badge-accepted'}">
            ${isFull ? 'Capacity Reached' : `${c.available} Slots Left`}
          </span>
        </div>
        <div class="cap-progress-bg">
          <div class="cap-progress-bar" style="width: ${pct}%"></div>
        </div>
        <div class="cap-meta">
          <span>Booked: <strong>${c.confirmed} / ${c.limit}</strong></span>
          <span>${pct}% filled</span>
        </div>
      </div>
    `;
  }).join('');
}

function renderRecentBookings(bookings) {
  const tbody = document.getElementById('recentBookingsTbody');
  if (!tbody) return;

  if (!bookings || bookings.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" class="table-empty">No recent bookings recorded in database.</td></tr>';
    return;
  }

  // Cache them for instant detail lookup
  bookings.forEach(b => { bookingsCache[b.id] = b; });

  tbody.innerHTML = bookings.map(b => {
    const isHomam = b.service_type === 'homam';
    const isPooja = b.service_type === 'pooja';
    const isConsult = b.service_type === 'consultation';

    return `
      <tr>
        <td><strong>#${b.id}</strong></td>
        <td>${formatIST(b.created_at)}</td>
        <td>
          <div class="cell-main">${escapeHtml(b.customer_name || 'N/A')}</div>
          <div class="cell-sub">${escapeHtml(b.customer_phone || '')}</div>
        </td>
        <td>
          <div class="cell-main">${escapeHtml(b.service_name || 'Service')}</div>
        </td>
        <td>
          <span class="type-pill ${b.service_type}">${b.service_type}</span>
        </td>
        <td><strong>${formatCurrency(b.amount || 0)}</strong></td>
        <td>${renderStatusBadge(b.booking_status)}</td>
        <td>${renderPaymentBadge(b.payment_status, b.refund_status)}</td>
        <td>
          <div class="action-btn-group">
            <button class="btn-sm btn-info" onclick="viewBookingDetail('${escapeHtml(b.id)}')" title="View Details">👁️</button>
            ${b.booking_status === 'pending' ? `
              <button class="btn-sm btn-accept" onclick="acceptBooking('${escapeHtml(b.id)}')" title="Accept Booking">✓</button>
              <button class="btn-sm btn-reject" onclick="openRejectModal('${escapeHtml(b.id)}')" title="Reject & Refund">✕</button>
            ` : ''}
            ${isConsult && (b.booking_status === 'pending' || b.booking_status === 'accepted') ? `
              <button class="btn-sm btn-schedule" onclick="openScheduleModal('${escapeHtml(b.id)}')" title="Schedule Consultation">📅</button>
            ` : ''}
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

// =========================================================================
// VIEW 2: HOMAM BOOKINGS
// =========================================================================

async function loadHomamBookings() {
  const search = document.getElementById('homamSearchInput')?.value.trim() || '';
  const status = document.getElementById('homamStatusSelect')?.value || 'all';
  const tbody = document.getElementById('homamBookingsTbody');
  if (tbody) tbody.innerHTML = '<tr><td colspan="10" class="table-empty">Loading Homam bookings...</td></tr>';

  try {
    const params = new URLSearchParams({
      service_type: 'homam',
      status: status,
      search: search,
      page: '1',
      limit: '100'
    });

    const res = await adminApi(`/api/admin/bookings?${params.toString()}`);
    if (!res.ok) throw new Error('Failed to fetch Homam bookings');
    const data = await res.json();

    const bookings = data.bookings || [];
    bookings.forEach(b => { bookingsCache[b.id] = b; });

    setText('badgeHomamCount', data.total || 0);
    setText('homamFilterSummary', `Showing ${bookings.length} of ${data.total} Homam bookings`);

    if (tbody) {
      if (bookings.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" class="table-empty">No Homam bookings matching criteria.</td></tr>';
        return;
      }

      tbody.innerHTML = bookings.map(b => `
        <tr>
          <td><strong>#${b.id}</strong></td>
          <td>${formatIST(b.created_at)}</td>
          <td>
            <div class="cell-main">${escapeHtml(b.customer_name || 'N/A')}</div>
            <div class="cell-sub">Gotra: ${escapeHtml(b.gotra || '—')} | Nakshatra: ${escapeHtml(b.nakshatra || '—')}</div>
          </td>
          <td>
            <div>${escapeHtml(b.customer_phone || '—')}</div>
            <div class="cell-sub">${escapeHtml(b.customer_email || '—')}</div>
          </td>
          <td>
            <div class="cell-main">${escapeHtml(b.service_name || 'Homam')}</div>
            ${b.is_group_booking ? '<span class="badge-mini">Samuhika Group</span>' : ''}
          </td>
          <td>${b.num_persons || 1}</td>
          <td><strong>${formatCurrency(b.amount || 0)}</strong></td>
          <td>${renderStatusBadge(b.booking_status)}</td>
          <td>${renderPaymentBadge(b.payment_status, b.refund_status)}</td>
          <td>
            <div class="action-btn-group">
              <button class="btn-sm btn-info" onclick="viewBookingDetail('${escapeHtml(b.id)}')" title="View Details">👁️</button>
              ${b.booking_status === 'pending' ? `
                <button class="btn-sm btn-accept" onclick="acceptBooking('${escapeHtml(b.id)}')" title="Accept Booking">✓ Accept</button>
                <button class="btn-sm btn-reject" onclick="openRejectModal('${escapeHtml(b.id)}')" title="Reject & Refund">✕ Reject</button>
              ` : ''}
            </div>
          </td>
        </tr>
      `).join('');
    }
  } catch (err) {
    console.error('Error loading Homam bookings:', err);
    if (tbody) tbody.innerHTML = `<tr><td colspan="10" class="table-empty text-danger">Error: ${escapeHtml(err.message)}</td></tr>`;
  }
}

// =========================================================================
// VIEW 3: POOJA BOOKINGS
// =========================================================================

async function loadPoojaBookings() {
  const search = document.getElementById('poojaSearchInput')?.value.trim() || '';
  const status = document.getElementById('poojaStatusSelect')?.value || 'all';
  const tbody = document.getElementById('poojaBookingsTbody');
  if (tbody) tbody.innerHTML = '<tr><td colspan="10" class="table-empty">Loading Pooja bookings...</td></tr>';

  try {
    const params = new URLSearchParams({
      service_type: 'pooja',
      status: status,
      search: search,
      page: '1',
      limit: '100'
    });

    const res = await adminApi(`/api/admin/bookings?${params.toString()}`);
    if (!res.ok) throw new Error('Failed to fetch Pooja bookings');
    const data = await res.json();

    const bookings = data.bookings || [];
    bookings.forEach(b => { bookingsCache[b.id] = b; });

    setText('badgePoojaCount', data.total || 0);
    setText('poojaFilterSummary', `Showing ${bookings.length} of ${data.total} Pooja bookings`);

    if (tbody) {
      if (bookings.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" class="table-empty">No Pooja bookings matching criteria.</td></tr>';
        return;
      }

      tbody.innerHTML = bookings.map(b => `
        <tr>
          <td><strong>#${b.id}</strong></td>
          <td>${formatIST(b.created_at)}</td>
          <td>
            <div class="cell-main">${escapeHtml(b.customer_name || 'N/A')}</div>
            <div class="cell-sub">Gotra: ${escapeHtml(b.gotra || '—')} | Nakshatra: ${escapeHtml(b.nakshatra || '—')}</div>
          </td>
          <td>
            <div>${escapeHtml(b.customer_phone || '—')}</div>
            <div class="cell-sub">${escapeHtml(b.customer_email || '—')}</div>
          </td>
          <td>
            <div class="cell-main">${escapeHtml(b.service_name || 'Pooja')}</div>
          </td>
          <td>${b.booking_date || 'Scheduled Weekly'}</td>
          <td><strong>${formatCurrency(b.amount || 0)}</strong></td>
          <td>${renderStatusBadge(b.booking_status)}</td>
          <td>${renderPaymentBadge(b.payment_status, b.refund_status)}</td>
          <td>
            <div class="action-btn-group">
              <button class="btn-sm btn-info" onclick="viewBookingDetail('${escapeHtml(b.id)}')" title="View Details">👁️</button>
              ${b.booking_status === 'pending' ? `
                <button class="btn-sm btn-accept" onclick="acceptBooking('${escapeHtml(b.id)}')" title="Accept Booking">✓ Accept</button>
                <button class="btn-sm btn-reject" onclick="openRejectModal('${escapeHtml(b.id)}')" title="Reject & Refund">✕ Reject</button>
              ` : ''}
            </div>
          </td>
        </tr>
      `).join('');
    }
  } catch (err) {
    console.error('Error loading Pooja bookings:', err);
    if (tbody) tbody.innerHTML = `<tr><td colspan="10" class="table-empty text-danger">Error: ${escapeHtml(err.message)}</td></tr>`;
  }
}

// =========================================================================
// VIEW 4: ASTROLOGER CONSULTATIONS
// =========================================================================

async function loadConsultationBookings() {
  const search = document.getElementById('consultSearchInput')?.value.trim() || '';
  const status = document.getElementById('consultStatusSelect')?.value || 'all';
  const tbody = document.getElementById('consultBookingsTbody');
  if (tbody) tbody.innerHTML = '<tr><td colspan="9" class="table-empty">Loading consultations...</td></tr>';

  try {
    const params = new URLSearchParams({
      service_type: 'consultation',
      status: status,
      search: search,
      page: '1',
      limit: '100'
    });

    const res = await adminApi(`/api/admin/bookings?${params.toString()}`);
    if (!res.ok) throw new Error('Failed to fetch consultations');
    const data = await res.json();

    const bookings = data.bookings || [];
    bookings.forEach(b => { bookingsCache[b.id] = b; });

    setText('badgeConsultCount', data.total || 0);
    setText('consultFilterSummary', `Showing ${bookings.length} of ${data.total} consultations`);

    if (tbody) {
      if (bookings.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="table-empty">No consultations matching criteria.</td></tr>';
        return;
      }

      tbody.innerHTML = bookings.map(b => `
        <tr>
          <td><strong>#${b.id}</strong></td>
          <td>${formatIST(b.created_at)}</td>
          <td>
            <div class="cell-main">${escapeHtml(b.customer_name || 'N/A')}</div>
            <div class="cell-sub">${escapeHtml(b.customer_email || '')}</div>
          </td>
          <td>${escapeHtml(b.customer_phone || '—')}</td>
          <td>
            <span class="badge-consult-mode">${escapeHtml(b.consultation_type || 'Phone Call')}</span>
          </td>
          <td>
            <div class="inquiry-text" title="${escapeHtml(b.notes || b.service_name || '')}">
              ${escapeHtml(b.notes || b.service_name || 'Astrology Consultation')}
            </div>
          </td>
          <td>
            ${b.scheduled_time ? `
              <div class="scheduled-chip">
                <span>🗓️ ${formatIST(b.scheduled_time)}</span>
              </div>
            ` : '<span class="text-muted">Not Scheduled Yet</span>'}
          </td>
          <td>${renderStatusBadge(b.booking_status)}</td>
          <td>
            <div class="action-btn-group">
              <button class="btn-sm btn-info" onclick="viewBookingDetail('${escapeHtml(b.id)}')" title="View Details">👁️</button>
              ${(!b.scheduled_time || b.booking_status === 'pending') ? `
                <button class="btn-sm btn-schedule" onclick="openScheduleModal('${escapeHtml(b.id)}')" title="Schedule Slot">📅 Schedule</button>
              ` : `
                <button class="btn-sm btn-reschedule" onclick="openRescheduleModal('${escapeHtml(b.id)}')" title="Reschedule Slot">🔄 Reschedule</button>
              `}
              ${b.booking_status === 'pending' ? `
                <button class="btn-sm btn-accept" onclick="acceptBooking('${escapeHtml(b.id)}')" title="Mark Accepted">✓</button>
                <button class="btn-sm btn-reject" onclick="openRejectModal('${escapeHtml(b.id)}')" title="Reject">✕</button>
              ` : ''}
            </div>
          </td>
        </tr>
      `).join('');
    }
  } catch (err) {
    console.error('Error loading consultations:', err);
    if (tbody) tbody.innerHTML = `<tr><td colspan="9" class="table-empty text-danger">Error: ${escapeHtml(err.message)}</td></tr>`;
  }
}

// =========================================================================
// VIEW 5: PAYMENTS & REFUNDS
// =========================================================================

async function loadPayments() {
  const tbody = document.getElementById('refundsTbody');
  if (tbody) tbody.innerHTML = '<tr><td colspan="10" class="table-empty">Loading refunds log...</td></tr>';

  try {
    const res = await adminApi('/api/admin/refunds');
    if (!res.ok) throw new Error('Failed to fetch refunds');
    const data = await res.json();
    const refunds = data.refunds || [];

    if (tbody) {
      if (refunds.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" class="table-empty">No refund records found in database. All customer payments are fully retained.</td></tr>';
        return;
      }

      tbody.innerHTML = refunds.map(r => `
        <tr>
          <td><code>${escapeHtml(r.refund_id || 'N/A')}</code></td>
          <td><strong>#${r.booking_id}</strong></td>
          <td>${escapeHtml(r.service_name || 'Service')}</td>
          <td><code>${escapeHtml(r.razorpay_payment_id || 'N/A')}</code></td>
          <td><strong>${formatCurrency(r.amount || 0)}</strong></td>
          <td>${renderRefundBadge(r.status)}</td>
          <td>${escapeHtml(r.reason || '—')}</td>
          <td><span class="text-danger small">${escapeHtml(r.error_detail || '—')}</span></td>
          <td>${formatIST(r.timestamp)}</td>
          <td>
            ${(r.status === 'failed' || r.status === 'pending') ? `
              <button class="btn-sm btn-retry" onclick="retryRefund('${escapeHtml(r.booking_id)}')">Retry Refund</button>
            ` : '—'}
          </td>
        </tr>
      `).join('');
    }
  } catch (err) {
    console.error('Error loading refunds:', err);
    if (tbody) tbody.innerHTML = `<tr><td colspan="10" class="table-empty text-danger">Error: ${escapeHtml(err.message)}</td></tr>`;
  }
}

// =========================================================================
// VIEW 6: CAPACITY TRACKER (50 LIMIT)
// =========================================================================

async function loadCapacity() {
  try {
    const res = await adminApi('/api/admin/capacity');
    if (!res.ok) throw new Error('Failed to fetch capacity');
    const data = await res.json();
    capacityCache = data.services || [];

    renderCapacityGrids(capacityCache);
  } catch (err) {
    console.error('Error loading capacity:', err);
    showToast('Failed to load capacity records: ' + err.message, 'error');
  }
}

function renderCapacityGrids(services) {
  const homamGrid = document.getElementById('homamCapacityGrid');
  const poojaGrid = document.getElementById('poojaCapacityGrid');

  const homams = services.filter(s => s.type === 'homam');
  const poojas = services.filter(s => s.type === 'pooja');

  if (homamGrid) {
    homamGrid.innerHTML = homams.map(renderCapacityCardHtml).join('');
  }

  if (poojaGrid) {
    poojaGrid.innerHTML = poojas.map(renderCapacityCardHtml).join('');
  }
}

function renderCapacityCardHtml(s) {
  const pct = Math.min(100, Math.round((s.confirmed / s.limit) * 100));
  const isFull = s.is_full;
  const isEnabled = s.is_enabled;

  return `
    <div class="capacity-card ${isFull ? 'full' : ''} ${!isEnabled ? 'disabled-card' : ''}">
      <div class="cap-header">
        <span class="cap-title">${escapeHtml(s.name)}</span>
        <div>
          ${!isEnabled ? '<span class="badge badge-muted">Coming Soon</span>' : ''}
          <span class="badge ${isFull ? 'badge-rejected' : 'badge-accepted'}">
            ${isFull ? 'Bookings Closed (50/50)' : `${s.available} / ${s.limit} Available`}
          </span>
        </div>
      </div>
      <div class="cap-progress-bg">
        <div class="cap-progress-bar" style="width: ${pct}%;"></div>
      </div>
      <div class="cap-meta">
        <span>Confirmed Bookings: <strong>${s.confirmed}</strong></span>
        <span>Limit: <strong>${s.limit}</strong> (${pct}%)</span>
      </div>
      <div class="cap-sub-status">
        ${isFull ? '⚠️ Capacity limit enforced: Direct & checkout booking blocked' : '✓ Accepting bookings'}
      </div>
    </div>
  `;
}

function filterCapacityCards() {
  const query = document.getElementById('capacitySearchInput')?.value.toLowerCase().trim() || '';
  if (!query) {
    renderCapacityGrids(capacityCache);
    return;
  }
  const filtered = capacityCache.filter(s => s.name.toLowerCase().includes(query));
  renderCapacityGrids(filtered);
}

// =========================================================================
// VIEW 7: AUDIT LOGS
// =========================================================================

async function loadAuditLogs() {
  const tbody = document.getElementById('auditLogsTbody');
  if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="table-empty">Loading audit trail...</td></tr>';

  try {
    const res = await adminApi('/api/admin/audit-logs?page=1&limit=50');
    if (!res.ok) throw new Error('Failed to fetch audit logs');
    const data = await res.json();
    const logs = data.logs || [];

    if (tbody) {
      if (logs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="table-empty">No audit logs recorded yet.</td></tr>';
        return;
      }

      tbody.innerHTML = logs.map(l => `
        <tr>
          <td><strong>#${l.id}</strong></td>
          <td>${formatIST(l.timestamp)}</td>
          <td><code>${escapeHtml(l.admin_email || 'info@taraastrovision.com')}</code></td>
          <td><span class="audit-action-tag">${escapeHtml(l.action)}</span></td>
          <td>${l.booking_id ? `<strong>#${l.booking_id}</strong>` : '—'}</td>
          <td><div class="cell-main">${escapeHtml(l.details || '—')}</div></td>
          <td><small>${escapeHtml(l.ip_address || '—')}</small></td>
        </tr>
      `).join('');
    }
  } catch (err) {
    console.error('Error loading audit logs:', err);
    if (tbody) tbody.innerHTML = `<tr><td colspan="7" class="table-empty text-danger">Error: ${escapeHtml(err.message)}</td></tr>`;
  }
}

// =========================================================================
// BOOKING ACTIONS (ACCEPT / REJECT / SCHEDULE / RESCHEDULE)
// =========================================================================

async function acceptBooking(bookingId) {
  const b = bookingsCache[bookingId];
  const name = b ? b.customer_name : `#${bookingId}`;
  if (!confirm(`Are you sure you want to accept booking #${bookingId} (${name})?\nAn acceptance confirmation email will be sent to the customer.`)) {
    return;
  }

  try {
    const res = await adminApi(`/api/admin/bookings/${bookingId}/accept`, {
      method: 'POST',
      body: { admin_notes: 'Accepted via Admin Console' }
    });

    const data = await res.json().catch(() => ({}));

    if (res.ok) {
      showToast(`Booking #${bookingId} accepted successfully! Confirmation email sent.`, 'success');
      refreshCurrentView();
    } else {
      showToast(data.detail || 'Failed to accept booking', 'error');
    }
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

function openRejectModal(bookingId) {
  const b = bookingsCache[bookingId];
  const hiddenInput = document.getElementById('rejectBookingId');
  const banner = document.getElementById('rejectSummaryBanner');
  const reasonInput = document.getElementById('rejectReason');
  const notesInput = document.getElementById('rejectAdminNotes');

  if (hiddenInput) hiddenInput.value = bookingId;
  if (reasonInput) reasonInput.value = '';
  if (notesInput) notesInput.value = '';

  if (banner) {
    if (b) {
      banner.innerHTML = `
        <div class="banner-title">Rejecting Booking #${b.id} — ${escapeHtml(b.service_name || 'Service')}</div>
        <div class="banner-sub">
          Customer: <strong>${escapeHtml(b.customer_name)}</strong> (${escapeHtml(b.customer_email)})<br>
          Amount Paid: <strong>${formatCurrency(b.amount || 0)}</strong> | Razorpay ID: <code>${escapeHtml(b.razorpay_payment_id || 'N/A')}</code>
        </div>
      `;
    } else {
      banner.innerHTML = `<div>Rejecting Booking #${bookingId}</div>`;
    }
  }

  openModal('modalReject');
}

async function submitRejectBooking(event) {
  event.preventDefault();
  const bookingId = document.getElementById('rejectBookingId')?.value;
  const reason = document.getElementById('rejectReason')?.value.trim();
  const notes = document.getElementById('rejectAdminNotes')?.value.trim();
  const btn = document.getElementById('btnConfirmReject');

  if (!bookingId || !reason) {
    showToast('Please state a reason for rejecting the booking.', 'warn');
    return;
  }

  setButtonLoading(btn, true, 'Processing Refund...');

  try {
    const res = await adminApi(`/api/admin/bookings/${bookingId}/reject`, {
      method: 'POST',
      body: { reason, admin_notes: notes }
    });

    const data = await res.json().catch(() => ({}));

    if (res.ok) {
      closeModal('modalReject');
      const refundMsg = data.refund_id ? ` Refund ID: ${data.refund_id}` : '';
      showToast(`Booking #${bookingId} rejected.${refundMsg} Customer has been notified.`, 'success');
      refreshCurrentView();
    } else {
      showToast(data.detail || 'Failed to reject booking.', 'error');
    }
  } catch (err) {
    showToast('Network error: ' + err.message, 'error');
  } finally {
    setButtonLoading(btn, false, 'Confirm Rejection & Refund');
  }
}

function openScheduleModal(bookingId) {
  const b = bookingsCache[bookingId];
  const hiddenInput = document.getElementById('scheduleBookingId');
  const banner = document.getElementById('scheduleSummaryBanner');
  const dateInput = document.getElementById('scheduleDate');
  const timeInput = document.getElementById('scheduleTime');
  const errBox = document.getElementById('scheduleCollisionError');

  if (hiddenInput) hiddenInput.value = bookingId;
  if (errBox) { errBox.classList.add('hidden'); errBox.textContent = ''; }

  // Set default date to tomorrow if not set
  if (dateInput && !dateInput.value) {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    dateInput.value = tomorrow.toISOString().split('T')[0];
  }
  if (timeInput && !timeInput.value) {
    timeInput.value = '10:00';
  }

  if (banner && b) {
    banner.innerHTML = `
      <div class="banner-title">Scheduling Consultation #${b.id}</div>
      <div class="banner-sub">
        Devotee: <strong>${escapeHtml(b.customer_name)}</strong> | Phone: <strong>${escapeHtml(b.customer_phone)}</strong><br>
        Topic / Inquiry: <em>${escapeHtml(b.notes || b.service_name || 'General Vedic Horoscope Consultation')}</em>
      </div>
    `;
  }

  openModal('modalSchedule');
}

async function submitScheduleConsultation(event) {
  event.preventDefault();
  const bookingId = document.getElementById('scheduleBookingId')?.value;
  const date = document.getElementById('scheduleDate')?.value;
  const time = document.getElementById('scheduleTime')?.value;
  const meetingLink = document.getElementById('scheduleMeetingLink')?.value.trim();
  const notes = document.getElementById('scheduleNotes')?.value.trim();
  const btn = document.getElementById('btnConfirmSchedule');
  const errBox = document.getElementById('scheduleCollisionError');

  if (!bookingId || !date || !time) {
    showToast('Please specify date and time for the appointment.', 'warn');
    return;
  }

  setButtonLoading(btn, true, 'Checking Availability...');
  if (errBox) { errBox.classList.add('hidden'); errBox.textContent = ''; }

  try {
    const res = await adminApi(`/api/admin/bookings/${bookingId}/schedule`, {
      method: 'POST',
      body: {
        date,
        time,
        meeting_link: meetingLink,
        admin_notes: notes
      }
    });

    const data = await res.json().catch(() => ({}));

    if (res.ok) {
      closeModal('modalSchedule');
      showToast(`Consultation #${bookingId} scheduled for ${date} at ${time} IST. Devotee notified!`, 'success');
      refreshCurrentView();
    } else if (res.status === 409) {
      if (errBox) {
        errBox.textContent = '⚠️ ' + (data.detail || 'Time slot collision detected. Please choose another time.');
        errBox.classList.remove('hidden');
      }
    } else {
      showToast(data.detail || 'Failed to schedule consultation.', 'error');
    }
  } catch (err) {
    showToast('Network error: ' + err.message, 'error');
  } finally {
    setButtonLoading(btn, false, 'Confirm Schedule & Email Customer');
  }
}

function openRescheduleModal(bookingId) {
  const b = bookingsCache[bookingId];
  const hiddenInput = document.getElementById('rescheduleBookingId');
  const banner = document.getElementById('rescheduleSummaryBanner');
  const dateInput = document.getElementById('rescheduleDate');
  const timeInput = document.getElementById('rescheduleTime');
  const reasonInput = document.getElementById('rescheduleReason');
  const notesInput = document.getElementById('rescheduleNotes');
  const errBox = document.getElementById('rescheduleCollisionError');

  if (hiddenInput) hiddenInput.value = bookingId;
  if (reasonInput) reasonInput.value = '';
  if (notesInput) notesInput.value = '';
  if (errBox) { errBox.classList.add('hidden'); errBox.textContent = ''; }

  if (banner && b) {
    banner.innerHTML = `
      <div class="banner-title">Rescheduling Consultation #${b.id}</div>
      <div class="banner-sub">
        Current Appointment: <strong>${b.scheduled_time ? formatIST(b.scheduled_time) : 'Not set'}</strong><br>
        Customer: <strong>${escapeHtml(b.customer_name)}</strong> (${escapeHtml(b.customer_phone)})
      </div>
    `;
  }

  openModal('modalReschedule');
}

async function submitRescheduleConsultation(event) {
  event.preventDefault();
  const bookingId = document.getElementById('rescheduleBookingId')?.value;
  const date = document.getElementById('rescheduleDate')?.value;
  const time = document.getElementById('rescheduleTime')?.value;
  const reason = document.getElementById('rescheduleReason')?.value.trim();
  const notes = document.getElementById('rescheduleNotes')?.value.trim();
  const btn = document.getElementById('btnConfirmReschedule');
  const errBox = document.getElementById('rescheduleCollisionError');

  if (!bookingId || !date || !time) {
    showToast('Please specify a new date and time.', 'warn');
    return;
  }

  setButtonLoading(btn, true, 'Updating Appointment...');
  if (errBox) { errBox.classList.add('hidden'); errBox.textContent = ''; }

  try {
    const res = await adminApi(`/api/admin/bookings/${bookingId}/reschedule`, {
      method: 'POST',
      body: {
        new_date: date,
        new_time: time,
        reason,
        admin_notes: notes
      }
    });

    const data = await res.json().catch(() => ({}));

    if (res.ok) {
      closeModal('modalReschedule');
      showToast(`Consultation rescheduled to ${date} at ${time} IST. Devotee notified!`, 'success');
      refreshCurrentView();
    } else if (res.status === 409) {
      if (errBox) {
        errBox.textContent = '⚠️ ' + (data.detail || 'Time slot collision detected. Please choose another slot.');
        errBox.classList.remove('hidden');
      }
    } else {
      showToast(data.detail || 'Failed to reschedule appointment.', 'error');
    }
  } catch (err) {
    showToast('Network error: ' + err.message, 'error');
  } finally {
    setButtonLoading(btn, false, 'Update Schedule & Notify');
  }
}

async function retryRefund(bookingId) {
  if (!confirm(`Attempt to re-trigger Razorpay refund for Booking #${bookingId}?`)) return;

  try {
    const res = await adminApi(`/api/admin/bookings/${bookingId}/retry-refund`, {
      method: 'POST'
    });
    const data = await res.json().catch(() => ({}));

    if (res.ok) {
      showToast(`Refund processed successfully! Refund ID: ${data.refund_id}`, 'success');
      loadPayments();
    } else {
      showToast(data.detail || 'Refund retry failed. Check Razorpay dashboard.', 'error');
    }
  } catch (err) {
    showToast('Network error: ' + err.message, 'error');
  }
}

// =========================================================================
// MODAL 1: BOOKING DETAIL VIEW
// =========================================================================

async function viewBookingDetail(bookingId) {
  const modalBody = document.getElementById('detailModalBody');
  const title = document.getElementById('detailModalTitle');
  if (title) title.textContent = `Booking Details #${bookingId}`;
  if (modalBody) modalBody.innerHTML = '<div class="table-empty">Fetching booking data from server...</div>';

  openModal('modalDetail');

  try {
    const res = await adminApi(`/api/admin/bookings/${bookingId}`);
    if (!res.ok) throw new Error('Could not retrieve booking details');
    const data = await res.json();
    const b = data.booking;
    bookingsCache[b.id] = b;

    let participantsHtml = '—';
    if (b.participants) {
      try {
        const pList = typeof b.participants === 'string' ? JSON.parse(b.participants) : b.participants;
        if (Array.isArray(pList) && pList.length > 0) {
          participantsHtml = '<ul class="participants-list">' + pList.map(p => `
            <li><strong>${escapeHtml(p.name || 'Member')}</strong>: Gotra: ${escapeHtml(p.gotra || '—')}, Nakshatra: ${escapeHtml(p.nakshatra || '—')}, Rasi: ${escapeHtml(p.rasi || '—')}</li>
          `).join('') + '</ul>';
        }
      } catch (e) {
        participantsHtml = escapeHtml(String(b.participants));
      }
    }

    if (modalBody) {
      modalBody.innerHTML = `
        <div class="detail-grid">
          <div class="detail-section">
            <h4>📋 Booking Summary</h4>
            <div class="detail-row"><span class="lbl">Booking ID:</span> <strong>#${b.id}</strong></div>
            <div class="detail-row"><span class="lbl">Service Name:</span> <strong>${escapeHtml(b.service_name || 'N/A')}</strong></div>
            <div class="detail-row"><span class="lbl">Service Type:</span> <span class="type-pill ${b.service_type}">${b.service_type}</span></div>
            <div class="detail-row"><span class="lbl">Booking Status:</span> ${renderStatusBadge(b.booking_status)}</div>
            <div class="detail-row"><span class="lbl">Created (IST):</span> ${formatIST(b.created_at)}</div>
            ${b.accepted_at ? `<div class="detail-row"><span class="lbl">Accepted At:</span> ${formatIST(b.accepted_at)}</div>` : ''}
            ${b.rejected_at ? `<div class="detail-row"><span class="lbl">Rejected At:</span> ${formatIST(b.rejected_at)}</div>` : ''}
            ${b.rejection_reason ? `<div class="detail-row"><span class="lbl">Rejection Reason:</span> <span class="text-danger">${escapeHtml(b.rejection_reason)}</span></div>` : ''}
          </div>

          <div class="detail-section">
            <h4>👤 Devotee / Customer Information</h4>
            <div class="detail-row"><span class="lbl">Full Name:</span> <strong>${escapeHtml(b.customer_name || '—')}</strong></div>
            <div class="detail-row"><span class="lbl">Phone:</span> <a href="tel:${escapeHtml(b.customer_phone || '')}">${escapeHtml(b.customer_phone || '—')}</a></div>
            <div class="detail-row"><span class="lbl">Email:</span> <a href="mailto:${escapeHtml(b.customer_email || '')}">${escapeHtml(b.customer_email || '—')}</a></div>
            <div class="detail-row"><span class="lbl">Address:</span> ${escapeHtml(b.address || '—')}</div>
          </div>

          <div class="detail-section">
            <h4>🪐 Vedic Astrological Details</h4>
            <div class="detail-row"><span class="lbl">Gotra:</span> <strong>${escapeHtml(b.gotra || '—')}</strong></div>
            <div class="detail-row"><span class="lbl">Nakshatra:</span> <strong>${escapeHtml(b.nakshatra || '—')}</strong></div>
            <div class="detail-row"><span class="lbl">Rasi:</span> <strong>${escapeHtml(b.rasi || '—')}</strong></div>
            <div class="detail-row"><span class="lbl">Sankalpam Wish:</span> <em>${escapeHtml(b.sankalpam || '—')}</em></div>
            <div class="detail-row"><span class="lbl">No. of Persons:</span> ${b.num_persons || 1}</div>
            <div class="detail-row"><span class="lbl">Additional Participants:</span> ${participantsHtml}</div>
          </div>

          <div class="detail-section">
            <h4>💳 Payment &amp; Refund Records</h4>
            <div class="detail-row"><span class="lbl">Amount:</span> <strong>${formatCurrency(b.amount || 0)}</strong></div>
            <div class="detail-row"><span class="lbl">Payment Status:</span> ${renderPaymentBadge(b.payment_status, b.refund_status)}</div>
            <div class="detail-row"><span class="lbl">Razorpay Order ID:</span> <code>${escapeHtml(b.razorpay_order_id || '—')}</code></div>
            <div class="detail-row"><span class="lbl">Razorpay Payment ID:</span> <code>${escapeHtml(b.razorpay_payment_id || '—')}</code></div>
            ${b.refund_id ? `
              <div class="detail-row"><span class="lbl">Refund ID:</span> <code>${escapeHtml(b.refund_id)}</code></div>
              <div class="detail-row"><span class="lbl">Refund Status:</span> ${renderRefundBadge(b.refund_status)}</div>
              <div class="detail-row"><span class="lbl">Refund Amount:</span> ${formatCurrency(b.refund_amount || b.amount || 0)}</div>
              <div class="detail-row"><span class="lbl">Refund Initiated:</span> ${formatIST(b.refund_initiated_at)}</div>
            ` : ''}
            ${b.refund_error ? `
              <div class="detail-row"><span class="lbl">Refund Error:</span> <span class="text-danger">${escapeHtml(b.refund_error)}</span></div>
            ` : ''}
          </div>

          ${b.service_type === 'consultation' ? `
            <div class="detail-section full-span">
              <h4>🔮 Consultation Scheduling</h4>
              <div class="detail-row"><span class="lbl">Scheduled Time (IST):</span> <strong>${b.scheduled_time ? formatIST(b.scheduled_time) : 'Not Scheduled'}</strong></div>
              <div class="detail-row"><span class="lbl">Consultation Mode:</span> ${escapeHtml(b.consultation_type || 'Phone')}</div>
              <div class="detail-row"><span class="lbl">Devotee Inquiry:</span> <em>${escapeHtml(b.notes || '—')}</em></div>
              <div class="detail-row"><span class="lbl">Admin Internal Notes:</span> <em>${escapeHtml(b.admin_notes || '—')}</em></div>
            </div>
          ` : `
            <div class="detail-section full-span">
              <h4>📝 Notes &amp; Instructions</h4>
              <div class="detail-row"><span class="lbl">Special Requests:</span> <em>${escapeHtml(b.special_requests || 'None')}</em></div>
              <div class="detail-row"><span class="lbl">Admin Notes:</span> <em>${escapeHtml(b.admin_notes || 'None')}</em></div>
            </div>
          `}
        </div>
      `;
    }
  } catch (err) {
    if (modalBody) {
      modalBody.innerHTML = `<div class="table-empty text-danger">Error: ${escapeHtml(err.message)}</div>`;
    }
  }
}

// =========================================================================
// UI HELPERS & FORMATTERS
// =========================================================================

function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove('hidden');
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.add('hidden');
}

function renderStatusBadge(status) {
  const s = (status || 'pending').toLowerCase();
  switch (s) {
    case 'accepted':
    case 'confirmed':
      return '<span class="badge badge-accepted">✓ Accepted</span>';
    case 'rejected':
      return '<span class="badge badge-rejected">✕ Rejected</span>';
    case 'scheduled':
      return '<span class="badge badge-scheduled">🗓️ Scheduled</span>';
    case 'rescheduled':
      return '<span class="badge badge-scheduled">🔄 Rescheduled</span>';
    case 'completed':
      return '<span class="badge badge-accepted">✓ Completed</span>';
    case 'pending':
    default:
      return '<span class="badge badge-pending">⏳ Pending Review</span>';
  }
}

function renderPaymentBadge(paymentStatus, refundStatus) {
  if (refundStatus === 'processed' || refundStatus === 'completed') {
    return '<span class="badge badge-refunded">↩ Refunded</span>';
  }
  if (refundStatus === 'pending') {
    return '<span class="badge badge-pending">⏳ Refund Pending</span>';
  }
  if (refundStatus === 'failed') {
    return '<span class="badge badge-rejected">⚠️ Refund Failed</span>';
  }

  const p = (paymentStatus || 'unpaid').toLowerCase();
  switch (p) {
    case 'paid':
    case 'captured':
    case 'success':
      return '<span class="badge badge-paid">● Paid</span>';
    case 'failed':
      return '<span class="badge badge-failed">● Failed</span>';
    default:
      return '<span class="badge badge-unpaid">○ Unpaid</span>';
  }
}

function renderRefundBadge(status) {
  const s = (status || '').toLowerCase();
  switch (s) {
    case 'processed':
    case 'completed':
      return '<span class="badge badge-accepted">✓ Processed</span>';
    case 'pending':
      return '<span class="badge badge-pending">⏳ In Process</span>';
    case 'failed':
      return '<span class="badge badge-rejected">✕ Failed</span>';
    default:
      return '<span class="badge badge-muted">Not Initiated</span>';
  }
}

function formatIST(isoDate) {
  if (!isoDate) return '—';
  try {
    const d = new Date(isoDate);
    if (isNaN(d.getTime())) return escapeHtml(isoDate);
    return d.toLocaleString('en-IN', {
      timeZone: 'Asia/Kolkata',
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    });
  } catch (e) {
    return escapeHtml(isoDate);
  }
}

function formatCurrency(val) {
  const num = Number(val) || 0;
  return '₹' + num.toLocaleString('en-IN');
}

function setText(elementId, text) {
  const el = document.getElementById(elementId);
  if (el) el.textContent = text;
}

function setButtonLoading(btn, isLoading, loadingText = '') {
  if (!btn) return;
  btn.disabled = isLoading;
  const textEl = btn.querySelector('.btn-text');
  const spinEl = btn.querySelector('.btn-spinner');
  if (textEl && loadingText) textEl.textContent = loadingText;
  if (spinEl) {
    if (isLoading) spinEl.classList.remove('hidden');
    else spinEl.classList.add('hidden');
  }
}

function debounceSearch(view) {
  clearTimeout(searchDebounceTimer);
  searchDebounceTimer = setTimeout(() => {
    if (view === 'homam') loadHomamBookings();
    else if (view === 'pooja') loadPoojaBookings();
    else if (view === 'consult') loadConsultationBookings();
  }, 350);
}

function showToast(message, type = 'info') {
  const toast = document.getElementById('toast');
  if (!toast) return;

  toast.textContent = message;
  toast.className = `toast toast-${type}`;
  toast.classList.remove('hidden');

  setTimeout(() => {
    toast.classList.add('hidden');
  }, 4000);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
