// /app/pricing: every model call from metrics.jsonl (GET /api/pricing), newest first, with its tokens, the per-1M
// prices it was costed at, and its cost; totals per model and overall on top; a model filter. Uses app.js's globals.
function pricing() {
  const d = data.pricing;
  if (!d) return `<h1>Pricing logs</h1><p class="lede">Loading…</p>`;
  if (d.error) return `<h1>Pricing logs</h1>${empty("Pricing logs need the router restarted with GET /api/pricing.")}`;
  const calls = d.calls || [], role = (c) => (c.upstream === "owned" ? "owned" : "frontier");
  const name = (c) => (c.upstream === "owned" ? `your model${String(c.model || "").startsWith("river://") ? " · River" : ""}` : c.model || "big model");
  const models = [...new Set(calls.map(name))], pick = data.pricingModel || "";
  const shown = pick ? calls.filter((c) => name(c) === pick) : calls, sum = (rs, k) => rs.reduce((a, c) => a + (c[k] || 0), 0);
  const price = (c) => { const p = (d.prices || {})[role(c)] || {}; return `$${p.input ?? "–"} / $${p.output ?? "–"}`; };
  return `<h1>Pricing logs</h1>
<div class="kpis ptot">${[["all calls", calls], ...models.map((m) => [m, calls.filter((c) => name(c) === m)])].map(([m, rs]) =>
    `<div class="kpi"><b>${money(sum(rs, "cost_usd"))}</b><span>${esc(m)} · ${rs.length} calls</span></div>`).join("")}</div>
<div class="race-bar"><select id="pmodel"><option value="">All models</option>${models.map((m) => `<option ${m === pick ? "selected" : ""}>${esc(m)}</option>`).join("")}</select></div>
${shown.length ? `<div class="scroll"><table class="plog"><thead><tr><th>Time</th><th>Model</th><th class="num">Input</th><th class="num">Cached</th><th class="num">Output</th><th class="num">Price per 1M in / out</th><th class="num">Cost</th></tr></thead><tbody>
${shown.slice(0, 300).map((c) => `<tr><td><code>${esc(String(c.ts || "").slice(11, 19))}</code></td><td>${esc(name(c))}</td><td class="num">${num(c.input_tokens || 0)}</td><td class="num">${num(c.cached_input_tokens || 0)}</td><td class="num">${num(c.output_tokens || 0)}</td><td class="num">${price(c)}</td><td class="num">${money(c.cost_usd || 0)}</td></tr>`).join("")}
</tbody></table></div>` : empty("No model calls recorded yet.")}`;
}
document.addEventListener("change", (e) => { if (e.target.id === "pmodel") { data.pricingModel = e.target.value; render(); } });
