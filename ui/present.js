// Showcase stage and presenter mode (#55). Uses index.html's globals (S, $, esc, money, tasks, N, ...).
// ?present or P hides the chrome and opens the showcase. In presenter mode: ←/→ switch stages,
// 1-3 jump, F fullscreen, B blackout, Esc leaves.
const STAGES = ["#/show", "#/", "#/system"];

// Averages over ledger rows. Frontier = the verified-run pool (escalation reruns excluded, contracts §2).
function arm(rows) {
  if (!rows.length) return null;
  const avg = (f) => rows.reduce((s, r) => s + (r[f] || 0), 0) / rows.length;
  return {
    n: rows.length, passed: rows.filter((r) => r.exit_code === 0).length,
    out: avg("output_tokens"), inp: avg("input_tokens"), cached: avg("cached_input_tokens"),
    cost: avg("cost_usd"), turns: avg("turns"), wall: avg("wall_secs"),
  };
}

// The task type on screen: #/show/<slug>, else the one with the newest ledger row.
function showTask(a) {
  const all = tasks();
  if (all[a]) return a;
  const last = [...S.ledger].reverse().find((r) => all[r.task_type]);
  return last ? last.task_type : Object.keys(all)[0];
}

const tok = (v) => v >= 1e5 ? `${Math.round(v / 1e3)}k` : v >= 1e4 ? `${(v / 1e3).toFixed(1)}k` : Math.round(v).toLocaleString();
const change = (f, o) => {
  if (o === 0 || f / o >= 3) return o === 0 ? "−100%" : `${Math.round(f / o)}× less`;
  const pct = Math.round((o / f - 1) * 100);
  return pct ? `${pct > 0 ? "+" : "−"}${Math.abs(pct)}%` : "same";
};

function viewShow(a) {
  const k = showTask(a), t = tasks()[k];
  if (!t) return `<h1>No task types yet</h1><p class="lede">Run a task with <code>graduate run</code> and it shows up here.</p>`;
  const rows = S.ledger.filter((r) => r.task_type === k);
  const f = arm(rows.filter((r) => r.routed_to === "frontier" && !r.escalated_from));
  const o = arm(rows.filter((r) => r.routed_to === "owned"));
  const n = N(), grad = t.state === "GRADUATED" || t.state === "PROBATION";
  const none = `<span class="muted">no runs yet</span>`;
  const cell = (x, fmt) => x ? fmt(x) : none;
  const row = (label, key, fmt, delta = true) => `<tr><th scope="row">${label}</th>
    <td data-qa="${key}-frontier">${cell(f, fmt)}</td><td class="own" data-qa="${key}-owned">${cell(o, fmt)}</td>
    <td class="chg">${delta && f && o && f[key] ? change(f[key], o[key]) : ""}</td></tr>`;
  const pass = (x) => `${x.passed} of ${x.n} <span class="muted">${Math.round((x.passed / x.n) * 100)}%</span>`;

  const esc_ = [...rows].reverse().find((r) => r.escalated_from);
  const failed = esc_ && S.ledger.find((r) => r.session_id === esc_.escalated_from);
  const negWired = esc_ && S.trace.some((e) => (e.nodes || []).includes("escalator"));
  const land = stampFor === k && Date.now() < stampUntil ? " land" : "";
  const stamp = t.state === "GRADUATED"
    ? `<div class="stamp${land}">Graduated<small>${clock(t.graduated_at)} · trained on ${t.trained_on_runs} runs</small></div>`
    : t.state === "PROBATION" ? `<div class="stamp probation">Probation<small>back on frontier</small></div>` : "";

  return `<div class="show">
  <header class="show-head">
    <div><p class="kicker">Task type</p><h1>${esc(t.title || k)}</h1></div>
    <p class="show-verify">Every run checked by <code>${esc(t.verify_command)}</code></p>
  </header>
  <section class="show-hero" aria-labelledby="hero-h">
    <h2 id="hero-h">Output tokens per run</h2>
    <p class="hero"><span class="f" data-qa="out-frontier">${f ? Math.round(f.out).toLocaleString() : "—"}</span><span class="arrow" aria-label="to">→</span><span class="o" data-qa="out-owned">${o ? Math.round(o.out).toLocaleString() : "—"}</span></p>
    <p class="hero-sub">${f && o ? `<b data-qa="out-change">${change(f.out, o.out)}</b> frontier model → your graduated model` : `Your model takes over after ${n} passing frontier runs`}</p>
    <table class="show-cmp">
      <thead><tr><th></th><th>Frontier</th><th class="own">Your model</th><th>Change</th></tr></thead>
      <tbody>
        ${row("Cost per run <small>est.</small>", "cost", (x) => money(x.cost))}
        ${row("Turns", "turns", (x) => round(x.turns))}
        ${row("Wall time", "wall", (x) => `${round(x.wall)}s`)}
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
    ${esc_ ? `<ol class="steps">
      <li class="fail">Your model failed · exit ${failed ? failed.exit_code : "≠0"}</li>
      <li class="pass">Re-ran on frontier · exit ${esc_.exit_code}</li>
      <li>Kept as a negative example ${negWired ? "" : `<span class="badge">Not wired</span>`}</li>
    </ol>` : `<p>A failed run on your model re-runs on the frontier. No escalations yet.</p>`}
    ${grad ? `<p class="muted">${t.failures_since_graduation} of ${S.config.fail_limit} failures before probation</p>` : ""}
  </section>
  <footer class="show-foot"><b data-qa="saved">${money(S.totals.saved_usd)}</b> saved across ${S.totals.owned_runs} runs on your models <span class="muted">· est.: tokens × list prices, frontier with caching on</span></footer>
</div>`;
}

const root = document.documentElement;
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
