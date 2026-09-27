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
${calls.length ? `<ul class="feed">${calls.map((e) => `<li><time>${time(e.ts)}</time><span><b>${esc(e.who)}</b> <code>${esc(String(e.call).slice(0, 90))}</code><br><span class="muted">${esc(String(e.result).slice(0, 140))}</span></span></li>`).join("")}</ul>` : empty("No calls in the current trace.")}
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
<section class="panel pviz"><h2>Runs served by your model</h2><div class="serve">${served.map((r) => `<div class="srv"><b>Task ${esc((String(r.verify_command || r.prompt || "").match(/test_mod_(\d+)/) || [])[1] || "?")}</b><span>${r.turns} turns · ${money(r.cost_usd || 0)}</span><em class="${r.exit_code === 0 ? "" : "bad"}">${r.exit_code === 0 ? "✓ tests passed" : "✗ re-run on the big model"}</em></div>`).join("") || empty("No runs served yet.")}</div></section>
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
<section class="panel pviz"><h2>Notes between agents</h2>${notesDiagram(calls)}<details ${notesRawOpen ? "open" : ""} ontoggle="notesRawOpen = this.open"><summary>Raw calls (${calls.length})</summary>${feedOf([...calls].reverse())}</details></section>`);
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

// The notes timeline: time runs left to right, one column per agent run (order of its first a2a call). The band on top
// is the GBrain page and how many fixes it held after each run; ↓ the run read the page before starting, ↑ its verified
// fix was appended. A write that fell back to the local notes file (GBrain busy) is a small muted marker on its column.
// The runner's calls carry the run's session id; an unsessioned one folds into the run before it.
let notesRawOpen = false; // the raw-call list stays open across the timer's re-renders
const NOTES_KEEP = 10; // graduate/a2a.py KEEP: the page keeps the newest 10 fixes
function notesDiagram(calls) {
  const is = (e, k) => (e.edges || []).includes(k);
  const ev = calls.filter((e) => is(e, "a2a-read") || is(e, "a2a-write")).sort((a, b) => String(a.ts).localeCompare(String(b.ts)));
  if (!ev.length) return empty("No notes read or written yet.");
  const pageOf = (e) => ((String(e.call).match(/a2a[-/][\w-]+/) || [])[0] || "a2a notes").replace("a2a/", "a2a-");
  const tally = {};
  ev.forEach((e) => { tally[pageOf(e)] = (tally[pageOf(e)] || 0) + 1; });
  const page = Object.keys(tally).sort((a, b) => tally[b] - tally[a])[0];
  const fell = (e) => /shared notes file/.test(e.result), count = (e) => +((String(e.result).match(/(\d+) procedures/) || [])[1] ?? NaN);
  const runs = [];
  ev.forEach((e) => {
    let r = e.session_id ? runs.find((x) => x.id === e.session_id) : runs[runs.length - 1];
    if (!r) runs.push((r = { id: e.session_id, ev: [] }));
    r.ev.push(e);
  });
  const led = data.state.ledger || [], sw = (data.swarm && data.swarm.agents) || [];
  const task = (id) => {
    const m = String((led.find((x) => x.session_id === id) || {}).verify_command || "").match(/test_mod_(\d+)/);
    return m ? m[1] : (sw.find((a) => a.session_id === id) || {}).task || "";
  };
  const COL = 72, PAD = 16, H = 250, W = Math.max(PAD * 2 + runs.length * COL, 560), fixes = (k) => `${k} fix${k === 1 ? "" : "es"}`;
  let held = 0;
  const cols = runs.map((r, i) => {
    const cx = PAD + COL * i + COL / 2, on = r.ev.filter((e) => pageOf(e) === page), t = task(r.id), before = held;
    const read = on.find((e) => is(e, "a2a-read")), wrote = on.filter((e) => is(e, "a2a-write") && !fell(e));
    const local = on.filter((e) => is(e, "a2a-write") && fell(e)), other = r.ev.filter((e) => pageOf(e) !== page && is(e, "a2a-write"));
    on.filter((e) => !fell(e) && !isNaN(count(e))).forEach((e) => { held = count(e); });
    const busy = local.some((e) => /busy/.test(e.result)) ? "GBrain busy" : "GBrain not installed";
    const tip = [`run ${i + 1}${t ? ` · task ${t}` : ""}${r.id ? ` · ${r.id}` : ""}`,
      ...r.ev.map((e) => `${(e.ts || "").slice(11, 19)} ${is(e, "a2a-read") ? "read" : "wrote"} ${pageOf(e)}: ${e.result}`)].join("\n");
    const band = held ? `<rect class="nfill" x="${cx - COL / 2 + 1}" y="${80 - (26 * Math.min(held, NOTES_KEEP)) / NOTES_KEEP}" width="${COL - 2}" height="${(26 * Math.min(held, NOTES_KEEP)) / NOTES_KEEP}"/>${held !== before ? `<text class="ncount" x="${cx}" y="48">${fixes(held)}</text>` : ""}` : "";
    const wLabel = wrote.length ? `<text class="nw" x="${cx}" y="220">wrote 1 fix</text>` : local.length ? `<text class="nm" x="${cx}" y="220">local file</text>` : other.length ? `<text class="nm" x="${cx}" y="220">other page</text>` : "";
    return `<g class="ncol"><title>${esc(tip)}</title><rect class="nhit" x="${cx - COL / 2}" y="84" width="${COL}" height="${H - 84}"/>${band}
${read ? `<path class="${fell(read) ? "nm" : "nr"}" d="M${cx - 12},88 V140" marker-end="url(#ntl-${fell(read) ? "m" : "r"})"/><text class="${fell(read) ? "nm" : "nr"}" x="${cx}" y="204">read ${isNaN(count(read)) ? "" : count(read)}</text>` : ""}
${wrote.length ? `<path class="nw" d="M${cx + 12},142 V90" marker-end="url(#ntl-w)"/>` : ""}${local.length ? `<circle class="nbusy" cx="${cx + 12}" cy="115" r="6"><title>saved to local notes file, ${busy}</title></circle>` : ""}
<rect class="nbox" x="${cx - 30}" y="146" width="60" height="40" rx="6"/><text class="nrun" x="${cx}" y="163">run ${i + 1}</text>${t ? `<text class="nsub" x="${cx}" y="179">task ${esc(t)}</text>` : ""}
${wLabel}<text class="nsub" x="${cx}" y="240">${esc((r.ev[0].ts || "").slice(11, 16))}${i ? "" : " UTC"}</text></g>`;
  });
  const mk = (id, c) => `<marker id="ntl-${id}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="${c}"/></marker>`;
  return `<div class="ntl-wrap"><svg class="ntl" viewBox="0 0 ${W} ${H}" style="min-width:${W}px;max-width:${Math.round(W * 1.4)}px" role="img" aria-label="Timeline of agent runs reading and writing the GBrain page ${esc(page)}">
<defs>${mk("r", "#9A9DFF")}${mk("w", "#F5B94A")}${mk("m", "#8A94A8")}</defs>
<text class="ntitle" x="${PAD}" y="16">GBrain page <tspan>${esc(page)}</tspan> · keeps the newest ${NOTES_KEEP} fixes · hover a run for its session</text>
<rect class="nband" x="${PAD}" y="24" width="${runs.length * COL}" height="58" rx="6"/>${cols.join("")}</svg></div>
<p class="muted notes-cap"><b class="nr">↓ read</b> at start (fixes seen) · <b class="nw">↑ wrote 1 fix</b>, tests passed${ev.some(fell) ? ` · <b class="nm">◌</b> local file, GBrain busy` : ""}</p>`;
}
