// #/swarm: one lane per `graduate swarm` agent (task, live status, turns, exit) and the notes agents share with each
// other (A2A), from /api/swarm (shape: fixtures/swarm.example.json); ?swarm=<url> points it elsewhere. Polls once a
// second while the view is open. Uses index.html's globals (render, route, esc, clock).
const SWARM_URL = new URLSearchParams(location.search).get("swarm") || "/api/swarm";
let swarm = null, swarmText = "";

async function pollSwarm() {
  if (route()[0] !== "swarm") return;
  const text = await fetch(SWARM_URL, { cache: "no-store" })
    .then((r) => r.ok ? r.text() : JSON.stringify({ error: `${SWARM_URL} answered ${r.status}.` }))
    .catch(() => JSON.stringify({ error: `${SWARM_URL} isn't reachable. Is the router running?` }));
  if (text === swarmText) return;
  swarmText = text;
  swarm = JSON.parse(text);
  render();
}
setInterval(pollSwarm, 1000);

function viewSwarm() {
  document.querySelector('[data-nav="swarm"]')?.setAttribute("aria-current", "page");
  if (!swarm) { pollSwarm(); return `<p class="lede">Loading the swarm…</p>`; }
  if (swarm.error) return `<h1>Swarm</h1><p class="lede">${esc(swarm.error)}</p>`;
  const agents = swarm.agents, count = (s) => agents.filter((a) => a.status === s).length;
  const who = Object.fromEntries(agents.filter((a) => a.session_id).map((a) => [a.session_id, a.agent]));
  const notes = (a) => [a.a2a_read && "read a note", a.a2a_write && "wrote a note"].filter(Boolean).join(" · ") || "—";
  const lanes = agents.map((a) => `<tr class="${esc(a.status)}" data-qa="lane-${esc(a.agent)}">
      <th scope="row">${esc(a.agent)}</th><td>${esc(a.task)} <small>${esc(a.task_type || "")}</small></td>
      <td class="st">${esc(a.status[0].toUpperCase() + a.status.slice(1))}</td><td>${a.turns ?? "—"}</td>
      <td>${a.exit_code ?? "—"}</td><td class="notes">${notes(a)}</td></tr>`).join("");
  const shown = agents.length > 7 ? 2 : 3;  // measured: lanes + notes fit a 720p projector up to 8 agents
  const feed = swarm.a2a.slice(-shown).reverse().map((e) => `<li>
      <time>${clock(e.ts, true)}</time><b>${esc(who[e.session_id] || e.session_id)}</b>
      <span class="dir">${e.edges.includes("a2a-write") ? "wrote" : "read"}</span><code>${esc(e.call)}</code>
      <span class="res">${esc(e.result)}</span></li>`).join("");
  return `<div class="swarm">
  <header class="show-head">
    <div><p class="kicker">Agents in parallel, sharing what they learn</p><h1>Swarm</h1></div>
    <p class="show-verify" data-qa="swarm-count">${count("passed")} passed · ${count("running")} running · ${count("failed")} failed · ${count("queued")} queued<br>
      ${esc(swarm.swarm_id)} · ${esc(swarm.launcher)} launcher · started ${clock(swarm.started)}</p>
  </header>
  <table class="show-cmp lanes">
    <thead><tr><th>Agent</th><th>Task</th><th>Status</th><th>Turns</th><th>Exit</th><th>Notes</th></tr></thead>
    <tbody>${lanes}</tbody>
  </table>
  <section><h2>Notes between agents, newest first</h2>
    ${feed ? `<ol class="a2a" data-qa="a2a">${feed}</ol>` : `<p class="muted">No notes read or written yet.</p>`}</section>
</div>`;
}

document.head.insertAdjacentHTML("beforeend", `<style>
#app:has(.swarm) { max-width: none; padding: 0 3vw; }
.swarm { display: grid; gap: calc(var(--u) * 2.4); font-size: calc(var(--u) * 2.6); }
.swarm .show-head { grid-area: auto; }
.swarm h1 { font-size: calc(var(--u) * 6); margin: 0; }
.swarm h2 { font-size: calc(var(--u) * 3); margin: 0 0 calc(var(--u) * 1); }
.swarm :is(small, .muted, time, .res) { color: var(--muted); font-size: 1em; font-weight: 400; }
.swarm code { font-size: calc(var(--u) * 2.5); }
.lanes .st::before { content: ""; display: inline-block; width: 0.6em; height: 0.6em; margin-right: 0.4em; border-radius: 50%; background: currentColor; }
.lanes .running .st { color: var(--owned); }
.lanes .running .st::before { animation: swarm-pulse 0.8s infinite alternate; }
.lanes .passed .st { color: var(--pass); }
.lanes .failed .st { color: var(--fail); }
.lanes .queued :is(td, th) { color: var(--muted); }
.lanes .notes { color: var(--owned); }
@keyframes swarm-pulse { to { opacity: 0.2; } }
.a2a { list-style: none; margin: 0; padding: 0; display: grid; gap: calc(var(--u) * 1.2); }
.a2a li { display: grid; grid-template-columns: auto auto auto minmax(0, 1fr); gap: 0 1em; align-items: baseline; }
.a2a .dir { font-weight: 700; color: var(--owned); }
.a2a code { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.a2a .res { grid-column: 2 / -1; }
</style>`);
