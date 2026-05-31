let token = localStorage.getItem('jaguarToken') || '';
let deferredPrompt;

window.addEventListener('beforeinstallprompt', (event) => {
  event.preventDefault();
  deferredPrompt = event;
  document.querySelector('#install').hidden = false;
});

document.querySelector('#install').addEventListener('click', async () => {
  if (deferredPrompt) await deferredPrompt.prompt();
});

async function api(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) throw new Error((await response.json()).detail || response.statusText);
  return response.json();
}

function metric(label, value) {
  return `<article class="metric"><span>${label}</span><strong>${value ?? 0}</strong></article>`;
}

async function refresh() {
  if (!token) return;
  const [dashboard, plans, subscribers, events] = await Promise.all([
    api('/api/dashboard'),
    api('/api/plans'),
    api('/api/subscribers'),
    api('/api/security/events'),
  ]);
  document.querySelector('#metrics').innerHTML = [
    metric('Subscribers', dashboard.subscribers),
    metric('Active', dashboard.active_subscribers),
    metric('Settled revenue', `$${Number(dashboard.monthly_revenue).toFixed(2)}`),
    metric('Security events', dashboard.security_events),
  ].join('');
  document.querySelector('#plans').innerHTML = plans.map((plan) => `<option value="${plan.id}">${plan.name} · ${plan.speed_down_mbps}/${plan.speed_up_mbps} Mbps · $${plan.monthly_price}</option>`).join('');
  document.querySelector('#subscribers').innerHTML = subscribers.map((subscriber) => `<div class="row"><strong>${subscriber.name}</strong><br>${subscriber.account_no} · ${subscriber.radius_username} · ${subscriber.status}<br>Satellite: ${subscriber.satellite_terminal_id || 'not linked'}</div>`).join('') || '<p>No subscribers yet.</p>';
  document.querySelector('#security-events').innerHTML = events.map((event) => `<div class="row"><strong>${event.severity}</strong> ${event.source}<br>${event.message}</div>`).join('') || '<p>No events recorded.</p>';
}

document.querySelector('#login-card').addEventListener('submit', async (event) => {
  event.preventDefault();
  const status = document.querySelector('#login-status');
  try {
    const data = await api('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        email: document.querySelector('#email').value,
        password: document.querySelector('#password').value,
        totp_code: document.querySelector('#totp').value || null,
      }),
    });
    token = data.access_token;
    localStorage.setItem('jaguarToken', token);
    status.textContent = `Signed in as ${data.role}`;
    await refresh();
  } catch (error) {
    status.textContent = error.message;
  }
});

document.querySelector('#subscriber-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = new FormData(event.target);
  const payload = Object.fromEntries(form.entries());
  payload.plan_id = Number(payload.plan_id);
  if (!payload.satellite_terminal_id) payload.satellite_terminal_id = null;
  await api('/api/subscribers', { method: 'POST', body: JSON.stringify(payload) });
  event.target.reset();
  await refresh();
});

refresh().catch(console.error);
