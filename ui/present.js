// Showcase stage and presenter mode (#55). Uses index.html's globals (S, $, esc, money, tasks, N, ...).
// ?present or P hides the chrome and opens the showcase. In presenter mode: ←/→ switch stages,
// 1-4 jump, F fullscreen, B blackout, Esc leaves.
const STAGES = ["#/show", "#/compare", "#/", "#/system"];

// Averages over ledger rows. Frontier = the verified-run pool (escalation reruns excluded, contracts §2).
function arm(rows) {
  if (!rows.length) return null;
  const avg = (f) => rows.reduce((s, r) => s + (r[f] || 0), 0) / rows.length;
  return {
    n: rows.length, passed: rows.filter((r) => r.exit_code === 0).length,
    out: avg("output_tokens"), cost: avg("cost_usd"), turns: avg("turns"), wall: avg("wall_secs"),
  };
}

// The task type on screen: #/show/<slug>, else the one with the newest ledger row.
function showTask(a) {
  const all = tasks();
  if (all[a]) return a;
  const last = [...S.ledger].reverse().find((r) => all[r.task_type]);
  return last ? last.task_type : Object.keys(all)[0];
}

const secs = (v) => v < 1 ? `${Math.round(v * 1000)}ms` : v < 10 ? `${v.toFixed(1)}s` : `${Math.round(v)}s`;
// Changes come from unrounded averages; a zero on either side makes no claim.
const change = (f, o) => {
  if (!o || !f) return "";
  if (f / o >= 3) return `${Math.round(f / o)}× less`;
  const pct = Math.round((o / f - 1) * 100);
  return pct ? `${pct > 0 ? "+" : "−"}${Math.abs(pct)}%` : "same";
};

function viewShow(a) {
  const k = showTask(a), t = tasks()[k];
  if (!t) return `<h1>No task types yet</h1><p class="lede">Run a task with <code>graduate run</code> and it shows up here.</p>`;
  const rows = S.ledger.filter((r) => r.task_type === k);
  const f = arm(rows.filter((r) => r.routed_to === "frontier" && !r.escalated_from));
  // "Your model" only for a GRADUATED type with runs its model really served (not a fallback to the frontier
  // model), and a change is claimed only once one of them passed (#87).
  const owned = rows.filter((r) => r.routed_to === "owned");
  const served = owned.filter((r) => r.model !== (rows.find((x) => x.routed_to === "frontier") || {}).model);
  const fellBack = owned.length > served.length;
  const o = t.state === "GRADUATED" ? arm(served) : null, won = o && o.passed > 0;
  const n = N(), grad = t.state === "GRADUATED" || t.state === "PROBATION";
  // The savings headline needs a GRADUATED type whose own model passed a run in this ledger.
  const savedReal = S.ledger.some((r) => r.routed_to === "owned" && r.exit_code === 0 && (tasks()[r.task_type] || {}).state === "GRADUATED"
    && r.model !== (S.ledger.find((x) => x.task_type === r.task_type && x.routed_to === "frontier") || {}).model);
  const none = `<span class="muted">${t.state === "GRADUATED" ? "no runs yet" : "not graduated yet"}</span>`;
  const cell = (x, fmt) => x ? fmt(x) : none;
  const row = (label, key, fmt, delta = true) => `<tr><th scope="row">${label}</th>
    <td data-qa="${key}-frontier">${f ? fmt(f) : `<span class="muted">no runs yet</span>`}</td><td class="own" data-qa="${key}-owned">${cell(o, fmt)}</td>
    <td class="chg">${delta && f && won ? change(f[key], o[key]) : ""}</td></tr>`;
  const pass = (x) => `${x.passed} of ${x.n} <span class="muted">${Math.round((x.passed / x.n) * 100)}%</span>`;

  const esc_ = [...rows].reverse().find((r) => r.escalated_from);
  const failed = esc_ && S.ledger.find((r) => r.session_id === esc_.escalated_from);
  const negWired = esc_ && S.trace.some((e) => (e.nodes || []).includes("escalator"));
  const land = stampFor === k && Date.now() < stampUntil ? " land" : "";
  const stamp = t.state === "GRADUATED"
    ? `<div class="stamp${land}">Graduated<small>${clock(t.graduated_at)}${t.trained_on_runs ? ` · trained on ${t.trained_on_runs} runs` : ""}</small></div>`
    : t.state === "PROBATION" ? `<div class="stamp probation">Probation<small>back on frontier</small></div>` : "";

  return `<div class="show">
  <header class="show-head">
    <div><p class="kicker">Task type</p><h1>${esc(t.title || k)}</h1></div>
    <p class="show-verify">Every run checked by <code>${esc(t.verify_command)}</code></p>
  </header>
  <section class="show-hero" aria-labelledby="hero-h">
    <h2 id="hero-h">Output tokens per run</h2>
    <p class="hero"><span class="f" data-qa="out-frontier">${f ? Math.round(f.out).toLocaleString() : "—"}</span><span class="arrow" aria-label="to">→</span><span class="o" data-qa="out-owned">${o ? Math.round(o.out).toLocaleString() : "—"}</span></p>
    <p class="hero-sub">${f && won ? `<b data-qa="out-change">${change(f.out, o.out)}</b> frontier model → your graduated model`
      : o ? `Your model hasn't passed a run yet: its ${o.n} ${o.n === 1 ? "run" : "runs"} failed and went back to the frontier`
      : fellBack ? `<span class="badge">Not wired</span> owned serving: “your model” runs fell back to the frontier model`
      : t.state === "GRADUATED" ? "No runs on your model yet" : `Your model takes over after ${n} passing frontier runs`}</p>
    <table class="show-cmp">
      <thead><tr><th></th><th>Frontier</th><th class="own">Your model</th><th>Change</th></tr></thead>
      <tbody>
        ${row("Cost per run <small>est.</small>", "cost", (x) => money(x.cost))}
        ${row("Turns", "turns", (x) => round(x.turns))}
        ${row("Wall time", "wall", (x) => secs(x.wall))}
        ${row("Tests pass", "pass", pass, false)}
      </tbody>
    </table>
  </section>
  <section class="show-grad sheet" aria-labelledby="grad-h">
    <h2 id="grad-h">Graduation</h2>
    <p class="count"><b data-qa="verified">${Math.min(t.verified_runs, n)}</b> of ${n} passing frontier runs</p>
    <div class="bigpips">${Array.from({ length: n }, (_, i) => `<i class="${i < t.verified_runs ? "on" : ""}"></i>`).join("")}</div>
    <p><span class="state ${t.state}" data-qa="state">${STATE_TEXT[t.state]}</span> ${esc(HINT[t.state].replace("N", n))}</p>
    ${stamp}
  </section>
  <section class="show-esc sheet" aria-labelledby="esc-h">
    <h2 id="esc-h">Safety net</h2>
    ${esc_ && grad ? `<ol class="steps">
      <li class="fail">Your model failed · exit ${failed ? failed.exit_code : "≠0"}</li>
      <li class="pass">Re-ran on frontier · exit ${esc_.exit_code}</li>
      <li>${failed && failed.forced_failure ? "Forced failure (GRADUATE_FORCE_FAIL): not kept for training" : `Kept as a negative example ${negWired ? "" : `<span class="badge">Not wired</span>`}`}</li>
    </ol>` : `<p>A failed run on your model re-runs on the frontier.${grad ? " No escalations yet." : " It starts once this type graduates."}</p>`}
    ${grad ? `<p class="muted">${t.failures_since_graduation} of ${S.config.fail_limit} failures before probation</p>` : ""}
  </section>
  <footer class="show-foot">${savedReal ? `<b data-qa="saved">${money(S.totals.saved_usd)}</b> saved across ${S.totals.owned_runs} runs on your models <span class="muted">· est.: tokens × list prices, frontier with caching on</span>` : `<span class="muted" data-qa="saved">No savings yet: no graduated task type has a passing run on your model.</span>`}</footer>
</div>`;
}

// Presenter Under the hood (stage D): #53's live diagram, the latest call as a one-line ticker, the agent's last
// terminal lines large, and the nodes with no real call yet named.
function viewStage() {
  // Skip the per-call "logs every call" rows, or they hide the call they log.
  const last = S.trace.findLast((t) => t.edges.join() !== "log") || S.trace[S.trace.length - 1];
  const wired = new Set(S.trace.flatMap((t) => t.nodes));
  const idle = Object.values(NODE).filter((n) => !wired.has(n.id)).map((n) => n.label);
  return `<div class="stage-d">
  <header class="stage-head"><h1>Under the hood</h1>
    <p class="ticker" data-qa="ticker">${last ? `<time>${clock(last.ts, true)}</time> <b>${esc(last.who)}</b> <span class="call">${esc(last.call)}</span> <span class="res">→ ${esc(last.result)}</span>` : "No calls yet. Run a task with <code>graduate run</code>."}</p></header>
  <figure class="arch sheet">${archSvg()}</figure>
  <p class="legend">Solid: your machine · dashed: outside service · indigo: latest call · faded: no real call yet${idle.length ? ` <span class="badge" data-qa="no-calls">No calls yet</span> ${esc(idle.join(", "))}` : ""}</p>
  <pre class="term stage-term">${S.terminal.slice(-2).map((l) => `<span class="${termClass(l)}">${esc(l.replace(/\x1b\[[0-9;]*m/g, ""))}</span>`).join("\n") || `<span class="d">Waiting for a task…</span>`}</pre>
</div>`;
}

const root = document.documentElement;
// Fixture state (?state=…/fixtures/…, or a router started by `graduate up --demo`): every number on screen is sample data (#87).
if (/\/fixtures\//.test(new URLSearchParams(location.search).get("state"))) root.classList.add("sample");
else fetch("/api/sample").then((r) => r.json()).then((j) => j.sample && root.classList.add("sample")).catch(() => {});
const stage = () => "#/" + location.hash.slice(2).split("/")[0];
if (new URLSearchParams(location.search).has("present")) root.classList.add("present");
if (root.classList.contains("present") && !location.hash) location.hash = STAGES[0];

addEventListener("keydown", (e) => {
  if (e.ctrlKey || e.metaKey || e.altKey || e.target.closest("input, textarea")) return;
  const key = e.key.toLowerCase(), on = root.classList.contains("present");
  if (key === "p") root.classList.toggle("present");
  else if (!on) return;
  else if (key === "escape") root.classList.remove("present", "blackout");
  else if (key === "b") root.classList.toggle("blackout");
  else if (key === "f") document.fullscreenElement ? document.exitFullscreen() : root.requestFullscreen();
  else if (key === "arrowright" || key === "arrowleft") {
    const i = STAGES.indexOf(stage()) + (key === "arrowright" ? 1 : -1);
    location.hash = STAGES[(i + STAGES.length) % STAGES.length];
  } else if (STAGES[+key - 1]) location.hash = STAGES[+key - 1];
  else return;
  e.preventDefault();
});
