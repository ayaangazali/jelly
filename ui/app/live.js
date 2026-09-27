// /app (Live): the showcase. One loop drives every panel at once: requests flow through the router graph, the tests
// light green or red, the log streams, counters and savings tick, a task type fills its ring to N, trains (its real
// loss curve when there is one) and graduates, agents pass notes, and the two models race.
// With real runs in this directory (GET /api/replay, not sample mode) it replays them in recorded order, gaps scaled
// by a stated speed-up, with their real tokens, cost, tests and tool calls: tagged "recorded real run". Without them
// it runs a scripted timeline seeded from the APIs' shapes: tagged "demo data". Uses app.js's globals at call time.
const SPONSORS = [
  ["openai", "OpenAI", "the big model when credited · no credit today", "off"],
  ["river", "River", "trains and serves your model", "off"],
  ["memorable", "Memorable", "classifies each task by recalling past procedures learned from verified runs", "on"],
  ["gbrain", "GBrain", "agents share notes", "off"],
];
const NODES = { agent: [100, 210], grad: [360, 210], big: [640, 95], yours: [640, 325], tests: [900, 210] };
const EDGES = { // straight lines, node edge to node edge; none cross
  in: "M 180 210 L 280 210",
  big: "M 440 195 L 560 105",
  yours: "M 440 225 L 560 315",
  bigOut: "M 720 105 L 820 195",
  yoursOut: "M 720 315 L 820 225",
};
const sim = { on: false, last: 0, t: 0, next: 0, dots: [], tokens: 0, cost: 0, runs: 0, passed: 0, yours: 0, shown: { tokens: 0, cost: 0 }, ring: 0, lanes: [], logs: 0, raceT: 0 };

function live() {
  const svg = `<svg class="graph" viewBox="10 50 980 320" preserveAspectRatio="xMidYMid meet" aria-label="How a request flows">
${Object.entries(EDGES).map(([k, d]) => `<path id="e-${k}" class="edge ${k.startsWith("yours") ? "mine" : ""}" d="${d}"/>`).join("")}
${node("agent", "Coding agents", "send tasks")}${node("grad", "Jelly router", "records · checks", "hub")}
${node("big", "Big model", "pay per token")}${node("yours", "Your model", "trained on your runs", "mine")}${node("tests", "Unit tests", "the task's own tests", "tests")}
<g id="dots"></g></svg>`;
  return `<div id="live-root" class="live">
<p id="yours-line"></p>
<header class="live-top">
<div class="kpis"><div class="kpi save"><b id="k-saved">$0.00</b><span id="k-saved-l">saved vs big model</span></div>${kpi("k-tokens", "tokens written")}${kpi("k-cost", "spent")}${kpi("k-runs", "tests passed")}${kpi("k-yours", "on your model")}</div><span class="tag src">demo data</span></header>
<section class="panel p-graph"><h2>How a task flows</h2>${svg}<p class="test-note">A run succeeds only if the task's own unit tests pass (e.g. <code>tests/test_mod_05.py</code>).</p></section>
<section class="panel p-ring"><h2>Graduation</h2><p class="ring-what" id="ring-what">5 passing runs, then your own model takes over</p><div class="ring-wrap"><svg viewBox="0 0 120 120" class="ring"><circle cx="60" cy="60" r="50" class="track"/><circle id="ring" cx="60" cy="60" r="50" class="fill" pathLength="100"/></svg>
<div class="ring-mid"><b id="ring-n">0 of 5</b><span id="ring-sub">passing runs</span></div></div><p id="ring-name" class="ring-name"></p><p id="ring-state" class="ring-state">learning on the big model</p>
<div class="train"><div class="bar"><i id="train-bar"></i></div><p id="train-line"></p></div>
<ol class="stepper" id="stepper"><li data-s="READY">Ready</li><li data-s="TRAINING">Training</li><li data-s="GRADUATED">Your model live</li></ol></section>
<section class="panel p-race"><h2>Race</h2>${raceRow("big", "Big model")}${raceRow("yours", "Your model")}<p id="race-verdict" class="race-verdict"></p></section>
<section class="panel p-log"><h2>Session log</h2><ol id="log" class="log"></ol></section>
<section class="panel p-lanes"><h2>Agents · GBrain tips</h2><div id="lanes" class="lanes"></div></section>
<footer class="sponsors">${SPONSORS.map(([id, name, role, st]) => `<div class="sp ${st}" id="sp-${id}"><i></i><b>${name}</b><span id="sp-${id}-role">${role}</span></div>`).join("")}</footer>
</div>`;
}
const node = (id, label, sub, cls = "") => `<g id="n-${id}" class="node ${cls}" transform="translate(${NODES[id][0]} ${NODES[id][1]})"><rect x="-80" y="-36" width="160" height="72" rx="8"/><text y="-4">${label}</text><text y="20" class="sub" id="${id}-sub">${sub}</text></g>`;
const kpi = (id, label) => `<div class="kpi"><b id="${id}">0</b><span>${label}</span></div>`;
const raceRow = (id, label) => `<div class="race-row ${id}"><span class="who">${label}</span><div class="bar"><i id="rb-${id}"></i></div><b id="rt-${id}">0</b><span class="unit">tokens</span><span id="rv-${id}" class="rv"></span></div>`;

// Seeds from the real data: task type titles, N, per-run averages, the recorded calls, the swarm's agent names.
function seed() {
  const s = data.state || { registry: { task_types: {} }, config: { n: 5 }, ledger: [] };
  const tt = Object.values(s.registry.task_types || {}).filter((t) => t.title);
  const types = tt.map((t) => t.title), grads = tt.filter((t) => t.state === "GRADUATED").map((t) => t.title);
  const learning = tt.filter((t) => t.state !== "GRADUATED").map((t) => t.title);
  const avg = (rows, k, d) => (rows.length ? rows.reduce((a, r) => a + (r[k] || 0), 0) / rows.length : d);
  const big = (s.ledger || []).filter((r) => r.routed_to === "frontier"), mine = (s.ledger || []).filter((r) => r.routed_to === "owned");
  const calls = pairs().flatMap((p) => [p.frontier.log, p.owned.log]).filter(Boolean).flat().map((c) => c.response || {});
  const steps = calls.flatMap((m) => (m.tool_calls || []).map((t) => { let a = ""; try { a = String(Object.values(JSON.parse(t.function.arguments))[0] || ""); } catch {} return `${t.function.name} ${a.split("\n")[0].replace(/^\/\S*\/(\S+\/\S+)/, "…/$1").slice(0, 48)}`; }));
  const agents = ((data.swarm && data.swarm.agents) || []).map((a) => a.agent);
  const title = Object.fromEntries(Object.entries(s.registry.task_types || {}).map(([k, t]) => [k, t.title || k]));
  if (data.sample === false) return realSeed(s, (data.replay && data.replay.runs) || [], title, agents);
  return {
    types: types.length ? types : ["Fix a failing test", "Update the changelog", "Add an API endpoint"],
    grads, learning: learning.length ? learning : types,
    n: s.config.n || 5,
    big: { out: avg(big, "output_tokens", 25800), cost: avg(big, "cost_usd", 0.42), secs: avg(big, "wall_secs", 94) },
    mine: { out: avg(mine, "output_tokens", 540), cost: avg(mine, "cost_usd", 0.0026), secs: avg(mine, "wall_secs", 21) },
    steps: steps.length ? steps : ["read calc/mod_05.py", "edit calc/mod_05.py", "bash pytest -q tests/test_mod_05.py"],
    agents: agents.length >= 3 ? agents.slice(0, 6) : ["a1", "a2", "a3", "a4", "a5"],
    tips: true,
  };
}

// Real mode: the ledger's runs in start order, launched at their recorded gaps sped up so one pass takes about 45 s.
function realSeed(s, rows, title, agents) {
  const at = (r) => Date.parse(r.started_at) || 0;
  rows = [...rows].sort((a, b) => at(a) - at(b));
  const span = rows.length ? (at(rows[rows.length - 1]) - at(rows[0])) / 1000 : 0, speed = Math.max(1, span / 45);
  const avg = (rs, k) => (rs.length ? rs.reduce((a, r) => a + (r[k] || 0), 0) / rs.length : null);
  const big = rows.filter((r) => r.routed_to === "frontier" && r.exit_code === 0 && !r.escalated_from), mine = rows.filter((r) => r.routed_to === "owned");
  const count = {};
  rows.forEach((r) => (count[r.task_type] = (count[r.task_type] || 0) + 1));
  const ringSlug = Object.keys(count).sort((a, b) => count[b] - count[a])[0];
  const queue = rows.map((r, i) => ({
    gap: i ? Math.max(0.25, (at(r) - at(rows[i - 1])) / 1000 / speed) : 0.3,
    slug: r.task_type, type: title[r.task_type] || r.task_type || "unclassified", mine: r.routed_to === "owned", pass: r.exit_code === 0,
    rerun: !!r.escalated_from, out: r.output_tokens || 0, cost: r.cost_usd || 0, model: r.model || "", steps: r.steps || [],
  }));
  const bigBy = {};
  big.forEach((r) => (bigBy[r.task_type] ||= []).push(r));
  return {
    real: true, speed, queue, ringSlug, ringTitle: title[ringSlug] || ringSlug, n: s.config.n || 5,
    loss: (((data.replay && data.replay.loss) || {})[ringSlug]) || null,
    bigBy: Object.fromEntries(Object.entries(bigBy).map(([k, rs]) => [k, { out: avg(rs, "output_tokens"), cost: avg(rs, "cost_usd") }])),
    big: { out: avg(big, "output_tokens") || 0, cost: avg(big, "cost_usd") || 0, secs: avg(big, "wall_secs") || 1 },
    mine: mine.length ? { out: avg(mine, "output_tokens"), cost: avg(mine, "cost_usd"), secs: avg(mine, "wall_secs") } : null,
    types: [title[ringSlug] || ringSlug], grads: [], learning: [title[ringSlug] || ringSlug],
    agents, // every real agent (none: the Agents card says so)
    tips: (data.state.trace || []).some((e) => (e.edges || []).includes("a2a-write")),
  };
}

function startLive() {
  const S = seed();
  sim.dots.forEach((d) => d.els.forEach((el) => el.remove()));
  Object.assign(sim, { S, t: 0, next: 0.2, qi: 0, dots: [], tokens: 0, cost: 0, runs: 0, passed: 0, yours: 0, saved: 0, savedTok: 0, ring: 0, typeIx: 0, graduated: new Set(S.grads), raceT: 0, training: null });
  const tag = document.querySelector("#live-root .tag.src"); // one source tag for the page
  tag.textContent = S.real ? "real runs" : "demo data";
  sim.seen = null;
  tag.classList.toggle("real", !!S.real);
  resetRing();
  sim.lanes = S.agents.map((a) => ({ a, busy: 0, dur: 1, status: "idle" }));
  document.getElementById("lanes").innerHTML = sim.lanes.map((l, i) => `<div class="lane" id="lane-${i}"><b>${esc(l.a)}</b><div class="bar"><i></i></div><span class="st">idle</span><span class="note"></span></div>`).join("");
  document.getElementById("ring-name").textContent = `“${ringType()}”`;
  if (!sim.on) { sim.on = true; sim.last = performance.now(); requestAnimationFrame(frame); }
}

function frame(now) {
  const root = document.getElementById("live-root");
  if (!root) { sim.on = false; return; }
  if (!root.dataset.started) { if (data.sample === undefined) return requestAnimationFrame(frame); root.dataset.started = 1; startLive(); }
  const dt = Math.min(0.05, (now - sim.last) / 1000);
  sim.last = now; sim.t += dt;
  if (sim.S.real) { realView(); moveDots(dt); realRing(); } // real data: nothing replays; a dot flies only when a new run lands
  else {
    if (sim.t >= sim.next) { launch(); sim.next = sim.t + 0.3 + Math.random() * 0.4; }
    moveDots(dt); lanes(dt); counters(dt); raceLoop(dt); training(dt);
  }
  facts();
  requestAnimationFrame(frame);
}

// One request: agent -> jelly router -> a model -> tests. A task type that has graduated goes to your model; a miss there is re-run on the big model.
function launch(run) {
  const S = sim.S, lane = sim.lanes.findIndex((l) => l.status === "idle");
  if (run) { // a recorded real run
    if (run.mine && run.slug === S.ringSlug && !sim.graduated.has(run.type)) sim.graduated.add(run.type);
    if (lane >= 0) Object.assign(sim.lanes[lane], { status: "working", busy: 0, dur: run.mine ? 1.6 : 3.2, type: run.type, pass: run.pass });
    const route = run.rerun ? ["in", "big", "bigOut"] : ["in", run.mine ? "yours" : "big", run.mine ? "yoursOut" : "bigOut"];
    return addDot({ ...run, route, lane, speed: run.mine ? 1.9 : 1.1 });
  }
  const type = Math.random() < 0.45 ? ringType() : S.types[Math.floor(Math.random() * S.types.length)];
  const mine = sim.graduated.has(type), pass = mine ? Math.random() > 0.12 : Math.random() > 0.08;
  if (lane >= 0) Object.assign(sim.lanes[lane], { status: "working", busy: 0, dur: mine ? 1.6 : 3.2, type, pass });
  addDot({ route: ["in", mine ? "yours" : "big", mine ? "yoursOut" : "bigOut"], mine, pass, type, lane, speed: mine ? 1.9 : 1.1 });
}

// A request is a glowing dot with a fading trail of three ghosts behind it.
function addDot(d) {
  const els = [0, 1, 2, 3].map((k) => {
    const el = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    el.setAttribute("r", (d.rerun ? 7 : 6) - k * 1.3);
    el.setAttribute("class", `dot ${d.rerun ? "rerun" : d.mine ? "mine" : "big"}`);
    el.setAttribute("opacity", 1 - k * 0.25);
    document.getElementById("dots").appendChild(el);
    return el;
  });
  sim.dots.push({ ...d, els, leg: 0, s: 0 });
}

function moveDots(dt) {
  for (const d of sim.dots) {
    const path = document.getElementById(`e-${d.route[d.leg]}`), len = path.getTotalLength();
    d.s += dt * d.speed * 420;
    if (d.s >= len) {
      d.s = 0; d.leg++;
      if (d.leg === 1) { flash("grad", "hit"); spark("memorable"); }
      if (d.leg === 2) { flash(d.route[1] === "yours" ? "yours" : "big", "hit"); if (d.route[1] === "big") spark("openai"); }
      if (d.leg >= d.route.length) { d.done = true; finish(d); continue; }
    }
    d.els.forEach((el, k) => {
      const p = path.getPointAtLength(Math.max(0, Math.min(d.s - k * 14, len)));
      el.setAttribute("cx", p.x); el.setAttribute("cy", p.y);
    });
  }
  sim.dots = sim.dots.filter((d) => (d.done ? (d.els.forEach((el) => el.remove()), false) : true));
}

const spark = (id) => { const el = document.getElementById(`sp-${id}`); if (el) { el.classList.remove("lit"); void el.offsetWidth; el.classList.add("lit"); } };

function flash(id, cls) {
  const n = document.getElementById(`n-${id}`);
  n.classList.remove(cls); void n.getBoundingClientRect(); n.classList.add(cls);
}

function finish(d) {
  if (sim.S.real) return flash("tests", d.pass ? "pass" : "fail");
  const S = sim.S, m = d.mine ? S.mine : S.big, jit = 0.75 + Math.random() * 0.5;
  const out = S.real ? d.out : m.out * jit, cost = S.real ? d.cost : m.cost * jit;
  flash("tests", d.pass ? "pass" : "fail");
  sim.tokens += out; sim.cost += cost; sim.runs += d.pass ? 1 : 0; sim.yours += d.mine && d.pass ? 1 : 0;
  if (d.mine) { // saved = what the big model averages on this kind of task, minus this run; a miss wastes its own cost
    const b = (S.bigBy && S.bigBy[d.slug]) || S.big;
    if (d.pass) { sim.saved += b.cost - cost; sim.savedTok += b.out - out; } else { sim.saved -= cost; sim.savedTok -= out; }
  }
  const steps = S.real ? (d.steps.length ? d.steps : [d.type]) : S.steps, step = steps[Math.floor(Math.random() * steps.length)];
  const who = d.rerun ? "big model · re-run" : d.mine ? "your model" : S.real && d.model ? d.model : "big model";
  log(`<span class="who ${d.mine ? "mine" : "big"}">${esc(who)}</span><span class="what">${esc(step.replace(/\/\S*\/(\S+\/\S+)/g, "…/$1"))}</span><span class="tok">${short(out)} tok</span><span class="${d.pass ? "ok" : "bad"}">${d.pass ? "✓ tests pass" : "✗ tests fail"}</span>`);
  if (d.lane >= 0 && sim.lanes[d.lane]) sim.lanes[d.lane].status = d.pass ? "passed" : "failed";
  if (!S.real && d.mine && !d.pass) addDot({ route: ["big", "bigOut"], mine: false, pass: true, type: d.type, lane: -1, speed: 1.2, rerun: true, pre: true });
  if (!S.real && !d.mine && d.pass && !d.rerun && d.type === ringType() && !sim.graduated.has(d.type) && !sim.training && sim.ring < S.n) graduateStep(d.type);
}

// The task type filling the ring: the next one still learning, in turn.
const ringType = () => { const l = sim.S.learning.filter((t) => !sim.graduated.has(t)); return l.length ? l[sim.typeIx % l.length] : sim.S.types[0]; };

function graduateStep(type) {
  const S = sim.S;
  sim.ring = Math.min(S.n, sim.ring + 1);
  document.getElementById("ring").style.strokeDashoffset = 100 - (sim.ring / S.n) * 100;
  document.getElementById("ring-n").textContent = `${sim.ring} of ${S.n}`;
  if (sim.ring < S.n) return;
  if (S.real && !S.loss) { // no training log in this directory yet: say so, invent no curve
    document.querySelector(".p-ring").classList.add("training");
    set("ring-state", "ready · training your model"); set("train-line", "LoRA on Qwen2.5-Coder-0.5B · on this machine");
    return;
  }
  // Training: the real loss curve when this task type has one, else a demo curve.
  const curve = S.real && S.loss && S.loss.steps.length ? S.loss.steps : Array.from({ length: 24 }, (_, i) => ({ step: i + 1, loss: 0.25 + 2.2 * Math.exp(-i / 5), secs: (i + 1) * 26 }));
  sim.training = { type, t: 0, dur: 7, curve, real: curve === (S.loss && S.loss.steps) };
  document.querySelector(".p-ring").classList.add("training");
  document.getElementById("ring-state").textContent = "training your model";
}

function training(dt) {
  const tr = sim.training;
  if (!tr) return;
  tr.t += dt;
  const f = Math.min(1, tr.t / tr.dur), c = tr.curve, k = Math.max(1, Math.ceil(f * c.length)), row = c[k - 1];
  document.getElementById("train-bar").style.transform = `scaleX(${f})`;
  set("train-line", `LoRA on Qwen2.5-Coder-0.5B · on this machine · step ${row.step}/${c[c.length - 1].step} · loss ${row.loss.toFixed(3)}${tr.real ? "" : " (demo curve)"}`);
  if (f < 1 || tr.t < tr.dur + 0.1) return;
  const wrap = document.querySelector(".p-ring"), mins = Math.max(1, Math.round((c[c.length - 1].secs || 0) / 60));
  sim.training = null; sim.graduated.add(tr.type);
  wrap.classList.remove("training"); wrap.classList.add("graduated");
  set("ring-state", "your model is live"); set("ring-n", "✓"); set("ring-sub", "Graduated");
  set("train-line", tr.real ? `trained in ${mins} min on this machine (real training log ${sim.S.loss.name})` : `trained in ${mins} min (demo curve)`);
  log(`<span class="who grad">graduated</span><span class="what">“${esc(tr.type)}” now runs on your model</span><span></span><span class="ok">✓</span>`);
  setTimeout(() => { // next task type starts learning
    if (!document.getElementById("live-root") || sim.S.real) return;
    sim.typeIx++;
    if (sim.graduated.size >= sim.S.types.length) sim.graduated = new Set(sim.S.grads);
    resetRing();
  }, 6000);
}


// Real mode: the ring is the registry's own count and state for its busiest task type, not the replay's.
const topType = () => Object.entries((data.state && data.state.registry.task_types) || {}).sort((a, b) => (b[1].verified_runs || 0) - (a[1].verified_runs || 0))[0] || [];
// Your model's side before it has a run in this directory: training, or live with no run recorded here yet.
const notYet = (short) => ((topType()[1] || {}).state === "GRADUATED" ? (short ? "no run yet" : "live · no run here yet") : short ? "model training" : "training on these runs");

// Every frame, from the newest /state: the big model the latest runs used, and your model's plain one-liner.
const toggleOn = (id, on) => { const el = document.getElementById(id); el.classList.toggle("on", on); el.classList.toggle("off", !on); };

function facts() {
  const s = data.state || {}, rows = s.ledger || [], reg = (s.registry && s.registry.task_types) || {}, tot = s.totals || {};
  const latest = ([...rows].reverse().find((r) => r.routed_to === "frontier" && r.model && r.model !== "unknown") || {}).model || "";
  const claude = /claude/i.test(latest), gpt = /gpt|openai/i.test(latest);
  set("big-sub", claude ? "Claude Haiku 4.5" : latest.split("/").pop() || "pay per token");
  const oai = document.getElementById("sp-openai");
  oai.classList.toggle("on", gpt); oai.classList.toggle("off", !gpt);
  if (gpt) set("sp-openai-role", `the big model now: ${latest}`);
  const verified = rows.filter((r) => r.routed_to === "frontier" && r.exit_code === 0 && !r.escalated_from).length;
  set("sp-memorable-role", `classifies each task by recalling past procedures · ${verified} learned from verified runs`);
  const riverT = Object.values(reg).find((t) => String(t.model || "").startsWith("river://"));
  const localT = Object.values(reg).find((t) => t.model && !String(t.model).startsWith("river://"));
  toggleOn("sp-river", !!riverT);
  set("sp-river-role", riverT ? `trains and serves your model · Qwen3.5-9B LoRA trained on ${riverT.trained_on_runs || "its"} real runs` : localT ? "not used · your model trained on this machine" : "not used yet · nothing trained");
  const gb = (s.trace || []).filter((e) => /GBrain/.test(e.who)), gbLive = gb.filter((e) => !/GBrain not installed|skipped|^exit [1-9]/.test(e.result));
  toggleOn("sp-gbrain", gbLive.length > 0);
  set("sp-gbrain-role", gbLive.length ? `agents share notes · ${gbLive.length} recent calls` : gb.length ? "not installed · notes go to a shared file" : "not called yet");
  const g = Object.values(reg).find((t) => t.state === "GRADUATED" && t.model);
  if (g && String(g.model).startsWith("river://")) set("sp-river-role", `trains and serves your model · Qwen3.5-9B LoRA trained on ${g.trained_on_runs || "your"} real runs`);
  if (!g || !sim.S.real) return set("yours-line", "");
  const base = String(g.model).startsWith("river://") ? "Qwen3.5-9B, trained on River" : "Qwen2.5-Coder-0.5B, trained on this machine";
  set("yours-line", `Your model: ${base} from ${g.trained_on_runs || "its"} real runs · now serving ${tot.owned_runs || 0} run${tot.owned_runs === 1 ? "" : "s"} · saved ${money(tot.saved_usd || 0)}`);
}

// Real data, over time: counters are the ledger's totals, the log its newest runs, the chart every run in order.
// Re-drawn only when the ledger changes; a new run sends one dot through the graph.
function realView() {
  const rows = [...((data.state && data.state.ledger) || [])].sort((a, b) => String(a.started_at).localeCompare(String(b.started_at)));
  const sig = rows.map((r) => r.session_id).join();
  if (sig === sim.seen) return;
  if (sim.seen !== null) rows.filter((r) => !sim.seen.includes(r.session_id)).forEach((r) => {
    const mine = r.routed_to === "owned";
    addDot({ route: ["in", mine ? "yours" : "big", mine ? "yoursOut" : "bigOut"], mine, pass: r.exit_code === 0, lane: -1, speed: 1.4 });
  });
  sim.seen = sig;
  const tot = data.state.totals || {}, sum = (rs, k) => rs.reduce((a, r) => a + (r[k] || 0), 0);
  const big = rows.filter((r) => r.routed_to === "frontier"), mine = rows.filter((r) => r.routed_to === "owned");
  set("k-tokens", num(sum(rows, "output_tokens"))); set("k-cost", money(sum(rows, "cost_usd")));
  set("k-runs", num(rows.filter((r) => r.exit_code === 0).length));
  set("k-yours", rows.length ? `${Math.round((mine.length / rows.length) * 100)}%` : "0%");
  set("k-saved", money(tot.saved_usd || 0)); set("k-saved-l", mine.length ? `saved · ${mine.length} runs` : `saved · ${notYet(true)}`);
  const steps = Object.fromEntries(((data.replay && data.replay.runs) || []).map((r) => [r.session_id, r.steps || []]));
  document.getElementById("log").innerHTML = [...rows].reverse().map((r) => {
    const m = r.routed_to === "owned", st = (steps[r.session_id] || []).slice(-1)[0] || String(r.prompt || "").slice(0, 60);
    return `<li style="animation:none"><time>${time(r.started_at)}</time><span class="who ${m ? "mine" : "big"}">${m ? "your model" : esc(r.model || "big model")}</span><span class="what">${esc(st.replace(/\/\S*\/(\S+\/\S+)/g, "…/$1"))}</span><span class="tok">${short(r.output_tokens || 0)} tok</span><span class="${r.exit_code === 0 ? "ok" : "bad"}">${r.exit_code === 0 ? "✓" : "✗"} ${esc(testFile(r))}</span></li>`;
  }).join("");
  const top = Math.max(...rows.map((r) => r.cost_usd || 0), 0.0001), w = 400 / Math.max(rows.length, 1);
  const wide = rows.length * 14 > 400; // bars would be thinner than ~12px: draw every run at 14px and scroll the chart sideways
  const avg = (rs, k) => (rs.length ? sum(rs, k) / rs.length : 0);
  document.querySelector(".p-race").innerHTML = `<h2>Cost per run, over time</h2>
<div class="over-wrap" data-end="1">${(() => { const W = wide ? rows.length * 14 : 400, bw = W / Math.max(rows.length, 1); return `<svg class="over" viewBox="0 0 ${W} 120" preserveAspectRatio="none" style="${wide ? `width:${W}px` : ""}">${rows.map((r, i) => `<rect class="${r.routed_to === "owned" ? "mine" : "big"}" x="${i * bw + 1}" y="${120 - Math.max(2, ((r.cost_usd || 0) / top) * 116)}" width="${Math.max(1, bw - 2)}" height="${Math.max(2, ((r.cost_usd || 0) / top) * 116)}"/>`).join("")}</svg>`; })()}</div>
<div class="over-tot"><p><b class="bigc">Big model</b> ${money(avg(big, "cost_usd"))}/run · ${num(avg(big, "output_tokens"))} tokens · ${big.length} runs</p>
<p><b class="minec">Your model</b> ${mine.length ? `${money(avg(mine, "cost_usd"))}/run · ${num(avg(mine, "output_tokens"))} tokens · ${mine.length} runs` : "no runs yet"}</p>
<p><b>Saved so far</b> ${money(tot.saved_usd || 0)}</p></div>`;
  const agents = (data.swarm && data.swarm.agents) || [];
  if (!agents.length) { document.getElementById("lanes").innerHTML = empty("No parallel agent run recorded in this data yet."); return; }
  const wrap = document.querySelector(".over-wrap");
  if (wrap && wrap.dataset.end) { wrap.scrollLeft = wrap.scrollWidth; delete wrap.dataset.end; } // newest run at the right, in view
  if (sim.lanes.length !== agents.length) {
    sim.lanes = agents.map((a) => ({ a: a.agent, busy: 0, dur: 1, status: "idle" }));
    document.getElementById("lanes").innerHTML = sim.lanes.map((l, i) => `<div class="lane" id="lane-${i}"><b>${esc(l.a)}</b><div class="bar"><i></i></div><span class="st"></span><span class="note"></span></div>`).join("");
  }
  sim.lanes.forEach((l, i) => {
    const el = document.getElementById(`lane-${i}`), a = agents[i];
    if (!el) return;
    const st = a ? a.status : "idle";
    el.className = `lane ${st === "passed" ? "passed" : st === "failed" ? "failed" : st === "running" ? "working" : "idle"}`;
    el.querySelector(".bar i").style.transform = `scaleX(${st === "passed" || st === "failed" ? 1 : 0})`;
    el.querySelector(".st").textContent = a ? `task ${a.task} · ${{ passed: "✓ fixed it", failed: "✗ re-run on big model", running: "working", queued: "waiting" }[st] || st}` : "no agent";
    el.querySelector(".note").textContent = a ? [a.a2a_read && "read a tip", a.a2a_write && "left a tip"].filter(Boolean).join(" · ") : "";
  });
}

function realRing() {
  const S = sim.S, s = data.state, n = s.config.n || 5;
  const [slug, t] = topType();
  if (!t) return;
  const v = t.verified_runs || 0, runs = `${v} real run${v === 1 ? "" : "s"}`;
  document.getElementById("ring").style.strokeDashoffset = 100 - (Math.min(v, n) / n) * 100;
  const grad = t.state === "GRADUATED", tot = s.totals || {};
  set("ring-n", grad ? "✓" : `${Math.min(v, n)} of ${n}`); set("ring-sub", grad ? "graduated" : "passing runs");
  const order = ["READY", "TRAINING", "GRADUATED"], at = order.indexOf(t.state);
  document.querySelectorAll("#stepper li").forEach((li, i) => { li.classList.toggle("done", at > i); li.classList.toggle("now", at === i); });
  set("ring-name", `“${t.title || slug}”`);
  const said = { LEARNING: "learning on the big model", READY: "ready · training your model", TRAINING: `training your model on these ${runs}`,
    GRADUATED: tot.owned_runs ? `serving ${tot.owned_runs} runs · saved $${(tot.saved_usd || 0).toFixed(2)}` : "waiting for its first run",
    PROBATION: "back on the big model after failures" };
  set("ring-state", said[t.state] || t.state);
  const wrap = document.querySelector(".p-ring");
  wrap.classList.toggle("training", t.state === "TRAINING"); wrap.classList.toggle("ready", t.state === "READY"); wrap.classList.toggle("graduated", t.state === "GRADUATED");
  const curve = (data.replay && data.replay.loss && data.replay.loss[slug]) || null, c = curve && curve.steps;
  const river = String(t.model || "").startsWith("river://") || (!t.model && s.config.backend === "river");
  const where = river ? "LoRA on Qwen3.5-9B · on River" : "LoRA on Qwen2.5-Coder-0.5B · on this machine";
  const run = c && c.length ? ` · ${c.length} steps · loss ${c[0].loss.toFixed(3)} → ${c[c.length - 1].loss.toFixed(3)} · ${Math.round(c[c.length - 1].secs || 0)} s`
    : "";
  const curveLine = c && c.length ? ` · ${c.length} steps · loss ${c[0].loss.toFixed(3)} → ${c[c.length - 1].loss.toFixed(3)} · ${Math.round(c[c.length - 1].secs || 0)} s` : "";
  set("train-line", (river ? "Qwen3.5-9B on River" : "Qwen2.5-Coder-0.5B on this machine") + curveLine);
  document.getElementById("train-bar").style.transform = `scaleX(${t.state === "GRADUATED" || c ? 1 : 0})`;
  set("ring-what", `${n} passing runs, then your own model takes over`);
}

function resetRing() {
  const wrap = document.querySelector(".p-ring");
  wrap.classList.remove("graduated", "training"); sim.ring = 0;
  document.getElementById("ring").style.strokeDashoffset = 100;
  document.getElementById("ring-n").textContent = `0 of ${sim.S.n}`; set("ring-sub", "passing runs");
  document.getElementById("ring-name").textContent = `“${ringType()}”`;
  set("ring-state", "learning on the big model"); set("train-line", ""); document.getElementById("train-bar").style.transform = "scaleX(0)";
}

function log(html) {
  const ol = document.getElementById("log"), li = document.createElement("li");
  const ts = localTime(new Date());
  li.innerHTML = `<time>${ts}</time>${html}`;
  ol.prepend(li);
  while (ol.children.length > 18) ol.lastChild.remove();
}

function lanes(dt) {
  sim.lanes.forEach((l, i) => {
    const el = document.getElementById(`lane-${i}`);
    if (!el) return;
    if (l.status === "working") l.busy = Math.min(1, l.busy + dt / l.dur);
    else if (l.status !== "idle") { l.hold = (l.hold || 0) + dt; if (l.hold > 1.2) { if (l.status === "passed" && sim.S.tips && Math.random() < 0.5) tip(i, l.type); Object.assign(l, { status: "idle", busy: 0, hold: 0 }); } }
    el.className = `lane ${l.status}`;
    el.querySelector(".bar i").style.transform = `scaleX(${l.status === "idle" ? 0 : l.status === "working" ? l.busy : 1})`;
    el.querySelector(".st").textContent = { idle: "waiting", working: `working · ${l.type || ""}`, passed: "✓ fixed it", failed: "✗ re-run on big model" }[l.status];
  });
}

// A tip: the agent that just passed writes how it did it; another agent reads it before its task.
function tip(from, type) {
  const to = (from + 1 + Math.floor(Math.random() * (sim.lanes.length - 1))) % sim.lanes.length;
  const a = document.getElementById(`lane-${from}`), b = document.getElementById(`lane-${to}`), box = document.getElementById("lanes");
  if (!a || !b) return;
  const chip = document.createElement("span");
  chip.className = "tip"; chip.textContent = "tip";
  chip.style.top = `${a.offsetTop + a.offsetHeight / 2 - 11}px`;
  box.appendChild(chip);
  requestAnimationFrame(() => { chip.style.top = `${b.offsetTop + b.offsetHeight / 2 - 11}px`; });
  setTimeout(() => chip.remove(), 1300);
  spark("gbrain");
  b.querySelector(".note").textContent = `read a tip on “${type}”`;
  a.querySelector(".note").textContent = `left a tip`;
  setTimeout(() => { if (b.isConnected) b.querySelector(".note").textContent = ""; if (a.isConnected) a.querySelector(".note").textContent = ""; }, 2500);
}

function counters(dt) {
  const ease = 1 - Math.pow(0.001, dt);
  sim.shown.tokens += (sim.tokens - sim.shown.tokens) * ease;
  sim.shown.cost += (sim.cost - sim.shown.cost) * ease;
  set("k-tokens", num(sim.shown.tokens));
  document.getElementById("n-yours").classList.toggle("lit", sim.graduated.size > 0); set("k-cost", money(sim.shown.cost)); set("k-runs", num(sim.runs));
  set("k-yours", sim.runs ? `${Math.round((sim.yours / sim.runs) * 100)}%` : "0%");
  const tot = sim.S.real && data.state && data.state.totals;
  if (tot && tot.owned_runs) { set("k-saved", money(tot.saved_usd || 0)); set("k-saved-l", `saved · ${tot.owned_runs} runs`); return; }
  set("k-saved", `${sim.saved < 0 ? "−" : ""}${money(Math.abs(sim.saved))}`);
  set("k-saved-l", sim.S.real && !sim.S.mine ? `saved · ${notYet(true)}` : `saved · ${short(Math.max(0, sim.savedTok))} tokens`);
}
const short = (v) => (v >= 1000 ? `${(v / 1000).toFixed(1)}k` : String(Math.round(v)));
const set = (id, v) => { const el = document.getElementById(id); if (el && el.textContent !== v) el.textContent = v; };

// The race: the same task on both models, 12-second loop. The big model takes 9 s; your model's time and both token
// counts keep the recorded averages' proportions.
function raceLoop(dt) {
  const S = sim.S;
  if (!S.mine || !S.big.out) { // real mode before your model has run: the big model's run only
    set("rt-big", num(S.big.out)); set("rv-big", "✓ tests pass"); set("rt-yours", "–"); set("rv-yours", notYet()); set("race-verdict", "");
    document.getElementById("rb-big").style.transform = "scaleX(1)"; document.getElementById("rb-yours").style.transform = "scaleX(0)";
    return;
  }
  sim.raceT = (sim.raceT + dt) % 12;
  const t = sim.raceT, lanes = [["big", S.big.out, 9], ["yours", S.mine.out, Math.min(9, Math.max(0.8, (9 * S.mine.secs) / (S.big.secs || 1)))]];
  for (const [id, total, dur] of lanes) {
    const f = Math.min(1, t / dur);
    document.getElementById(`rb-${id}`).style.transform = `scaleX(${f * (total / S.big.out) || 0.004})`;
    set(`rt-${id}`, num(total * f));
    set(`rv-${id}`, f >= 1 ? "✓ tests pass" : "");
  }
  const x = S.big.out / (S.mine.out || 1);
  set("race-verdict", t > 9.2 ? (x >= 1.5 ? `${Math.round(x)}× fewer tokens written by your model` : "both passed the tests") : "");
}

// The unit test file a run was verified by ("test_mod_05.py"), from its verify command.
const testFile = (r) => (String(r.verify_command || r.prompt || "").match(/test_\w+\.py/) || ["tests"])[0];
