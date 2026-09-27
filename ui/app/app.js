// GRADUATE app (/app): one page per job, all from the live APIs. Nothing here computes a win the ledger doesn't show.
const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
const time = (ts) => esc((ts || "").slice(11, 19));
const money = (v) => `$${Number(v).toFixed(v < 1 ? 4 : 2)}`;
const num = (v) => Math.round(v).toLocaleString();
const data = { state: null, swarm: null, reviews: {} };

async function get(url, init) {
  try {
    const r = await fetch(url, { cache: "no-store", ...init });
    const body = await r.json().catch(() => ({ error: `${url} answered ${r.status}.` }));
    return r.ok ? body : { error: body.error || `${url} answered ${r.status}.`, ...body };
  } catch {
    return { error: `${url} isn't reachable.` };
  }
}

const page = () => (location.hash.split("/")[1] || "compare");

function render() {
  const p = PAGES[page()] ? page() : "compare";
  document.querySelectorAll("nav.side [data-nav]").forEach((a) => a.dataset.nav === p ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"));
  const html = data.state ? PAGES[p]() : `<p class="lede">Loading /state…</p>`;
  if ($("#view").dataset.html !== html) { $("#view").innerHTML = html; $("#view").dataset.html = html; }
  tick();
}

async function poll() {
  const s = await get("/state");
  const up = !s.error;
  $("#live").innerHTML = `<span class="dot${up ? " on" : ""}"></span> ${up ? "live · updates every 3s" : "router unreachable"}`;
  if (up) data.state = s;
  if (["home", "agents"].includes(page())) data.swarm = await get("/api/swarm");
  if (page() === "compare") data.race = await get("/api/race");
  render();
}

const types = () => Object.entries(data.state.registry.task_types || {});
const N = () => data.state.config.n;
const stateTag = (s) => `<span class="state s-${esc(s)}">${esc(s)}</span>`;
const empty = (text) => `<p class="empty">${text}</p>`;

function feed(events) {
  if (!events.length) return empty("Nothing yet. Run <code>graduate run</code> and each verified run shows up here.");
  return `<ul class="feed">${events.map((e) => `<li><time>${time(e.ts)}</time><span>${esc(e.text)}</span></li>`).join("")}</ul>`;
}

function home() {
  const s = data.state, tt = types();
  const verified = tt.reduce((a, [, t]) => a + (t.verified_runs || 0), 0);
  const grads = tt.filter(([, t]) => t.state === "GRADUATED").length;
  const owned = s.totals.owned_runs;
  const events = [...(s.registry.events || [])].sort((a, b) => (b.ts || "").localeCompare(a.ts || "")).slice(0, 12);
  const agents = (data.swarm && data.swarm.agents) || [];
  return `<h1>Your agents, getting cheaper</h1>
<p class="lede">GRADUATE sits between your coding agent and the frontier model. It watches which kinds of task your agents repeat, and once a task type has ${N()} test-verified runs, it trains a small model you own on them and routes that task to it. Every run is still verified; a failure goes back to the frontier.</p>
<div class="cards">
  <div class="card"><b>${tt.length}</b><span>task types seen</span></div>
  <div class="card"><b>${verified}</b><span>verified runs</span></div>
  <div class="card"><b class="owned">${grads}</b><span>graduated to your model</span></div>
  <div class="card"><b class="owned">${owned}</b><span>runs served by your model</span></div>
  <div class="card"><b>${owned ? money(s.totals.saved_usd) : "n/a"}</b><span>${owned ? "saved vs frontier baseline (ledger)" : "saved: no owned runs in the ledger yet"}</span></div>
</div>
<div class="cols">
  <section><h2>Live activity</h2>${feed(events)}</section>
  <section><h2>Agents now</h2>${agents.length ? `<p>${agents.length} agents in <code>${esc(data.swarm.swarm_id)}</code>: ${["running", "passed", "failed", "queued"].map((st) => `${agents.filter((a) => a.status === st).length} ${st}`).join(" · ")}.</p><p><a href="#/agents">See the agents →</a></p>` : empty("No swarm running. <code>graduate swarm --tasks 01,02,03 --agents 3</code> starts one.")}</section>
</div>`;
}

function agents() {
  const w = data.swarm;
  if (!w) return `<h1>Agents</h1><p class="lede">Loading /api/swarm…</p>`;
  const list = w.agents || [];
  const flags = (a) => `${a.a2a_read ? `<span class="flag">read a note</span>` : ""}${a.a2a_write ? `<span class="flag">left a note</span>` : ""}`;
  const notes = [...(w.a2a || [])].reverse();
  return `<h1>Agents</h1>
<p class="lede">Parallel agents from <code>graduate swarm</code>, one per task in its own copy of the demo repo. Agents on the same task type share what worked through agent-to-agent notes.</p>
${w.error ? empty(esc(w.error)) : `<p class="muted"><code>${esc(w.swarm_id)}</code> · started ${esc((w.started || "").replace("T", " ").slice(0, 19))}Z · launcher ${esc(w.launcher)}</p>`}
${list.length ? `<table><thead><tr><th>Agent</th><th>Task</th><th>Task type</th><th>Status</th><th class="num">Exit</th><th class="num">Turns</th><th>Notes</th><th>Session</th></tr></thead><tbody>
${list.map((a) => `<tr><td><b>${esc(a.agent)}</b></td><td>${esc(a.task)}</td><td>${a.task_type ? `<code>${esc(a.task_type)}</code>` : `<span class="muted">not yet</span>`}</td><td>${stateTag(a.status)}</td><td class="num">${a.exit_code ?? "–"}</td><td class="num">${a.turns ?? "–"}</td><td>${flags(a)}</td><td><code class="muted">${esc((a.session_id || "–").slice(0, 13))}</code></td></tr>`).join("")}
</tbody></table>` : ""}
<h2>Agent-to-agent notes</h2>
${notes.length ? `<ul class="feed">${notes.map((e) => `<li><time>${time(e.ts)}</time><span><b>${(e.edges || []).includes("a2a-write") ? "wrote" : "read"}</b> <code>${esc(e.call)}</code><br><span class="muted">${esc(e.result)}</span></span></li>`).join("")}</ul>` : empty("No notes read or written yet.")}`;
}

function tasks() {
  const tt = types();
  if (!tt.length) return `<h1>Task types</h1>${empty("No task types yet: they appear after the first classified run.")}`;
  const approvable = (t) => ["READY", "PROBATION"].includes(t.state);
  return `<h1>Task types</h1>
<p class="lede">Each kind of task your agents repeat. At ${N()} verified runs it is ready to train; nothing trains until you approve its data.</p>
<table><thead><tr><th>Task type</th><th>State</th><th>Progress to graduation</th><th>Consent</th><th>Turns / cost per run</th><th>Actions</th></tr></thead><tbody>
${tt.map(([id, t]) => {
    const n = Math.min(t.verified_runs || 0, N());
    const cur = t.current, base = t.baseline;
    const r = data.reviews[id];
    return `<tr><td><b>${esc(t.title || id)}</b><br><code class="muted">${esc(id)}</code></td>
<td>${stateTag(t.state)}</td>
<td><span class="pips">${Array.from({ length: N() }, (_, i) => `<i class="${i < n ? "on" : ""}"></i>`).join("")}</span>${t.verified_runs} of ${N()} verified${t.failed_runs ? ` <span class="muted">· ${t.failed_runs} failed</span>` : ""}</td>
<td>${t.consent ? "approved" : `<span class="muted">not given</span>`}</td>
<td>${base ? `frontier ${base.turns} · ${money(base.cost_usd)}` : `<span class="muted">n/a</span>`}${cur ? `<br><b style="color:var(--owned)">yours ${cur.turns} · ${money(cur.cost_usd)}</b>` : ""}</td>
<td><button class="btn" data-act="review" data-t="${esc(id)}">Review data</button>
<button class="btn owned" data-act="approve" data-t="${esc(id)}" ${approvable(t) ? "" : "disabled"}>Approve</button>
<button class="btn" data-act="revoke" data-t="${esc(id)}" ${approvable(t) && t.consent ? "" : "disabled"}>Revoke</button>
${r ? reviewPanel(r) : ""}</td></tr>`;
  }).join("")}
</tbody></table>`;
}

function reviewPanel(r) {
  if (r.loading) return `<div class="review muted">Loading…</div>`;
  if (r.msg) return `<p class="msg${r.bad ? " err" : ""}">${esc(r.msg)}</p>`;
  return `<div class="review">${r.error ? `<p class="msg err">${esc(r.error)}</p>` : ""}
<p>${r.records ?? 0} runs${r.tokens != null ? `, ${num(r.tokens)} tokens` : ""}. Trains on: ${esc(r.destination || r.where || "n/a")}.</p>
${r.sample ? `<pre>${esc(JSON.stringify(r.sample, null, 1).slice(0, 1500))}</pre>` : ""}</div>`;
}

async function act(kind, t) {
  if (kind === "approve" && !confirm(`Train ${t} on its verified runs? This starts training now.`)) return;
  data.reviews[t] = { loading: true };
  render();
  const method = { review: "GET", approve: "POST", revoke: "DELETE" }[kind];
  const r = await get(`/api/consent/${encodeURIComponent(t)}`, { method });
  if (kind === "review") data.reviews[t] = r;
  else data.reviews[t] = r.error ? { msg: r.error, bad: true } : { msg: kind === "approve" ? `Approved. Training started (${r.records} runs, log ${r.log}).` : "Consent revoked. Nothing will be trained." };
  await poll();
}

// Compare: the same task, frontier (left) vs your model (right), replayed from the recorded session logs at recorded
// speed. Pairs come from the ledger: a prompt with both a frontier row and an owned row. Counters only reach what the
// ledger row and session log hold; a pane without a log shows the ledger's totals when its recorded time is up.
const race = { key: null, speed: 1, base: 0, since: 0, panes: null };

const pairs = () => (data.race && data.race.pairs) || [];

function pane({ row, log }) {
  const calls = log || [];
  const start = calls.length ? Date.parse(calls[0].ts) - (calls[0].latency_ms || 0) : 0;
  const tokens = (u) => (u.input_tokens || 0) + (u.output_tokens || 0);
  const all = calls.reduce((a, c) => a + tokens(c.usage || {}), 0) || 1;
  const steps = calls.map((c) => ({
    at: Date.parse(c.ts) - start, from: Date.parse(c.ts) - start - (c.latency_ms || 0), out: (c.usage || {}).output_tokens || 0,
    cost: (row.cost_usd || 0) * tokens(c.usage || {}) / all, what: describe(c.response || {}),
  }));
  const end = Math.max(row.wall_secs * 1000 || 0, steps.length ? steps[steps.length - 1].at : 0);
  return { row, steps, end, logged: calls.length > 0 };
}

function describe(m) {
  if (m.tool_calls && m.tool_calls.length) return m.tool_calls.map((t) => {
    let args = t.function.arguments;
    try { args = Object.values(JSON.parse(args)).map(String)[0] || ""; } catch {}
    return `<b>${esc(t.function.name)}</b> <code>${esc(String(args).split("\n")[0].replace(/^\/\S*\/(\S+\/\S+)/, "…/$1").slice(0, 70))}</code>`;
  }).join("<br>");
  return m.content ? esc(m.content.slice(0, 160)) : `<span class="muted">(empty reply)</span>`;
}

function startRace(p) {
  Object.assign(race, { key: p.owned.row.session_id, panes: [pane(p.frontier), pane(p.owned)], rescue: p.rescue, base: 0, since: performance.now() });
}

const elapsed = () => race.base + (performance.now() - race.since) * race.speed;
function setSpeed(x) { race.base = elapsed(); race.since = performance.now(); race.speed = x; tick(); }

const source = (r, side) => /stub/i.test(r.model) ? "stub model, offline" : r.model.startsWith("/") ? "local model on this machine"
  : r.model.startsWith("river://") ? "River model" : side === "owned" ? `routed to your model, upstream reported ${esc(r.model)}` : "frontier API";
const secsOf = (ms) => `${(ms / 1000).toFixed(1)}s`;

function paneHTML(p, t, side) {
  const r = p.row, done = t >= p.end, shown = p.steps.filter((s) => s.at <= t), next = p.steps.find((s) => s.at > t);
  const counts = done ? { out: r.output_tokens, turns: r.turns, cost: r.cost_usd, ms: r.wall_secs * 1000 }  // the ledger has the last word
    : { out: shown.reduce((a, s) => a + s.out, 0), turns: shown.length, cost: shown.reduce((a, s) => a + s.cost, 0), ms: t };
  const verdict = !done ? `<p class="verify muted">running…</p>` : r.exit_code === 0
    ? `<p class="verify pass">Tests pass: ${r.tests_passed} of ${r.tests_total} · exit 0</p>`
    : `<p class="verify fail">Tests fail · exit ${r.exit_code}${race.rescue && side === "owned" ? `<br>Escalated to the frontier: <code>${esc(race.rescue.session_id)}</code>, exit ${race.rescue.exit_code}, ${money(race.rescue.cost_usd)}` : ""}</p>`;
  return `<header><b>${side === "owned" ? "Your model" : "Frontier"}</b> <code>${esc(r.model.split("/").pop())}</code>
<p class="muted">${data.sample ? "sample data" : "recorded run"} · ${source(r, side)} · ${p.logged ? `${p.steps.length} logged calls` : "no session log: ledger totals at the end"}</p></header>
<div class="ctr"><div class="big"><b>${num(counts.out)}</b><span>output tokens</span></div>
<div><b>${counts.turns}</b><span>turns</span></div><div><b>${money(counts.cost)}</b><span>cost est.</span></div>
<div><b>${secsOf(counts.ms)}</b><span>wall time</span></div></div>
<ol class="turns">${shown.map((s, i) => `<li><span class="muted">${i + 1}</span><span>${s.what}<br><small class="muted">${num(s.out)} output tokens · ${secsOf(s.at)}</small></span></li>`).join("")}
${next && next.from <= t ? `<li class="now"><span class="muted">${shown.length + 1}</span><span class="muted">model thinking…</span></li>` : ""}${p.logged ? "" : `<li><span></span><span class="muted">This run kept no per-call log, so its turns can't be replayed. The ledger's totals show when its recorded ${r.wall_secs}s are up.</span></li>`}</ol>
${verdict}`;
}

function verdictHTML([f, o]) {
  const F = f.row, O = o.row;
  if (O.exit_code !== 0) return `<p class="diff fail">Your model failed this task${race.rescue ? " and the frontier finished it" : ""}. No win to claim here.</p>`;
  if (F.exit_code !== 0) return `<p class="diff">The frontier failed this task; your model passed.</p>`;
  const cmp = (f, o, fmt, less, more) => `${o < f ? less : o > f ? more : "same"} ${fmt(f)} → ${fmt(o)}`;
  const x = O.output_tokens < F.output_tokens ? `<b>${(F.output_tokens / (O.output_tokens || 1)).toFixed(1)}× fewer output tokens</b> (${num(F.output_tokens)} → ${num(O.output_tokens)})` : cmp(F.output_tokens, O.output_tokens, num, "fewer output tokens", "more output tokens");
  return `<p class="diff">Both passed. Your model: ${x} · ${cmp(F.turns, O.turns, String, "fewer turns", "more turns")} · ${cmp(F.cost_usd, O.cost_usd, money, "cheaper", "costlier")} · ${cmp(F.wall_secs, O.wall_secs, (v) => `${v}s`, "faster", "slower")} <span class="muted">(ledger)</span></p>`;
}

function tick() {
  const box = document.getElementById("race");
  if (!box || !race.panes) return;
  const t = elapsed();
  race.panes.forEach((p, i) => {
    const el = box.children[i], html = paneHTML(p, t, i ? "owned" : "frontier");
    if (el.dataset.html !== html) { el.innerHTML = html; el.dataset.html = html; el.querySelector(".turns").scrollTop = 1e6; }
  });
  const v = document.getElementById("verdict"), html = race.panes.every((p) => t >= p.end) ? verdictHTML(race.panes) : "";
  if (v.dataset.html !== html) { v.innerHTML = html; v.dataset.html = html; }
}
setInterval(tick, 100);

function compare() {
  if (!data.race) return `<h1>Compare</h1><p class="lede">Loading the recorded runs…</p>`;
  if (data.race.error) return `<h1>Compare</h1>${empty(esc(data.race.error))}`;
  const ps = pairs();
  if (!ps.length) return `<h1>Compare</h1>${empty("No task has both a frontier run and a run on your model in the ledger yet. Once a task type graduates, its next run races here against a frontier run of the same task.")}`;
  const key = (x) => x.owned.row.session_id;
  let p = ps.find((x) => key(x) === race.key);
  if (!p) startRace((p = ps.find((x) => x.owned.row.exit_code === 0) || ps[0]));
  const o = p.owned.row;
  return `<h1>Same task, side by side</h1>
<p class="lede">${esc(o.prompt)} <span class="muted">· ${esc(o.task_type)} · frontier on the left, your model on the right, replayed at recorded speed.</span></p>
<div class="race-bar"><select id="pair">${ps.map((x) => `<option value="${esc(key(x))}" ${x === p ? "selected" : ""}>${esc(x.owned.row.prompt.slice(0, 60))} · ${esc(x.owned.row.started_at.slice(11, 16))} · yours ${x.owned.row.exit_code === 0 ? "passed" : "failed"}</option>`).join("")}</select>
<button class="btn" data-race="replay">Replay</button>${[1, 4, 16].map((x) => `<button class="btn" data-race="${x}">${x}×</button>`).join("")}
<a href="/#/compare">Bench: frontier vs small vs yours →</a></div>
<div id="race" class="race"><section class="pane frontier"></section><section class="pane owned"></section></div><div id="verdict"></div>`;
}

function activity() {
  const s = data.state;
  const trace = [...(s.trace || [])].reverse().slice(0, 40);
  return `<h1>Activity</h1>
<p class="lede">Every external call GRADUATE makes, newest first. The full architecture diagram, lit up live, is <a href="/#/system">Under the hood</a> on the classic dashboard.</p>
<div class="cols">
<section><h2>Call trace</h2>${trace.length ? `<ul class="feed">${trace.map((e) => `<li><time>${time(e.ts)}</time><span><b>${esc(e.who)}</b> <code>${esc(e.call)}</code><br><span class="muted">${esc(e.result)}</span></span></li>`).join("")}</ul>` : empty("No calls traced yet.")}</section>
<section><h2>Terminal</h2>${(s.terminal || []).length ? `<pre class="term">${esc(s.terminal.slice(-60).join("\n"))}</pre>` : empty("Nothing in terminal.log yet.")}</section>
</div>`;
}

const PAGES = { home, agents, tasks, compare, activity };

document.addEventListener("click", (e) => {
  const b = e.target.closest("button[data-act]");
  if (b) act(b.dataset.act, b.dataset.t);
  const r = e.target.closest("button[data-race]");
  if (r && r.dataset.race === "replay") { race.base = 0; race.since = performance.now(); tick(); }
  else if (r) setSpeed(Number(r.dataset.race));
});
document.addEventListener("change", (e) => {
  if (e.target.id === "pair") { startRace(pairs().find((x) => x.owned.row.session_id === e.target.value)); render(); }
});
window.addEventListener("hashchange", poll);
get("/api/sample").then((r) => { data.sample = r.sample; $("#sample").hidden = !r.sample; });
poll();
setInterval(poll, 3000);
