const $ = (sel) => document.querySelector(sel);

async function api(path, opts) {
  const res = await fetch(path, opts);
  return res.json();
}

function showToast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => t.classList.add("hidden"), 4000);
}

function renderLane(laneKey, projects) {
  const el = $(`#lane-${laneKey}`);
  if (!el) return;
  if (!projects || !projects.length) {
    el.innerHTML = `<div class="empty">No projects discovered yet in this lane.</div>`;
    return;
  }
  const ACTION_LABELS = {
    scan_project: "Update Me",
    inspect_project: "Inspect Project",
    find_missing_evidence: "Find Missing Evidence",
    build_worklist: "Build Worklist",
    run_qa: "Run QA",
    inspect_candidates: "Open Best Candidate",
  };
  const actionButton = (action, p) =>
    `<button data-action="${action}" data-path="${p.path}" data-lane="${laneKey}" data-project="${p.project}" ` +
    `aria-label="${ACTION_LABELS[action]} for ${p.project}">${ACTION_LABELS[action]}</button>`;
  el.innerHTML = projects.map((p) => `
    <div class="card">
      <div class="card-title">${p.project}</div>
      <div class="card-meta">${p.file_count} files &middot; last activity ${p.last_mtime_iso || "unknown"}
        &middot; evidence: ${p.evidence_present && p.evidence_present.length ? p.evidence_present.join(", ") : "none detected"}</div>
      <div class="card-actions">
        ${actionButton("scan_project", p)}
        ${actionButton("inspect_project", p)}
        ${actionButton("find_missing_evidence", p)}
        ${actionButton("build_worklist", p)}
        ${actionButton("run_qa", p)}
        ${actionButton("inspect_candidates", p)}
      </div>
    </div>
  `).join("");
}

function renderDataBossXLane(state) {
  const el = $("#lane-databossx");
  const owned = (state.workers_owned || []).length;
  el.innerHTML = `
    <div class="card">
      <div class="card-title">System Health</div>
      <div class="card-meta">
        AI mode: ${state.ai_mode} &middot; Local model: ${state.local_model.available ? "available" : "not detected"}<br>
        Owned workers running: ${owned} &middot; Server time: ${state.server_time}
      </div>
    </div>
  `;
}

function runAction(button) {
  const task = button.dataset.action;
  const path = button.dataset.path;
  const lane = button.dataset.lane;
  const project = button.dataset.project;
  button.disabled = true;
  api("/api/actions/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task, project_path: path, lane, project }),
  }).then((res) => {
    button.disabled = false;
    if (res.refused) {
      showToast(`Refused: ${res.reason}`);
      return;
    }
    if (res.ok === false) {
      showToast(`Failed: ${res.error || "unknown error"}`);
      return;
    }
    showToast(res.summary || "Done.");
    loadState();
  }).catch((e) => {
    button.disabled = false;
    showToast(`Error: ${e}`);
  });
}

function renderLists(state) {
  const jobsEl = $("#activeJobs");
  jobsEl.innerHTML = (state.active_jobs || []).length
    ? state.active_jobs.map((j) => `<li>${j.task} &middot; ${j.project || ""} &middot; ${j.status}</li>`).join("")
    : `<li class="empty">No active jobs.</li>`;

  const receiptsEl = $("#recentReceipts");
  receiptsEl.innerHTML = (state.recent_receipts || []).length
    ? state.recent_receipts.map((r) => `<li>${r.action} &middot; ${r.output_summary || ""}</li>`).join("")
    : `<li class="empty">No receipts yet.</li>`;
}

async function loadWorkers() {
  const data = await api("/api/workers");
  const el = $("#workersPanel");
  const owned = data.owned || [];
  const observed = data.observed || [];
  el.innerHTML = `
    <div class="card-meta">Owned by DataBossX: ${owned.length}</div>
    <ul class="list">${owned.map((w) => `<li>PID ${w.pid} &middot; ${w.task || ""} &middot; ${w.status}</li>`).join("") || '<li class="empty">None running.</li>'}</ul>
    <div class="card-meta">Observed (not owned): ${observed.length}</div>
    <ul class="list">${observed.map((w) => `<li>PID ${w.pid} &middot; ${w.name}</li>`).join("") || '<li class="empty">Nothing else observed.</li>'}</ul>
  `;
  return owned;
}

const WRITE_ACTIONS = new Set(["build_worklist"]);

async function loadSetup() {
  const setup = await api("/api/setup");
  const banner = $("#setupBanner");
  if (setup.setup_confirmed) {
    banner.classList.add("hidden");
  } else {
    banner.classList.remove("hidden");
    $("#setupBody").textContent =
      `Configured read roots: ${JSON.stringify(setup.read_roots)}\n` +
      `Every write lands only inside: ${setup.write_root_pattern}\n` +
      `${setup.note}`;
  }

  const sandboxBanner = $("#sandboxBanner");
  if (setup.sandbox_mode) {
    sandboxBanner.classList.remove("hidden");
    sandboxBanner.textContent =
      `SANDBOX MODE -- NO CLIENT DATA. Penterra: ${setup.read_roots.penterra} ` +
      `&middot; Horizon: ${setup.read_roots.horizon}`.replace("&middot;", "·");
  } else {
    sandboxBanner.classList.add("hidden");
  }

  return setup.setup_confirmed;
}

$("#setupConfirmBtn").addEventListener("click", async () => {
  await api("/api/setup/confirm", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
  showToast("Setup confirmed -- write actions enabled.");
  loadState();
});

async function loadState() {
  const setupConfirmed = await loadSetup();
  const state = await api("/api/state");
  const move = state.next_best_move;
  $("#heroMove").textContent = move.project
    ? `${move.label}: ${move.action.replace(/_/g, " ")} on ${move.project}`
    : "No projects discovered yet";
  $("#heroWhy").textContent = move.why;
  $("#doNextBtn").onclick = () => {
    if (!move.project) { showToast("Nothing to act on yet -- add project folders under the configured roots."); return; }
    api("/api/actions/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task: move.action, project_path: move.path, lane: move.lane, project: move.project }),
    }).then((res) => { showToast(res.summary || res.reason || "Done."); loadState(); });
  };

  renderLane("penterra", state.lanes.penterra);
  renderLane("horizon", state.lanes.horizon);
  const ownedWorkers = await loadWorkers();
  renderDataBossXLane({ ...state, workers_owned: ownedWorkers });
  renderLists(state);

  const pill = $("#localModelPill");
  pill.textContent = `LOCAL MODEL: ${state.local_model.available ? "ONLINE" : "OFFLINE"}`;
  pill.className = "pill " + (state.local_model.available ? "ok" : "warn");

  document.querySelectorAll(".card-actions button").forEach((btn) => {
    if (WRITE_ACTIONS.has(btn.dataset.action) && !setupConfirmed) {
      btn.disabled = true;
      btn.setAttribute("aria-disabled", "true");
      btn.title = "Confirm local setup above before running write actions.";
      btn.setAttribute(
        "aria-label",
        `${btn.getAttribute("aria-label") || btn.textContent} (disabled until local setup is confirmed)`
      );
    }
    btn.addEventListener("click", () => runAction(btn));
  });
}

$("#refreshBtn").addEventListener("click", loadState);

$("#commandBtn").addEventListener("click", async () => {
  const text = $("#commandInput").value;
  if (!text.trim()) return;
  const res = await api("/api/command", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  const el = $("#commandResult");
  el.classList.remove("hidden");
  el.textContent = res.proposed_action
    ? `Interpreted as: ${res.proposed_action} (approval: ${res.required_approval}). Use a project card button to run it.`
    : `Could not confidently map that to a known bounded action. ${res.note}`;
});

$("#modeSelect").addEventListener("change", async (e) => {
  const res = await api("/api/mode", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode: e.target.value }),
  });
  showToast(res.ok ? `AI mode set to ${res.mode}` : "Failed to set mode");
});

loadState();
setInterval(loadState, 30000);
