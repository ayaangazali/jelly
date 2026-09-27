// GRADUATE app (/app): one page per job, all from the live APIs. Nothing here computes a win the ledger doesn't show.
const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
const time = (ts) => esc((ts || "").slice(11, 19));
const money = (v) => `$${Number(v).toFixed(v < 1 ? 3 : 2)}`;
const num = (v) => Math.round(v).toLocaleString();
const data = { state: null, swarm: null, reviews: {} };

async function get(url, init) {
  try {
    const r = await fetch(url, { cache: "no-store", ...init });
    const body = await r.json().catch(() => ({ error: `${url} answered ${r.status}.` }));
    return r.ok ? body : { error: body.error || `${url} answered ${r.status}.`, ...body, status: r.status };
  } catch {
    return { error: `${url} isn't reachable.` };
  }
}

// Clean paths: /app is the live showcase (live.js), /app/<page> the working pages.
const page = () => location.pathname.replace(/^\/app\/?/, "").split("/")[0] || "live";

function render() {
  const p = PAGES[page()] ? page() : "live";
  document.body.classList.toggle("on-live", p === "live");
  const nav = { logs: "activity", "under-the-hood": "activity", chat: "race" }[p] || p; // merged pages keep their old URLs
  document.querySelectorAll("nav.side [data-nav]").forEach((a) => a.dataset.nav === nav ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"));
  const html = data.state ? PAGES[p]() : `<p class="lede">Loading /state…</p>`;
  swap($("#view"), html);
  tick();
  if (p === "live" && !sim.on) { sim.on = true; sim.last = performance.now(); requestAnimationFrame(frame); }
}

// Replace an element's HTML only when what we render changed (compared with what we last wrote, not the live DOM, which
// an opened <details> alters), and keep every opened expander and scroll position across the replacement.
const SCROLLERS = ".drawer, .oc-body, .filebox, .scroll, .turns, .tbody, .log, .feed, .procs, .bars, .serve, pre.term";
function swap(el, html) {
  if (!el || el.dataset.html === html) return false;
  const open = new Set([...el.querySelectorAll("details[open] > summary")].map((x) => x.textContent));
  const key = (x, i, all) => `${x.closest("section, .panel, figure")?.querySelector("h2, h3")?.textContent || ""}|${x.className}|${all.filter((y) => y.className === x.className).indexOf(x)}`;
  const was = [...el.querySelectorAll(SCROLLERS)], tops = new Map(was.map((x, i) => [key(x, i, was), x.scrollTop]));
  el.innerHTML = html; el.dataset.html = html;
  el.querySelectorAll("details > summary").forEach((x) => { if (open.has(x.textContent)) x.parentElement.open = true; });
  const now = [...el.querySelectorAll(SCROLLERS)];
  now.forEach((x, i) => { const t = tops.get(key(x, i, now)); if (t) x.scrollTop = t; });
  return true;
}

async function poll() {
  const s = await get("/state");
  const up = !s.error;
  $("#live").textContent = up ? "" : "router unreachable";
  if (up) data.state = s;
  if (["overview", "agents", "live", "providers"].includes(page())) data.swarm = await get("/api/swarm");
  if (["race", "chat", "live"].includes(page())) data.race = await get("/api/race");
  if (page() === "pricing") data.pricing = await get("/api/pricing");
  if (page() === "bench" && !data.bench) data.bench = await get("/bench/latest/results.json");
  if (page() === "providers" && !data.replay) data.replay = await get("/api/replay");
  if (["providers", "under-the-hood"].includes(page())) { const c = await get("/api/provider-calls"); data.calls = Array.isArray(c) ? c : null; }
  if (page() === "live" && !data.replay) {
    data.replay = await get("/api/replay");
    if (sim.S && (data.replay.runs || []).length && !data.sample) startLive(); // real runs arrived: replay them
  }
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
<p class="lede">Jelly sits between your coding agent and the frontier model. It watches which kinds of task your agents repeat, and once a task type has ${N()} test-verified runs, it trains a small model you own on them and routes that task to it. Every run is still verified; a failure goes back to the frontier.</p>
<div class="cards">
  <div class="card"><b>${tt.length}</b><span>task types seen</span></div>
  <div class="card"><b>${verified}</b><span>verified runs</span></div>
  <div class="card"><b class="owned">${grads}</b><span>graduated to your model</span></div>
  <div class="card"><b class="owned">${owned}</b><span>runs served by your model</span></div>
  <div class="card"><b>${owned ? money(s.totals.saved_usd) : "n/a"}</b><span>${owned ? "saved vs frontier baseline (ledger)" : "saved: no owned runs in the ledger yet"}</span></div>
</div>
<div class="cols">
  <section><h2>Live activity</h2>${feed(events)}</section>
  <section><h2>Agents now</h2>${agents.length ? `<p>${agents.length} agents in <code>${esc(data.swarm.swarm_id)}</code>: ${["running", "passed", "failed", "queued"].map((st) => `${agents.filter((a) => a.status === st).length} ${st}`).join(" · ")}.</p><p><a href="/app/agents">See the agents →</a></p>` : empty("No swarm running. <code>graduate swarm --tasks 01,02,03 --agents 3</code> starts one.")}</section>
</div>`;
}

function agents() {
  const w = data.swarm;
  if (!w) return `<h1>Agents</h1><p class="lede">Loading /api/swarm…</p>`;
  const list = w.agents || [];
  const flags = (a) => `${a.a2a_read ? `<span class="flag">read a note</span>` : ""}${a.a2a_write ? `<span class="flag">left a note</span>` : ""}`;
  const notes = [...(w.a2a || [])].reverse();
  return `<h1>Agents</h1>
${w.error ? empty(esc(w.error)) : `<p class="muted"><code>${esc(w.swarm_id)}</code> · started ${esc((w.started || "").replace("T", " ").slice(0, 19))}Z · launcher ${esc(w.launcher)}</p>`}
${list.length ? `<div class="scroll"><table><thead><tr><th>Agent</th><th>Task</th><th>Task type</th><th>Status</th><th class="num">Exit</th><th class="num">Turns</th><th>Notes</th><th>Session</th></tr></thead><tbody>
${list.map((a) => `<tr><td><b>${esc(a.agent)}</b></td><td>${esc(a.task)}</td><td>${a.task_type ? `<code>${esc(a.task_type)}</code>` : `<span class="muted">not yet</span>`}</td><td>${stateTag(a.status)}</td><td class="num">${a.exit_code ?? "–"}</td><td class="num">${a.turns ?? "–"}</td><td>${flags(a)}</td><td><code class="muted">${esc((a.session_id || "–").slice(0, 13))}</code></td></tr>`).join("")}
</tbody></table></div>` : ""}
<h2>Agent-to-agent notes</h2>
${notes.length ? `<ul class="feed">${notes.map((e) => `<li><time>${time(e.ts)}</time><span><b>${(e.edges || []).includes("a2a-write") ? "wrote" : "read"}</b> <code>${esc(e.call)}</code><br><span class="muted">${esc(e.result)}</span></span></li>`).join("")}</ul>` : empty("No notes read or written yet.")}`;
}

function tasks() {
  const tt = types();
  if (!tt.length) return `<h1>Task types</h1>${empty("No task types yet: they appear after the first classified run.")}`;
  const approvable = (t) => ["READY", "PROBATION"].includes(t.state) && !data.readOnly;
  const off = data.readOnly ? ` title="${READ_ONLY}"` : "";
  return `<h1>Task types</h1>
<p class="lede">A task type is one kind of job your agents repeat, like fixing a failing test. Memorable sorts every run into a type. After ${N()} passing runs of a type, Jelly trains your own model on them, and from then on that type goes to your model; everything else stays on the big model.</p>
<p class="muted states-line">Learning (k of ${N()}) → Ready → Training → Graduated</p>
<div class="scroll"><table class="ttypes"><thead><tr><th>Task type</th><th>State</th><th>Progress</th><th>Consent</th><th>Big model per run</th><th>Your model per run</th><th></th></tr></thead><tbody>
${tt.map(([id, t]) => {
    const n = Math.min(t.verified_runs || 0, N());
    const cur = t.current, base = t.baseline;
    const r = data.reviews[id];
    const per = (x) => (x ? `${Math.round(x.turns * 10) / 10} turns · ${money(x.cost_usd)}` : `<span class="muted">–</span>`);
    const passing = t.verified_runs || 0, learning = t.state === "LEARNING";
    return `<tr><td class="tname" title="${esc(t.title || id)}"><b>${esc(t.title || id)}</b>${learning ? `<br><small class="muted">Only ${passing} passing run${passing === 1 ? "" : "s"} so far; it stays on the big model until ${N()} pass.</small>` : ""}</td>
<td>${stateTag(t.state)}</td>
<td><span class="pips">${Array.from({ length: N() }, (_, i) => `<i class="${i < n ? "on" : ""}"></i>`).join("")}</span>${t.verified_runs} verified · ${N()} needed${t.failed_runs ? ` <span class="muted">· ${t.failed_runs} failed</span>` : ""}</td>
<td>${t.consent ? "approved" : `<span class="muted">not given</span>`}</td>
<td>${per(base)}</td><td style="color:var(--owned)">${per(cur)}</td>
<td class="actions"><button class="btn" data-act="review" data-t="${esc(id)}">Review data</button>
${t.state === "READY" && !data.readOnly ? `<button class="btn owned" data-act="approve" data-t="${esc(id)}">Approve</button>` : ""}</td></tr>`;
  }).join("")}
</tbody></table></div>
${data.readOnly ? `<p class="msg muted">${READ_ONLY}</p>` : ""}
${data.drawer ? `<aside class="drawer" aria-label="Training data"><button class="btn close" data-act="close">Close</button><h2>${esc(data.drawer)}</h2>${reviewPanel(data.reviews[data.drawer])}</aside>` : ""}`;
}

function reviewPanel(r) {
  if (r.loading) return `<div class="review muted">Loading…</div>`;
  if (r.msg) return `<p class="msg${r.bad ? " err" : ""}">${esc(r.msg)}</p>`;
  return `<div class="review">${r.error ? `<p class="msg err">${esc(r.error)}</p>` : ""}
<p>${r.records ?? 0} runs${r.tokens != null ? `, ${num(r.tokens)} tokens` : ""}. Trains on: ${esc(r.destination || r.where || "n/a")}.</p>
${runsView(r.runs || (r.sample ? [r.sample] : []), r.records)}</div>`;
}

// One row per training run (session, task, turns, tokens); a row opens that run as a conversation. Nothing is clipped.
function runsView(runs, total) {
  if (!runs.length) return "";
  const text = (c) => (Array.isArray(c) ? c.map((x) => x.text || "").join("") : String(c ?? ""));
  const turn = (m) => {
    if (m.role === "system") return `<div class="turn sys"><b>system prompt</b> · ${text(m.content).length.toLocaleString()} chars</div>`;
    const calls = (m.tool_calls || []).map((t) => `<code>${esc(t.function.name)}(${esc(String(t.function.arguments).slice(0, 400))})</code>`).join("<br>");
    return `<div class="turn ${m.role}"><b>${m.role === "tool" ? "tool result" : m.role}</b><div>${esc(text(m.content))}${calls ? `<br>${calls}` : ""}</div></div>`;
  };
  return `${total && runs.length < total ? `<p class="muted">Showing ${runs.length} of ${total} runs.</p>` : ""}<div class="runs">${runs.map((rec, i) => {
    const md = rec.metadata || {}, msgs = rec.messages || [], chars = msgs.reduce((a, m) => a + text(m.content).length, 0);
    const task = (String(md.verify_command || "").match(/test_mod_(\d+)/) || [])[1];
    return `<details class="run"><summary><span>${i + 1}</span><code>${esc((md.session_id || "run").slice(0, 17))}</code><span>${task ? `task ${task}` : esc(md.task_type || "")}</span><span>${md.turns ?? msgs.filter((m) => m.role === "assistant").length} turns</span><span>~${num(chars / 4)} tokens</span></summary>${msgs.map(turn).join("")}</details>`;
  }).join("")}</div>`;
}

// The public link is view-only: every POST/DELETE answers 405. Remember that and disable Approve/Revoke.
const READ_ONLY = "View-only public demo: approving starts real training, so it is disabled here.";
data.readOnly = localStorage.getItem("graduate-read-only") === "1";

async function act(kind, t) {
  if (kind === "close") { data.drawer = null; return render(); }
  if (kind === "approve" && !confirm(`Train ${t} on its verified runs? This starts training now.`)) return;
  data.drawer = t; data.reviews[t] = { loading: true };
  render();
  const method = { review: "GET", approve: "POST", revoke: "DELETE" }[kind];
  const r = await get(`/api/consent/${encodeURIComponent(t)}`, { method });
  if (r.status === 405) { data.readOnly = true; localStorage.setItem("graduate-read-only", "1"); }
  if (kind === "review") data.reviews[t] = r;
  else data.reviews[t] = r.status === 405 ? { msg: READ_ONLY } : r.error ? { msg: r.error, bad: true } : { msg: kind === "approve" ? `Approved. Training started (${r.records} runs, log ${r.log}).` : "Consent revoked. Nothing will be trained." };
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
  // Streams once at recorded pace when the tab opens or a task is picked; no loop. Your model left, big model right.
  Object.assign(race, { key: p.owned.row.session_id, panes: [pane(p.owned), pane(p.frontier)], rescue: p.rescue, base: 0, since: performance.now() });
}

const elapsed = () => race.base + (performance.now() - race.since) * race.speed;
function setSpeed(x) { race.base = elapsed(); race.since = performance.now(); race.speed = x; tick(); }

const secsOf = (ms) => `${(ms / 1000).toFixed(1)}s`;

// A race pane: a terminal window streaming the recorded run's calls at their recorded pace, then its cost and time.
function paneHTML(p, t, side) {
  const r = p.row, done = t >= p.end, shown = p.steps.filter((s) => s.at <= t), mine = side === "owned";
  const river = String(r.model || "").startsWith("river://");
  const model = mine ? (river ? "Qwen3.5-9B · River" : "your model") : String(r.model || "big model").split("/").pop();
  const status = mine ? `Sending request to your model${river ? " on River" : ""}...` : `Sending request to ${esc(model)}. Waiting for first token...`;
  return `<header><i></i><i></i><i></i><b>${mine ? "YOUR MODEL" : "BIG MODEL"}</b></header>
<p class="cmd">$ graduate race ask ${mine ? "owned" : "frontier"}</p><p class="dim">${status}</p>
<div class="tbody">${shown.map((s) => `<div class="tl">${s.what}</div>`).join("")}${p.logged ? "" : `<div class="tl dim">no step-by-step record kept for this run</div>`}</div>
<footer>${done ? `<p>cost ${money(r.cost_usd || 0)}</p><p>completed in ${r.wall_secs}s · <span class="${r.exit_code === 0 ? "ok" : "bad"}">${r.exit_code === 0 ? "✓" : "✗"} ${esc(testFile(r))}</span></p>` : `<p class="dim">running… ${secsOf(t)}</p>`}</footer>
<span class="chip">${esc(model)}</span>`;
}

function verdictHTML([f, o]) {
  const F = f.row, O = o.row;
  if (O.exit_code !== 0) return `<p class="diff fail">Your model got this one wrong. The tests caught it${race.rescue ? " and it was re-run on the big model" : ""}. No win to claim here.</p>`;
  if (F.exit_code !== 0) return `<p class="diff">The big model failed this one; your model fixed it.</p>`;
  const x = F.output_tokens / (O.output_tokens || 1);
  const fewer = x >= 1.5 ? `wrote ${x.toFixed(0)}× less text` : x > 1 / 1.5 ? "wrote about as much text" : "wrote more text";
  const caveat = data.sample ? " (sample data)" : bigIsReal() ? "" : " The big model here is a stand-in, not OpenAI, so there is no real saving to claim yet.";
  return `<p class="diff">Both fixed it. Your model ${fewer} and cost ${money(O.cost_usd)} instead of ${money(F.cost_usd)}.${caveat}</p>`;
}
const bigIsReal = () => (data.race && data.race.big_model) === "api.openai.com";

function tick() {
  const box = document.getElementById("race");
  if (!box || !race.panes) return;
  const t = elapsed();
  race.panes.forEach((p, i) => {
    const el = box.children[i], html = paneHTML(p, t, i ? "frontier" : "owned");
    if (el.dataset.html !== html) { el.innerHTML = html; el.dataset.html = html; const tb = el.querySelector(".tbody, .turns"); if (tb) tb.scrollTop = 1e6; }
  });
  const v = document.getElementById("verdict"), html = race.panes.every((p) => t >= p.end) ? verdictHTML([race.panes[1], race.panes[0]]) : "";
  if (v.dataset.html !== html) { v.innerHTML = html; v.dataset.html = html; }
}
setInterval(tick, 100);

// "Task 05 · fix failing test · your model passed": the demo task's number, its kind, and how your model did.
function pairLabel(x) {
  const o = x.owned.row, nn = (String(o.prompt).match(/test_mod_(\d+)/) || [])[1];
  const kind = ((data.state.registry.task_types || {})[o.task_type] || {}).title || o.task_type || "task";
  const how = o.exit_code === 0 ? "your model passed" : x.rescue ? "handed to big model" : "your model failed";
  return `${nn ? `Task ${nn}` : "Task"} · ${kind.toLowerCase()} · ${how}${x.match === "task_type" ? " · same task type, different task" : ""}`;
}

// The pair on screen: the one picked, else the newest where your model passed, else the newest.
function currentPair(ps) {
  let p = ps.find((x) => x.owned.row.session_id === race.key);
  if (!p) startRace((p = ps.find((x) => x.owned.row.exit_code === 0) || ps[0]));
  return p;
}

function compare() {
  if (!data.race) return `<h1>Compare</h1><p class="lede">Loading the recorded runs…</p>`;
  if (data.race.error) return `<h1>Compare</h1>${empty(esc(data.race.error))}`;
  const ps = pairs();
  if (!ps.length) return `<h1>Compare</h1>${empty("No task has both a frontier run and a run on your model in the ledger yet. Once a task type graduates, its next run races here against a frontier run of the same task.")}`;
  const key = (x) => x.owned.row.session_id;
  const p = currentPair(ps), o = p.owned.row;
  return `<h1>Same task, side by side</h1>

<div class="race-bar"><select id="pair">${ps.map((x) => `<option value="${esc(key(x))}" ${x === p ? "selected" : ""}>${esc(pairLabel(x))}</option>`).join("")}</select>

<a href="/app/bench">Benchmark table →</a></div>
<div id="race" class="race stage"><section class="term owned"></section><section class="term frontier"></section></div><div id="verdict"></div>
<p class="muted prompt-line">${p.match === "task_type" ? `Same task type, different task. Yours: ${esc(o.prompt)} · Big model: ${esc(p.frontier.row.prompt)}` : `Task prompt: ${esc(o.prompt)}`}</p>`;
}

// /app/bench: `graduate bench`'s table (GET /bench/latest/results.json, the classic Compare's endpoint): the same tasks
// through each model, output tokens first; an arm without runs says n/a. Numbers as measured: no saving is inferred.
function bench() {
  const b = data.bench;
  if (!b) return `<h1>Benchmark</h1><p class="lede">Loading…</p>`;
  if (b.error || !b.arms) return `<h1>Benchmark</h1>${empty(`No benchmark yet: ${esc(b.error || "no results")} Run <code>graduate bench</code>.`)}`;
  const arms = [["frontier", "Big model"], ["small", "Small model"], ["owned", "Your model"]].filter(([k]) => b.arms[k]);
  const name = (a) => (String(a.model || "").startsWith("river://") ? "Qwen3.5-9B · River" : a.model || "");
  const cell = (a, k, f) => (a.runs > 0 && a[k] != null ? f(a[k], a) : `<span class="muted">${esc(a.note || "n/a")}</span>`);
  const row = (label, k, f, cls = "") => `<tr class="${cls}"><th>${label}</th>${arms.map(([id]) => `<td class="num">${cell(b.arms[id], k, f)}</td>`).join("")}</tr>`;
  const bud = b.budget || {};
  return `<h1>Benchmark</h1>
<p class="lede">The same demo tasks (${(b.tasks || []).map(esc).join(", ")}) through each model, from <code>graduate bench</code> at ${esc(String(b.started_at || "").slice(0, 16).replace("T", " "))}Z${bud.spent_usd != null ? `. Spent ${money(bud.spent_usd)} of a ${money(bud.cap_usd)} cap.` : "."}</p>
${benchTakeaway(b)}
<div class="scroll"><table><thead><tr><th>Per run (mean)</th>${arms.map(([id, l]) => `<th class="num">${l}<br><small class="muted">${esc(name(b.arms[id]))}</small></th>`).join("")}</tr></thead><tbody>
${row("Output tokens", "output_tokens", num, "lead")}
${row("Input tokens", "input_tokens", (v, a) => `${num(v)} <span class="muted">${Math.round(((a.cached_input_tokens || 0) / (v || 1)) * 100)}% cached</span>`)}
${row("Cost", "cost_usd", money)}
${row("Turns", "turns", (v) => Math.round(v * 10) / 10)}
${row("Wall time (median)", "wall_secs_p50", (v) => `${Math.round(v * 10) / 10}s`)}
${row("Tests pass", "passed", (v, a) => `${v} of ${a.runs}`)}
</tbody></table></div>
<p class="muted">Means over each model's runs. Cost is tokens × list prices. n/a: that model has no runs in this benchmark.</p>`;
}

// "What this shows": every number and ratio computed from the same results the table shows, so the two never disagree.
// A claim the results file does not carry (held-out tasks, big-model calls) is left out rather than asserted.
function benchTakeaway(b) {
  const f = b.arms.frontier, m = b.arms.small, o = b.arms.owned, ran = (a) => a && a.runs > 0;
  if (!ran(o) || !ran(f)) return "";
  const x = (p, q) => Math.round(p / q), n = (b.tasks || []).length, all = [f, m, o].filter(ran);
  const cheap = (a) => `${money(a.cost_usd)} on ${esc(a.model)} (${x(a.cost_usd, o.cost_usd)}× cheaper)`;
  const pct = Math.round((o.output_tokens / f.output_tokens - 1) * 100);
  const lines = [
    all.every((a) => a.passed === a.runs) ? `All ${all.length} models passed the tests on all ${n} tasks (${(b.tasks || []).map(esc).join(", ")}).` : `Tests passed: ${all.map((a) => `${esc(a.model.startsWith("river://") ? "your model" : a.model)} ${a.passed} of ${a.runs}`).join(", ")}.`,
    `Your model: ${money(o.cost_usd)} a task vs ${cheap(f)}${ran(m) ? ` and ${cheap(m)}; it beats just buying a cheaper model` : ""}.`,
    `Why: it learned the job, so it reads ${x(f.input_tokens, o.input_tokens)}× fewer input tokens (${num(o.input_tokens)} vs ${num(f.input_tokens)} a task)${o.turns && f.turns ? `, about ${num(o.input_tokens / o.turns)} per call instead of ${num(f.input_tokens / f.turns)}` : ""}.`,
  ];
  // Held out: stated only for the run docs/results.md describes, never inferred.
  if (b.bench_id === "bench-20260927T225656Z") lines.splice(1, 0, "In this run, tasks 09 and 10 were held out of your model's training data (docs/results.md).");
  const limits = `Limits: it wrote ${pct >= 0 ? `${pct}% more` : `${-pct}% fewer`} output tokens than ${esc(f.model)} and took ${Math.round(o.wall_secs_p50)} s vs ${Math.round(f.wall_secs_p50)} s; ${o.runs} runs per model; your model's cost is priced at list rates, not billed.`;
  return `<section class="panel takeaway"><h2>What this shows</h2>${lines.map((l) => `<p>${l}</p>`).join("")}<p class="muted">${limits}</p></section>`;
}

function activity() {
  const s = data.state;
  const trace = [...(s.trace || [])].reverse().slice(0, 500);
  return `<h1>Activity</h1>

<div class="cols">
<section><h2>Call trace</h2>${trace.length ? `<ul class="feed">${trace.map((e) => `<li><time>${time(e.ts)}</time><span><b>${esc(e.who)}</b> <code>${esc(e.call)}</code><br><span class="muted">${esc(e.result)}</span></span></li>`).join("")}</ul>` : empty("No calls traced yet.")}</section>
<section><h2>Terminal</h2>${(s.terminal || []).length ? `<pre class="term">${esc(s.terminal.join("\n"))}</pre>` : empty("Nothing in terminal.log yet.")}</section>
</div>`;
}

const PAGES = { live, overview: home, race: compare, tasks, agents, logs: activity, providers, pricing, "under-the-hood": underTheHood, setup , bench };
// One Activity page (the captain's merge): the architecture diagram on top, the call feed and terminal, then parts and files.
PAGES.activity = PAGES.logs = PAGES["under-the-hood"] = () => underTheHood().replace("<h1>Under the hood</h1>", "<h1>Activity</h1>");

function go(url) { history.pushState(null, "", url); render(); poll(); }

document.addEventListener("click", (e) => {
  const a = e.target.closest('a[href^="/app"]');
  if (a && !e.metaKey && !e.ctrlKey) { e.preventDefault(); go(a.getAttribute("href")); return; }
  const b = e.target.closest("button[data-act]");
  if (b) act(b.dataset.act, b.dataset.t);
  const r = e.target.closest("button[data-race]");
  if (r && r.dataset.race === "replay") { race.base = 0; race.since = performance.now(); tick(); }
  else if (r) setSpeed(Number(r.dataset.race));
});
document.addEventListener("change", (e) => {
  if (e.target.id === "pair") { startRace(pairs().find((x) => x.owned.row.session_id === e.target.value)); render(); }
});
window.addEventListener("popstate", () => { render(); poll(); });
get("/api/sample").then((r) => { data.sample = r.sample; $("#sample").hidden = !r.sample; });
poll();
setInterval(poll, 3000);
