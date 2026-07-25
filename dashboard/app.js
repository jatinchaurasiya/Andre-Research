/* Andre dashboard v2.1 — frontend state + WebSocket + HTTP API client */
(() => {
"use strict";

const AGENT_META = {
  pmf:                  { name: "PMF Research",          phase: 1,  color: "#5DCAA5", file: "01_pmf_research.md" },
  requirements:         { name: "Requirements",          phase: 2,  color: "#7F77DD", file: "02_requirements.md", parallel: true },
  competitor:           { name: "Competitor Analysis",   phase: 2,  color: "#EF9F27", file: "03_competitor_analysis.md", parallel: true },
  improvement:          { name: "Improvement Blueprint", phase: 3,  color: "#D85A30", file: "04_improvement_blueprint.md" },
  feature_architecture: { name: "Feature Architecture",  phase: 4,  color: "#3B82F6", file: "05_feature_architecture.md" },
  prd:                  { name: "PRD",                   phase: 5,  color: "#8B5CF6", file: "06_PRD.md" },
  uiux:                 { name: "UI/UX Design Prompt",   phase: 6,  color: "#EC4899", file: "07_UI_UX_DESIGN_PROMPT.md" },
  marketing:            { name: "Marketing Playbook",    phase: 7,  color: "#D4537E", file: "08_marketing_playbook.md" },
};
const AGENT_IDS = Object.keys(AGENT_META);
const TOTAL_AGENTS = AGENT_IDS.length;
const PHASE_LABELS = [
  { n: 1, key: "pmf", label: "PMF" },
  { n: 2, key: "req", label: "Req+Comp" },
  { n: 3, key: "impr", label: "Improve" },
  { n: 4, key: "feat", label: "Features" },
  { n: 5, key: "prd", label: "PRD" },
  { n: 6, key: "uiux", label: "UI/UX" },
  { n: 7, key: "mktg", label: "Marketing" },
];

// ── State ────────────────────────────────────────────
const state = {
  runId: null,
  isHistorical: false,            // true when viewing a past run
  startTime: null,
  elapsedTimer: null,
  totalTokens: 0,
  totalSearches: 0,
  totalPages: 0,
  totalErrors: 0,
  totalThinking: 0,
  completed: 0,
  phase: 0,                       // current phase number (0 = not started)
  searches: [],                   // {ts, agent, query, results, pages}
  outputs: {},                    // agentId → markdown
  pipelineStatus: "idle",         // idle | running | done | stopped | error
  perAgent: {},                   // see ensureAgentState
  logBuffers: {},                 // per-agent line buffers for thinking/text
  logLines: 0,
  history: [],
};

AGENT_IDS.forEach(id => {
  state.perAgent[id] = ensureAgentState(id);
  state.logBuffers[id] = { text: "", thinking: "" };
});

function ensureAgentState(id) {
  return {
    status: "waiting",
    tokensIn: 0, tokensOut: 0, reasoning: 0,
    searches: 0, pages: 0, errors: 0,
    startedAt: null, finishedAt: null,
  };
}

// ── DOM helpers ──────────────────────────────────────
const $ = sel => document.querySelector(sel);
const $$ = sel => Array.from(document.querySelectorAll(sel));

// ── Phase bar (built once) ───────────────────────────
function buildPhaseBar() {
  const bar = $("#phase-bar");
  bar.innerHTML = "";
  for (let i = 0; i < PHASE_LABELS.length; i++) {
    const p = PHASE_LABELS[i];
    const step = document.createElement("div");
    step.className = "ph-step";
    step.dataset.phase = String(p.n);
    step.innerHTML = `<div class="ph-dot">${p.n}</div><div class="ph-label">${p.label}</div>`;
    bar.appendChild(step);
    if (i < PHASE_LABELS.length - 1) {
      const line = document.createElement("div");
      line.className = "ph-line";
      bar.appendChild(line);
    }
  }
  updatePhaseBar();
}
function updatePhaseBar() {
  const steps = $$("#phase-bar .ph-step");
  const lines = $$("#phase-bar .ph-line");
  steps.forEach((step, idx) => {
    const dot = step.querySelector(".ph-dot");
    const n = Number(step.dataset.phase);
    step.classList.remove("done", "run");
    dot.classList.remove("done", "run");
    if (n < state.phase) {
      step.classList.add("done"); dot.classList.add("done");
    } else if (n === state.phase && state.pipelineStatus === "running") {
      step.classList.add("run"); dot.classList.add("run");
    } else if (n === state.phase && state.pipelineStatus === "done") {
      step.classList.add("done"); dot.classList.add("done");
    }
  });
  lines.forEach((line, idx) => {
    line.classList.toggle("done", idx + 1 < state.phase);
  });
}

// ── Sidebar (built once) ─────────────────────────────
function buildSidebar() {
  const list = $("#agent-list");
  list.innerHTML = "";
  AGENT_IDS.forEach(id => {
    const meta = AGENT_META[id];
    const row = document.createElement("div");
    row.className = "agent-row";
    row.id = `agent-${id}`;
    row.dataset.agent = id;
    const phaseLabel = `P${meta.phase}${meta.parallel ? (id === "requirements" ? "a" : "b") : ""}`;
    row.innerHTML = `
      <div class="ar-top">
        <span class="dot" style="background:#444"></span>
        <span class="ar-name">${meta.name}</span>
        <span class="ar-phase" style="background:${meta.color}22;color:${meta.color}">${phaseLabel}</span>
      </div>
      <div class="ar-stats">
        <span class="ar-stat ar-status">waiting</span>
        <span class="ar-stat ar-tokens">0 tok</span>
        <span class="ar-stat ar-searches">0 🔍</span>
        <span class="ar-stat ar-pages">0 📄</span>
        <span class="ar-stat ar-elapsed">—</span>
      </div>`;
    row.addEventListener("click", () => focusAgent(id));
    list.appendChild(row);
  });
}
function focusAgent(id) {
  $$(".agent-row").forEach(r => r.classList.remove("active"));
  const row = $(`#agent-${id}`);
  if (row) row.classList.add("active");
  // Switch to outputs tab + open this agent's markdown if available
  switchTab("outputs");
  selectOutput(id);
}
function setAgentStatus(id, status) {
  const a = state.perAgent[id];
  if (!a) return;
  a.status = status;
  const row = $(`#agent-${id}`);
  if (!row) return;
  row.classList.remove("waiting", "running", "done", "error");
  row.classList.add(status);
  const dot = row.querySelector(".dot");
  const meta = AGENT_META[id];
  if (status === "running") dot.style.background = meta.color;
  else if (status === "done") dot.style.background = "#6fdc8c";
  else if (status === "error") dot.style.background = "#D85A30";
  else dot.style.background = "#444";
  row.querySelector(".ar-status").textContent = status;
}
function updateAgentRow(id) {
  const a = state.perAgent[id];
  const row = $(`#agent-${id}`);
  if (!row) return;
  const tok = a.tokensIn + a.tokensOut;
  row.querySelector(".ar-tokens").textContent = formatTokens(tok) + " tok";
  row.querySelector(".ar-searches").textContent = `${a.searches} 🔍`;
  row.querySelector(".ar-pages").textContent = `${a.pages} 📄`;
  if (a.startedAt) {
    const end = a.finishedAt || Date.now();
    row.querySelector(".ar-elapsed").textContent = formatShortDuration((end - a.startedAt) / 1000);
  }
}

// ── Tabs ─────────────────────────────────────────────
function switchTab(target) {
  $$(".tab").forEach(b => b.classList.toggle("active", b.dataset.tab === target));
  $$(".panel").forEach(p => p.classList.toggle("active", p.dataset.panel === target));
  if (target === "history") refreshHistory();
}
$$(".tab").forEach(btn => btn.addEventListener("click", () => switchTab(btn.dataset.tab)));

// ── Live Log ─────────────────────────────────────────
const logFilters = {
  thinking: true, text: true, search: true, autoscroll: true,
};
["ck-thinking", "ck-text", "ck-search", "ck-autoscroll"].forEach(id => {
  const el = $("#" + id);
  el.addEventListener("change", () => {
    if (id === "ck-thinking") logFilters.thinking = el.checked;
    if (id === "ck-text") logFilters.text = el.checked;
    if (id === "ck-search") logFilters.search = el.checked;
    if (id === "ck-autoscroll") logFilters.autoscroll = el.checked;
  });
});

function buildLegend() {
  const wrap = $("#legend-inline");
  wrap.innerHTML = AGENT_IDS.map(id => {
    const m = AGENT_META[id];
    return `<span><span class="lg-dot" style="background:${m.color}"></span>${m.name.split(" ")[0]}</span>`;
  }).join("");
}

const logEl = $("#log-area");
function appendLog({ agent, text, cls, ts }) {
  const line = document.createElement("div");
  line.className = "log-line";
  const tsSpan = document.createElement("span");
  tsSpan.className = "log-ts";
  tsSpan.textContent = `[${formatTime(new Date((ts || Date.now() / 1000) * 1000))}]`;
  const agSpan = document.createElement("span");
  agSpan.className = `log-agent la-${agent || "system"}`;
  const meta = AGENT_META[agent];
  agSpan.textContent = `[${meta ? meta.name.split(" ")[0].toUpperCase() : (agent || "SYSTEM").toUpperCase()}]`;
  const body = document.createElement("span");
  body.className = "log-msg" + (cls ? " " + cls : "");
  body.textContent = text;
  line.appendChild(tsSpan); line.appendChild(agSpan); line.appendChild(body);
  logEl.appendChild(line);
  state.logLines++;
  if (state.logLines > 2000) {
    for (let i = 0; i < 200 && logEl.firstChild; i++) { logEl.removeChild(logEl.firstChild); state.logLines--; }
  }
  if (logFilters.autoscroll) logEl.scrollTop = logEl.scrollHeight;
}
function flushBuffer(agent, kind) {
  const buf = state.logBuffers[agent][kind];
  const parts = buf.split("\n");
  const tail = parts.pop();
  state.logBuffers[agent][kind] = tail || "";
  for (const p of parts) {
    const t = p.trim(); if (!t) continue;
    if (kind === "thinking") {
      if (!logFilters.thinking) continue;
      appendLog({ agent, text: `🧠 ${t}`, cls: "thinking" });
    } else {
      if (!logFilters.text) continue;
      appendLog({ agent, text: t });
    }
  }
}
function flushAllBuffers(agent) {
  if (state.logBuffers[agent].text)     { appendLog({ agent, text: state.logBuffers[agent].text.trim() }); state.logBuffers[agent].text = ""; }
  if (state.logBuffers[agent].thinking) {
    if (logFilters.thinking) appendLog({ agent, text: `🧠 ${state.logBuffers[agent].thinking.trim()}`, cls: "thinking" });
    state.logBuffers[agent].thinking = "";
  }
}

// ── Metrics + ETA ────────────────────────────────────
function recomputeMetrics() {
  let tok = 0, think = 0, srch = 0, pages = 0, errs = 0;
  for (const id of AGENT_IDS) {
    const a = state.perAgent[id];
    tok += a.tokensIn + a.tokensOut;
    think += a.reasoning;
    srch += a.searches;
    pages += a.pages;
    errs += a.errors;
  }
  state.totalTokens = tok; state.totalThinking = think;
  state.totalSearches = srch; state.totalPages = pages; state.totalErrors = errs;
  $("#m-tok").textContent = formatTokens(tok);
  $("#m-think").textContent = formatTokens(think);
  $("#m-srch").textContent = String(srch);
  $("#m-pages").textContent = String(pages);
  $("#m-err").textContent = String(errs);
  $("#m-done").innerHTML = `${state.completed} <span class="m-denom">/ ${TOTAL_AGENTS}</span>`;
  updateETA();
  updateTokenEconomics();
  updateResearchIntel();
}
function updateETA() {
  if (!state.startTime || state.completed === 0) { $("#m-eta").textContent = "—"; return; }
  if (state.completed >= TOTAL_AGENTS) { $("#m-eta").textContent = "—"; return; }
  const elapsed = (Date.now() - state.startTime) / 1000;
  const perAgent = elapsed / state.completed;
  const remaining = (TOTAL_AGENTS - state.completed) * perAgent * 0.7;  // 0.7 = P2 parallel speedup
  $("#m-eta").textContent = "~" + formatShortDuration(remaining);
}
function setElapsed() {
  if (!state.startTime) return;
  const s = (Date.now() - state.startTime) / 1000;
  $("#m-time").textContent = formatDuration(s);
  AGENT_IDS.forEach(updateAgentRow);
  updateETA();
}
function ensureTimer() {
  if (state.elapsedTimer) return;
  state.startTime = Date.now();
  state.elapsedTimer = setInterval(setElapsed, 1000);
}

// ── Pipeline status ──────────────────────────────────
function setPipelineStatus(s) {
  state.pipelineStatus = s;
  const pill = $("#status-pill");
  pill.classList.remove("running", "done", "stopped");
  if (s === "running") pill.classList.add("running");
  else if (s === "done") pill.classList.add("done");
  else if (s === "stopped" || s === "error") pill.classList.add("stopped");
  $("#status-text").textContent = s;
  $("#stop-btn").disabled = (s !== "running");
  updatePhaseBar();
}
function setPhase(n) { state.phase = n; updatePhaseBar(); }

// ── Token Economics ──────────────────────────────────
function updateTokenEconomics() {
  // Totals
  let inTok = 0, outTok = 0, think = 0;
  for (const id of AGENT_IDS) {
    inTok += state.perAgent[id].tokensIn;
    outTok += state.perAgent[id].tokensOut;
    think += state.perAgent[id].reasoning;
  }
  const totals = $("#tok-totals");
  totals.innerHTML = `
    <div class="tt-card in"><div class="rc-title">Input</div><div class="tt-val">${formatTokens(inTok)}</div></div>
    <div class="tt-card out"><div class="rc-title">Output</div><div class="tt-val">${formatTokens(outTok)}</div></div>
    <div class="tt-card think"><div class="rc-title">Thinking</div><div class="tt-val">${formatTokens(think)}</div></div>
    <div class="tt-card search"><div class="rc-title">Searches</div><div class="tt-val">${state.totalSearches}</div></div>`;

  // Per-agent
  const grid = $("#tok-grid");
  grid.innerHTML = "";
  const maxIn = Math.max(1, ...AGENT_IDS.map(id => state.perAgent[id].tokensIn));
  const maxOut = Math.max(1, ...AGENT_IDS.map(id => state.perAgent[id].tokensOut));
  const maxThink = Math.max(1, ...AGENT_IDS.map(id => state.perAgent[id].reasoning));
  for (const id of AGENT_IDS) {
    const a = state.perAgent[id];
    const meta = AGENT_META[id];
    const card = document.createElement("div");
    card.className = "tac" + (a.status === "waiting" ? " dim" : "");
    const statusMark = a.status === "done" ? "✓" : a.status === "running" ? "▶" : a.status === "error" ? "✗" : "—";
    if (a.tokensIn + a.tokensOut + a.reasoning === 0 && a.status !== "running") {
      card.innerHTML = `
        <div class="tac-name" style="color:${meta.color}"><span>${meta.name}</span><span>${statusMark}</span></div>
        <div class="tac-waiting">waiting…</div>`;
    } else {
      card.innerHTML = `
        <div class="tac-name" style="color:${meta.color}"><span>${meta.name}</span><span>${statusMark}</span></div>
        <div class="tac-bars">
          <div class="tac-row"><span class="tac-label">Input</span><div class="tac-bar"><div class="tac-fill in" style="width:${(a.tokensIn/maxIn*100).toFixed(1)}%"></div></div><span class="tac-n">${formatTokens(a.tokensIn)}</span></div>
          <div class="tac-row"><span class="tac-label">Output</span><div class="tac-bar"><div class="tac-fill out" style="width:${(a.tokensOut/maxOut*100).toFixed(1)}%"></div></div><span class="tac-n">${formatTokens(a.tokensOut)}</span></div>
          <div class="tac-row"><span class="tac-label">Think</span><div class="tac-bar"><div class="tac-fill think" style="width:${(a.reasoning/maxThink*100).toFixed(1)}%"></div></div><span class="tac-n">${formatTokens(a.reasoning)}</span></div>
        </div>`;
    }
    grid.appendChild(card);
  }
}

// ── Research Intel ───────────────────────────────────
function updateResearchIntel() {
  const snap = $("#pipeline-snapshot");
  snap.innerHTML = `
    <div class="rc-item"><span class="rc-key">Pipeline status</span><span class="rc-val ${statusClass()}">${state.pipelineStatus}</span></div>
    <div class="rc-item"><span class="rc-key">Current phase</span><span class="rc-val">${state.phase || "—"} / 7</span></div>
    <div class="rc-item"><span class="rc-key">Agents completed</span><span class="rc-val g">${state.completed} / ${TOTAL_AGENTS}</span></div>
    <div class="rc-item"><span class="rc-key">Total searches</span><span class="rc-val a">${state.totalSearches}</span></div>
    <div class="rc-item"><span class="rc-key">Pages fetched</span><span class="rc-val">${state.totalPages}</span></div>
    <div class="rc-item"><span class="rc-key">Total tokens</span><span class="rc-val">${formatTokens(state.totalTokens)}</span></div>
    <div class="rc-item"><span class="rc-key">Reasoning tokens</span><span class="rc-val p">${formatTokens(state.totalThinking)}</span></div>
    <div class="rc-item"><span class="rc-key">Errors</span><span class="rc-val ${state.totalErrors ? 'r' : 'g'}">${state.totalErrors}</span></div>
  `;

  const am = $("#agent-metrics");
  am.innerHTML = AGENT_IDS.map(id => {
    const a = state.perAgent[id];
    const meta = AGENT_META[id];
    return `<div class="rc-item">
      <span class="rc-key" style="color:${meta.color}">${meta.name}</span>
      <span class="rc-val">${formatTokens(a.tokensIn + a.tokensOut)} tok · ${a.searches}🔍 · ${a.pages}📄</span>
    </div>`;
  }).join("");

  // PMF score parsing (best-effort)
  const pmfMd = state.outputs.pmf;
  const pmfBox = $("#pmf-scores");
  const brief = $("#winner-brief");
  if (pmfMd) {
    const scores = parsePmfScores(pmfMd);
    if (scores) {
      pmfBox.innerHTML = scores.rows.map(r => `
        <div class="rc-item"><span class="rc-key">${r.label}</span><span class="rc-val g">${r.value}/10</span></div>
        <div class="score-bar"><div class="score-fill" style="width:${r.value * 10}%"></div></div>
      `).join("") + `
        <div class="rc-item" style="margin-top:8px;padding-top:8px;border-top:1px solid #1e1e1e">
          <span class="rc-key">Total PMF Score</span>
          <span class="rc-val g" style="font-size:15px">${scores.total}/50</span>
        </div>`;
    } else {
      pmfBox.innerHTML = `<div class="rc-empty">PMF report rendered but scores could not be parsed.</div>`;
    }
    const w = parsePmfWinner(pmfMd);
    brief.innerHTML = w ? `
      <div class="rc-item"><span class="rc-key">App</span><span class="rc-val g">${escapeHtml(w.name)}</span></div>
      <div class="rc-item"><span class="rc-key">Problem</span><span class="rc-val" style="white-space:normal;text-align:right;max-width:60%">${escapeHtml(w.problem || "—")}</span></div>
      <div class="rc-item"><span class="rc-key">Persona</span><span class="rc-val" style="white-space:normal;text-align:right;max-width:60%">${escapeHtml(w.persona || "—")}</span></div>
      ${w.killer ? `<div class="rc-quote">${escapeHtml(w.killer)}</div>` : ""}
    ` : `<div class="rc-empty">Winner section not parsed.</div>`;
  } else {
    pmfBox.innerHTML = `<div class="rc-empty">PMF agent has not completed yet.</div>`;
    brief.innerHTML = `<div class="rc-empty">Winner data appears once PMF completes.</div>`;
  }
}
function statusClass() {
  return state.pipelineStatus === "done"    ? "g"
       : state.pipelineStatus === "running" ? "a"
       : state.pipelineStatus === "error"   ? "r" : "";
}
function parsePmfScores(md) {
  // Match a "Scores:" line in the WINNER section if present, otherwise the first idea.
  const re = /\*\*Scores:\*\*\s*Demand:\s*(\d+(?:\.\d+)?)\/10\s*\|\s*Gap:\s*(\d+(?:\.\d+)?)\/10\s*\|\s*Build:\s*(\d+(?:\.\d+)?)\/10\s*\|\s*Monetise:\s*(\d+(?:\.\d+)?)\/10\s*\|\s*Retain:\s*(\d+(?:\.\d+)?)\/10/i;
  const m = re.exec(md);
  if (!m) return null;
  const rows = [
    { label: "Demand",       value: parseFloat(m[1]) },
    { label: "Competition gap", value: parseFloat(m[2]) },
    { label: "Buildability", value: parseFloat(m[3]) },
    { label: "Monetisation", value: parseFloat(m[4]) },
    { label: "Retention",    value: parseFloat(m[5]) },
  ];
  const total = rows.reduce((s, r) => s + r.value, 0).toFixed(1);
  return { rows, total };
}
function parsePmfWinner(md) {
  const nm = /^##\s*Winner\s*:\s*(.+?)\s*$/m.exec(md);
  if (!nm) return null;
  const field = (label) => {
    const re = new RegExp("\\*\\*" + label.replace(/[.*+?^${}()|[\\]\\\\]/g, "\\$&") + "\\s*:\\*\\*\\s*(.+?)\\s*(?:\\n|$)");
    const m = re.exec(md);
    return m ? m[1].trim().replace(/^\[|\]$/g, "") : "";
  };
  return {
    name: nm[1].trim().replace(/^\[|\]$/g, ""),
    problem: field("The single core problem this solves"),
    persona: field("Core user persona"),
    killer:  field("Killer insight"),
  };
}

// ── Search Log ───────────────────────────────────────
function recordSearch(agent, query, ts) {
  state.searches.push({ ts, agent, query, results: "…", pages: "…" });
  renderSearchLog();
}
function recordSearchResult(agent, query, results, pages) {
  // Update the latest matching search entry
  for (let i = state.searches.length - 1; i >= 0; i--) {
    const s = state.searches[i];
    if (s.agent === agent && s.query === query && (s.results === "…" || s.results == null)) {
      s.results = results; s.pages = pages; break;
    }
  }
  renderSearchLog();
}
function renderSearchLog() {
  const tbody = $("#search-tbody");
  if (state.searches.length === 0) {
    $("#search-empty").hidden = false;
    $("#search-table").hidden = true;
    return;
  }
  $("#search-empty").hidden = true;
  $("#search-table").hidden = false;
  tbody.innerHTML = state.searches.slice().reverse().map(s => {
    const meta = AGENT_META[s.agent];
    return `<tr>
      <td>${formatTime(new Date(s.ts * 1000))}</td>
      <td><span class="sa" style="color:${meta ? meta.color : '#888'}">${meta ? meta.name.split(' ')[0] : s.agent}</span></td>
      <td class="sq">"${escapeHtml(s.query)}"</td>
      <td>${s.results}</td>
      <td>${s.pages}</td>
    </tr>`;
  }).join("");
}

// ── Outputs ──────────────────────────────────────────
let currentOutputAgent = null;
function buildOutputChips() {
  const wrap = $("#out-chips");
  wrap.innerHTML = "";
  for (const id of AGENT_IDS) {
    const m = AGENT_META[id];
    const chip = document.createElement("button");
    chip.className = "out-chip";
    chip.dataset.agent = id;
    chip.type = "button";
    chip.innerHTML = `<span class="badge">${m.phase}</span>${m.name}`;
    chip.addEventListener("click", () => {
      if (state.outputs[id]) selectOutput(id);
    });
    wrap.appendChild(chip);
  }
  // Master report
  const master = document.createElement("button");
  master.className = "out-chip";
  master.dataset.agent = "master";
  master.type = "button";
  master.innerHTML = "★ Master Report";
  master.addEventListener("click", () => { if (state.outputs.master) selectOutput("master"); });
  wrap.appendChild(master);
}
function updateOutputChips() {
  $$(".out-chip").forEach(c => {
    const id = c.dataset.agent;
    c.classList.toggle("ready", !!state.outputs[id]);
    c.classList.toggle("active", currentOutputAgent === id);
  });
}
function selectOutput(id) {
  if (!state.outputs[id]) return;
  currentOutputAgent = id;
  switchTab("outputs");
  const viewer = $("#out-viewer");
  try { viewer.innerHTML = marked.parse(state.outputs[id]); }
  catch { viewer.textContent = state.outputs[id]; }
  updateOutputChips();
}

// ── Run History ──────────────────────────────────────
async function refreshHistory() {
  $("#hist-info").textContent = "Loading apps library…";
  try {
    const r = await fetch("/api/runs");
    const data = await r.json();
    state.history = data.runs || [];
    const active = !!data.pipeline_active;
    const liveLabel = active ? `▶ ${data.current_run_id}` : (data.current_run_id ? `idle (last: ${data.current_run_id})` : "idle");
    $("#hist-info").textContent = `${state.history.length} app${state.history.length === 1 ? "" : "s"} · ${liveLabel}`;
    renderHistory(data.current_run_id, active);
    renderRunSelMenu(data.current_run_id);
  } catch (e) {
    $("#hist-info").textContent = `Error loading history: ${e}`;
  }
}
function renderHistory(currentId, pipelineActive) {
  const tb = $("#hist-tbody");
  if (!state.history || state.history.length === 0) {
    tb.innerHTML = `<div class="hcard-empty">No runs yet. Start one with the "New Run" button or by running <code>python orchestrator.py</code>.</div>`;
    return;
  }
  tb.innerHTML = state.history.map(r => {
    const isCurrent = r.run_id === currentId;
    const isLive = isCurrent && pipelineActive;
    const incomplete = !r.has_master && r.agents_completed < r.agents_total;
    const cardCls = ["hcard"];
    if (isCurrent) cardCls.push("current");
    if (incomplete && !isLive) cardCls.push("incomplete");

    let statusBadge;
    if (isLive)         statusBadge = `<span class="hcard-status live">▶ running</span>`;
    else if (r.has_master) statusBadge = `<span class="hcard-status done">✓ done</span>`;
    else                statusBadge = `<span class="hcard-status incomplete">⚠ incomplete</span>`;

    const winnerHtml = r.winner
      ? `<div class="hcard-winner">${escapeHtml(r.winner)}</div>`
      : `<div class="hcard-winner muted">(no winner parsed yet)</div>`;

    const progressPct = Math.min(100, Math.round(r.agents_completed / r.agents_total * 100));

    // Action buttons depend on state.
    const actions = [];
    if (isLive) {
      actions.push(`<button class="hcard-btn current" disabled>Live view</button>`);
    } else {
      actions.push(`<button class="hcard-btn primary" data-action="load" data-id="${r.run_id}">Load</button>`);
      if (incomplete) {
        actions.push(`<button class="hcard-btn amber" data-action="continue" data-id="${r.run_id}">⟳ Continue</button>`);
      }
      actions.push(`<button class="hcard-btn danger" data-action="restart" data-id="${r.run_id}">↻ Restart</button>`);
    }

    return `<div class="${cardCls.join(' ')}" data-run="${r.run_id}">
      <div class="hcard-top">
        ${winnerHtml}
        ${statusBadge}
      </div>
      <div class="hcard-meta">
        <span><span class="meta-icon">🆔</span>${r.run_id}</span>
        <span><span class="meta-icon">⏱</span>${formatShortDuration(r.duration_seconds)}</span>
      </div>
      <div class="hcard-progress-row">
        <div class="hcard-progress-bar"><div class="hcard-progress-fill" style="width:${progressPct}%"></div></div>
        <span class="hcard-progress-n">${r.agents_completed}/${r.agents_total}</span>
      </div>
      <div class="hcard-actions">${actions.join("")}</div>
    </div>`;
  }).join("");

  // Wire up the buttons
  $$(".hcard-btn[data-action]").forEach(btn => {
    btn.addEventListener("click", () => handleHistoryAction(btn.dataset.action, btn.dataset.id));
  });
}

async function handleHistoryAction(action, runId) {
  if (action === "load") {
    loadHistoricalRun(runId);
    return;
  }
  if (action === "continue") {
    if (!confirm(`Continue run ${runId}?\nThe pipeline will skip agents that already produced output and resume from the first missing one.\n\nThis will cancel any currently-running pipeline.`)) return;
    await callAction(`/api/continue/${runId}`, "Continue requested. Resuming pipeline…");
    return;
  }
  if (action === "restart") {
    if (!confirm(`Restart run ${runId} from scratch?\nThis will DELETE all existing Markdown files in this run's folder and re-run every agent.\n\nThis will cancel any currently-running pipeline.`)) return;
    await callAction(`/api/restart/${runId}`, "Restart requested. Rebuilding from scratch…");
    return;
  }
}
async function callAction(url, okMsg) {
  try {
    const r = await fetch(url, { method: "POST" });
    const data = await r.json();
    if (data.ok) {
      toast(okMsg);
      // Switch back to live view if we were in historical mode.
      if (state.isHistorical) {
        state.isHistorical = false;
        $("#hist-banner")?.remove();
      }
      switchTab("log");
      // Give the new pipeline a moment to start emitting events.
      setTimeout(refreshHistory, 1500);
    } else {
      toast(`Action failed: ${data.reason || "unknown"}`, true);
    }
  } catch (e) { toast(`Action failed: ${e}`, true); }
}
function renderRunSelMenu(currentId) {
  const menu = $("#run-sel-menu");
  menu.innerHTML = state.history.slice(0, 12).map(r => `
    <div class="item ${r.run_id === currentId ? 'current' : ''}" data-load="${r.run_id}">
      <span class="id">${r.run_id}</span>
      <span class="win">${escapeHtml(r.winner || (r.run_id === currentId ? '(current)' : '(no winner)'))}</span>
    </div>`).join("");
  $$(".run-sel-menu .item").forEach(item => {
    item.addEventListener("click", () => {
      menu.hidden = true;
      const id = item.dataset.load;
      if (id === currentId) return;
      loadHistoricalRun(id);
    });
  });
}
async function loadHistoricalRun(runId) {
  state.isHistorical = true;
  state.runId = runId;
  $("#run-sel-label").textContent = runId + " (read-only)";
  showHistBanner(runId);
  toast(`Loading run ${runId}…`);
  try {
    const r = await fetch(`/api/runs/${runId}`);
    const data = await r.json();
    // Reset outputs map and fetch each file
    state.outputs = {};
    for (const file of data.files || []) {
      const agentId = fileToAgent(file);
      try {
        const fr = await fetch(`/api/runs/${runId}/files/${file}`);
        const txt = await fr.text();
        if (agentId) state.outputs[agentId] = txt;
        if (file === "MASTER_REPORT.md") state.outputs.master = txt;
      } catch {}
    }
    updateOutputChips();
    updateResearchIntel();
    if (state.outputs.master) selectOutput("master");
    else if (state.outputs.pmf) selectOutput("pmf");
  } catch (e) {
    toast(`Failed to load: ${e}`, true);
  }
}

function showHistBanner(runId) {
  // Place a banner above the .content scroll area so it sticks.
  document.getElementById("hist-banner")?.remove();
  const banner = document.createElement("div");
  banner.id = "hist-banner";
  banner.className = "hist-banner";
  banner.innerHTML = `<span>Viewing <strong>${runId}</strong> (read-only · live events suppressed)</span><button id="hist-back-btn">↩ Back to Live</button>`;
  const tabs = document.querySelector(".tabs");
  tabs.parentNode.insertBefore(banner, tabs.nextSibling);
  document.getElementById("hist-back-btn").addEventListener("click", () => {
    state.isHistorical = false;
    banner.remove();
    $("#run-sel-label").textContent = state.runId || "—";
    toast("Live view restored.");
  });
}
function fileToAgent(filename) {
  for (const id of AGENT_IDS) if (AGENT_META[id].file === filename) return id;
  return null;
}

$("#hist-refresh").addEventListener("click", refreshHistory);
$("#hist-new").addEventListener("click", async () => {
  if (!confirm("Start a brand-new run?\n\nThis cancels any active pipeline and creates a fresh timestamped run.")) return;
  try {
    const r = await fetch("/api/new", { method: "POST" });
    const data = await r.json();
    if (data.ok) {
      toast(`New run starting: ${data.run_id}`);
      if (state.isHistorical) { state.isHistorical = false; document.getElementById("hist-banner")?.remove(); }
      switchTab("log");
      setTimeout(refreshHistory, 1500);
    } else toast(`Could not start: ${data.reason || "unknown"}`, true);
  } catch (e) { toast(`Start failed: ${e}`, true); }
});
$("#run-sel").addEventListener("click", e => {
  e.stopPropagation();
  const menu = $("#run-sel-menu");
  if (menu.hidden) refreshHistory().then(() => { menu.hidden = false; });
  else menu.hidden = true;
});
document.addEventListener("click", () => { $("#run-sel-menu").hidden = true; });
$("#run-sel-menu").addEventListener("click", e => e.stopPropagation());

// ── Stop / New ───────────────────────────────────────
$("#stop-btn").addEventListener("click", async () => {
  if (!confirm("Stop the running pipeline? Completed agents will be preserved; the remaining ones will be cancelled.")) return;
  try {
    const r = await fetch("/api/stop", { method: "POST" });
    const data = await r.json();
    if (data.ok) toast("Stop signal sent. Pipeline cancelling…");
    else toast(`Cannot stop: ${data.reason || "no active pipeline"}`, true);
  } catch (e) { toast(`Stop failed: ${e}`, true); }
});
$("#new-btn").addEventListener("click", async () => {
  if (!confirm("Start a brand-new run?\n\nThis cancels any active pipeline and creates a fresh timestamped run.")) return;
  try {
    const r = await fetch("/api/new", { method: "POST" });
    const data = await r.json();
    if (data.ok) {
      toast(`New run starting: ${data.run_id}`);
      if (state.isHistorical) { state.isHistorical = false; document.getElementById("hist-banner")?.remove(); }
      switchTab("log");
      setTimeout(refreshHistory, 1500);
    } else toast(`Could not start: ${data.reason || "unknown"}`, true);
  } catch (e) { toast(`Start failed: ${e}`, true); }
});

function toast(msg, err) {
  const t = document.createElement("div");
  t.className = "toast" + (err ? " err" : "");
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

// ── Formatters ───────────────────────────────────────
function formatTime(d) { return d.toTimeString().slice(0, 8); }
function formatDuration(s) {
  s = Math.max(0, Math.floor(s));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  if (h > 0) return `${pad(h)}:${pad(m)}:${pad(r)}`;
  return `${pad(m)}:${pad(r)}`;
}
function formatShortDuration(s) {
  s = Math.max(0, Math.floor(s));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60), r = s % 60;
  if (m < 60) return `${m}m ${pad(r)}s`;
  const h = Math.floor(m / 60), rm = m % 60;
  return `${h}h ${pad(rm)}m`;
}
function pad(n) { return String(n).padStart(2, "0"); }
function formatTokens(n) {
  n = Number(n) || 0;
  if (n >= 10000) return (n / 1000).toFixed(1) + "k";
  if (n >= 1000)  return (n / 1000).toFixed(2) + "k";
  return String(n);
}
function escapeHtml(s) {
  return String(s || "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

// ── Run state reset (called when a new run_started arrives for a different id) ──
function resetForNewRun(newId) {
  state.runId = newId;
  state.startTime = null;
  if (state.elapsedTimer) { clearInterval(state.elapsedTimer); state.elapsedTimer = null; }
  state.totalTokens = 0; state.totalThinking = 0; state.totalSearches = 0;
  state.totalPages = 0; state.totalErrors = 0; state.completed = 0; state.phase = 0;
  state.searches = []; state.outputs = {}; state.logLines = 0;
  AGENT_IDS.forEach(id => {
    state.perAgent[id] = ensureAgentState(id);
    state.logBuffers[id] = { text: "", thinking: "" };
    setAgentStatus(id, "waiting");
    updateAgentRow(id);
  });
  logEl.innerHTML = "";
  $("#out-viewer").innerHTML = `<div class="empty">Click a completed output above to view it.</div>`;
  currentOutputAgent = null;
  updateOutputChips();
  renderSearchLog();
  recomputeMetrics();
  $("#run-sel-label").textContent = newId;
}
// ── Event handler (WebSocket) ────────────────────────
function handleEvent(ev) {
  if (state.isHistorical) {
    // While viewing a historical run, ignore live events. The user has
    // explicitly entered read-only mode; clicking Continue/Restart resets
    // this flag.
    return;
  }
  const agent = ev.agent;
  switch (ev.type) {
    case "run_started":
      if (state.runId && state.runId !== ev.run_id) resetForNewRun(ev.run_id);
      state.runId = ev.run_id;
      $("#run-sel-label").textContent = ev.run_id;
      setPipelineStatus("running");
      ensureTimer();
      refreshHistory();
      break;
    case "phase_change":
      setPhase(ev.phase);
      break;
    case "agent_start": {
      ensureTimer();
      if (!agent) break;
      state.perAgent[agent].startedAt = Date.now();
      setAgentStatus(agent, "running");
      setPipelineStatus("running");
      appendLog({ agent, text: "▶ started", ts: ev.ts });
      break;
    }
    case "agent_done": {
      if (!agent) break;
      const a = state.perAgent[agent];
      a.finishedAt = Date.now();
      a.tokensIn = ev.tokens_in || a.tokensIn;
      a.tokensOut = ev.tokens_out || a.tokensOut;
      a.reasoning = ev.reasoning_tokens || a.reasoning;
      a.searches = ev.searches || a.searches;
      a.pages = ev.pages || a.pages;
      a.errors = ev.errors || a.errors;
      flushAllBuffers(agent);
      setAgentStatus(agent, a.errors > 0 && a.tokensOut === 0 ? "error" : "done");
      updateAgentRow(agent);
      state.completed++;
      appendLog({ agent, text: `✓ done — in:${a.tokensIn} out:${a.tokensOut} think:${a.reasoning} search:${a.searches} pages:${a.pages}`, cls: "done", ts: ev.ts });
      recomputeMetrics();
      break;
    }
    case "text": {
      if (!agent) break;
      state.logBuffers[agent].text += ev.content || "";
      if (logFilters.text) flushBuffer(agent, "text");
      break;
    }
    case "thinking": {
      if (!agent) break;
      state.logBuffers[agent].thinking += ev.content || "";
      if (logFilters.thinking) flushBuffer(agent, "thinking");
      break;
    }
    case "tool_use": {
      if (!agent) break;
      state.perAgent[agent].searches++;
      updateAgentRow(agent);
      recordSearch(agent, ev.query, ev.ts);
      recomputeMetrics();
      if (logFilters.search) appendLog({ agent, text: `🔍 Searching: "${ev.query}"`, cls: "search", ts: ev.ts });
      break;
    }
    case "search_result": {
      if (!agent) break;
      state.perAgent[agent].pages += Number(ev.pages_fetched || 0);
      updateAgentRow(agent);
      recordSearchResult(agent, ev.query, ev.result_count, ev.pages_fetched);
      recomputeMetrics();
      break;
    }
    case "info":
      appendLog({ agent: agent || "system", text: ev.content || "", cls: "info", ts: ev.ts });
      break;
    case "error":
      state.totalErrors++;
      $("#m-err").textContent = state.totalErrors;
      appendLog({ agent: agent || "system", text: `⚠ ${ev.content || ""}`, cls: "error", ts: ev.ts });
      break;
    case "output_ready":
      if (!agent) break;
      state.outputs[agent] = ev.markdown || "";
      updateOutputChips();
      // Auto-select if nothing selected yet
      if (!currentOutputAgent) selectOutput(agent);
      break;
    case "complete":
      setPipelineStatus("done");
      setPhase(8);
      if (ev.master_markdown) state.outputs.master = ev.master_markdown;
      updateOutputChips();
      selectOutput("master");
      if (state.elapsedTimer) { clearInterval(state.elapsedTimer); state.elapsedTimer = null; }
      setElapsed();
      refreshHistory();
      break;
    case "stopped":
      setPipelineStatus("stopped");
      if (ev.master_markdown) {
        state.outputs.master = ev.master_markdown;
        updateOutputChips();
      }
      if (state.elapsedTimer) { clearInterval(state.elapsedTimer); state.elapsedTimer = null; }
      setElapsed();
      refreshHistory();
      break;
  }
}

// ── WebSocket ────────────────────────────────────────
function connectWs() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  let pingTimer = null;
  ws.onopen = () => {
    appendLog({ agent: "system", text: "WebSocket connected.", cls: "info" });
    pingTimer = setInterval(() => { try { ws.send("ping"); } catch {} }, 25000);
  };
  ws.onmessage = e => {
    let ev; try { ev = JSON.parse(e.data); } catch { return; }
    try { handleEvent(ev); }
    catch (err) { appendLog({ agent: "system", text: `handler error: ${err}`, cls: "error" }); }
  };
  ws.onclose = () => {
    if (pingTimer) clearInterval(pingTimer);
    appendLog({ agent: "system", text: "WebSocket disconnected. Reconnecting in 2s…", cls: "info" });
    setTimeout(connectWs, 2000);
  };
  ws.onerror = () => {};
}

// ── Boot ─────────────────────────────────────────────
buildPhaseBar();
buildSidebar();
buildLegend();
buildOutputChips();
setPipelineStatus("idle");
recomputeMetrics();
refreshHistory();
connectWs();

})();
