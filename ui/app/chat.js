// /app/chat: one fixed task (GET /api/chat-preset: files, failing pytest, instruction), sent once to your model and
// the big model at the same instant (POST /api/chat-compare {preset}), both proposed fixes streaming side by side. Loaded after app.js; registers itself in its PAGES and reuses $ and esc.
// chat() returns a constant shell (app.js re-renders #view only when that string changes); streaming fills it in place.
const CHAT = {
  small: { who: "Your model", wait: "Waiting for your model on River…" },
  big: { who: "Big model", wait: "Waiting for the first token…" },
};
const chatRun = { busy: false, sides: {}, note: "" };

function chat() {
  if (!document.getElementById("chat-css")) document.head.insertAdjacentHTML("beforeend", `<style id="chat-css">
.chat-ask{display:flex;gap:10px;margin-bottom:16px}
.chat-ask input{flex:1;min-width:0;font:inherit;padding:10px 14px;background:var(--sheet);color:var(--ink);border:1px solid var(--rule);border-radius:6px}
.chat-ask input:focus{border-color:var(--owned);outline:0}
.chat-ask .btn{margin:0;padding:10px 22px;font-weight:700}
.chat-panes{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.chat-pane{min-width:0;display:flex;flex-direction:column;background:var(--sheet);border:1px solid var(--rule);border-radius:8px;border-top:3px solid var(--c)}
.chat-pane.small{--c:var(--owned)}.chat-pane.big{--c:var(--big)}
.chat-pane header{display:flex;justify-content:space-between;align-items:baseline;gap:12px;padding:12px 16px;border-bottom:1px solid var(--rule)}
.chat-pane header b{color:var(--c);font-weight:800;letter-spacing:.02em}
.chat-pane header span{color:var(--muted);font-size:.85em;text-align:right;overflow-wrap:anywhere}
.chat-pane .status{color:var(--muted);font-size:.9em;padding:10px 16px 0;margin:0;min-height:1.4em}
.chat-pane pre{flex:1;margin:0;padding:8px 16px 14px;min-height:16em;max-height:50vh;overflow-y:auto;white-space:pre-wrap;overflow-wrap:anywhere;font:.88em/1.6 "JetBrains Mono",ui-monospace,monospace;color:var(--ink)}
.chat-pane footer{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border-top:1px solid var(--rule)}
.chat-pane footer div{padding:10px 16px;border-right:1px solid var(--rule);min-width:0}
.chat-pane footer div:last-child{border-right:0}
.chat-pane footer b{display:block;font-size:1.3em;font-weight:800;font-variant-numeric:tabular-nums}
.chat-pane footer span{color:var(--muted);font-size:.8em}
.chat-verdict{margin:16px 0 0}
.chat-env{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:12px}
.chat-env .card{min-width:0;padding:0;overflow:hidden}
.chat-env h3,.chat-out h3{margin:0;padding:8px 14px;font:600 .85em "JetBrains Mono",monospace;color:var(--muted);border-bottom:1px solid var(--rule)}
.chat-env pre,.chat-out pre{margin:0;padding:10px 14px;white-space:pre-wrap;overflow-wrap:anywhere;font:.85em/1.55 "JetBrains Mono",monospace;max-height:14em;overflow-y:auto}
.chat-out{margin-bottom:12px;padding:0;overflow:hidden}.chat-out pre{color:var(--fail)}
.chat-run{display:flex;align-items:center;gap:16px;margin:0 0 16px}.chat-run p{margin:0;color:var(--ink)}
.chat-run .btn{margin:0;padding:10px 22px;font-weight:700;white-space:nowrap}
@media (max-width:999px){.chat-env{grid-template-columns:1fr}}
@media (max-width:999px){.chat-pane footer{grid-template-columns:1fr}.chat-pane footer div{display:flex;justify-content:space-between;align-items:baseline;gap:8px;padding:6px 16px;border-right:0;border-bottom:1px solid var(--rule)}.chat-pane footer div:last-child{border-bottom:0}.chat-pane footer b{font-size:1.05em;order:2}.chat-pane header{flex-direction:column;gap:2px}.chat-pane header span{text-align:left}}
</style>`);
  const pane = (id) => `<section class="chat-pane ${id}" id="chat-${id}"><header><b>${CHAT[id].who}</b><span data-f="model"></span></header>
<p class="status" data-f="status"></p><pre data-f="out"></pre>
<footer><div><b data-f="tokens">–</b><span>output tokens</span></div><div><b data-f="cost">–</b><span>cost</span></div><div><b data-f="time">–</b><span>time to complete</span></div></footer></section>`;
  setTimeout(paintChat);
  const env = data.preset, pre = (t) => `<pre>${esc(t)}</pre>`;
  if (!env) fetch("/api/chat-preset").then((r) => r.json()).then((p) => { data.preset = p; render(); }).catch(() => {});
  return `<h1>Chat</h1><p class="lede">One fixed task, sent once. Your trained model and the big model get the same files and the same failing test at the same instant, and propose a fix side by side.</p>
${env && env.files ? `<div class="chat-env">${env.files.map((f) => `<section class="card"><h3>${esc(f.path)}</h3>${pre(f.text)}</section>`).join("")}</div>
<section class="card chat-out"><h3>$ ${esc(env.pytest.command)} · exit ${env.pytest.exit_code}</h3>${pre(env.pytest.output)}</section>
<form class="chat-run" id="chat-form"><button class="btn owned" id="chat-send">Run both</button><p><b>Task:</b> ${esc(env.instruction)} <span class="muted">${esc(env.title)}</span></p></form>` : `<p class="muted">Loading the task…</p>`}
<div class="chat-panes">${pane("small")}${pane("big")}</div><p class="banner chat-verdict" id="chat-verdict" hidden></p>`;
}

const chatName = (m) => String(m || "").startsWith("river://") ? `Qwen3.5-9B on River · ${String(m).split("/").pop()}` : `OpenAI ${m}`;

function paintChat() {
  if (!document.getElementById("chat-form")) return;
  $("#chat-send").disabled = chatRun.busy;
  for (const id of ["small", "big"]) {
    const s = chatRun.sides[id], el = document.getElementById(`chat-${id}`);
    const f = (k) => el.querySelector(`[data-f="${k}"]`);
    f("model").textContent = s && s.model ? chatName(s.model) : id === "small" ? "Qwen3.5-9B on River" : "OpenAI";
    if (!s) {
      f("status").textContent = "Press Run both.";
      f("out").textContent = "";
      for (const k of ["tokens", "cost", "time"]) f(k).textContent = "–";
      continue;
    }
    const secs = ((s.done ? s.done.wall_ms : performance.now() - s.t0) / 1000).toFixed(2);
    f("status").textContent = s.error || (s.done ? "Done." : s.text ? "Streaming…" : `${CHAT[id].wait} ${secs}s`);
    if (f("out").textContent !== s.text) f("out").textContent = s.text;
    f("tokens").textContent = s.done ? s.done.output_tokens : s.pieces ? `~${s.pieces}` : "–";
    f("cost").textContent = s.done ? `$${s.done.cost_usd.toFixed(6)}` : "–";
    f("time").textContent = s.done || !s.error ? `${secs}s` : "–";
  }
  const v = $("#chat-verdict"), a = chatRun.sides.small && chatRun.sides.small.done, b = chatRun.sides.big && chatRun.sides.big.done;
  v.hidden = !(chatRun.note || (a && b));
  if (a && b) {
    const x = a.cost_usd > 0 ? ` Your model cost ${(b.cost_usd / a.cost_usd).toFixed(1)}× less.` : "";
    v.textContent = `Your model: ${a.output_tokens} tokens, $${a.cost_usd.toFixed(6)}, ${(a.wall_ms / 1000).toFixed(2)}s. Big model: ${b.output_tokens} tokens, $${b.cost_usd.toFixed(6)}, ${(b.wall_ms / 1000).toFixed(2)}s.${x}`;
  } else if (chatRun.note) v.textContent = chatRun.note;
}

async function sendChat() {
  const t0 = performance.now();
  Object.assign(chatRun, { busy: true, note: "", sides: { small: { t0, text: "", pieces: 0 }, big: { t0, text: "", pieces: 0 } } });
  const timer = setInterval(paintChat, 100);
  try {
    const r = await fetch("/api/chat-compare", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ preset: (data.preset && data.preset.id) || "broken-09" }) });
    if (!r.ok) { const b = await r.json().catch(() => ({})); chatRun.sides = {}; chatRun.note = b.error || `The chat answered ${r.status}.`; return; }
    const reader = r.body.getReader(), dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n\n")) >= 0) {
        const line = buf.slice(0, i); buf = buf.slice(i + 2);
        if (!line.startsWith("data:")) continue;
        const e = JSON.parse(line.slice(5)), s = chatRun.sides[e.side];
        if (!s) continue;
        if (e.type === "start") s.model = e.model;
        else if (e.type === "delta") { s.text += e.text; s.pieces += 1; }
        else if (e.type === "done") s.done = e;
        else if (e.type === "error") s.error = e.message;
      }
      paintChat();
    }
  } catch {
    chatRun.note = "The chat stream broke off. Try again.";
  } finally {
    clearInterval(timer);
    chatRun.busy = false;
    paintChat();
  }
}

document.addEventListener("submit", (e) => {
  if (e.target.id !== "chat-form") return;
  e.preventDefault();
  if (!chatRun.busy) sendChat();
});
PAGES.chat = chat;
