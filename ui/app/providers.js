// /app/providers: each outside service GRADUATE calls, lit by its real calls in /state's trace (last 100) and ledger.
// Loaded before app.js; uses its globals (data, esc, time, empty) at call time.
const PROVIDERS = [
  { id: "memorable", name: "Memorable", role: "recognises the kind of task from its prompt", hit: (e) => /Memorable/.test(e.who) },
  { id: "frontier", name: "Frontier model", role: "the big model: answers until a task type graduates, and reruns every failure", hit: (e) => e.who === "Router → OpenAI" },
  { id: "river", name: "River", role: "trains your small model (LoRA) and serves it", hit: (e) => /River/.test(e.who) },
  { id: "gbrain", name: "GBrain", role: "agents share notes: read one before a task, write one after a verified pass", hit: (e) => /GBrain/.test(e.who) },
  { id: "superset", name: "Superset", role: "launches many agents in parallel", hit: (e) => /Superset/.test(`${e.who} ${e.result}`) },
];

function providerFacts() {
  const s = data.state, trace = s.trace || [], ledger = s.ledger || [];
  const big = [...ledger].reverse().find((r) => r.routed_to === "frontier" && r.model && r.model !== "unknown");
  const out = {};
  for (const p of PROVIDERS) out[p.id] = { calls: trace.filter(p.hit), sessions: 0, name: p.name };
  if (big) out.frontier.name = `${/claude/i.test(big.model) ? "Anthropic" : "OpenAI"} · ${big.model}`;
  out.frontier.sessions = ledger.filter((r) => r.routed_to === "frontier").length;
  out.river.sessions = ledger.filter((r) => String(r.model || "").startsWith("river://")).length;
  const launcher = data.swarm && data.swarm.launcher;
  if (launcher === "superset") out.superset.sessions = (data.swarm.agents || []).length;
  out.superset.note = launcher && launcher !== "superset" ? `the last swarm used the ${launcher} launcher, not Superset` : "";
  return out;
}

function providers() {
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
<p class="lede">Every outside service GRADUATE calls, lit when it was really called. Counts come from the last 100 traced calls and the run ledger.</p>
<div class="flow">
${f.superset.sessions ? node("superset", "Superset", `${f.superset.sessions} agents launched`) + arrow : ""}${plain("Your agents", "OpenCode")}${arrow}${plain("GRADUATE router", "")}${arrow}${node("memorable", "Memorable", `${n("memorable")} calls`)}${arrow}
${node("river", "River · your model", `${f.river.sessions} sessions`)}<span class="arrow">or</span>${node("frontier", f.frontier.name, `${f.frontier.sessions} sessions`)}${arrow}${plain("Tests", "pass or fail decides")}${arrow}${node("gbrain", "GBrain", `${n("gbrain")} calls`)}
</div>
${owned ? `<p class="muted">Your model now: <code>${esc(owned.model)}</code> ${String(owned.model).startsWith("river://") ? "(on River)" : "(on this machine, not River)"}</p>` : ""}
<div class="prov">${PROVIDERS.map((p) => {
    const x = f[p.id], calls = [...x.calls].reverse();
    const status = calls.length || x.sessions ? `<span class="state s-passed">used</span>` : `<span class="state">not called yet</span>`;
    return `<section class="${calls.length || x.sessions ? "lit" : ""}"><h2>${esc(x.name)}</h2>
<p class="muted">${esc(p.role)}</p>
<p>${status} ${calls.length} call${calls.length === 1 ? "" : "s"} traced${x.sessions ? ` · ${x.sessions} session${x.sessions === 1 ? "" : "s"}` : ""}${x.note ? ` · <span class="muted">${esc(x.note)}</span>` : ""}</p>
${calls.length ? `<ul class="feed">${calls.slice(0, 5).map((e) => `<li><time>${time(e.ts)}</time><span><b>${esc(e.who)}</b> <code>${esc(String(e.call).slice(0, 90))}</code><br><span class="muted">${esc(String(e.result).slice(0, 140))}</span></span></li>`).join("")}</ul>` : empty("No calls in the current trace.")}
</section>`;
  }).join("")}</div>`;
}
