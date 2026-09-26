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
      paidAt: null,
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

// ─── Start booking from Pooja card ─────────────────────────────────────
function startPoojaBooking(poojaName, price) {
  BOOKING.initBooking('pooja', poojaName, price, 1);
  BOOKING.ensureParticipantSections();
  showPage('booking-form');
  renderBookingForm();
}

// ─── Start booking from Homam card ─────────────────────────────────────
function startHomamBooking(btn, homamName, pricePerPerson) {
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

  document.getElementById('paymentPageTitle').textContent = 'Secure Payment';
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
      <p class="payment-note">Complete your payment to confirm the booking.</p>
    </div>
    <div class="payment-methods" style="margin-top:24px">
      <button class="btn-payment btn-phonepe" onclick="processBookingPayment('PhonePe')">🟣 PhonePe</button>
      <button class="btn-payment btn-gpay" onclick="processBookingPayment('GPay')">🔴🟡🔵🟢 Google Pay</button>
      <div class="payment-divider">OR</div>
      <button class="btn-secondary full-width" onclick="processBookingPayment('Other UPI')">Other UPI ID / Scanner</button>
    </div>
    <div id="paymentProcessingView" class="processing-view hidden">
      <span class="processing-spinner">🔄</span>
      <h3>Processing Payment...</h3>
      <p>Please do not refresh the page.</p>
    </div>
  `;
}

function processBookingPayment(method) {
  document.querySelector('.payment-summary-box')?.classList.add('hidden');
  document.querySelector('.payment-methods')?.classList.add('hidden');
  document.getElementById('paymentProcessingView')?.classList.remove('hidden');

  setTimeout(() => {
    completeBookingPayment();
  }, 2200);
}

function completeBookingPayment() {
  const b = BOOKING.currentBooking;
  if (!b) return;

  b.paidAt = new Date().toISOString();
  b.status = 'confirmed';
  b.paymentMethod = 'UPI';

  // Generate PDF
  const pdfBlob = generateBookingPDF(b);
  b.pdfBlob = pdfBlob;

  // Save to localStorage for persistence (optional)
  try {
    const all = JSON.parse(localStorage.getItem('tav_bookings') || '[]');
    all.push({ ...b, pdfBlob: null });
    localStorage.setItem('tav_bookings', JSON.stringify(all));
  } catch (e) {}

  // Convert PDF to base64 for email attachment, then send
  const reader = new FileReader();
  reader.onload = function () {
    const base64 = (reader.result && reader.result.split(',')[1]) || '';
    sendBookingEmails(b, base64);
  };
  reader.onerror = function () {
    sendBookingEmails(b, null);
  };
  reader.readAsDataURL(pdfBlob);

  showPage('confirmation');
  renderConfirmationPage();
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
      <button class="btn-secondary" onclick="showPage('home')" style="margin-left:12px">Return to Home</button>
    </div>
  `;
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

// ─── Email notifications (calls backend) ───────────────────────────────
function sendBookingEmails(booking, pdfBase64) {
  const apiBase = window.TAV_API_BASE || '';
  const url = apiBase ? `${apiBase}/api/booking/confirm` : '/api/booking/confirm';

  const payload = {
    id: booking.id,
    type: booking.type,
    name: booking.name,
    price: booking.price,
    persons: booking.persons || 1,
    participants: booking.participants,
    contactEmail: booking.contactEmail,
    contactPhone: booking.contactPhone,
    status: booking.status,
    paidAt: booking.paidAt,
    scheduledDate: booking.scheduledDate || null
  };
  if (pdfBase64) payload.pdfBase64 = pdfBase64;

  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
    .then(res => {
      if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
      return res.json();
    })
    .then(data => {
      if (data.emails_sent) {
        if (!data.emails_sent.admin || !data.emails_sent.user) {
          console.warn('Some emails may not have been sent:', data.emails_sent);
        }
      }
    })
    .catch(err => {
      console.error('Booking/email API failed:', err);
    });
}

// Expose globally
window.startPoojaBooking = startPoojaBooking;
window.startHomamBooking = startHomamBooking;
window.submitBookingForm = submitBookingForm;
window.downloadBookingReceipt = downloadBookingReceipt;
window.processBookingPayment = processBookingPayment;
