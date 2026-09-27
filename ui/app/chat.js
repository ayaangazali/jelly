// /app/chat: one prompt, sent once to your model and the big model at the same instant (POST /api/chat-compare),
// both answers streaming side by side. Loaded after app.js; registers itself in its PAGES and reuses esc/money.
const CHAT = {
  small: { title: "YOUR MODEL", cmd: "graduate race ask owned", chip: "Qwen3.5-9B · River", wait: "Sending request to your model (Qwen3.5-9B, LoRA on River)... Waiting for the answer..." },
  big: { title: "FRONTIER", cmd: "graduate race ask frontier", chip: "gpt-5.5", wait: "Sending request to OpenAI gpt-5.5... Waiting for first token..." },
};
const chatRun = { busy: false, sides: {}, note: "" };

function chat() {
  if (!document.getElementById("chat-css")) document.head.insertAdjacentHTML("beforeend", `<style id="chat-css">
main:has(.chat){max-width:none}
.chat{background:#F29BB4;border-radius:10px;padding:14px;margin-top:8px}
.chat form{display:flex;gap:10px;margin-bottom:14px}
.chat input{flex:1;min-width:0;font:inherit;font-size:15px;padding:10px 12px;border:0;border-radius:6px;background:#FFF8F0;color:#2A2226}
.chat button{font:inherit;font-weight:600;padding:10px 20px;border:0;border-radius:6px;background:#3A2F33;color:#FFF8F0;cursor:pointer}
.chat button:disabled{opacity:.5;cursor:default}
.chat .panes{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.chat .term{position:relative;min-width:0;background:#463A3E;color:#E9E1DA;border-radius:10px;padding:14px 18px 64px;min-height:420px;font-family:"JetBrains Mono",ui-monospace,monospace;font-size:13px;line-height:1.6}
.chat .bar{display:flex;align-items:center;gap:7px;margin-bottom:10px}
.chat .bar i{width:12px;height:12px;border-radius:50%;display:inline-block}
.chat .bar h2{flex:1;text-align:center;margin:0 60px 0 0;font:600 15px "JetBrains Mono",monospace;letter-spacing:.06em;color:#F4EEE8}
.chat .cmd{color:#F4EEE8;margin:0 0 6px}
.chat .dim{color:#A8999C;margin:0 0 10px}
.chat pre{white-space:pre-wrap;overflow-wrap:anywhere;margin:0;font:inherit;max-height:52vh;overflow-y:auto}
.chat .s{color:#F09AAE}.chat .n{color:#9ED9A6}.chat .c{color:#F4D58D}
.chat .foot{margin-top:12px;color:#E9E1DA}
.chat .chip{position:absolute;left:50%;bottom:10px;transform:translateX(-50%);background:#EFE9DC;color:#2A2226;border-radius:4px;padding:6px 18px;white-space:nowrap;font-size:14px;outline:1px solid #2A2226;outline-offset:-5px}
.chat .verdict{margin:14px 0 0;background:#FFF8F0;color:#2A2226;border-radius:6px;padding:10px 14px;font-family:"JetBrains Mono",monospace;font-size:13px;overflow-wrap:anywhere}
@media (max-width:1100px){.chat .term{padding:12px 12px 60px;font-size:12px}.chat .bar h2{margin-right:0;font-size:13px}.chat .chip{font-size:12px;padding:5px 10px}}
</style>`);
  const pane = (id) => `<section class="term" id="chat-${id}"><div class="bar"><i style="background:#FF5F57"></i><i style="background:#FEBC2E"></i><i style="background:#28C840"></i><h2>${CHAT[id].title}</h2></div>
<p class="cmd">$ ${CHAT[id].cmd}</p><p class="dim" data-f="status"></p><pre data-f="out"></pre><div class="foot" data-f="foot"></div><span class="chip">[ ${CHAT[id].chip} ]</span></section>`;
  setTimeout(paintChat);
  return `<h1>Chat</h1><p class="lede">One prompt, sent once: your trained model and the big model get it at the same instant and answer side by side.</p>
<div class="chat"><form id="chat-form"><input id="chat-q" maxlength="2000" placeholder="Ask both models something…" autocomplete="off"><button id="chat-send">Send</button></form>
<div class="panes">${pane("small")}${pane("big")}</div><p class="verdict" id="chat-verdict" hidden></p></div>`;
}

// Light colouring for streamed text: "strings", numbers, `code`; every piece escaped on its own.
const tint = (t) => String(t).split(/("[^"\n]*"|`[^`\n]+`|\b\d+(?:\.\d+)?\b)/).map((p, i) => i % 2 ? `<span class="${p[0] === '"' ? "s" : p[0] === "`" ? "c" : "n"}">${esc(p)}</span>` : esc(p)).join("");

function paintChat() {
  if (!document.getElementById("chat-form")) return;
  $("#chat-send").disabled = chatRun.busy;
  for (const id of ["small", "big"]) {
    const s = chatRun.sides[id], el = document.getElementById(`chat-${id}`);
    const f = (k) => el.querySelector(`[data-f="${k}"]`);
    if (!s) { f("status").textContent = "Type a prompt above and press Send."; f("out").innerHTML = ""; f("foot").innerHTML = ""; continue; }
    const secs = ((s.done ? s.done.wall_ms : performance.now() - s.t0) / 1000).toFixed(3);
    f("status").textContent = s.error ? s.error : s.done ? "" : s.text ? `streaming · ~${s.pieces} tokens so far` : `${CHAT[id].wait} ${secs}s`;
    f("out").innerHTML = tint(s.text);
    f("foot").innerHTML = s.done ? `cost $${s.done.cost_usd.toFixed(6)}<br>completed in ${secs}s · ${s.done.output_tokens} output tokens` : "";
  }
  const v = $("#chat-verdict"), a = chatRun.sides.small && chatRun.sides.small.done, b = chatRun.sides.big && chatRun.sides.big.done;
  v.hidden = !(chatRun.note || (a && b));
  if (a && b) {
    const x = a.cost_usd > 0 ? ` · your model cost ${(b.cost_usd / a.cost_usd).toFixed(1)}× less` : "";
    v.textContent = `Your model: ${a.output_tokens} tokens, $${a.cost_usd.toFixed(6)}, ${(a.wall_ms / 1000).toFixed(2)}s  |  Big model: ${b.output_tokens} tokens, $${b.cost_usd.toFixed(6)}, ${(b.wall_ms / 1000).toFixed(2)}s${x}`;
  } else if (chatRun.note) v.textContent = chatRun.note;
}

async function sendChat(prompt) {
  const t0 = performance.now();
  Object.assign(chatRun, { busy: true, note: "", sides: { small: { t0, text: "", pieces: 0 }, big: { t0, text: "", pieces: 0 } } });
  const timer = setInterval(paintChat, 100);
  try {
    const r = await fetch("/api/chat-compare", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ prompt }) });
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
        if (e.type === "delta") { s.text += e.text; s.pieces += 1; }
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
  const q = $("#chat-q").value.trim();
  if (q && !chatRun.busy) sendChat(q);
});
PAGES.chat = chat;
