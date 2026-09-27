// /app (Live): the showcase. One looping, scripted timeline drives every panel at once: requests flow through the
// router graph, the tests light green or red, the log streams, counters tick, a task type fills its ring to N and
// graduates, agents pass notes, and the two models race. It is seeded from the live APIs (task type titles, N, the
// recorded session logs, the swarm's agents, per-run token and cost averages) but its numbers are simulated, so every
// panel wears a "demo data" tag. Uses app.js's globals (data, esc, num, money, pairs) at call time.
const NODES = { agent: [95, 210], grad: [380, 210], big: [680, 75], yours: [680, 345], tests: [910, 210] };
const EDGES = {
  in: "M 183 210 L 292 210",
  big: "M 468 190 C 530 110, 555 75, 592 75",
  yours: "M 468 230 C 530 310, 555 345, 592 345",
  bigOut: "M 768 75 C 820 75, 850 140, 868 168",
  yoursOut: "M 768 345 C 820 345, 850 280, 868 252",
};
const sim = { on: false, last: 0, t: 0, next: 0, dots: [], tokens: 0, cost: 0, runs: 0, passed: 0, yours: 0, shown: { tokens: 0, cost: 0 }, ring: 0, lanes: [], logs: 0, raceT: 0 };

function live() {
  const svg = `<svg class="graph" viewBox="0 0 1000 420" preserveAspectRatio="xMidYMid meet" aria-label="How a request flows">
<defs><filter id="glow"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
${Object.entries(EDGES).map(([k, d]) => `<path id="e-${k}" class="edge ${k.startsWith("yours") ? "mine" : ""}" d="${d}"/>`).join("")}
${node("agent", "Coding agents", "send every task")}${node("grad", "GRADUATE", "routes · records · checks", "hub")}
${node("big", "Big model", "rented, pay per token")}${node("yours", "Your model", "small, trained on your runs", "mine")}${node("tests", "Tests", "pass or fail", "tests")}
<g id="dots"></g></svg>`;
  return `<div id="live-root" class="live">
<header class="live-top"><div><span class="pulse"></span> <b>Live</b> <span class="muted">every task your agents send, checked by its own tests</span></div>
<div class="kpis">${kpi("k-tokens", "tokens written")}${kpi("k-cost", "spent on models")}${kpi("k-runs", "tasks verified by tests")}${kpi("k-yours", "handled by your model")}</div><span class="tag">demo data</span></header>
<section class="panel p-graph"><h2>Request flow <span class="tag">demo data</span></h2>${svg}</section>
<section class="panel p-ring"><h2>Graduation <span class="tag">demo data</span></h2><div class="ring-wrap"><svg viewBox="0 0 120 120" class="ring"><circle cx="60" cy="60" r="50" class="track"/><circle id="ring" cx="60" cy="60" r="50" class="fill" pathLength="100"/></svg>
<div class="ring-mid"><b id="ring-n">0</b><span id="ring-of">of 5 passing runs</span></div></div><p id="ring-name" class="ring-name"></p><p id="ring-state" class="ring-state">learning on the big model</p></section>
<section class="panel p-race"><h2>Same task, both models <span class="tag">demo data</span></h2>${raceRow("big", "Big model")}${raceRow("yours", "Your model")}<p id="race-verdict" class="race-verdict"></p></section>
<section class="panel p-log"><h2>Session log <span class="tag">demo data</span></h2><ol id="log" class="log"></ol></section>
<section class="panel p-lanes"><h2>Agents in parallel · sharing tips through GBrain <span class="tag">demo data</span></h2><div id="lanes" class="lanes"></div></section>
</div>`;
}
const node = (id, label, sub, cls = "") => `<g id="n-${id}" class="node ${cls}" transform="translate(${NODES[id][0]} ${NODES[id][1]})"><rect x="-88" y="-42" width="176" height="84" rx="14"/><text y="-4">${label}</text><text y="22" class="sub">${sub}</text></g>`;
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
  return {
    types: types.length ? types : ["Fix a failing test", "Update the changelog", "Add an API endpoint"],
    grads, learning: learning.length ? learning : types,
    n: s.config.n || 5,
    big: { out: avg(big, "output_tokens", 25800), cost: avg(big, "cost_usd", 0.42), secs: avg(big, "wall_secs", 94) },
    mine: { out: avg(mine, "output_tokens", 540), cost: avg(mine, "cost_usd", 0.0026), secs: avg(mine, "wall_secs", 21) },
    steps: steps.length ? steps : ["read calc/mod_05.py", "edit calc/mod_05.py", "bash pytest -q tests/test_mod_05.py"],
    agents: agents.length >= 3 ? agents.slice(0, 6) : ["a1", "a2", "a3", "a4", "a5"],
  };
}

function startLive() {
  const S = seed();
  Object.assign(sim, { S, t: 0, next: 0.2, dots: [], tokens: 0, cost: 0, runs: 0, passed: 0, yours: 0, ring: 0, typeIx: 0, graduated: new Set(S.grads), raceT: 0 });
  sim.lanes = S.agents.map((a) => ({ a, busy: 0, dur: 1, status: "idle" }));
  document.getElementById("lanes").innerHTML = sim.lanes.map((l, i) => `<div class="lane" id="lane-${i}"><b>${esc(l.a)}</b><div class="bar"><i></i></div><span class="st">idle</span><span class="note"></span></div>`).join("");
  document.getElementById("ring-name").textContent = `“${ringType()}”`;
  if (!sim.on) { sim.on = true; sim.last = performance.now(); requestAnimationFrame(frame); }
}

function frame(now) {
  const root = document.getElementById("live-root");
  if (!root) { sim.on = false; return; }
  if (!root.dataset.started) { root.dataset.started = 1; startLive(); }
  const dt = Math.min(0.05, (now - sim.last) / 1000);
  sim.last = now; sim.t += dt;
  if (sim.t >= sim.next) { launch(); sim.next = sim.t + 0.3 + Math.random() * 0.4; }
  moveDots(dt); lanes(dt); counters(dt); raceLoop(dt);
  requestAnimationFrame(frame);
}

// One request: agent -> GRADUATE -> a model -> tests. A task type that has graduated goes to your model; a miss there is re-run on the big model.
function launch() {
  const S = sim.S, lane = sim.lanes.findIndex((l) => l.status === "idle");
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
    if (!k) el.setAttribute("filter", "url(#glow)");
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
      if (d.leg === 1) flash("grad", "hit");
      if (d.leg === 2) flash(d.route[1] === "yours" ? "yours" : "big", "hit");
      if (d.leg >= d.route.length) { d.done = true; finish(d); continue; }
    }
    d.els.forEach((el, k) => {
      const p = path.getPointAtLength(Math.max(0, Math.min(d.s - k * 14, len)));
      el.setAttribute("cx", p.x); el.setAttribute("cy", p.y);
    });
  }
  sim.dots = sim.dots.filter((d) => (d.done ? (d.els.forEach((el) => el.remove()), false) : true));
}

function flash(id, cls) {
  const n = document.getElementById(`n-${id}`);
  n.classList.remove(cls); void n.getBoundingClientRect(); n.classList.add(cls);
}

function finish(d) {
  const S = sim.S, m = d.mine ? S.mine : S.big, jit = 0.75 + Math.random() * 0.5;
  flash("tests", d.pass ? "pass" : "fail");
  sim.tokens += m.out * jit; sim.cost += m.cost * jit; sim.runs += d.pass ? 1 : 0; sim.yours += d.mine && d.pass ? 1 : 0;
  const step = S.steps[Math.floor(Math.random() * S.steps.length)];
  log(`<span class="who ${d.mine ? "mine" : "big"}">${d.rerun ? "big model · re-run" : d.mine ? "your model" : "big model"}</span><span class="what">${esc(step)}</span><span class="tok">${short(m.out * jit)} tok</span><span class="${d.pass ? "ok" : "bad"}">${d.pass ? "✓ tests pass" : "✗ tests fail"}</span>`);
  if (d.lane >= 0 && sim.lanes[d.lane]) sim.lanes[d.lane].status = d.pass ? "passed" : "failed";
  if (d.mine && !d.pass) addDot({ route: ["big", "bigOut"], mine: false, pass: true, type: d.type, lane: -1, speed: 1.2, rerun: true, pre: true });
  if (!d.mine && d.pass && !d.rerun && d.type === ringType() && !sim.graduated.has(d.type)) graduateStep(d.type);
}

// The task type filling the ring: the next one still learning, in turn.
const ringType = () => { const l = sim.S.learning.filter((t) => !sim.graduated.has(t)); return l.length ? l[sim.typeIx % l.length] : sim.S.types[0]; };

function graduateStep(type) {
  const S = sim.S;
  sim.ring = Math.min(S.n, sim.ring + 1);
  document.getElementById("ring").style.strokeDashoffset = 100 - (sim.ring / S.n) * 100;
  document.getElementById("ring-n").textContent = sim.ring;
  document.getElementById("ring-of").textContent = `of ${S.n} passing runs`;
  if (sim.ring < S.n) return;
  const st = document.getElementById("ring-state"), wrap = document.querySelector(".p-ring");
  st.textContent = "training your model…";
  wrap.classList.add("training");
  setTimeout(() => {
    if (!document.getElementById("live-root")) return;
    sim.graduated.add(type); wrap.classList.remove("training"); wrap.classList.add("graduated"); st.textContent = "GRADUATED · now runs on your model";
    log(`<span class="who grad">graduated</span><span class="what">“${esc(type)}” now runs on your model</span><span></span><span class="ok">✓</span>`);
    setTimeout(() => { // next task type starts learning
      if (!document.getElementById("live-root")) return;
      wrap.classList.remove("graduated"); sim.typeIx++; sim.ring = 0;
      if (sim.graduated.size >= S.types.length) sim.graduated = new Set(S.grads);
      document.getElementById("ring").style.strokeDashoffset = 100; document.getElementById("ring-n").textContent = 0;
      document.getElementById("ring-name").textContent = `“${ringType()}”`; st.textContent = "learning on the big model";
    }, 5000);
  }, 2600);
}

function log(html) {
  const ol = document.getElementById("log"), li = document.createElement("li");
  const ts = new Date().toISOString().slice(11, 19);
  li.innerHTML = `<time>${ts}</time>${html}`;
  ol.prepend(li);
  while (ol.children.length > 18) ol.lastChild.remove();
}

function lanes(dt) {
  sim.lanes.forEach((l, i) => {
    const el = document.getElementById(`lane-${i}`);
    if (!el) return;
    if (l.status === "working") l.busy = Math.min(1, l.busy + dt / l.dur);
    else if (l.status !== "idle") { l.hold = (l.hold || 0) + dt; if (l.hold > 1.2) { if (l.status === "passed" && Math.random() < 0.5) tip(i, l.type); Object.assign(l, { status: "idle", busy: 0, hold: 0 }); } }
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
}
const short = (v) => (v >= 1000 ? `${(v / 1000).toFixed(1)}k` : String(Math.round(v)));
const set = (id, v) => { const el = document.getElementById(id); if (el && el.textContent !== v) el.textContent = v; };

// The race: the same task on both models, 12-second loop. The big model takes 9 s; your model's time and both token
// counts keep the recorded averages' proportions.
function raceLoop(dt) {
  const S = sim.S;
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
