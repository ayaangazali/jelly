// /app/providers: each outside service GRADUATE calls, lit by its real calls in /state's trace (last 100) and ledger.
// Loaded before app.js; uses its globals (data, esc, time, empty) at call time.
const PROVIDERS = [
  { id: "memorable", name: "Memorable", role: "recognises the kind of task from its prompt", hit: (e) => /Memorable/.test(e.who) },
  { id: "frontier", name: "Frontier model", role: "the big model: answers until a task type graduates, and reruns every failure", hit: (e) => e.who === "Router → OpenAI" },
  { id: "river", name: "River", role: "trains your small model (LoRA) and serves it", hit: (e) => /River/.test(e.who) },
  { id: "gbrain", name: "GBrain", role: "agents share notes: read one before a task, write one after a verified pass", hit: (e) => /GBrain/.test(e.who) },
];

function providerFacts() {
  const s = data.state, trace = allCalls(), ledger = s.ledger || [];
  const big = [...ledger].reverse().find((r) => r.routed_to === "frontier" && r.model && r.model !== "unknown");
  const out = {};
  for (const p of PROVIDERS) out[p.id] = { calls: trace.filter(p.hit), sessions: 0, name: p.name };
  if (big) out.frontier.name = bigName(big.model);
  out.frontier.sessions = ledger.filter((r) => r.routed_to === "frontier").length;
  out.river.sessions = ledger.filter((r) => String(r.model || "").startsWith("river://")).length;
  const launcher = data.swarm && data.swarm.launcher;
  return out;
}

function providers() {
  const one = location.pathname.split("/")[3];
  if (one) return providerPage(one);
  if (!document.getElementById("prov-css")) document.head.insertAdjacentHTML("beforeend", `<style id="prov-css">
.flow{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:12px 0 24px}
.flow .node{border:1px solid #3a4150;border-radius:8px;padding:8px 12px;opacity:.45;white-space:nowrap}
.flow .node.lit{opacity:1;border-color:var(--owned);box-shadow:0 0 0 1px var(--owned) inset}
.flow .node small{display:block;opacity:.75}
.flow .arrow{opacity:.5}
.prov{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}
.prov section{border:1px solid #3a4150;border-radius:10px;padding:14px 16px;min-width:0}
.prov section.lit{border-color:var(--owned)}
.prov h2{margin:0 0 4px}
.prov .feed li span{overflow-wrap:anywhere}
</style>`);
  const f = providerFacts();
  const n = (id) => f[id].calls.length;
  const node = (id, label, sub) => `<span class="node${n(id) || f[id].sessions ? " lit" : ""}">${esc(label)}<small>${esc(sub)}</small></span>`;
  const arrow = `<span class="arrow">→</span>`;
  const plain = (label, sub) => `<span class="node lit">${esc(label)}<small>${esc(sub)}</small></span>`;
  const reg = Object.values(data.state.registry.task_types || {});
  const owned = reg.find((t) => t.state === "GRADUATED" && t.model);
  return `<h1>Providers</h1>
<p class="lede">Every outside service Jelly calls, lit when it was really called. Counts come from the last 100 traced calls and the run ledger.</p>
<div class="flow">
${plain("Your agents", "OpenCode")}${arrow}${plain("Jelly router", "")}${arrow}${node("memorable", "Memorable", `${n("memorable")} calls`)}${arrow}
${node("river", "River · your model", `${f.river.sessions} sessions`)}<span class="arrow">or</span>${node("frontier", f.frontier.name, `${f.frontier.sessions} sessions`)}${arrow}${plain("Tests", "pass or fail decides")}${arrow}${node("gbrain", "GBrain", `${n("gbrain")} calls`)}
</div>
${owned ? `<p class="muted">Your model now: ${String(owned.model).startsWith("river://") ? "Qwen3.5-9B on River" : "Qwen2.5-Coder-0.5B on this machine"}</p>` : ""}
<div class="prov">${PROVIDERS.map((p) => {
    const x = f[p.id], calls = [...x.calls].reverse();
    const status = calls.length || x.sessions ? `<span class="state s-passed">used</span>` : `<span class="state">not called yet</span>`;
    return `<section class="${calls.length || x.sessions ? "lit" : ""}"><h2><a href="/app/providers/${p.id}">${esc(x.name)} →</a></h2>
<p class="muted">${esc(p.role)}</p>
<p>${status} ${calls.length} call${calls.length === 1 ? "" : "s"} traced${x.sessions ? ` · ${x.sessions} session${x.sessions === 1 ? "" : "s"}` : ""}${x.note ? ` · <span class="muted">${esc(x.note)}</span>` : ""}</p>
${calls.length ? `<ul class="feed">${calls.slice(0, 5).map((e) => `<li><time>${time(e.ts)}</time><span><b>${esc(e.who)}</b> <code>${esc(String(e.call).slice(0, 90))}</code><br><span class="muted">${esc(String(e.result).slice(0, 140))}</span></span></li>`).join("")}</ul>` : empty("No calls in the current trace.")}
</section>`;
  }).join("")}</div>`;
}

// One page per provider (/app/providers/<id>): a visual deep-dive from the real trace, ledger, registry and the served
// loss curve (GET /api/replay); nothing about a run is hard-coded.
const stat = (v, label) => `<div class="kpi"><b>${v}</b><span>${label}</span></div>`;
const feedOf = (calls) => calls.length ? `<ul class="feed pfeed">${calls.map((e, i) => `<li style="animation-delay:${i * 0.12}s"><time>${time(e.ts)}</time><span><code>${esc(String(e.call).slice(0, 110))}</code><br><span class="muted">${esc(String(e.result).slice(0, 140))}</span></span></li>`).join("")}</ul>` : empty("No calls traced yet.");

function providerPage(id) {
  const s = data.state, trace = allCalls(), ledger = s.ledger || [], reg = s.registry.task_types || {};
  const back = `<p><a href="/app/providers">← All providers</a></p>`;
  const page = (name, role, status, body) => `${back}<div class="pdeep"><header><h1>${name}</h1><span class="state ${status[0]}">${status[1]}</span></header><p class="muted">${role}</p>${body}</div>`;
  if (id === "river") {
    const g = Object.entries(reg).find(([, t]) => String(t.model || "").startsWith("river://")), served = ledger.filter((r) => r.routed_to === "owned");
    const curve = g && data.replay && data.replay.loss && data.replay.loss[g[0]], c = (curve && curve.steps) || [];
    const w = 600, h = 200, max = Math.max(...c.map((x) => x.loss), 0.01), pts = c.map((x, i) => `${(i / Math.max(c.length - 1, 1)) * w},${h - (x.loss / max) * h}`).join(" ");
    return page("River", "trains your small model with LoRA and serves it", g ? ["s-passed", "live"] : ["", "not trained here yet"], `
<div class="kpis">${stat("Qwen3.5-9B", "base model")}${stat(c.length || "–", `training steps${g ? ` on ${g[1].trained_on_runs || "?"} real runs` : ""}`)}${stat(c.length ? `${c[0].loss.toFixed(3)} → ${c[c.length - 1].loss.toFixed(3)}` : "–", "loss")}${stat(c.length ? `${Math.round(c[c.length - 1].secs || 0)} s` : "–", "training time")}${stat(served.length, "runs served")}</div>
<section class="panel pviz"><h2>Training loss${c.length ? ` · ${c.length} steps` : ""}</h2>${c.length ? `<svg viewBox="-10 -10 ${w + 20} ${h + 30}" class="loss"><polyline points="${pts}" pathLength="100"/>${c.map((x, i) => `<circle cx="${(i / Math.max(c.length - 1, 1)) * w}" cy="${h - (x.loss / max) * h}" r="4" style="animation-delay:${0.1 * i}s"/>`).join("")}<text x="0" y="${h + 18}">step 1</text><text x="${w}" y="${h + 18}" text-anchor="end">step ${c.length}</text></svg>` : empty("No training log in this directory yet.")}</section>
<section class="panel pviz"><h2>Runs served by your model</h2><div class="serve">${served.slice(-6).map((r) => `<div class="srv"><b>Task ${esc((String(r.verify_command || r.prompt || "").match(/test_mod_(\d+)/) || [])[1] || "?")}</b><span>${r.turns} turns · ${money(r.cost_usd || 0)}</span><em class="${r.exit_code === 0 ? "" : "bad"}">${r.exit_code === 0 ? "✓ tests passed" : "✗ re-run on the big model"}</em></div>`).join("") || empty("No runs served yet.")}</div></section>
${g ? `<p class="muted">Model <code>${esc(g[1].model)}</code></p>` : ""}`);
  }
  if (id === "memorable") {
    const ingest = trace.filter((e) => /Memorable/.test(e.who) && /ingest/.test(e.call)), recall = trace.filter((e) => /Memorable/.test(e.who) && /recall/.test(e.call));
    return page("Memorable", "classifies each task by recalling past procedures", ingest.length || recall.length ? ["s-passed", "live"] : ["", "not called yet"], `
<div class="kpis">${stat(ingest.length, "procedures ingested · recent traced calls")}${stat(recall.length, "recall calls")}</div>
<section class="panel pviz"><h2>Procedures learned</h2><div class="procs">${ingest.map((e, i) => `<div class="proc" style="animation-delay:${i * 0.15}s"><b>${esc(String(e.result).split(" · ")[0].replace(/^procedures\/\w+-/, ""))}</b><small>${esc(String(e.result).split(" · ").slice(1).join(" · "))}</small></div>`).join("") || empty("No procedures ingested yet.")}</div></section>
<section class="panel pviz"><h2>Recall: a new task → its kind</h2>${recall.length ? recall.map((e) => `<div class="recall"><code>${esc(String(e.call).slice(0, 90))}</code><i>→</i><b>${esc(String(e.result).slice(0, 90))}</b></div>`).join("") : empty("No recall traced in this window.")}</section>
<section class="panel pviz"><h2>Where procedures live</h2><ul class="howto"><li>Memorable keeps its 23 procedures in its own encrypted local store. We tried migrating them to GBrain with Memorable's native integration (<code>memorable init gbrain</code>, then GBrain's <code>integrations.memorable</code> switch); GBrain refused it (<code>writer_coordinator_required</code>): a new writer on the shared brain needs a deliberate ownership change by its operator, not made at the freeze. So the migration was rolled back at once and nothing moved. After the rollback a real recall on task 09 scored 0.727. Memorable and GBrain run side by side.</li></ul></section>`);
  }
  if (id === "gbrain") {
    const calls = trace.filter((e) => /GBrain/.test(e.who)), writes = calls.filter((e) => /write|put/.test(e.call)), reads = calls.filter((e) => /read|get/.test(e.call));
    return page("GBrain", "agents share what worked: read a note before a task, write one after a verified pass", calls.length ? ["s-passed", "used"] : ["", "not called yet"], `
<div class="kpis">${stat(writes.length, "notes written")}${stat(reads.length, "notes read")}${stat(calls.length - writes.length - reads.length, "other pages")}</div>
<section class="panel pviz"><h2>How Jelly uses GBrain</h2><ul class="howto">
<li><b>One feature:</b> reading and writing pages, locally on this machine with GBrain's built-in database.</li>
<li><b>Agents share notes:</b> OpenCode agents connect to the local GBrain as an MCP tool. Before a task an agent reads the page <code>a2a-&lt;task type&gt;</code> (fixes that worked before); after its tests pass it writes its own page, e.g. <code>a2a-fix-failing-test/sess-…</code>, with the files, the fix, the test command, turns and cost. Jelly's runner also appends each verified fix to <code>a2a-&lt;task type&gt;</code>, keeping the newest 10.</li>
<li><b>Graduation record:</b> on every graduation Jelly writes the page <code>graduated</code>, listing each graduated task type, its River model, run count and date.</li>
<li><b>Not used:</b> GBrain search and embeddings, and hosted access.</li>
<li><b>Memorable's store, not migrated:</b> Memorable keeps its 23 procedures in its own encrypted local store. We tried migrating them to GBrain with Memorable's native integration (<code>memorable init gbrain</code>, then GBrain's <code>integrations.memorable</code> switch); GBrain refused it (<code>writer_coordinator_required</code>): a new writer on the shared brain needs a deliberate ownership change by its operator, not made at the freeze. So the migration was rolled back at once and nothing moved. After the rollback a real recall on task 09 scored 0.727. Memorable and GBrain run side by side.</li>
</ul></section>
<section class="panel pviz"><h2>Notes between agents</h2><div class="notes">${calls.map((e, i) => `<div class="gnote ${/write|put/.test(e.call) ? "w" : "r"}" style="animation-delay:${i * 0.2}s"><b>${/write|put/.test(e.call) ? "wrote" : /read|get/.test(e.call) ? "read" : "page"}</b><code>${esc(String(e.call).slice(0, 70))}</code><small>${esc(String(e.result).slice(0, 90))}</small></div>`).join("") || empty("No notes yet.")}</div></section>`);
  }
  if (id === "frontier") {
    const rows = ledger.filter((r) => r.routed_to === "frontier"), top = Math.max(...rows.map((r) => r.cost_usd || 0), 0.0001);
    const model = (rows[rows.length - 1] || {}).model || "big model", esc_ = rows.filter((r) => r.escalated_from).length;
    const earlier = [...new Set(rows.map((r) => r.model))].filter((m) => m && m !== model).map((m) => `${bigName(m)}, ${rows.filter((r) => r.model === m).length} runs`);
    const sum = (k) => rows.reduce((a, r) => a + (r[k] || 0), 0);
    return page(`Big model: ${esc(bigName(model))}`, `the big model: answers until a task type graduates, and re-runs every failure${earlier.length ? ` · earlier: ${esc(earlier.join("; "))}` : ""}`, rows.length ? ["s-passed", "used"] : ["", "not called yet"], `
<div class="kpis">${stat(rows.length, "sessions")}${stat(money(sum("cost_usd")), "spent")}${stat(num(sum("output_tokens")), "tokens written")}${stat(rows.length ? (sum("turns") / rows.length).toFixed(1) : "–", "turns per session")}${stat(esc_, "re-runs after your model failed")}</div>
<section class="panel pviz"><h2>Cost per session</h2><div class="bars">${rows.map((r, i) => `<div class="barrow"><code>${esc(r.session_id.slice(0, 12))}</code><div class="bar"><i style="width:${((r.cost_usd || 0) / top) * 100}%;animation-delay:${i * 0.1}s"></i></div><b>${money(r.cost_usd || 0)}</b><span class="${r.exit_code === 0 ? "ok" : "bad"}">${r.exit_code === 0 ? "✓" : "✗"}</span></div>`).join("")}</div></section>`);
  }
  return `${back}${empty("No such provider.")}`;
}

// The whole trace's provider calls (GET /api/provider-calls), else /state's last 100 until the router has that endpoint.
const allCalls = () => (Array.isArray(data.calls) ? data.calls : data.state.trace || []);
const bigName = (m) => (/claude/i.test(m) ? "Anthropic Claude Haiku 4.5" : /gpt|openai/i.test(m) ? `OpenAI ${m}` : m);
