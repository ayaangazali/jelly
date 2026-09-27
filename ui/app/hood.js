// /app/under-the-hood and /app/setup: the classic dashboard's Under the hood and Setup views in the app's look, from
// the same /state. Loaded before app.js; uses its globals (data, esc, time, empty) at call time.
const PARTS = [ // every part Jelly calls, matched against the trace's `who`; a part with no call yet is marked not wired
  ["Coding agent", /OpenCode|Runner → Open/], ["Memorable", /Memorable/], ["Big model", /OpenAI|Anthropic/],
  ["Your model (River)", /River/], ["Unit tests", /Test suite|verify/i], ["Ledger", /Ledger/], ["Registry", /registry/i],
  ["Session log", /Session log/], ["Metrics", /Metrics/], ["Watcher", /Watcher/], ["Registrar / training", /Registrar|Consent/],
  ["GBrain", /GBrain/],
];
let hoodFile = "registry";

function underTheHood() {
  const s = data.state, trace = s.trace || [];
  const whole = Array.isArray(data.calls) ? data.calls : null; // outside providers: the whole trace, not /state's last 100
  const parts = PARTS.map(([name, re]) => {
    const src = whole && /Memorable|OpenAI|River|GBrain|Registrar/.test(re.source) ? whole : trace;
    const hits = src.filter((e) => re.test(`${e.who} ${e.call}`));
    return { name, n: hits.length, last: hits[hits.length - 1] };
  });
  const files = {
    registry: (s.files || {})["registry.json"] || "No registry.json yet.",
    ledger: (s.files || {})["ledger.jsonl"] || "No ledger rows yet.",
    session: (s.session_log || []).map((r) => JSON.stringify(r)).join("\n") || "No calls logged yet.",
  };
  const cls = (l) => (l.startsWith("$ ") ? "c" : /FAILED|failed|exit [1-9]/.test(l) ? "f" : /passed|exit 0/.test(l) ? "p" : "");
  return `<h1>Under the hood</h1>
<div class="parts">${parts.map((p) => `<div class="part${p.n ? " on" : ""}"><b>${esc(p.name)}</b><span>${p.n ? `${p.n} calls · last ${time(p.last.ts)}` : "not wired: no calls yet"}</span></div>`).join("")}</div>
<div class="cols">
<section><h2>Every call, newest first</h2>${trace.length ? `<ul class="feed">${[...trace].reverse().slice(0, 40).map((e) => `<li><time>${time(e.ts)}</time><span><b>${esc(e.who)}</b> <code>${esc(String(e.call).slice(0, 120))}</code><br><span class="muted">${esc(String(e.result).slice(0, 160))}</span></span></li>`).join("")}</ul>` : empty("No calls yet.")}</section>
<section><h2>Terminal</h2>${(s.terminal || []).length ? `<pre class="term">${s.terminal.slice(-80).map((l) => `<span class="${cls(l)}">${esc(l)}</span>`).join("\n")}</pre>` : empty("Waiting for a task…")}</section>
</div>
<h2>Files on disk</h2>
<div class="race-bar">${[["registry", "registry.json"], ["ledger", "ledger.jsonl"], ["session", "sessions/…jsonl"]].map(([k, l]) => `<button class="btn${hoodFile === k ? " owned" : ""}" data-file="${k}">${l}</button>`).join("")}</div>
<pre class="filebox">${esc(files[hoodFile])}</pre>`;
}

let setupTab = "opencode";
const SETUP = {
  opencode: ["OpenCode", `<p>Add a provider in <code>opencode.json</code>:</p><pre class="filebox">"provider": { "graduate": {\n  "npm": "@ai-sdk/openai-compatible",\n  "options": { "baseURL": "http://localhost:4141/v1", "apiKey": "{env:GRADUATE_SESSION}" }\n} }</pre><p class="muted">This is the harness the demo uses.</p>`],
  claude: ["Claude Code", `<p>Point Claude Code at the proxy and turn on the headers Jelly uses to count turns:</p><pre class="filebox">export ANTHROPIC_BASE_URL=http://localhost:4141\nexport ANTHROPIC_API_KEY=sess-$(uuidgen | tr A-Z a-z)\nexport CLAUDE_CODE_GATEWAY_HINT_HEADERS=1</pre><p class="muted">The key is the session id: use a new <code>sess-…</code> value per session.</p>`],
  aider: ["Aider and scripts", `<p>Anything that speaks OpenAI Chat Completions:</p><pre class="filebox">export OPENAI_API_BASE=http://localhost:4141/v1</pre><p class="muted">Aider reads OPENAI_API_BASE; the OpenAI SDK reads OPENAI_BASE_URL.</p>`],
  codex: ["Codex", `<p>Codex only talks the OpenAI Responses API, which Jelly doesn't serve, so Codex runs go straight to OpenAI.</p>`],
};

function setup() {
  const s = data.state, tt = Object.entries(s.registry.task_types || {});
  const where = { river: "River", local: "this machine", none: "nowhere (the big model serves everything)" }[s.config.backend] || s.config.backend;
  return `<h1>Setup</h1>
<p class="lede">Change one setting per tool; your agent works as before. Nothing trains until you approve a task type's data; Approve trains on ${esc(where)}.</p>
<div class="race-bar">${Object.entries(SETUP).map(([k, [l]]) => `<button class="btn${setupTab === k ? " owned" : ""}" data-setup="${k}">${l}</button>`).join("")}</div>
<section class="panel setup-body">${SETUP[setupTab][1]}</section>
<h2>Consent and status</h2>
${tt.length ? `<div class="scroll"><table class="ttypes"><thead><tr><th>Task type</th><th>State</th><th>Verified runs</th><th>Consent to train</th><th>Model</th></tr></thead><tbody>${tt.map(([id, t]) => `<tr><td class="tname" title="${esc(t.title || id)}"><b>${esc(t.title || id)}</b></td><td>${stateTag(t.state)}</td><td>${t.verified_runs} of ${s.config.n}</td><td>${t.consent ? "given" : `<span class="muted">not given</span>`}</td><td>${t.model ? (String(t.model).startsWith("river://") ? "Qwen3.5-9B on River" : "on this machine") : `<span class="muted">none yet</span>`}</td></tr>`).join("")}</tbody></table></div>` : empty("No task types yet.")}`;
}

document.addEventListener("click", (e) => {
  const f = e.target.closest("button[data-file]"), t = e.target.closest("button[data-setup]");
  if (f) { hoodFile = f.dataset.file; render(); }
  if (t) { setupTab = t.dataset.setup; render(); }
});
