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
.oc-panes{display:grid;grid-template-columns:1fr 1fr;gap:12px;height:420px}@media (max-height:800px){.oc-panes{height:340px}}
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
.oc-dim{color:#6B7589;margin:0}.oc-result{padding:6px 12px;border-top:1px solid #1B2130;min-height:2.1em;font-size:.84em}.oc-result:empty{display:none}.oc-result p{margin:0}.oc-ok{color:var(--pass);margin:4px 0 0;font-weight:700}.oc-bad{color:var(--fail);margin:4px 0 0;font-weight:700}
.oc-cursor{display:inline-block;width:.6em;background:#D6DBE5;animation:ocblink 1s steps(1) infinite}
@keyframes ocblink{50%{opacity:0}}
.oc-tiles{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border-top:1px solid #1B2130}
.oc-tiles div{padding:8px 12px;border-right:1px solid #1B2130;min-width:0}.oc-tiles div:last-child{border-right:0}
.oc-tiles b{display:block;font-size:1.25em;font-weight:700;color:#E8ECF4;font-variant-numeric:tabular-nums;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.oc-tiles span{font-size:.72em;color:#8A94A8}
.oc-tiles .win{background:#0F2A1C}.oc-tiles .win b{color:var(--pass)}
.oc-prompt{display:flex;align-items:center;gap:10px;padding:8px 12px;background:#07090D;border:1px solid #1B2130;border-radius:6px}
.oc-prompt b{color:var(--owned)}
.oc-prompt input{flex:1;min-width:0;background:transparent;border:0;color:#E8ECF4;font:inherit;font-size:.9em;outline:0}
.oc-prompt small{color:#6B7589;white-space:nowrap}
.oc-prompt button{display:none}
@media (max-width:999px){.oc-panes{grid-template-columns:1fr;height:auto}.oc-pane{height:360px}}
</style>`);
  const env = data.preset;
  if (!env) fetch("/api/chat-preset").then((r) => r.json()).then((p) => { data.preset = p; render(); }).catch(() => {});
  const pane = (id) => `<section class="oc-pane ${id}" id="chat-${id}"><header><b data-f="title">session</b><span data-f="model"></span></header>
<div class="oc-body"><div class="oc-user" data-f="user"></div><div class="oc-asst" data-f="out"></div></div>
<div class="oc-result" data-f="status"></div>
<footer class="oc-tiles"><div data-t="tokens"><b data-f="tokens">–</b><span>output tokens</span></div><div data-t="cost"><b data-f="cost">–</b><span>cost</span></div><div data-t="time"><b data-f="time">–</b><span>time to complete</span></div></footer></section>`;
  setTimeout(paintChat);
  return `<div class="oc">
<div class="oc-panes">${pane("small")}${pane("big")}</div><p class="oc-bar" id="chat-verdict" hidden></p>
<form class="oc-prompt" id="chat-form"><b>&gt;</b><input id="chat-q" maxlength="2000" value="${esc(env ? env.instruction : "")}" autocomplete="off" aria-label="Prompt for both models"><small>enter send</small><button id="chat-send">Send</button></form></div>`;
}

const chatName = (m, id) => (id === "small" ? "Qwen3.5-9B · River" : `${String(m || "gpt-5.5")} · OpenAI`);
// Thinking level: from the side's done event (the settings that call used), else the router's /api/thinking.
const thinkOf = (s, id) => (s && s.done && s.done.thinking) || (data.thinking && data.thinking.chat && data.thinking.chat[id]);

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
<details><summary class="fail">before the fix · pytest: ${env.pytest.exit_code ? "1 failed" : "passed"}</summary><pre class="fail">${esc(env.pytest.output)}</pre></details>`;
}

function paintChat() {
  if (!document.getElementById("chat-form")) return;
  const q = $("#chat-q");
  if (data.preset && !q.value && !chatRun.own) q.value = data.preset.instruction;
  q.disabled = chatRun.busy;
  for (const id of ["small", "big"]) {
    const s = chatRun.sides[id], el = document.getElementById(`chat-${id}`);
    const f = (k) => el.querySelector(`[data-f="${k}"]`), put = (k, h) => swap(f(k), h);
    put("title", esc(chatRun.own ? "session · your question" : `session · ${(data.preset && data.preset.title) || "fix the failing test"}`));
    const th = thinkOf(s, id);
    put("model", esc(chatName(s && s.model, id) + (th ? ` · thinking: ${th}` : "")));
    put("user", userTurn());
    const tile = (k, v) => { if (f(k).textContent !== v) f(k).textContent = v; };
    if (!s) { put("out", ""); put("status", "press enter to send to both"); tile("tokens", "–"); tile("cost", "–"); tile("time", "–"); continue; }
    const secs = ((s.done ? s.done.wall_ms : performance.now() - s.t0) / 1000).toFixed(2);
    const body = el.querySelector(".oc-body"), atEnd = body.scrollHeight - body.scrollTop - body.clientHeight < 40;
    const changed = put("out", md(s.text) + (!s.done && !s.error && s.text ? `<span class="oc-cursor">&nbsp;</span>` : ""));
    if (changed && atEnd && !s.done) body.scrollTop = body.scrollHeight;
    const v = s.verify, result = !v ? (s.done && !chatRun.own ? `<p class="oc-dim">applying the fix · running pytest…</p>` : "")
      : v.exit_code === 0 ? `<p class="oc-ok">✓ after the fix · pytest: ${esc(v.summary)}</p>`
      : v.exit_code == null ? `<p class="oc-dim">${esc(v.summary)}</p>` : `<p class="oc-bad">✗ still failing after the fix · ${esc(v.summary)}</p>`;
    put("status", s.error ? esc(s.error) : s.done ? result : s.text ? "" : `thinking… ${secs}s`);
    tile("tokens", s.done ? String(s.done.output_tokens) : s.pieces ? `~${s.pieces}` : "–");
    tile("cost", s.done ? `$${s.done.cost_usd.toFixed(6)}` : "–");
    tile("time", s.error && !s.done ? "–" : `${secs}s`);
  }
  const v = $("#chat-verdict"), a = chatRun.sides.small && chatRun.sides.small.done, b = chatRun.sides.big && chatRun.sides.big.done;
  // Once both finish, mark the lower value of each tile (a tie marks neither): never a win the numbers don't show.
  for (const [k, fa, fb] of [["tokens", a && a.output_tokens, b && b.output_tokens], ["cost", a && a.cost_usd, b && b.cost_usd], ["time", a && a.wall_ms, b && b.wall_ms]]) {
    const win = a && b && fa !== fb ? (fa < fb ? "small" : "big") : null;
    for (const id of ["small", "big"]) document.querySelector(`#chat-${id} [data-t="${k}"]`)?.classList.toggle("win", win === id);
  }
  v.hidden = !(chatRun.note || (a && b));
  if (a && b) {
    const r = a.cost_usd > 0 ? b.cost_usd / a.cost_usd : 0;
    const x = r >= 1.1 ? ` · your model cost ${r.toFixed(1)}× less` : r > 0 && r <= 1 / 1.1 ? ` · your model cost ${(1 / r).toFixed(1)}× more` : r ? " · about the same cost" : "";
    const va = chatRun.sides.small.verify, vb = chatRun.sides.big.verify, t = (v) => (!v ? "" : v.exit_code === 0 ? "test passed" : v.exit_code == null ? "no fix tested" : "test failed");
    const tests = va || vb ? `  |  tests: your model ${t(va) || "running…"}, big model ${t(vb) || "running…"}` : "";
    v.textContent = `your model ${a.output_tokens} tokens · $${a.cost_usd.toFixed(6)} · ${(a.wall_ms / 1000).toFixed(2)}s  |  big model ${b.output_tokens} tokens · $${b.cost_usd.toFixed(6)} · ${(b.wall_ms / 1000).toFixed(2)}s${x}${tests}`;
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
        else if (e.type === "verify") s.verify = e;
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
PAGES.race = () => `${chat()}<h2 class="rec-h">Recorded races</h2>${whyTasks()}${compare().replace(/<h1>[^<]*<\/h1>/, "")}`;

// "Why these tasks": which runs trained your model, which raced it, and which never reached it, all from the ledger
// and the registry's graduated_at (no task numbers written here by hand).
function whyTasks() {
  const s = data.state; if (!s) return "";
  const reg = s.registry.task_types || {}, rows = s.ledger || [];
  const [slug, g] = Object.entries(reg).find(([, t]) => t.state === "GRADUATED" && t.graduated_at) || [];
  if (!g) return "";
  const n = (r) => (String(r.verify_command || r.prompt || "").match(/test_mod_(\d+)/) || [])[1];
  const list = (rs) => { const x = [...new Set(rs.map(n).filter(Boolean))].sort(); return x.length > 1 ? `${x.slice(0, -1).join(", ")} and ${x.at(-1)}` : x[0] || ""; };
  const before = rows.filter((r) => r.task_type === slug && r.routed_to === "frontier" && r.exit_code === 0 && String(r.started_at) < g.graduated_at);
  const raced = rows.filter((r) => r.task_type === slug && r.routed_to === "owned" && r.exit_code === 0 && String(r.started_at) >= g.graduated_at);
  const other = rows.filter((r) => r.task_type !== slug);
  const types = [...new Set(other.map((r) => (reg[r.task_type] || {}).title || r.task_type))];
  const lines = [];
  if (before.length) lines.push(`Tasks ${list(before)} were your model's training data: the big model solved them first and your model learned from those runs, so racing on them would grade it on questions it studied.`);
  if (raced.length) lines.push(`After it graduated, new tasks went to your model: it passed ${list(raced)}, none of them part of those training runs. The big model was then run on the same tasks so both sides face the same unseen task.`);
  if (other.length) lines.push(`${other.length === 1 ? "Task" : "Tasks"} ${list(other)} ${other.length === 1 ? "was" : "were"} classified as <span title="${esc(types.join(", "))}">a different task type</span>, still learning, so ${other.length === 1 ? "it" : "they"} went to the big model and never reached your model.`);
  return lines.length ? `<section class="panel why-tasks"><h2>Why these tasks</h2>${lines.map((l) => `<p>${l}</p>`).join("")}</section>` : "";
}
PAGES.chat = PAGES.race;
