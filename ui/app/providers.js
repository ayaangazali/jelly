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

// One page per provider (/app/providers/<id>): a visual deep-dive from the real trace, ledger and registry. River's
// training and serving numbers are the recorded run in docs/results.md § River, quoted there, since River's SDK
// keeps no log in this directory.
const RIVER = {
  loss: [0.261, 0.181, 0.171, 0.176, 0.152, 0.121, 0.203, 0.135, 0.059, 0.079, 0.094, 0.071, 0.065, 0.081, 0.093, 0.073, 0.024, 0.031, 0.054, 0.032, 0.038, 0.043, 0.067, 0.030],
  serve: [["07", "repeat", "7 of 7 calls on River", "exit 0 on River alone"], ["09", "held out", "8 of 8 calls on River, 0 big-model calls", "exit 0 on River alone"]],
};
const stat = (v, label) => `<div class="kpi"><b>${v}</b><span>${label}</span></div>`;
const feedOf = (calls) => calls.length ? `<ul class="feed pfeed">${calls.map((e, i) => `<li style="animation-delay:${i * 0.12}s"><time>${time(e.ts)}</time><span><code>${esc(String(e.call).slice(0, 110))}</code><br><span class="muted">${esc(String(e.result).slice(0, 140))}</span></span></li>`).join("")}</ul>` : empty("No calls traced yet.");

function providerPage(id) {
  const s = data.state, trace = allCalls(), ledger = s.ledger || [], reg = s.registry.task_types || {};
  const back = `<p><a href="/app/providers">← All providers</a></p>`;
  const page = (name, role, status, body) => `${back}<div class="pdeep"><header><h1>${name}</h1><span class="state ${status[0]}">${status[1]}</span></header><p class="muted">${role}</p>${body}</div>`;
  if (id === "river") {
    const g = Object.entries(reg).find(([, t]) => String(t.model || "").startsWith("river://")), served = ledger.filter((r) => String(r.model || "").startsWith("river://"));
    const w = 600, h = 200, max = 0.3, pts = RIVER.loss.map((l, i) => `${(i / 23) * w},${h - (l / max) * h}`).join(" ");
    return page("River", "trains your small model with LoRA and serves it", ["s-passed", "live"], `
<div class="kpis">${stat("Qwen3.5-9B", "base model · LoRA rank 16")}${stat("24", "training steps on 8 real runs")}${stat("0.261 → 0.030", "loss")}${stat("122 s", "start to checkpoint")}${stat(served.length, "sessions served here")}</div>
<section class="panel pviz"><h2>Training loss · 24 steps</h2><svg viewBox="-10 -10 ${w + 20} ${h + 30}" class="loss"><polyline points="${pts}" pathLength="100"/>${RIVER.loss.map((l, i) => `<circle cx="${(i / 23) * w}" cy="${h - (l / max) * h}" r="4" style="animation-delay:${0.1 * i}s"/>`).join("")}<text x="0" y="${h + 18}">step 1</text><text x="${w}" y="${h + 18}" text-anchor="end">step 24</text></svg></section>
<section class="panel pviz"><h2>Served through the router</h2><div class="serve">${RIVER.serve.map(([st, kind, calls, res], i) => `<div class="srv" style="animation-delay:${0.4 + i * 0.5}s"><b>Task ${st}</b><span>${kind}</span><span>${calls}</span><em>✓ ${res}</em></div>`).join("")}</div></section>
<p class="muted">Checkpoint <code>${esc(g ? g[1].model : "river://…/fix-failing-test-v1")}</code>. Loss, time and serving results: the recorded run in docs/results.md § River.</p>`);
  }
  if (id === "memorable") {
    const ingest = trace.filter((e) => /Memorable/.test(e.who) && /ingest/.test(e.call)), recall = trace.filter((e) => /Memorable/.test(e.who) && /recall/.test(e.call));
    return page("Memorable", "classifies each task by recalling past procedures", ingest.length || recall.length ? ["s-passed", "live"] : ["", "not called yet"], `
<div class="kpis">${stat(ingest.length, "procedures ingested · recent traced calls")}${stat(recall.length, "recall calls")}</div>
<section class="panel pviz"><h2>Procedures learned</h2><div class="procs">${ingest.map((e, i) => `<div class="proc" style="animation-delay:${i * 0.15}s"><b>${esc(String(e.result).split(" · ")[0].replace(/^procedures\/\w+-/, ""))}</b><small>${esc(String(e.result).split(" · ").slice(1).join(" · "))}</small></div>`).join("") || empty("No procedures ingested yet.")}</div></section>
<section class="panel pviz"><h2>Recall: a new task → its kind</h2>${recall.length ? recall.map((e) => `<div class="recall"><code>${esc(String(e.call).slice(0, 90))}</code><i>→</i><b>${esc(String(e.result).slice(0, 90))}</b></div>`).join("") : empty("No recall traced in this window.")}</section>`);
  }
  if (id === "gbrain") {
    const calls = trace.filter((e) => /GBrain/.test(e.who)), writes = calls.filter((e) => /write|put/.test(e.call)), reads = calls.filter((e) => /read|get/.test(e.call));
    return page("GBrain", "agents share what worked: read a note before a task, write one after a verified pass", calls.length ? ["s-passed", "used"] : ["", "not called yet"], `
<div class="kpis">${stat(writes.length, "notes written")}${stat(reads.length, "notes read")}${stat(calls.length - writes.length - reads.length, "other pages")}</div>
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
