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
.oc{display:flex;flex-direction:column;gap:10px;font-family:"JetBrains Mono",ui-monospace,monospace}
.oc-bar{margin:0;padding:6px 12px;border:1px solid var(--rule);border-radius:6px;font-size:.82em;color:var(--ink);background:var(--sheet)}
.oc-panes{display:grid;grid-template-columns:1fr 1fr;gap:12px;height:calc(100vh - 190px);min-height:420px}
.oc-pane{min-width:0;display:flex;flex-direction:column;background:#07090D;border:1px solid #1B2130;border-radius:6px;overflow:hidden}
.oc-pane header{display:flex;justify-content:space-between;gap:12px;padding:6px 12px;border-bottom:1px solid #1B2130;font-size:.78em;color:#8A94A8}
.oc-pane header b{color:#E8ECF4;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.oc-pane header span{white-space:nowrap}
.oc-pane.small header span{color:var(--owned)}.oc-pane.big header span{color:var(--big)}
.oc-body{flex:1;overflow-y:auto;padding:10px 12px;font-size:.84em;line-height:1.55;color:#D6DBE5}
.oc-user{border-left:2px solid var(--owned);padding:4px 10px;margin-bottom:12px;background:#0C1019}
.oc-pane.big .oc-user{border-left-color:var(--big)}
.oc-user p{margin:0 0 6px;white-space:pre-wrap;overflow-wrap:anywhere}
.oc-user details{margin:2px 0}.oc-user summary{cursor:pointer;color:#8A94A8}
.oc-user details pre{margin:4px 0 6px;padding:6px 8px;background:#07090D;border:1px solid #1B2130;white-space:pre-wrap;overflow-wrap:anywhere;max-height:18em;overflow:auto}
.oc-user .fail{color:var(--fail)}
.oc-asst p{margin:0 0 8px;overflow-wrap:anywhere}.oc-asst code{color:#F5B94A}
.oc-asst pre{margin:6px 0 10px;padding:8px 10px;background:#0C1019;border:1px solid #1B2130;border-radius:4px;overflow-x:auto;white-space:pre}
.oc-asst pre code{color:#D6DBE5}.oc-asst .k{color:#C792EA}.oc-asst .s{color:#A5E075}.oc-asst .n{color:#F78C6C}.oc-asst .c{color:#6B7589}
.oc-dim{color:#6B7589;margin:0}
.oc-cursor{display:inline-block;width:.6em;background:#D6DBE5;animation:ocblink 1s steps(1) infinite}
@keyframes ocblink{50%{opacity:0}}
.oc-pane footer{padding:5px 12px;border-top:1px solid #1B2130;font-size:.76em;color:#8A94A8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.oc-prompt{display:flex;align-items:center;gap:10px;padding:8px 12px;background:#07090D;border:1px solid #1B2130;border-radius:6px}
.oc-prompt b{color:var(--owned)}
.oc-prompt input{flex:1;min-width:0;background:transparent;border:0;color:#E8ECF4;font:inherit;font-size:.9em;outline:0}
.oc-prompt small{color:#6B7589;white-space:nowrap}
.oc-prompt button{display:none}
@media (max-width:999px){.oc-panes{grid-template-columns:1fr;height:auto}.oc-pane{height:60vh}}
</style>`);
  const env = data.preset;
  if (!env) fetch("/api/chat-preset").then((r) => r.json()).then((p) => { data.preset = p; render(); }).catch(() => {});
  const pane = (id) => `<section class="oc-pane ${id}" id="chat-${id}"><header><b data-f="title">session</b><span data-f="model"></span></header>
<div class="oc-body"><div class="oc-user" data-f="user"></div><div class="oc-asst" data-f="out"></div><p class="oc-dim" data-f="status"></p></div>
<footer data-f="foot">tokens – · $– · –s</footer></section>`;
  setTimeout(paintChat);
  return `<div class="oc"><p class="oc-bar" id="chat-verdict" hidden></p>
<div class="oc-panes">${pane("small")}${pane("big")}</div>
<form class="oc-prompt" id="chat-form"><b>&gt;</b><input id="chat-q" maxlength="2000" value="${esc(env ? env.instruction : "")}" autocomplete="off" aria-label="Prompt for both models"><small>enter send</small><button id="chat-send">Send</button></form></div>`;
}

const chatName = (m, id) => (id === "small" ? "Qwen3.5-9B · River" : `${String(m || "gpt-5.5")} · OpenAI`);

// Markdown, the small safe subset: ```code``` blocks (syntax-coloured), `inline code`, paragraphs and line breaks.
function md(text) {
  const plain = (t) => esc(t).replace(/`([^`\n]+)`/g, "<code>$1</code>").split(/\n{2,}/).map((p) => `<p>${p.replace(/\n/g, "<br>")}</p>`).join("");
  const code = (t) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(
    /(#[^\n]*)|("(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*')|\b(def|return|import|from|class|if|elif|else|for|in|while|True|False|None|assert|and|or|not|with|as|lambda)\b|\b(\d+(?:\.\d+)?)\b/g,
    (m, c, str, k, n) => (c ? `<span class="c">${c}</span>` : str ? `<span class="s">${str}</span>` : k ? `<span class="k">${k}</span>` : `<span class="n">${n}</span>`));
  return String(text).split("```").map((seg, i) => (i % 2 ? `<pre><code>${code(seg.replace(/^[\w+-]*\n/, ""))}</code></pre>` : plain(seg))).join("");
}

function userTurn() {
  const env = data.preset, own = chatRun.own;
  if (own) return `<p>${esc(own)}</p>`;
  if (!env || !env.files) return `<p class="oc-dim">Loading the task…</p>`;
  return `<p>${esc(env.instruction)}</p>${env.files.map((f) => `<details><summary>${esc(f.path)}</summary><pre>${esc(f.text)}</pre></details>`).join("")}
<details><summary class="fail">pytest: ${env.pytest.exit_code ? "1 failed" : "passed"}</summary><pre class="fail">${esc(env.pytest.output)}</pre></details>`;
}

function paintChat() {
  if (!document.getElementById("chat-form")) return;
  const q = $("#chat-q");
  if (data.preset && !q.value && !chatRun.own) q.value = data.preset.instruction;
  q.disabled = chatRun.busy;
  for (const id of ["small", "big"]) {
    const s = chatRun.sides[id], el = document.getElementById(`chat-${id}`);
    const f = (k) => el.querySelector(`[data-f="${k}"]`), put = (k, h) => { if (f(k).innerHTML !== h) f(k).innerHTML = h; };
    put("title", esc(chatRun.own ? "session · your question" : `session · ${(data.preset && data.preset.title) || "fix the failing test"}`));
    put("model", esc(chatName(s && s.model, id)));
    put("user", userTurn());
    if (!s) { put("out", ""); put("status", "press enter to send to both"); put("foot", "tokens – · $– · –s"); continue; }
    const secs = ((s.done ? s.done.wall_ms : performance.now() - s.t0) / 1000).toFixed(2);
    put("out", md(s.text) + (!s.done && !s.error && s.text ? `<span class="oc-cursor">&nbsp;</span>` : ""));
    put("status", esc(s.error || (s.done ? "" : s.text ? "" : `thinking… ${secs}s`)));
    put("foot", s.done ? `tokens ${s.done.output_tokens} · $${s.done.cost_usd.toFixed(6)} · ${secs}s` : `tokens ${s.pieces ? `~${s.pieces}` : "–"} · $– · ${secs}s`);
  }
  const v = $("#chat-verdict"), a = chatRun.sides.small && chatRun.sides.small.done, b = chatRun.sides.big && chatRun.sides.big.done;
  v.hidden = !(chatRun.note || (a && b));
  if (a && b) {
    const x = a.cost_usd > 0 ? ` · your model cost ${(b.cost_usd / a.cost_usd).toFixed(1)}× less` : "";
    v.textContent = `your model ${a.output_tokens} tokens · $${a.cost_usd.toFixed(6)} · ${(a.wall_ms / 1000).toFixed(2)}s  |  big model ${b.output_tokens} tokens · $${b.cost_usd.toFixed(6)} · ${(b.wall_ms / 1000).toFixed(2)}s${x}`;
  } else if (chatRun.note) v.textContent = chatRun.note;
}

async function sendChat(own) {
  const t0 = performance.now();
  Object.assign(chatRun, { own: own || null, busy: true, note: "", sides: { small: { t0, text: "", pieces: 0 }, big: { t0, text: "", pieces: 0 } } });
  const timer = setInterval(paintChat, 100);
  try {
    const body = own ? { prompt: own } : { preset: (data.preset && data.preset.id) || "broken-09" };
    const r = await fetch("/api/chat-compare", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!r.ok) { chatRun.sides = {}; chatRun.note = await refusal(r); return; }
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

// Every refusal in plain words, never raw JSON: the server's own sentence, or what the status means.
async function refusal(r) {
  const b = await r.json().catch(() => null);
  if (r.status === 429) return b && /budget/i.test(b.error || "") ? "Demo budget reached, try again later." : "Too many requests from you, try again in a few minutes.";
  if (b && typeof b.error === "string" && !/[{}]/.test(b.error)) return b.error;
  return "The chat couldn't answer right now. Try again in a moment.";
}

// One box, prefilled with the task: sent unchanged it runs the preset (with its files); edited, it is the person's own prompt.
document.addEventListener("submit", (e) => {
  if (e.target.id !== "chat-form") return;
  e.preventDefault();
  const q = $("#chat-q").value.trim();
  if (q.length > 2000) { chatRun.note = "Keep it under 2,000 characters."; paintChat(); return; }
  if (!q || chatRun.busy) return;
  sendChat(data.preset && q === String(data.preset.instruction).trim() ? undefined : q);
});
PAGES.chat = chat;
// Race and Chat are one page: the live chat on top, the recorded race pairs of real runs below.
PAGES.race = () => `${chat()}<h2 class="rec-h">Recorded races</h2>${compare().replace(/<h1>[^<]*<\/h1>/, "")}`;
PAGES.chat = PAGES.race;
