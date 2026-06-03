/* NiveshAI Auth Page Logic */

let pendingEmail = '';
let selectedRisk = 'moderate';

// ── Panel switching ──────────────────────────────────────────────────────────

function showPanel(name) {
  document.querySelectorAll('.auth-panel').forEach(p => p.classList.add('hidden'));
  document.getElementById('panel-' + name).classList.remove('hidden');
}

// Auto-detect mode from URL param
const urlMode = new URLSearchParams(window.location.search).get('mode');
if (urlMode === 'signup') showPanel('signup');

// ── Helpers ──────────────────────────────────────────────────────────────────

function showError(id, msg) {
  const el = document.getElementById(id);
  el.textContent = msg;
  el.classList.remove('hidden');
}
function hideError(id) { document.getElementById(id).classList.add('hidden'); }
function setBtn(id, txt, disabled = false) {
  const el = document.getElementById(id);
  if (el) { el.textContent = txt; el.disabled = disabled; }
}
function togglePass(id) {
  const el = document.getElementById(id);
  el.type = el.type === 'password' ? 'text' : 'password';
}

// ── Sign In ──────────────────────────────────────────────────────────────────

async function doSignIn() {
  const email = document.getElementById('si-email').value.trim();
  const pass  = document.getElementById('si-pass').value;
  hideError('si-error');

  if (!email || !pass) { showError('si-error', 'Please fill in all fields.'); return; }

  try {
    const res = await fetch('/api/auth/signin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password: pass }),
    });
    const data = await res.json();
    if (!res.ok) { showError('si-error', data.detail || 'Sign in failed.'); return; }

    localStorage.setItem('niveshai_token', data.token);
    localStorage.setItem('niveshai_user', JSON.stringify(data.user));
    window.location.href = '/dashboard';
  } catch (e) {
    showError('si-error', 'Server error. Please try again.');
  }
}

// ── Sign Up ──────────────────────────────────────────────────────────────────

async function doSignUp() {
  const name  = document.getElementById('su-name').value.trim();
  const email = document.getElementById('su-email').value.trim();
  const pass  = document.getElementById('su-pass').value;
  hideError('su-error');

  if (!name || !email || !pass) { showError('su-error', 'Please fill in all fields.'); return; }
  if (pass.length < 6) { showError('su-error', 'Password must be at least 6 characters.'); return; }

  try {
    const res = await fetch('/api/auth/signup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ full_name: name, email, password: pass }),
    });
    const data = await res.json();
    if (!res.ok) { showError('su-error', data.detail || 'Signup failed.'); return; }

    pendingEmail = email;
    document.getElementById('verify-email-display').textContent = email;
    showPanel('verify');

    // If SMTP not configured, server returns the OTP directly — show it on screen
    if (data.otp_visible) {
      const box = document.getElementById('otp-visible-box');
      if (box) {
        box.textContent = data.otp_visible;
        document.getElementById('otp-visible-section').classList.remove('hidden');
      }
      // Auto-fill the OTP boxes
      data.otp_visible.split('').forEach((ch, i) => {
        const el = document.getElementById('otp' + i);
        if (el) el.value = ch;
      });
    }
  } catch (e) {
    showError('su-error', 'Server error. Please try again.');
  }
}

// ── OTP Boxes ────────────────────────────────────────────────────────────────

function otpMove(idx) {
  const val = document.getElementById('otp' + idx).value;
  if (val && idx < 5) {
    document.getElementById('otp' + (idx + 1)).focus();
  }
  // Auto-submit when all 6 filled
  const all = Array.from({ length: 6 }, (_, i) => document.getElementById('otp' + i).value);
  if (all.every(v => v)) doVerify();
}

function getOTP() {
  return Array.from({ length: 6 }, (_, i) => document.getElementById('otp' + i).value).join('');
}

async function doVerify() {
  const otp = getOTP();
  hideError('otp-error');
  if (otp.length < 6) { showError('otp-error', 'Enter all 6 digits.'); return; }

  try {
    const res = await fetch('/api/auth/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: pendingEmail, otp }),
    });
    const data = await res.json();
    if (!res.ok) { showError('otp-error', data.detail || 'Incorrect code.'); return; }

    localStorage.setItem('niveshai_token', data.token);
    localStorage.setItem('niveshai_user', JSON.stringify(data.user));
    showPanel('profile');
  } catch (e) {
    showError('otp-error', 'Server error. Please try again.');
  }
}

async function resendOTP() {
  if (!pendingEmail) return;
  const res = await fetch('/api/auth/resend-otp?email=' + encodeURIComponent(pendingEmail));
  const data = await res.json();

  if (data.otp_visible) {
    const box = document.getElementById('otp-visible-box');
    if (box) {
      box.textContent = data.otp_visible;
      document.getElementById('otp-visible-section').classList.remove('hidden');
    }
    data.otp_visible.split('').forEach((ch, i) => {
      const el = document.getElementById('otp' + i);
      if (el) el.value = ch;
    });
  } else {
    alert('New code sent! Check your inbox.');
  }
}

// ── Profile Setup ─────────────────────────────────────────────────────────────

function selectRisk(val) {
  selectedRisk = val;
  document.querySelectorAll('.risk-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('risk-' + val).classList.add('active');
}

async function doCompleteProfile() {
  const token = localStorage.getItem('niveshai_token');
  if (token) {
    try {
      await fetch('/api/auth/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
        body: JSON.stringify({ risk_profile: selectedRisk }),
      });
    } catch {}
  }
  window.location.href = '/dashboard';
}

// ── Enter key support ─────────────────────────────────────────────────────────

document.addEventListener('keydown', e => {
  if (e.key !== 'Enter') return;
  const active = document.querySelector('.auth-panel:not(.hidden)');
  if (!active) return;
  const id = active.id;
  if (id === 'panel-signin')  doSignIn();
  if (id === 'panel-signup')  doSignUp();
  if (id === 'panel-verify')  doVerify();
});
