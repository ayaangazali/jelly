// Verified-response cache (#144): its hit rate, turns replayed and $ saved on the Overview, from /api/cache
// (?cache=<url> points it elsewhere), kept apart from the owned model's savings; and a `cache` node on Under the hood
// that the router's "Router → Cache" trace events light up. Polls once a second. Loaded after index.html's script:
// uses its globals (NODES, NODE, COL, ROW, money, render).
const CACHE_URL = new URLSearchParams(location.search).get("cache") || "/api/cache";
let cacheStats = null, cacheText = "";

async function pollCache() {
  const text = await fetch(CACHE_URL, { cache: "no-store" }).then((r) => (r.ok ? r.text() : "")).catch(() => "");
  if (!text || text === cacheText) return;
  cacheText = text;
  cacheStats = JSON.parse(text);
  render();
}
setInterval(pollCache, 1000);
pollCache();

function cacheOverview() {
  const c = cacheStats;
  if (!c || !(c.hits || c.entries)) return "";
  return `<div class="savings cache" data-qa="cache"><span class="amount">${money(c.saved_usd)}</span>
      <span class="what">saved by the verified cache: ${c.hits} of ${c.turns} calls replayed at $0, ${Math.round(c.hit_rate * 100)}% hit rate<small>What the frontier would have charged for those calls. Not your model's savings; the tests still decide every session. ${c.entries} answers cached, ${c.evicted} evicted.</small></span></div>`;
}

NODES.push({ id: "cache", c: "D", r: 1, label: "Cache", sub: "verified replays, $0", issues: [144],
  what: "Answers a call from an earlier verified frontier session when the whole conversation so far and the tools match exactly. No model runs, and the task's tests still decide the session. A replay that fails its tests is evicted.",
  calls: ["sha256(messages + tools) → sessions/<verified id>.jsonl"], files: [] });
NODE.cache = { ...NODES[NODES.length - 1], x: COL.D, y: ROW[1] };
