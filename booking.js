/* ═══════════════════════════════════════════════════════════
   TARA ASTRO VISION — Pooja & Homam Booking System
   Flow: Select Item → Participant Details → Payment → Confirmation
   ═══════════════════════════════════════════════════════════ */

const BOOKING = {
  currentBooking: null,
  RELATION_OPTIONS: [
    'Self', 'Spouse', 'Wife', 'Husband', 'Son', 'Daughter',
    'Father', 'Mother', 'Brother', 'Sister', 'Grandfather', 'Grandmother',
    'Uncle', 'Aunt', 'Cousin', 'Other'
  ],

  generateId() {
    return 'TAV-' + Date.now() + '-' + Math.random().toString(36).substr(2, 6).toUpperCase();
  },

  initBooking(type, name, price, persons) {
    this.currentBooking = {
      id: this.generateId(),
      type,
      name,
      price,
      persons: persons || 1,
      participants: [],
      scheduledDate: '', // YYYY-MM-DD; shared by all participants
      contactEmail: '',
      contactPhone: '',
      submittedAt: null,
      status: 'draft'
    };
    return this.currentBooking;
  },

  getParticipantCount() {
    if (!this.currentBooking) return 0;
    if (this.currentBooking.type === 'homam') {
      return Math.max(1, parseInt(this.currentBooking.persons) || 1);
    }
    return Math.max(1, this.currentBooking.participants.length || 1);
  },

  addParticipant() {
    if (!this.currentBooking) return;
    if (this.currentBooking.type === 'homam') return; // Homam has fixed count
    const idx = this.currentBooking.participants.length + 1;
    this.currentBooking.participants.push({
      name: '',
      gotra: '',
      relation: ''
    });
    return idx;
  },

  removeParticipant(index) {
    if (!this.currentBooking || index <= 0) return;
    this.currentBooking.participants.splice(index - 1, 1);
  },

  ensureParticipantSections() {
    if (!this.currentBooking) return;
    if (this.currentBooking.type === 'homam') {
      const n = Math.max(1, parseInt(this.currentBooking.persons) || 1);
      while (this.currentBooking.participants.length < n) {
        this.currentBooking.participants.push({ name: '', gotra: '', relation: '' });
      }
      this.currentBooking.participants = this.currentBooking.participants.slice(0, n);
    } else if (this.currentBooking.participants.length === 0) {
      this.currentBooking.participants.push({ name: '', gotra: '', relation: 'Self' });
    }
  }
};

// ─── Service Booking Limit & Availability (50 per service) ───────────────────
window.SERVICE_AVAILABILITY = {};

const CANONICAL_SERVICE_MAP = {
  'Prathyangira Homam': 'Pratyangira Homam',
  'Pratyangira Homam': 'Pratyangira Homam',
  'Bhagalamukhi Homam': 'Bagalamukhi Homam',
  'Bagalamukhi Homam': 'Bagalamukhi Homam',
  'Bhairavi Homam': 'Tripura Bhairavi Homam',
  'Tripura Bhairavi Homam': 'Tripura Bhairavi Homam',
  'Shodasi Homam': 'Shodashi Homam',
  'Shodashi Homam': 'Shodashi Homam',
  'Kalabhairava Homam': 'Kala Bhairava Homam',
  'Kala Bhairava Homam': 'Kala Bhairava Homam',
  'Sudarsana Homam': 'Sudarshana Homam',
  'Sudarshana Homam': 'Sudarshana Homam',
  'Vaarahi Homam': 'Varahi Homam',
  'Varahi Homam': 'Varahi Homam',
};

function getCanonicalServiceName(name) {
  const n = (name || '').trim();
  return CANONICAL_SERVICE_MAP[n] || n;
}

function getServiceAvailabilityInfo(name) {
  if (!window.SERVICE_AVAILABILITY) return null;
  const n = (name || '').trim();
  const canon = getCanonicalServiceName(n);
  return window.SERVICE_AVAILABILITY[n] || window.SERVICE_AVAILABILITY[canon] || null;
}

function updateServiceAvailabilityUI(availabilityMap) {
  if (!availabilityMap) return;

  // 1. Process all Pooja cards
  document.querySelectorAll('.pooja-card').forEach(card => {
    const nameEl = card.querySelector('.pooja-name');
    const bookBtn = card.querySelector('.btn-add-cart') || card.querySelector('button');
    let serviceName = '';

    if (bookBtn && bookBtn.getAttribute('onclick')) {
      const match = bookBtn.getAttribute('onclick').match(/startPoojaBooking\(\s*['"]([^'"]+)['"]/);
      if (match) serviceName = match[1];
    }
    if (!serviceName && bookBtn && bookBtn.dataset.name) {
      serviceName = bookBtn.dataset.name;
    }
    if (!serviceName && nameEl) {
      serviceName = nameEl.textContent.trim();
    }
    if (!serviceName) return;

    const info = getServiceAvailabilityInfo(serviceName);
    if (!info) return;

    let badge = card.querySelector('.service-slot-badge');
    if (!badge) {
      badge = document.createElement('div');
      badge.className = 'service-slot-badge';
      if (bookBtn) {
        card.insertBefore(badge, bookBtn);
      } else {
        card.appendChild(badge);
      }
    }

    if (info.sold_out) {
      badge.className = 'service-slot-badge sold-out';
      badge.textContent = 'Bookings Closed — Maximum Capacity Reached (50/50)';
      if (bookBtn) {
        bookBtn.disabled = true;
        bookBtn.classList.add('btn-disabled', 'sold-out');
        bookBtn.setAttribute('aria-disabled', 'true');
        bookBtn.textContent = 'Bookings Closed (50/50)';
      }
    } else {
      const isLow = info.remaining <= 5;
      badge.className = `service-slot-badge available ${isLow ? 'slot-low' : ''}`;
      badge.textContent = `Available Slots: ${info.remaining}/${info.max_limit}`;
      if (bookBtn && !bookBtn.classList.contains('btn-disabled')) {
        bookBtn.disabled = false;
        bookBtn.classList.remove('sold-out');
      }
    }
  });

  // 2. Process all Homam cards
  document.querySelectorAll('.homam-card').forEach(card => {
    const nameEl = card.querySelector('.homam-name');
    const bookBtn = card.querySelector('.btn-add-cart') || card.querySelector('button');
    const qtyInput = card.querySelector('.homam-qty');
    let serviceName = '';

    if (bookBtn && bookBtn.getAttribute('onclick')) {
      const match = bookBtn.getAttribute('onclick').match(/startHomamBooking\([^,]+,\s*['"]([^'"]+)['"]/);
      if (match) serviceName = match[1];
    }
    if (!serviceName && bookBtn && bookBtn.dataset.name) {
      serviceName = bookBtn.dataset.name;
    }
    if (!serviceName && nameEl) {
      serviceName = nameEl.textContent.trim();
    }
    if (!serviceName) return;

    const info = getServiceAvailabilityInfo(serviceName);
    if (!info) return;

    let badge = card.querySelector('.service-slot-badge');
    if (!badge) {
      badge = document.createElement('div');
      badge.className = 'service-slot-badge';
      if (bookBtn) {
        card.insertBefore(badge, bookBtn);
      } else {
        card.appendChild(badge);
      }
    }

    if (info.coming_soon) {
      badge.className = 'service-slot-badge coming-soon';
      badge.textContent = 'Coming Soon';
      if (bookBtn) {
        bookBtn.disabled = true;
        bookBtn.classList.add('btn-disabled');
        bookBtn.setAttribute('aria-disabled', 'true');
        bookBtn.textContent = 'Coming Soon';
      }
      if (qtyInput) qtyInput.disabled = true;
    } else if (info.sold_out) {
      badge.className = 'service-slot-badge sold-out';
      badge.textContent = 'Bookings Closed — Maximum Capacity Reached (50/50)';
      if (bookBtn) {
        bookBtn.disabled = true;
        bookBtn.classList.add('btn-disabled', 'sold-out');
        bookBtn.setAttribute('aria-disabled', 'true');
        bookBtn.textContent = 'Bookings Closed (50/50)';
      }
      if (qtyInput) qtyInput.disabled = true;
    } else {
      const isLow = info.remaining <= 5;
      badge.className = `service-slot-badge available ${isLow ? 'slot-low' : ''}`;
      badge.textContent = `Available Slots: ${info.remaining}/${info.max_limit}`;
      if (bookBtn && isHomamEnabled(serviceName)) {
        bookBtn.disabled = false;
        bookBtn.classList.remove('btn-disabled', 'sold-out');
        bookBtn.removeAttribute('aria-disabled');
        bookBtn.innerHTML = '📋 Book Now';
        if (qtyInput) qtyInput.disabled = false;
      }
    }
  });
}

async function fetchServiceAvailability() {
  const apiBase = window.TAV_API_BASE || '';
  try {
    const res = await fetch(`${apiBase}/api/services/availability`);
    if (!res.ok) return;
    const data = await res.json();
    if (data && data.availability) {
      window.SERVICE_AVAILABILITY = data.availability;
      updateServiceAvailabilityUI(data.availability);
    }
  } catch (err) {
    console.warn('Could not load service availability:', err.message);
  }
}

// ─── Start booking from Pooja card ─────────────────────────────────────
function startPoojaBooking(poojaName, price) {
  const avail = getServiceAvailabilityInfo(poojaName);
  if (avail && avail.sold_out) {
    alert(`Bookings Closed — Maximum Capacity Reached (50/50) for ${poojaName}.`);
    return;
  }
  BOOKING.initBooking('pooja', poojaName, price, 1);
  BOOKING.ensureParticipantSections();
  showPage('booking-form');
  renderBookingForm();
}

const ENABLED_HOMAMS = new Set([
  'Pratyangira Homam',
  'Prathyangira Homam',
  'Lakshmi Ganapathi Homam',
  'Kala Bhairava Homam',
  'Kalabhairava Homam',
  'Chandi Mula Mantra Homam'
]);

function isHomamEnabled(name) {
  return ENABLED_HOMAMS.has((name || '').trim());
}

// ─── Start booking from Homam card ─────────────────────────────────────
function startHomamBooking(btn, homamName, pricePerPerson) {
  if (!isHomamEnabled(homamName)) {
    alert('Booking for ' + (homamName || 'this homam') + ' is coming soon.');
    return;
  }
  const avail = getServiceAvailabilityInfo(homamName);
  if (avail && avail.sold_out) {
    alert(`Bookings Closed — Maximum Capacity Reached (50/50) for ${homamName}.`);
    return;
  }
  const card = btn.closest('.homam-card');
  const qtyInput = card ? card.querySelector('.homam-qty') : null;
  const persons = qtyInput ? Math.max(1, parseInt(qtyInput.value) || 1) : 1;
  const totalPrice = pricePerPerson * persons;

  BOOKING.initBooking('homam', homamName, totalPrice, persons);
  BOOKING.currentBooking.pricePerPerson = pricePerPerson;
  BOOKING.ensureParticipantSections();
  showPage('booking-form');
  renderBookingForm();
}

// ─── Render participant form ───────────────────────────────────────────
function renderBookingForm() {
  const b = BOOKING.currentBooking;
  if (!b) {
    showPage('poojas');
    return;
  }

  const container = document.getElementById('bookingFormContainer');
  const summaryEl = document.getElementById('bookingSummary');
  if (!container || !summaryEl) return;

  summaryEl.innerHTML = `
    <div class="booking-summary-card">
      <span class="booking-type-badge">${b.type === 'pooja' ? '🪔 Pooja' : '🔥 Homam'}</span>
      <h3>${b.name}</h3>
      <p class="booking-price">₹${b.price.toLocaleString('en-IN')}${b.type === 'homam' ? ` (${b.persons} person${b.persons > 1 ? 's' : ''})` : ''}</p>
    </div>
  `;

  const minDateEligible = new Date().toISOString().split('T')[0];
  const ritualLabel = b.type === 'pooja' ? 'Pooja' : 'Homam';
  let participantsHtml = `
    <div class="booking-date-section">
      <div class="form-group">
        <label>Date of ${ritualLabel} <span class="required">*</span></label>
        <input type="date" class="form-input" id="bookingScheduledDate" min="${minDateEligible}" value="${escapeHtml(b.scheduledDate || '')}" required />
        <p class="booking-date-hint">This date applies to all participants in this booking.</p>
      </div>
    </div>
  `;

  b.participants.forEach((p, i) => {
    const num = i + 1;
    const isBookingMember = num === 1;
    const relationOptions = BOOKING.RELATION_OPTIONS.map(opt =>
      `<option value="${opt}" ${(p.relation || (isBookingMember ? 'Self' : '')) === opt ? 'selected' : ''}>${opt}</option>`
    ).join('');

    participantsHtml += `
      <div class="participant-section" data-index="${num}">
        <div class="participant-header">
          <span class="participant-label">Participant ${num} ${isBookingMember ? '<strong>(Booking Member)</strong>' : ''}</span>
          ${!isBookingMember && b.type === 'pooja' ? `<button type="button" class="btn-remove-participant" onclick="removeParticipantSection(${num})" title="Remove">✕</button>` : ''}
        </div>
        <div class="participant-fields">
          <div class="form-group">
            <label>Participant Name <span class="required">*</span></label>
            <input type="text" class="form-input participant-name" data-index="${num}" placeholder="Full name" value="${escapeHtml(p.name)}" ${isBookingMember ? 'id="bookingMemberName"' : ''} />
          </div>
          <div class="form-group">
            <label>Gotra <span class="required">*</span></label>
            <input type="text" class="form-input participant-gotra" data-index="${num}" placeholder="e.g. Bharadwaja" value="${escapeHtml(p.gotra)}" />
          </div>
          <div class="form-group">
            <label>Relation with Booking Member <span class="required">*</span></label>
            <select class="form-input participant-relation" data-index="${num}" ${isBookingMember ? 'disabled' : ''}>
              ${relationOptions}
            </select>
          </div>
          ${isBookingMember ? `
          <div class="form-row">
            <div class="form-group">
              <label>Email <span class="required">*</span></label>
              <input type="email" class="form-input" id="bookingContactEmail" placeholder="your@email.com" value="${escapeHtml(b.contactEmail)}" />
            </div>
            <div class="form-group">
              <label>Phone <span class="required">*</span></label>
              <input type="tel" class="form-input" id="bookingContactPhone" placeholder="9014308190" value="${escapeHtml(b.contactPhone)}" />
            </div>
          </div>
          ` : ''}
        </div>
      </div>
    `;
  });

  container.innerHTML = participantsHtml;

  const addBtnContainer = document.getElementById('addParticipantContainer');
  if (addBtnContainer) {
    if (b.type === 'pooja') {
      addBtnContainer.innerHTML = `<button type="button" class="btn-add-participant" onclick="addParticipantSection()">+ Add Participant</button>`;
      addBtnContainer.style.display = '';
    } else {
      addBtnContainer.innerHTML = '';
      addBtnContainer.style.display = 'none';
    }
  }
}

function escapeHtml(s) {
  if (!s) return '';
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

function addParticipantSection() {
  collectParticipantData();
  BOOKING.addParticipant();
  renderBookingForm();
}

function removeParticipantSection(num) {
  if (num <= 1) return;
  collectParticipantData();
  BOOKING.removeParticipant(num);
  renderBookingForm();
}

// ─── Collect form data ─────────────────────────────────────────────────
function collectParticipantData() {
  const b = BOOKING.currentBooking;
  if (!b) return null;

  const participants = [];
  document.querySelectorAll('.participant-section').forEach((section, i) => {
    const idx = i + 1;
    const name = section.querySelector('.participant-name')?.value?.trim() || '';
    const gotra = section.querySelector('.participant-gotra')?.value?.trim() || '';
    const relation = section.querySelector('.participant-relation');
    const relVal = relation?.disabled ? 'Self' : (relation?.value || '');

    participants.push({ name, gotra, relation: relVal });
  });

  b.contactEmail = document.getElementById('bookingContactEmail')?.value?.trim() || '';
  b.contactPhone = document.getElementById('bookingContactPhone')?.value?.trim() || '';
  b.scheduledDate = document.getElementById('bookingScheduledDate')?.value?.trim() || '';
  b.participants = participants;
  return b;
}

// ─── Validate form ───────────────────────────────────────────────────
function validateBookingForm() {
  collectParticipantData();
  const b = BOOKING.currentBooking;
  if (!b) return false;

  const errors = [];
  b.participants.forEach((p, i) => {
    if (!p.name.trim()) errors.push(`Participant ${i + 1}: Name is required`);
    if (!p.gotra.trim()) errors.push(`Participant ${i + 1}: Gotra is required`);
    if (!p.relation.trim()) errors.push(`Participant ${i + 1}: Relation is required`);
  });

  if (!b.contactEmail.trim()) errors.push('Email is required');
  else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(b.contactEmail)) errors.push('Please enter a valid email');
  if (!b.contactPhone.trim()) errors.push('Phone number is required');
  if (!b.scheduledDate || !b.scheduledDate.trim()) {
    errors.push(`Please select the date of the ${b.type === 'pooja' ? 'pooja' : 'homam'}`);
  } else {
    const minD = new Date().toISOString().split('T')[0];
    if (b.scheduledDate < minD) errors.push('Scheduled date cannot be in the past');
  }

  const errEl = document.getElementById('bookingFormError');
  if (errors.length > 0) {
    if (errEl) {
      errEl.textContent = errors.join('. ');
      errEl.classList.remove('hidden');
    }
    return false;
  }
  if (errEl) errEl.classList.add('hidden');
  return true;
}

// ─── Submit form & go to payment ───────────────────────────────────────
function submitBookingForm(e) {
  e.preventDefault();
  if (!validateBookingForm()) return;

  const b = BOOKING.currentBooking;
  b.submittedAt = new Date().toISOString();
  b.status = 'pending_payment';

  showPage('payment');
  renderPaymentPage();
}

// ─── Payment page ───────────────────────────────────────────────────────
function renderPaymentPage() {
  const b = BOOKING.currentBooking;
  if (!b) return;

  const container = document.getElementById('paymentPageContent');
  if (!container) return;

  document.getElementById('paymentPageTitle').textContent = 'Payment';
  document.getElementById('paymentPageSub').textContent = `${b.name} — ₹${b.price.toLocaleString('en-IN')}`;

  const schedDisplay = b.scheduledDate
    ? new Date(b.scheduledDate + 'T12:00:00').toLocaleDateString('en-IN', {
        weekday: 'long',
        day: 'numeric',
        month: 'long',
        year: 'numeric'
      })
    : '—';
  container.innerHTML = `
    <div class="payment-summary-box">
      <h3>Booking Summary</h3>
      <p><strong>${b.name}</strong></p>
      <p><strong>${b.type === 'pooja' ? 'Pooja' : 'Homam'} date:</strong> ${schedDisplay}</p>
      <p>Amount: ₹${b.price.toLocaleString('en-IN')}</p>
      <p>Participants: ${b.participants.length}</p>
      <hr style="border-color:var(--border);margin:16px 0" />
      <p class="payment-note">Pay securely with Razorpay. You will receive a PDF receipt by email once payment succeeds.</p>
      <button id="rzpPayBtn" class="btn-primary full-width" style="margin-top:16px">Pay ₹${b.price.toLocaleString('en-IN')} Now</button>
      <p id="rzpStatus" class="payment-note" style="margin-top:10px"></p>
    </div>
  `;
  const payBtn = document.getElementById('rzpPayBtn');
  if (payBtn) payBtn.addEventListener('click', () => startRazorpayCheckout());
}

// ─── Razorpay Checkout ─────────────────────────────────────────────
function loadRazorpayScript() {
  if (window.Razorpay) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = 'https://checkout.razorpay.com/v1/checkout.js';
    s.onload = resolve;
    s.onerror = () => reject(new Error('Could not load Razorpay checkout'));
    document.body.appendChild(s);
  });
}

/**
 * Parse a fetch Response safely.
 * Returns the JSON body if Content-Type is application/json, otherwise
 * returns an object with a 'detail' key containing the raw text.
 */
async function _safeJson(res) {
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) {
    try { return await res.json(); } catch (_) { /* fall through */ }
  }
  const text = await res.text().catch(() => '');
  return { detail: text || `HTTP ${res.status}` };
}

let _rzpInFlight = false; // guard against double-clicks

async function startRazorpayCheckout() {
  const b = BOOKING.currentBooking;
  if (!b) return;
  if (_rzpInFlight) return; // prevent duplicate submission

  const btn = document.getElementById('rzpPayBtn');
  const statusEl = document.getElementById('rzpStatus');
  const apiBase = window.TAV_API_BASE || '';
  const setStatus = (m, isError) => {
    if (!statusEl) return;
    statusEl.textContent = m;
    statusEl.style.color = isError ? '#e53e3e' : '';
  };

  _rzpInFlight = true;
  if (btn) { btn.disabled = true; btn.textContent = 'Processing…'; }

  const avail = getServiceAvailabilityInfo(b.name);
  if (avail && avail.sold_out) {
    if (btn) { btn.disabled = true; btn.textContent = 'Bookings Closed (50/50)'; }
    setStatus(`Bookings Closed — Maximum Capacity Reached (50/50) for ${b.name}.`, true);
    _rzpInFlight = false;
    return;
  }

  try {
    setStatus('Creating order…', false);

    // Step 1 — server validates service against catalogue and creates a Razorpay order.
    // We send the service name, type, and persons — NOT a browser-calculated price.
    let orderRes;
    try {
      orderRes = await fetch(`${apiBase}/api/payment/order`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: b.name,
          serviceType: b.type || 'pooja',
          persons: b.persons || 1,
          bookingId: b.id,
          contactEmail: b.contactEmail || null,
          contactPhone: b.contactPhone || null,
          participants: b.participants || [],
          scheduledDate: b.scheduledDate || null
        })
      });
    } catch (networkErr) {
      throw new Error(
        'Could not reach the payment server. The backend may be stopped or unavailable. Please try again later or contact support.'
      );
    }

    const orderData = await _safeJson(orderRes);
    if (!orderRes.ok) {
      throw new Error(orderData.detail || `Order creation failed (${orderRes.status})`);
    }
    if (!orderData.order_id || !orderData.key_id) {
      throw new Error('Invalid response from payment server. Please try again.');
    }

    // Use the server-confirmed amount (authoritative), update display
    const confirmedAmount = orderData.amount;   // paise from Razorpay
    const confirmedRupees = confirmedAmount / 100;
    if (btn) btn.textContent = `Pay ₹${confirmedRupees.toLocaleString('en-IN')} Now`;

    setStatus('', false);
    await loadRazorpayScript();

    const first = b.participants && b.participants[0] ? b.participants[0] : {};
    const rzp = new window.Razorpay({
      key: orderData.key_id,
      order_id: orderData.order_id,
      amount: confirmedAmount,
      currency: orderData.currency,
      name: 'Tara Astro Vision',
      description: b.name,
      image: '/logo.jpg',
      prefill: {
        name: first.name || '',
        email: b.contactEmail || '',
        contact: b.contactPhone || ''
      },
      notes: { booking_id: b.id },
      theme: { color: '#c9962b' },

      handler: async function (response) {
        // This handler fires when Razorpay reports success in the browser.
        // We MUST verify the signature server-side before trusting this.
        try {
          setStatus('Verifying payment…', false);

          // Step 2 — server verifies HMAC-SHA256 signature AND fetches the order
          // from Razorpay to confirm amount, currency, and captured status.
          let vr;
          try {
            vr = await fetch(`${apiBase}/api/payment/verify`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                razorpay_order_id:    response.razorpay_order_id,
                razorpay_payment_id:  response.razorpay_payment_id,
                razorpay_signature:   response.razorpay_signature,
                expected_amount_paise: confirmedAmount,
                booking_id: b.id
              })
            });
          } catch (networkErr) {
            throw new Error(
              'Payment completed but verification could not be reached. ' +
              'Please contact support with your Booking ID: ' + b.id
            );
          }

          const vd = await _safeJson(vr);
          if (!vr.ok) {
            throw new Error(vd.detail || 'Payment verification failed. Contact support.');
          }

          // Signature verified — update booking state
          b.razorpayOrderId   = response.razorpay_order_id;
          b.razorpayPaymentId  = response.razorpay_payment_id;
          b.razorpaySignature  = response.razorpay_signature;
          b.paidAt  = new Date().toISOString();

          setStatus('Payment verified! Saving your booking…', false);
          await sendBookingEmails(b, await bookingPdfBase64(b));
          b.status = 'paid';
          b.backendConfirmed = true;

          setStatus('Payment verified and booking saved.', false);
          _rzpInFlight = false;
          if (btn) {
            btn.disabled = false;
            btn.textContent = 'Pay ₹' + confirmedRupees.toLocaleString('en-IN') + ' Now';
          }
          goToConfirmation();

        } catch (err) {
          setStatus(err.message || 'Payment could not be verified. Contact support.', true);
          _rzpInFlight = false;
          if (btn) {
            btn.disabled = false;
            btn.textContent = 'Pay ₹' + b.price.toLocaleString('en-IN') + ' Now';
          }
        }
      },

      modal: {
        ondismiss: () => {
          // Checkout window closed — payment may or may not have been made.
          // Do NOT assume failure; just re-enable the button.
          setStatus('Payment cancelled. You can try again.', false);
          _rzpInFlight = false;
          if (btn) {
            btn.disabled = false;
            btn.textContent = 'Pay ₹' + b.price.toLocaleString('en-IN') + ' Now';
          }
        }
      }
    });

    rzp.on('payment.failed', function (response) {
      const reason = (response.error && response.error.description) || 'Payment failed';
      setStatus('Payment failed: ' + reason, true);
      _rzpInFlight = false;
      if (btn) {
        btn.disabled = false;
        btn.textContent = 'Pay ₹' + b.price.toLocaleString('en-IN') + ' Now';
      }
    });

    rzp.open();

  } catch (err) {
    setStatus(err.message || 'Payment could not be started. Please try again.', true);
    _rzpInFlight = false;
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Pay ₹' + b.price.toLocaleString('en-IN') + ' Now';
    }
  }
}

// ─── PDF Receipt Generation ────────────────────────────────────────────
function generateBookingPDF(booking) {
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF();

  const yStart = 20;
  let y = yStart;

  doc.setFontSize(22);
  doc.setFont('helvetica', 'bold');
  doc.text('Tara Astro Vision', 105, y, { align: 'center' });
  y += 12;

  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');
  doc.text('Booking Receipt', 105, y, { align: 'center' });
  y += 20;

  doc.setDrawColor(201, 150, 43);
  doc.setLineWidth(0.5);
  doc.line(20, y, 190, y);
  y += 15;

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(12);
  doc.text('Booking ID:', 20, y);
  doc.text(booking.id, 70, y);
  y += 8;

  doc.setFont('helvetica', 'normal');
  doc.text('Pooja/Homam:', 20, y);
  doc.text(booking.name, 70, y);
  y += 8;

  if (booking.scheduledDate) {
    const sd = new Date(booking.scheduledDate + 'T12:00:00').toLocaleDateString('en-IN', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric'
    });
    doc.text('Scheduled Pooja/Homam Date:', 20, y);
    doc.text(sd, 70, y);
    y += 8;
  }

  doc.text('Date of Booking:', 20, y);
  doc.text(new Date(booking.paidAt || booking.submittedAt).toLocaleString('en-IN'), 70, y);
  y += 8;

  doc.text('Payment Status:', 20, y);
  doc.setTextColor(76, 175, 80);
  doc.text('Paid', 70, y);
  doc.setTextColor(0, 0, 0);
  y += 8;

  doc.text('Amount:', 20, y);
  doc.text('₹' + booking.price.toLocaleString('en-IN'), 70, y);
  y += 15;

  doc.setFont('helvetica', 'bold');
  doc.text('Participants', 20, y);
  y += 8;

  doc.setFont('helvetica', 'normal');
  booking.participants.forEach((p, i) => {
    doc.text(`${i + 1}. ${p.name}`, 25, y);
    doc.text(`Gotra: ${p.gotra}`, 100, y);
    doc.text(`Relation: ${p.relation}`, 150, y);
    y += 7;
  });

  y += 10;
  doc.setFont('helvetica', 'bold');
  doc.text('Contact Details', 20, y);
  y += 7;
  doc.setFont('helvetica', 'normal');
  doc.text(`Email: ${booking.contactEmail}`, 25, y);
  y += 6;
  doc.text(`Phone: ${booking.contactPhone}`, 25, y);
  y += 15;

  doc.setFontSize(8);
  doc.setTextColor(100, 100, 100);
  doc.text('Thank you for choosing Tara Astro Vision. May divine blessings be with you.', 105, y, { align: 'center' });

  return doc.output('blob');
}

// ─── Confirmation page ─────────────────────────────────────────────────
function renderConfirmationPage() {
  const b = BOOKING.currentBooking;
  if (!b) return;

  const container = document.getElementById('confirmationContent');
  if (!container) return;

  const participantsList = b.participants.map((p, i) =>
    `<li><strong>${p.name}</strong> — Gotra: ${p.gotra}, Relation: ${p.relation}</li>`
  ).join('');

  const schedConfirmed = b.scheduledDate
    ? new Date(b.scheduledDate + 'T12:00:00').toLocaleDateString('en-IN', {
        weekday: 'long',
        day: 'numeric',
        month: 'long',
        year: 'numeric'
      })
    : '—';

  container.innerHTML = `
    <div class="confirmation-success">
      <span class="success-icon">✅</span>
      <h2>Booking Confirmed!</h2>
      <p class="confirmation-id">Booking ID: <strong>${b.id}</strong></p>
      <p>Your ${b.type === 'pooja' ? 'Pooja' : 'Homam'} booking for <strong>${b.name}</strong> has been confirmed.</p>
      <p>A confirmation email has been sent to ${b.contactEmail}</p>
      <div class="confirmation-details">
        <h3>Booking Details</h3>
        <p><strong>${b.type === 'pooja' ? 'Pooja' : 'Homam'} date:</strong> ${schedConfirmed}</p>
        <p><strong>Payment received:</strong> ${new Date(b.paidAt).toLocaleString('en-IN')}</p>
        <p><strong>Amount Paid:</strong> ₹${b.price.toLocaleString('en-IN')}</p>
        <p><strong>Payment Status:</strong> <span class="status-paid">Paid</span></p>
        <h4>Participants</h4>
        <ul>${participantsList}</ul>
        <p><strong>Contact:</strong> ${b.contactEmail} | ${b.contactPhone}</p>
      </div>
      <button class="btn-primary" onclick="downloadBookingReceipt()">📄 Download PDF Receipt</button>
      <button class="btn-secondary" onclick="navigateTo('home', event)" style="margin-left:12px">Return to Home</button>
    </div>
  `;
}

function goToConfirmation() {
  const b = BOOKING.currentBooking;
  if (!b) return;
  showPage('confirmation');
  renderConfirmationPage();
  if (!b.pdfBlob) b.pdfBlob = generateBookingPDF(b);
  if (!b.backendConfirmed) {
    bookingPdfBase64(b)
      .then(pdfBase64 => sendBookingEmails(b, pdfBase64))
      .then(() => { b.backendConfirmed = true; })
      .catch(err => console.error('Booking confirmation could not be saved:', err));
  }
}

async function bookingPdfBase64(booking) {
  if (!booking.pdfBlob) booking.pdfBlob = generateBookingPDF(booking);
  const bytes = new Uint8Array(await booking.pdfBlob.arrayBuffer());
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function downloadBookingReceipt() {
  const b = BOOKING.currentBooking;
  if (!b || !b.pdfBlob) {
    b.pdfBlob = generateBookingPDF(b);
  }
  const url = URL.createObjectURL(b.pdfBlob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `Tara-Astro-Vision-Receipt-${b.id}.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}

// ─── Booking confirmation + email notifications (calls backend) ────────────
function sendBookingEmails(booking, pdfBase64) {
  const apiBase = window.TAV_API_BASE || '';
  const url = `${apiBase}/api/booking/confirm`;

  const payload = {
    id:               booking.id,
    type:             booking.type,
    name:             booking.name,
    price:            booking.price,
    persons:          booking.persons || 1,
    participants:     booking.participants,
    contactEmail:     booking.contactEmail,
    contactPhone:     booking.contactPhone,
    status:           'paid',
    paidAt:           booking.paidAt,
    razorpayOrderId:  booking.razorpayOrderId  || null,
    razorpayPaymentId: booking.razorpayPaymentId || null,
    razorpaySignature: booking.razorpaySignature || null,
    scheduledDate:    booking.scheduledDate || null
  };
  if (pdfBase64) payload.pdfBase64 = pdfBase64;

  return fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
    .then(async res => {
      // Parse response safely regardless of Content-Type
      const ct = res.headers.get('content-type') || '';
      let data;
      if (ct.includes('application/json')) {
        data = await res.json().catch(() => ({}));
      } else {
        const text = await res.text().catch(() => '');
        data = { detail: text };
      }
      if (!res.ok) {
        if (res.status === 409 || (data && data.message && data.message.includes('already'))) {
          fetchServiceAvailability();
          return data;
        }
        throw new Error(data.detail || `Booking confirmation failed (${res.status})`);
      }
      fetchServiceAvailability();
      if (data.emails_sent && (!data.emails_sent.admin || !data.emails_sent.user)) {
        console.warn('Some emails may not have been sent:', data.emails_sent);
      }
      return data;
    })
    .catch(err => {
      console.error('Booking confirm request failed (network):', err.message);
      throw err;
    });
}

// Expose globally
window.startPoojaBooking = startPoojaBooking;
window.startHomamBooking = startHomamBooking;
window.submitBookingForm = submitBookingForm;
window.downloadBookingReceipt = downloadBookingReceipt;
window.fetchServiceAvailability = fetchServiceAvailability;
window.updateServiceAvailabilityUI = updateServiceAvailabilityUI;

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => fetchServiceAvailability());
  } else {
    fetchServiceAvailability();
  }
}
