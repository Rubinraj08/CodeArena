// ─── Auth Logic ───
const tabs = { login: document.getElementById('login-tab'), register: document.getElementById('register-tab') };
const forms = { login: document.getElementById('login-form'), register: document.getElementById('register-form') };
const msgDiv = document.getElementById('auth-msg');

function switchTab(tab) {
  Object.keys(tabs).forEach(k => {
    tabs[k].classList.toggle('active', k === tab);
    forms[k].classList.toggle('active', k === tab);
  });
  msgDiv.innerHTML = '';
}

// Role selection
document.querySelectorAll('.role-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.role-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  });
});

// Login
document.getElementById('login-form').addEventListener('submit', async e => {
  e.preventDefault();
  const btn = e.target.querySelector('button[type=submit]');
  btn.disabled = true; btn.textContent = 'Authenticating...';
  const res = await fetch('/login', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      username: document.getElementById('login-username').value,
      password: document.getElementById('login-password').value
    })
  });
  const data = await res.json();
  if (data.success) {
    msgDiv.innerHTML = '<div class="alert alert-success">✅ Login successful! Redirecting...</div>';
    setTimeout(() => window.location.href = data.redirect, 600);
  } else {
    msgDiv.innerHTML = `<div class="alert alert-danger">❌ ${data.message}</div>`;
    btn.disabled = false; btn.textContent = 'Enter Arena';
  }
});

// Register
document.getElementById('register-form').addEventListener('submit', async e => {
  e.preventDefault();
  const btn = e.target.querySelector('button[type=submit]');
  const role = document.querySelector('.role-btn.active')?.dataset.role || 'student';
  btn.disabled = true; btn.textContent = 'Creating...';
  const res = await fetch('/register', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      username: document.getElementById('reg-username').value,
      email: document.getElementById('reg-email').value,
      password: document.getElementById('reg-password').value,
      role: role
    })
  });
  const data = await res.json();
  if (data.success) {
    msgDiv.innerHTML = '<div class="alert alert-success">✅ Account created! Entering arena...</div>';
    setTimeout(() => window.location.href = data.redirect, 600);
  } else {
    msgDiv.innerHTML = `<div class="alert alert-danger">❌ ${data.message}</div>`;
    btn.disabled = false; btn.textContent = 'Join Arena';
  }
});
