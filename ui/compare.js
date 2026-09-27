// #/compare (#61): the same demo tasks through each arm, from `graduate bench`'s bench/latest/results.json
// (shape: fixtures/bench.example.json). ?bench=<url> points it elsewhere. Uses present.js's change() and secs().
const BENCH_URL = new URLSearchParams(location.search).get("bench") || "/bench/latest/results.json";
let bench = null;

function loadBench() {
  bench = { loading: true };
  fetch(BENCH_URL, { cache: "no-store" })
    .then((r) => r.ok ? r.json() : { error: `${BENCH_URL} answered ${r.status}.` })
    .catch(() => ({ error: `${BENCH_URL} isn't reachable.` }))
    .then((b) => { bench = b; render(); });
}

function claudePrice(r, p) {
  return ((r.input_tokens - r.cached_input_tokens) * p.input + r.cached_input_tokens * p.cached_input + r.output_tokens * p.output) / 1e6;
}

function claudeCost() {
  const p = S.config.reference;
  const rows = S.ledger.filter((r) => r.harness === "claude-code");
  if (!p || !rows.length) return `<section class="cmp-claude"><h2>Claude Code: Claude API vs through GRADUATE</h2><p class="lede">No Claude Code sessions yet. Run one with <code>graduate run --harness claude-code --task-file demo-repo/tasks/01.json --repo demo-repo</code>.</p></section>`;
  const pair = (label, api, us) => {
    const max = Math.max(api, us) || 1;
    return `<div class="metric" title="${esc(label)}: Claude API ${money(api)}, through GRADUATE ${money(us)}"><div class="label"><span>${esc(label)}</span><span>${api ? (us <= api ? Math.round((1 - us / api) * 100) + "% less" : Math.round((us / api - 1) * 100) + "% more") : ""}</span></div>
      <div class="bar rented"><span>Claude API</span><span class="track"><span class="fill" style="width:${(api / max) * 100}%;display:block"></span></span><span class="v">${money(api)}</span></div>
      <div class="bar owned"><span>Through GRADUATE</span><span class="track"><span class="fill" style="width:${Math.max((us / max) * 100, 1.5)}%;display:block"></span></span><span class="v">${money(us)}</span></div></div>`;
  };
  const recent = rows.slice(-6);
  const api = rows.reduce((a, r) => a + claudePrice(r, p), 0), us = rows.reduce((a, r) => a + r.cost_usd, 0);
  return `<section class="cmp-claude" data-qa="claude-cost"><h2>Claude Code: Claude API vs through GRADUATE</h2>
  <div class="compare">${pair(`All ${rows.length} Claude Code sessions`, api, us)}${recent.map((r) => pair(`${r.session_id} · ${r.routed_to} · exit ${r.exit_code}`, claudePrice(r, p), r.cost_usd)).join("")}</div>
  <p class="cmp-foot muted">Claude API: the same token counts at ${esc(p.model)} list prices ($${p.input} in, $${p.cached_input} cached, $${p.output} out per 1M), an estimate because tokenizers differ. Through GRADUATE: what the router paid for the session, frontier or your model.</p></section>`;
}

function viewCompare() {
  if (!bench) loadBench();
  const cc = claudeCost();
  if (bench.loading) return `${cc}<p class="lede">Loading the bench…</p>`;
  if (bench.error) return `${cc}<h1>Compare</h1><p class="lede">No bench results yet: ${esc(bench.error)} Run <code>graduate bench</code> (it prints its cost estimate and asks first).</p>`;
  const arms = [["frontier", "Frontier"], ["small", "Small model"], ["owned", "Your model"]].filter(([k]) => bench.arms[k]);
  const f = bench.arms.frontier, o = bench.arms.owned;
  const ran = (a) => a && a.runs > 0;
  const row = (label, key, fmt, cls = "") => `<tr class="${cls}"><th scope="row">${label}</th>${arms.map(([k]) => {
    const a = bench.arms[k];
    return `<td class="${k}" data-qa="cmp-${key}-${k}">${ran(a) && a[key] != null ? fmt(a[key], a) : `<span class="muted">${esc(a.note || "n/a")}</span>`}</td>`;
  }).join("")}<td class="chg">${ran(f) && ran(o) && key !== "passed" ? change(f[key], o[key]) : ""}</td></tr>`;
  const b = bench.budget;
  return `${cc}<div class="cmp">
  <header class="show-head">
    <div><p class="kicker">Same tasks, each model</p><h1>Compare</h1></div>
    <p class="show-verify">Tasks ${bench.tasks.map(esc).join(", ")} · ${esc(bench.started_at.slice(0, 16).replace("T", " "))}Z · ${esc(bench.git_sha)} · spent ${money(b.spent_usd)} of ${money(b.cap_usd)} cap</p>
  </header>
  <table class="show-cmp cmp-table">
    <thead><tr><th>Per run</th>${arms.map(([k, l]) => `<th class="${k}">${l}<small>${esc((bench.arms[k].model || "").split("/").pop())}</small></th>`).join("")}<th>Frontier → yours</th></tr></thead>
    <tbody>
      ${row("Output tokens", "output_tokens", (v) => Math.round(v).toLocaleString(), "lead")}
      ${row("Input tokens", "input_tokens", (v, a) => `${Math.round(v).toLocaleString()} <span class="muted">${Math.round((a.cached_input_tokens / (v || 1)) * 100)}% cached</span>`)}
      ${row("Cost <small>est.</small>", "cost_usd", money)}
      ${row("Turns", "turns", round)}
      ${row("Wall time <small>median</small>", "wall_secs_p50", secs)}
      ${row("Latency per call <small>median</small>", "latency_ms_p50", (v) => secs(v / 1000))}
      ${row("Tests pass", "passed", (v, a) => `${v} of ${a.runs}`)}
    </tbody>
  </table>
  <p class="cmp-foot muted">Means over ${f ? f.runs : 0} runs per arm. Cost is tokens × list prices (contracts §9), frontier with caching on.</p>
</div>`;
}
