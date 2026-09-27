// /app/under-the-hood and /app/setup: the classic dashboard's Under the hood and Setup views in the app's look, from
// the same /state. Loaded before app.js; uses its globals (data, esc, time, empty) at call time.
const PARTS = [ // every part Jelly calls, matched against the trace's `who`; a part with no call yet is marked not wired
  ["Coding agent", /OpenCode|Runner → Open/], ["Memorable", /Memorable/], ["Big model", /OpenAI|Anthropic/],
  ["Your model (River)", /River/], ["Unit tests", /Test suite|verify/i], ["Ledger", /Ledger/], ["Registry", /registry/i],
  ["Session log", /Session log/], ["Metrics", /Metrics/], ["Watcher", /Watcher/], ["Registrar / training", /Registrar|Consent/],
  ["GBrain", /GBrain/],
];
let hoodFile = "registry";

// The architecture diagram (the classic dashboard's, in Jelly's look): each part where it sits, lit from the latest
// real call's `nodes` and `edges` in the trace; a part no call has touched yet is faded.
const AC = { A: 40, B: 290, C: 580, D: 820 }, AR = { 1: 20, 2: 130, 3: 240, 4: 350, 5: 460 }, ABW = 190, ABH = 56;
const ARCH_NODES = [
  ["runner", "A", 1, "Runner", "graduate run"], ["memorable", "B", 1, "Memorable", "recall · ingest", 1], ["openai", "C", 1, "Big model", "OpenAI", 1],
  ["opencode", "A", 2, "OpenCode", "the coding agent"], ["router", "B", 2, "Jelly router :4141", "/v1/chat/completions"], ["river", "C", 2, "Your model", "served on River", 1],
  ["dashboard", "D", 2, "Jelly app", "GET /state"], ["pytest", "A", 3, "Unit tests", "verify → exit code"], ["disk", "B", 3, "Session log", "sessions/ · metrics.jsonl"],
  ["registry", "C", 3, "registry.json", "state per task type"], ["consent", "D", 3, "You", "approve training data"], ["ledger", "A", 4, "ledger.jsonl", "one row per session"],
  ["watcher", "B", 4, "Watcher", "counts passing runs"], ["rivertrain", "C", 4, "River training", "LoRA on your runs", 1], ["registrar", "D", 4, "Registrar", "dataset + trainer"],
  ["escalator", "A", 5, "Escalator", "reset · re-run on big model"],
];
const ARCH_EDGES = [
  ["launch", "M135,76 V130", 141, 107, "launches", "start"], ["ingest", "M230,48 H290", 260, 42, "ingest", "middle"], ["chat", "M230,158 H290", 260, 152, "chat calls", "middle"],
  ["recall", "M385,130 V76", 391, 107, "recall", "start"], ["frontier", "M480,146 H530 V48 H580", 536, 98, "not graduated", "start"], ["owned", "M480,172 H580", 530, 166, "graduated", "middle"],
  ["log", "M385,186 V240", 379, 206, "logs every call", "end"], ["reads", "M580,262 H545 V214 H455 V186", 500, 229, "reads state", "middle"], ["verify", "M40,48 H22 V268 H40", 30, 216, "verify", "start"],
  ["exit", "M135,296 V350", 141, 327, "exit code", "start"], ["tail", "M230,378 H290", 260, 372, "tails", "middle"], ["ready", "M480,378 H530 V278 H580", 536, 332, "5 passing → Ready", "start"],
  ["ask", "M770,268 H820", 795, 262, "asks", "middle"], ["approved", "M915,296 V350", 921, 327, "approved", "start"], ["train", "M820,392 H770", 795, 418, "trains", "middle"],
  ["serve", "M770,362 H796 V158 H770", 802, 205, "checkpoint", "start"], ["graduate", "M870,350 V316 H720 V296", 752, 311, "Graduated", "middle"], ["state", "M960,186 V214 H745 V240", 952, 208, "GET /state", "end"],
  ["failed", "M135,406 V460", 141, 437, "your model failed", "start"], ["rerun", "M230,488 H260 V178 H290", 266, 470, "re-run on big model", "start"],
];

function archSvg(trace) {
  const last = trace[trace.length - 1] || {}, onN = new Set(last.nodes || []), onE = new Set(last.edges || []);
  const wired = new Set([...trace, ...(Array.isArray(data.calls) ? data.calls : [])].flatMap((e) => e.nodes || []));
  const big = ([...(data.state.ledger || [])].reverse().find((r) => r.routed_to === "frontier") || {}).model;
  const edges = ARCH_EDGES.map(([id, d, lx, ly, t, a]) => `<g class="aedge${onE.has(id) ? " on" : ""}"><path d="${d}"/><text x="${lx}" y="${ly}" text-anchor="${a}">${t}</text></g>`).join("");
  const nodes = ARCH_NODES.map(([id, c, r, label, sub, ext]) => {
    const x = AC[c], y = AR[r], s2 = id === "openai" && big ? big : sub;
    return `<g class="anode${ext ? " ext" : ""}${onN.has(id) ? " on" : ""}${wired.has(id) ? "" : " idle"}"><rect x="${x}" y="${y}" width="${ABW}" height="${ABH}" rx="6"/><text x="${x + 14}" y="${y + 24}">${esc(label)}</text><text class="sub" x="${x + 14}" y="${y + 42}">${esc(s2)}</text></g>`;
  }).join("");
  return `<svg class="arch" viewBox="0 0 1030 530" role="img" aria-label="Jelly's parts, lit from the latest real call">${edges}${nodes}</svg>`;
}


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
<figure class="panel arch-fig">${archSvg(trace)}<figcaption class="muted">Solid boxes run on this machine; dashed boxes are outside services. Indigo is the latest real call; faded boxes have not been called yet.</figcaption></figure>
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
  opencode: ["OpenCode", `<p>Add a provider in <code>opencode.json</code>:</p><pre class="filebox">"provider": { "jelly": {\n  "npm": "@ai-sdk/openai-compatible",\n  "options": { "baseURL": "http://localhost:4141/v1", "apiKey": "{env:JELLY_SESSION}" }\n} }</pre><p class="muted">Set <code>JELLY_SESSION</code> to a new <code>sess-…</code> id for each session: Jelly uses it to tell sessions apart. This is the harness the demo uses.</p>`],
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
${tt.length ? `<div class="scroll"><table class="ttypes"><thead><tr><th>Task type</th><th>State</th><th>Verified runs</th><th>Consent to train</th><th>Model</th></tr></thead><tbody>${tt.map(([id, t]) => `<tr><td class="tname" title="${esc(t.title || id)}"><b>${esc(t.title || id)}</b></td><td>${stateTag(t.state)}</td><td>${t.verified_runs} verified · ${s.config.n} needed</td><td>${t.consent ? "given" : `<span class="muted">not given</span>`}</td><td>${t.model ? (String(t.model).startsWith("river://") ? "Qwen3.5-9B on River" : "on this machine") : `<span class="muted">none yet</span>`}</td></tr>`).join("")}</tbody></table></div>` : empty("No task types yet.")}`;
}

document.addEventListener("click", (e) => {
  const f = e.target.closest("button[data-file]"), t = e.target.closest("button[data-setup]");
  if (f) { hoodFile = f.dataset.file; render(); }
  if (t) { setupTab = t.dataset.setup; render(); }
});
