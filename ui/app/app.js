// GRADUATE app (/app): one page per job, all from the live APIs. Nothing here computes a win the ledger doesn't show.
const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
const time = (ts) => esc((ts || "").slice(11, 19));
const money = (v) => `$${Number(v).toFixed(v < 1 ? 4 : 2)}`;
const num = (v) => Math.round(v).toLocaleString();
const data = { state: null, swarm: null, bench: null, reviews: {} };

async function get(url, init) {
  try {
    const r = await fetch(url, { cache: "no-store", ...init });
    const body = await r.json().catch(() => ({ error: `${url} answered ${r.status}.` }));
    return r.ok ? body : { error: body.error || `${url} answered ${r.status}.`, ...body };
  } catch {
    return { error: `${url} isn't reachable.` };
  }
}

const page = () => (location.hash.split("/")[1] || "home");

function render() {
  const p = PAGES[page()] ? page() : "home";
  document.querySelectorAll("nav.side [data-nav]").forEach((a) => a.dataset.nav === p ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"));
  const html = data.state ? PAGES[p]() : `<p class="lede">Loading /state…</p>`;
  if ($("#view").dataset.html !== html) { $("#view").innerHTML = html; $("#view").dataset.html = html; }
}

async function poll() {
  const s = await get("/state");
  const up = !s.error;
  $("#live").innerHTML = `<span class="dot${up ? " on" : ""}"></span> ${up ? "live · updates every 3s" : "router unreachable"}`;
  if (up) data.state = s;
  if (["home", "agents"].includes(page())) data.swarm = await get("/api/swarm");
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

function compare() {
  const b = data.bench;
  if (!b) { data.bench = { loading: true }; get("/bench/latest/results.json").then((x) => { data.bench = x; render(); }); }
  if (!b || b.loading) return `<h1>Compare</h1><p class="lede">Loading the bench…</p>`;
  if (b.error) return `<h1>Compare</h1>${empty(`No bench results yet: ${esc(b.error)} Run <code>graduate bench</code> (it prints its cost estimate and asks first).`)}`;
  const arms = [["frontier", "Frontier"], ["small", "Small model"], ["owned", "Your model"]].filter(([k]) => b.arms[k]);
  const row = (label, key, fmt, cls = "") => `<tr class="${cls}"><th>${label}</th>${arms.map(([k]) => {
    const a = b.arms[k];
    return `<td class="num">${a.runs > 0 && a[key] != null ? fmt(a[key], a) : `<span class="muted">${esc(a.note || "n/a")}</span>`}</td>`;
  }).join("")}</tr>`;
  return `<h1>Compare</h1>
<p class="lede">The same demo tasks (${b.tasks.map(esc).join(", ")}) through each model, from <code>graduate bench</code> at ${esc(b.started_at.slice(0, 16).replace("T", " "))}Z on <code>${esc(b.git_sha)}</code>. Spent ${money(b.budget.spent_usd)} of a ${money(b.budget.cap_usd)} cap.</p>
<table><thead><tr><th>Per run (mean)</th>${arms.map(([k, l]) => `<th class="num">${l}<br><small class="muted">${esc((b.arms[k].model || "").split("/").pop())}</small></th>`).join("")}</tr></thead><tbody>
${row("Output tokens", "output_tokens", num, "lead")}
${row("Input tokens", "input_tokens", (v, a) => `${num(v)} <span class="muted">${Math.round((a.cached_input_tokens / (v || 1)) * 100)}% cached</span>`)}
${row("Cost <small>est.</small>", "cost_usd", money)}
${row("Turns", "turns", (v) => v)}
${row("Wall time <small>median</small>", "wall_secs_p50", (v) => `${v}s`)}
${row("Tests pass", "passed", (v, a) => `${v} of ${a.runs}`)}
</tbody></table>
<p class="muted">Means over each arm's runs. Cost is tokens × list prices, frontier with prompt caching on. n/a: that arm has no real runs.</p>`;
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
});
window.addEventListener("hashchange", () => { if (page() === "compare") data.bench = null; poll(); });
get("/api/sample").then((r) => { $("#sample").hidden = !r.sample; });
poll();
setInterval(poll, 3000);
