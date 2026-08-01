/* DataBossX Command Center - phone client.
 *
 * Contract this client honors:
 *  - It is a view. It never decides risk, never removes a hold, never claims a
 *    lease. Those all live server-side.
 *  - Voice never executes. A transcript becomes an intent, the human confirms
 *    both, and only then does a command exist.
 *  - Every consequential tap is idempotent: the same idempotency key is reused
 *    for retries, so a double tap cannot produce two jobs.
 *  - The Command Core is decorative by contract. Every value it draws is also
 *    rendered as text.
 */
'use strict';

const API = {
  csrf: null,
  async call(path, { method = 'GET', body } = {}) {
    const headers = { 'Content-Type': 'application/json' };
    if (method !== 'GET' && API.csrf) headers['X-DBX-CSRF'] = API.csrf;
    const res = await fetch(path, {
      method,
      headers,
      credentials: 'same-origin',
      body: body ? JSON.stringify(body) : undefined,
    });
    let payload = {};
    try { payload = await res.json(); } catch (_) { /* empty body is fine */ }
    if (!res.ok) {
      const err = new Error(payload.message || payload.error || `HTTP ${res.status}`);
      err.code = payload.error;
      err.status = res.status;
      throw err;
    }
    return payload;
  },
};

const state = {
  posture: null,
  moves: null,
  intake: null,
  screen: 'command',
  /* Stable per-request key. Regenerated only after a confirmed submission, so
     retries of the same request collapse server-side. */
  idempotencyKey: null,
  inFlight: false,
};

/* ------------------------------------------------------------------ utils */
const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;   // textContent, never innerHTML
  return node;
};
const newKey = () => {
  const buf = new Uint8Array(16);
  crypto.getRandomValues(buf);
  return Array.from(buf, (b) => b.toString(16).padStart(2, '0')).join('');
};

let toastTimer = null;
function toast(message, kind) {
  const node = $('toast');
  node.textContent = message;
  node.className = 'toast' + (kind ? ` is-${kind}` : '');
  node.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { node.hidden = true; }, 4200);
}

function fill(container, items, render, emptyText) {
  container.textContent = '';
  if (!items || items.length === 0) {
    container.appendChild(el('p', 'empty', emptyText));
    return;
  }
  items.forEach((item) => container.appendChild(render(item)));
}

/* ------------------------------------------------------------ navigation */
function showScreen(name) {
  state.screen = name;
  document.querySelectorAll('.screen').forEach((section) => {
    const active = section.id === `screen-${name}`;
    section.hidden = !active;
    section.classList.toggle('is-active', active);
  });
  document.querySelectorAll('.nav-btn').forEach((btn) => {
    const active = btn.dataset.screen === name;
    btn.classList.toggle('is-active', active);
    if (active) btn.setAttribute('aria-current', 'page');
    else btn.removeAttribute('aria-current');
  });
  window.scrollTo({ top: 0, behavior: 'instant' in window ? 'instant' : 'auto' });
  if (name === 'more') loadMore();
  if (name === 'jobs') loadJobs();
}

/* ------------------------------------------------------------- rendering */
function renderSix(posture, moves) {
  const running = posture.running.length;
  const blocked = posture.blocked.length;
  const needs = posture.needs_ryan.length;
  const changed = posture.changed.length;
  const safeAuto = (moves && moves.alternatives)
    ? moves.alternatives.filter((m) => m.risk_class === 'READ_ONLY').length
    : 0;
  const decision = needs > 0 ? `${needs}` : '0';

  const cards = [
    { q: 'What is running?', a: String(running), note: running ? 'Active jobs' : 'Idle', tone: running ? 'is-ok' : '' },
    { q: 'What is blocked?', a: String(blocked), note: blocked ? 'Needs triage' : 'Nothing blocked', tone: blocked ? 'is-alert' : '' },
    { q: 'What changed?', a: String(changed), note: 'Verified receipts', tone: '' },
    { q: 'Decision required?', a: decision, note: needs ? 'Awaiting approval' : 'None open', tone: needs ? 'is-warn' : '' },
    { q: 'Waiting on Ryan?', a: String(needs), note: needs ? 'Open Decisions' : 'Nothing waiting', tone: needs ? 'is-warn' : '' },
    { q: 'Safe to automate?', a: String(safeAuto), note: 'Read-only moves', tone: '' },
  ];

  const grid = $('sixGrid');
  grid.textContent = '';
  cards.forEach((card) => {
    const node = el('div', `six-card ${card.tone}`.trim());
    node.appendChild(el('span', 'six-q', card.q));
    node.appendChild(el('span', 'six-a', card.a));
    node.appendChild(el('span', 'six-note', card.note));
    grid.appendChild(node);
  });
}

function renderBestMove(move) {
  const slot = $('bestMove');
  slot.textContent = '';
  if (!move) {
    slot.appendChild(el('p', 'empty', 'No eligible move. Every candidate is withheld by policy.'));
    return;
  }
  const card = el('div', 'best-move');

  const top = el('div', 'bm-top');
  const riskPill = el('span', `pill ${move.risk_class === 'READ_ONLY' ? 'pill-ok' : 'pill-warn'}`,
    move.risk_class.replace('_', ' '));
  top.appendChild(riskPill);
  if (move.approval_required) top.appendChild(el('span', 'pill pill-hold', 'Approval'));
  top.appendChild(el('span', 'pill pill-sim', `Score ${move.score.toFixed(3)}`));
  card.appendChild(top);

  card.appendChild(el('h3', null, move.title));
  card.appendChild(el('p', 'bm-why', move.why_now));

  const facts = el('dl', 'bm-facts');
  const pairs = [
    ['Benefit', move.expected_benefit],
    ['Risk', move.risk],
    ['Confidence', String(move.confidence)],
    ['Verification', move.verification_method],
    ['If it fails', move.if_it_fails],
    ['Owner', move.owner],
  ];
  pairs.forEach(([label, value]) => {
    const wrap = el('div', 'bm-fact');
    wrap.appendChild(el('dt', null, label));
    wrap.appendChild(el('dd', null, value));
    facts.appendChild(wrap);
  });
  card.appendChild(facts);

  const click = el('div', 'bm-click');
  click.appendChild(el('span', null, '→'));
  click.appendChild(el('span', null, move.exact_next_click));
  card.appendChild(click);

  const run = el('button', 'btn btn-primary', 'Run this move (simulated)');
  run.type = 'button';
  run.addEventListener('click', () => runSlice(run));
  card.appendChild(run);

  slot.appendChild(card);
}

function moveCard(move, vetoed) {
  const card = el('div', `card${vetoed ? ' is-veto' : ''}`);
  const row = el('div', 'card-row');
  row.appendChild(el('h4', null, move.title));
  row.appendChild(el('span', `pill ${vetoed ? 'pill-danger' : 'pill-ok'}`,
    vetoed ? 'Withheld' : move.score.toFixed(2)));
  card.appendChild(row);
  card.appendChild(el('p', null, vetoed ? move.risk : move.why_now));
  if (vetoed && move.vetoes.length) {
    const list = el('ul', 'veto-list');
    move.vetoes.forEach((reason) => list.appendChild(el('li', null, reason)));
    card.appendChild(list);
  }
  card.appendChild(el('div', 'meta', `${move.exact_action} · ${move.resource_scope}`));
  return card;
}

function renderMoves(moves) {
  renderBestMove(moves.best_next_move);
  fill($('altMoves'), moves.alternatives, (m) => moveCard(m, false), 'No alternatives.');
  fill($('vetoMoves'), moves.vetoed, (m) => moveCard(m, true), 'Nothing withheld.');
  $('altCount').textContent = `(${moves.alternatives.length})`;
  $('vetoCount').textContent = `(${moves.vetoed.length})`;
}

function jobCard(job) {
  const card = el('div', 'card');
  const row = el('div', 'card-row');
  row.appendChild(el('h4', null, job.title));
  row.appendChild(el('span', 'pill pill-warn', job.state));
  card.appendChild(row);
  if (job.detail) card.appendChild(el('p', null, job.detail));
  card.appendChild(el('div', 'meta', job.job_id));
  return card;
}

function renderPosture(posture) {
  $('holdCount').textContent = `${posture.holds.length} active holds`;
  fill($('needsRyan'), posture.needs_ryan, jobCard, 'Nothing is waiting on you.');
  fill($('blockedList'), posture.blocked, jobCard, 'Nothing is blocked.');
  fill($('recentChanges'), posture.changed, (change) => {
    const card = el('div', 'card');
    const row = el('div', 'card-row');
    row.appendChild(el('h4', null, change.outcome));
    row.appendChild(el('span', 'pill pill-sim', change.execution_mode));
    card.appendChild(row);
    card.appendChild(el('p', null, change.summary));
    card.appendChild(el('div', 'meta', `${change.receipt_id} · ${change.at}`));
    return card;
  }, 'No verified changes yet.');

  const writer = $('activeWriter');
  writer.textContent = '';
  if (posture.active_writer) {
    const w = posture.active_writer;
    const card = el('div', 'card');
    card.appendChild(el('h4', null, w.writer_identity));
    card.appendChild(el('p', null, `Sole writer for ${w.resource_scope}. Concurrency 1.`));
    card.appendChild(el('div', 'meta',
      `lease ${w.lease_id} · fencing #${w.fencing_sequence} · expires ${w.expires_at}`));
    writer.appendChild(card);
  } else {
    writer.appendChild(el('p', 'empty', 'No active writer lease. No one is mutating anything.'));
  }

  const badge = $('decBadge');
  if (posture.needs_ryan.length) {
    badge.textContent = String(posture.needs_ryan.length);
    badge.hidden = false;
  } else {
    badge.hidden = true;
  }

  fill($('decisionList'), posture.needs_ryan, jobCard, 'No decisions are open.');
  fill($('projectList'), [{ job_id: 'synthetic-alpha', title: 'synthetic-alpha (SYNTHETIC)',
    state: 'ACTIVE', detail: 'Synthetic fixture project. No client evidence in this lane.' }],
    jobCard, 'No projects.');
}

/* ---------------------------------------------------------- command core */
const Core = {
  ctx: null, nodes: [], raf: null, t: 0,

  init(posture) {
    const canvas = $('commandCore');
    if (!canvas || document.documentElement.dataset.core === 'off') return this.disable();
    let ctx;
    try { ctx = canvas.getContext('2d'); } catch (_) { ctx = null; }
    if (!ctx) return this.disable();      // no-canvas fallback
    this.ctx = ctx;
    this.canvas = canvas;

    const holds = posture.holds.length;
    const running = posture.running.length;
    const writers = posture.active_writer ? 1 : 0;
    this.nodes = [
      { label: 'Command', n: 1, color: '#4da3ff', r: 0.00 },
      { label: 'Writer', n: writers, color: '#3ddc97', r: 0.20 },
      { label: 'Watchers', n: 5, color: '#b98cff', r: 0.40 },
      { label: 'Jobs', n: running, color: '#ffb340', r: 0.60 },
      { label: 'Holds', n: holds, color: '#ff8a3d', r: 0.80 },
      { label: 'Receipts', n: posture.changed.length, color: '#9aa9bd', r: 1.00 },
    ];

    const legend = $('coreLegend');
    legend.textContent = '';
    this.nodes.forEach((node) => {
      const item = el('span');
      const dot = el('i');
      dot.style.background = node.color;
      item.appendChild(dot);
      item.appendChild(document.createTextNode(`${node.label}: ${node.n}`));
      legend.appendChild(item);
    });

    this.stop();
    const reduced = document.documentElement.dataset.motion === 'reduced'
      || window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced) this.draw(0);            // one static frame, no animation
    else this.loop();
  },

  disable() {
    const canvas = $('commandCore');
    if (canvas) canvas.hidden = true;
    const fallback = $('coreFallback');
    if (fallback) fallback.hidden = false;
  },

  stop() { if (this.raf) cancelAnimationFrame(this.raf); this.raf = null; },

  loop() {
    this.t += 0.006;
    this.draw(this.t);
    this.raf = requestAnimationFrame(() => this.loop());
  },

  draw(t) {
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;
    ctx.clearRect(0, 0, w, h);

    const grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, '#070c14');
    grad.addColorStop(1, '#05070d');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, w, h);

    const cx = w / 2, cy = h / 2;
    const ringR = Math.min(w, h) * 0.34;

    ctx.strokeStyle = 'rgba(77,163,255,0.12)';
    ctx.lineWidth = 1;
    for (let i = 1; i <= 3; i++) {
      ctx.beginPath();
      ctx.arc(cx, cy, ringR * (i / 3), 0, Math.PI * 2);
      ctx.stroke();
    }

    const points = this.nodes.map((node, i) => {
      const angle = t + (i / this.nodes.length) * Math.PI * 2;
      return { ...node, x: cx + Math.cos(angle) * ringR, y: cy + Math.sin(angle) * ringR * 0.72 };
    });

    ctx.strokeStyle = 'rgba(154,169,189,0.16)';
    points.forEach((p) => {
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
    });

    points.forEach((p) => {
      const radius = 6 + Math.min(p.n, 6) * 1.8;
      ctx.beginPath();
      ctx.arc(p.x, p.y, radius, 0, Math.PI * 2);
      ctx.fillStyle = p.color;
      ctx.globalAlpha = 0.85;
      ctx.fill();
      ctx.globalAlpha = 1;

      ctx.font = '600 11px ui-sans-serif, system-ui, sans-serif';
      ctx.fillStyle = '#9aa9bd';
      ctx.textAlign = 'center';
      ctx.fillText(`${p.label} ${p.n}`, p.x, p.y + radius + 13);
    });

    ctx.beginPath();
    ctx.arc(cx, cy, 17, 0, Math.PI * 2);
    ctx.fillStyle = '#0e141f';
    ctx.fill();
    ctx.strokeStyle = 'rgba(77,163,255,0.55)';
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.font = '800 10px ui-sans-serif, system-ui, sans-serif';
    ctx.fillStyle = '#4da3ff';
    ctx.textAlign = 'center';
    ctx.fillText('CORE', cx, cy + 3.5);
  },
};

/* --------------------------------------------------------------- loaders */
async function loadPosture() {
  try {
    const [posture, moves] = await Promise.all([
      API.call('/api/posture'),
      API.call('/api/best-moves'),
    ]);
    state.posture = posture;
    state.moves = moves;
    renderPosture(posture);
    renderMoves(moves);
    renderSix(posture, moves);
    Core.init(posture);
  } catch (err) {
    toast(`Could not load posture: ${err.message}`, 'error');
  }
}

async function loadJobs() {
  try {
    const data = await API.call('/api/jobs');
    fill($('jobList'), data.jobs, jobCard, 'No jobs yet.');
  } catch (err) {
    toast(err.message, 'error');
  }
}

async function loadMore() {
  try {
    const [watchers, holds, audit] = await Promise.all([
      API.call('/api/watchers'),
      API.call('/api/holds'),
      API.call('/api/audit?limit=25').catch(() => ({ events: [], chain_valid: null })),
    ]);

    fill($('watcherList'), watchers.reviews, (review) => {
      const card = el('div', 'card');
      const row = el('div', 'card-row');
      row.appendChild(el('h4', null, review.watcher_name));
      row.appendChild(el('span', `pill ${review.verdict === 'PASS' ? 'pill-ok' : 'pill-danger'}`,
        review.verdict));
      card.appendChild(row);
      card.appendChild(el('p', null,
        review.checks.map((c) => `${c.name}: ${c.status}`).join(' · ')));
      card.appendChild(el('div', 'meta', `read-only · confidence ${review.confidence}`));
      return card;
    }, 'No watcher reviews.');

    fill($('holdList'), holds.holds, (hold) => {
      const card = el('div', 'card is-hold');
      const row = el('div', 'card-row');
      row.appendChild(el('h4', null, hold.label));
      row.appendChild(el('span', 'pill pill-hold', 'IMMUTABLE'));
      card.appendChild(row);
      card.appendChild(el('p', null, hold.reason));
      card.appendChild(el('div', 'meta', hold.scope_pattern));
      return card;
    }, 'No holds recorded.');

    fill($('auditList'), audit.events.slice(0, 12), (event) => {
      const card = el('div', 'card');
      const row = el('div', 'card-row');
      row.appendChild(el('h4', null, event.event_type));
      row.appendChild(el('span',
        `pill ${event.outcome === 'DENY' ? 'pill-danger' : 'pill-ok'}`, event.outcome));
      card.appendChild(row);
      card.appendChild(el('p', null, `${event.actor} · ${event.occurred_at}`));
      card.appendChild(el('div', 'meta', event.content_sha256.slice(0, 32) + '…'));
      return card;
    }, 'Audit requires a reviewer role.');

    const health = $('healthList');
    health.textContent = '';
    const card = el('div', 'card');
    card.appendChild(el('h4', null, 'Control kernel'));
    card.appendChild(el('p', null,
      `Audit chain ${audit.chain_valid === null ? 'not readable at this role'
        : audit.chain_valid ? 'verified intact' : 'BROKEN'} · policy ${state.posture ? state.posture.policy_version : '?'}`));
    card.appendChild(el('div', 'meta', 'Single writer enforced by database constraint, not UI state.'));
    health.appendChild(card);
  } catch (err) {
    toast(err.message, 'error');
  }
}

/* ------------------------------------------------------------ voice flow */
function openSheet(intake) {
  state.intake = intake;
  $('transcriptBox').value = intake.transcript.text;

  const list = $('interpList');
  list.textContent = '';
  const intent = intake.intent;
  const rows = [
    ['Operation', intent.operation || '(none matched)'],
    ['Goal', intent.goal],
    ['Project', intent.target_project || '(not stated)'],
    ['Resource', intent.target_resource || '(not stated)'],
    ['Urgency', intent.urgency],
    ['Transcript SHA', intake.transcript.sha256.slice(0, 24) + '…'],
  ];
  rows.forEach(([label, value]) => {
    list.appendChild(el('dt', null, label));
    list.appendChild(el('dd', null, String(value)));
  });

  const unresolved = intent.unresolved || [];
  $('unresolvedBlock').hidden = unresolved.length === 0;
  const ul = $('unresolvedList');
  ul.textContent = '';
  unresolved.forEach((item) => ul.appendChild(el('li', null, item)));

  $('confirmBtn').disabled = unresolved.length > 0 || !intent.operation;

  $('sheetBackdrop').hidden = false;
  $('confirmSheet').hidden = false;
  $('transcriptBox').focus();
}

function closeSheet() {
  $('sheetBackdrop').hidden = true;
  $('confirmSheet').hidden = true;
  state.intake = null;
}

async function interpret(text) {
  try {
    const intake = await API.call('/api/voice/intake', {
      method: 'POST',
      body: { transcript: text, provider: 'local-stub-v1', default_project: 'synthetic-alpha' },
    });
    openSheet(intake);
  } catch (err) {
    toast(err.message, 'error');
  }
}

async function confirmCommand() {
  if (state.inFlight) return;                       // double-tap guard, client side
  const btn = $('confirmBtn');
  state.inFlight = true;
  btn.disabled = true;
  try {
    if (!state.idempotencyKey) state.idempotencyKey = newKey();
    const result = await API.call('/api/commands', {
      method: 'POST',
      body: {
        idempotency_key: state.idempotencyKey,          // server-side guard is the real one
        transcript: $('transcriptBox').value,
        intent: state.intake.intent,
        channel: 'VOICE',
        provider: state.intake.transcript.provider,
        confirmed: true,
      },
    });
    toast(`Command created (${result.command_id.slice(0, 12)}…). Nothing has executed yet.`, 'ok');
    state.idempotencyKey = null;
    closeSheet();
    loadPosture();
  } catch (err) {
    toast(err.message, 'error');
  } finally {
    state.inFlight = false;
    btn.disabled = false;
  }
}

async function runSlice(button) {
  if (state.inFlight) return;
  state.inFlight = true;
  button.disabled = true;
  const original = button.textContent;
  button.textContent = 'Running…';
  try {
    const summary = await API.call('/api/run-slice', { method: 'POST' });
    toast(`${summary.execution_mode} run ${summary.outcome}. Receipt ${summary.receipt_id.slice(0, 14)}…`, 'ok');
    await loadPosture();
  } catch (err) {
    toast(err.message, 'error');
  } finally {
    state.inFlight = false;
    button.disabled = false;
    button.textContent = original;
  }
}

/* ------------------------------------------------------------------ boot */
async function login() {
  const session = await API.call('/api/session', {
    method: 'POST',
    body: { user_id: 'ryan', device_id: 'iphone-pwa' },
  });
  API.csrf = session.csrf;
  return session;
}

function wireEvents() {
  document.querySelectorAll('.nav-btn').forEach((btn) => {
    btn.addEventListener('click', () => showScreen(btn.dataset.screen));
  });

  $('refreshBtn').addEventListener('click', loadPosture);

  const ptt = $('pttBtn');
  let holding = false;
  const start = (event) => {
    event.preventDefault();
    holding = true;
    ptt.classList.add('is-recording');
    ptt.querySelector('.ptt-label').textContent = 'Listening… release to stop';
  };
  const stop = (event) => {
    if (!holding) return;
    event.preventDefault();
    holding = false;
    ptt.classList.remove('is-recording');
    ptt.querySelector('.ptt-label').textContent = 'Hold to speak';
    /* No speech provider is authorized in this lane, so the transcript comes
       from the local stub. It is labelled as such in the confirmation sheet. */
    interpret('What should I do next?');
  };
  ptt.addEventListener('pointerdown', start);
  ptt.addEventListener('pointerup', stop);
  ptt.addEventListener('pointercancel', stop);
  ptt.addEventListener('pointerleave', stop);
  ptt.addEventListener('keydown', (e) => { if (e.key === ' ' || e.key === 'Enter') start(e); });
  ptt.addEventListener('keyup', (e) => { if (e.key === ' ' || e.key === 'Enter') stop(e); });

  $('textBtn').addEventListener('click', () => {
    const text = window.prompt('Type your request');
    if (text) interpret(text);
  });

  $('cancelBtn').addEventListener('click', closeSheet);
  $('sheetBackdrop').addEventListener('click', closeSheet);
  $('reinterpretBtn').addEventListener('click', () => interpret($('transcriptBox').value));
  $('confirmBtn').addEventListener('click', confirmCommand);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !$('confirmSheet').hidden) closeSheet();
  });

  const motion = $('reduceMotionToggle');
  motion.checked = localStorage.getItem('dbx.motion') === 'reduced';
  if (motion.checked) document.documentElement.dataset.motion = 'reduced';
  motion.addEventListener('change', () => {
    if (motion.checked) {
      document.documentElement.dataset.motion = 'reduced';
      localStorage.setItem('dbx.motion', 'reduced');
      Core.stop();
      Core.draw(0);
    } else {
      delete document.documentElement.dataset.motion;
      localStorage.removeItem('dbx.motion');
      if (state.posture) Core.init(state.posture);
    }
  });

  const lowPower = $('lowPowerToggle');
  lowPower.checked = localStorage.getItem('dbx.core') === 'off';
  if (lowPower.checked) document.documentElement.dataset.core = 'off';
  lowPower.addEventListener('change', () => {
    if (lowPower.checked) {
      document.documentElement.dataset.core = 'off';
      localStorage.setItem('dbx.core', 'off');
      Core.stop();
      Core.disable();
    } else {
      delete document.documentElement.dataset.core;
      localStorage.removeItem('dbx.core');
      $('commandCore').hidden = false;
      $('coreFallback').hidden = true;
      if (state.posture) Core.init(state.posture);
    }
  });
}

async function boot() {
  wireEvents();
  try {
    await login();
    await loadPosture();
  } catch (err) {
    toast(`Sign-in failed: ${err.message}`, 'error');
  }
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => { /* offline cache is optional */ });
  }
}

document.addEventListener('DOMContentLoaded', boot);
