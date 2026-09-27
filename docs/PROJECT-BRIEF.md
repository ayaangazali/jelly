---
title: "Project Brief — what we're building, whether it's feasible, and how every sponsor fits"
project: "GRADUATE"
event: "Own Your Intelligence Hackathon (YC, 2026-09-27)"
purpose: "Single source of truth for scope and design. Where this file and the original pack disagree, this file wins, because it's based on primary-source research done after the pack was written."
updated: "2026-09-26"
related:
  - docs/research/river.md
  - docs/research/memorable-gbrain.md
  - docs/research/superset-qm-ufo.md
  - docs/research/harness-protocols.md
  - mock-up/index.html
---

# Project brief

## One paragraph

GRADUATE sits between a coding agent and its model. It records every agent session. After each one it runs the task's test command and keeps the exit code. Once one type of task has passed its tests 5 times, GRADUATE trains a small open model on River using those passing sessions. From then on it sends that task type to the small model. The tests still run after every session. When the small model's attempt fails, GRADUATE resets the repo, runs the task again on the frontier model, and keeps the failed attempt as a negative example. You own the weights.

## The agenda (Sunday 2026-09-27, Pacific time)

| Time | What happens | Issues |
|---|---|---|
| Sat night | Accounts and keys, demo repo, contracts, River SFT spike, Memorable setup, research questions to River on Discord | #2 #3 #4 #5 #9 #10 #11 #38 |
| Sun morning | Scaffold, proxy, session log, runner, dataset and trainer code, corpus, pre-trained fallback model, dashboard skeleton | #12–#15 #21 #22 #34 #35 #6 #7 |
| 12:00–1:00 | Lunch with the sponsor teams. Get the answers that unblock the build | #16 |
| 1:15–1:45 | Metrics and turn counting through the proxy | #17 |
| 1:45–2:15 | Registry, watcher, Memorable-based classifier | #18 #19 #20 #36 |
| 2:15–3:00 | Submit a real River training run live, in the background | #22 |
| 3:00–3:30 | Escalation on failure, River serving adapter | #23 #37 |
| 3:30–4:15 | Live dashboard, consent screen, and the live Under the hood view (real call trace, agent terminal, files on disk) | #24 #25 #39 |
| 4:15–4:35 | Scripted demo, real numbers, backup recording | #31 |
| 4:35–4:50 | Exactly one stretch goal | #26–#30 |
| 4:50–5:00 | Freeze and submit | #33 |
| 5:00–5:45 | Judging | #32 |

## Scope

**In (the demo must show all four):**
1. A task type graduating live, from 4 of 5 verified runs up to Graduated.
2. The same task on the owned model in fewer turns, with the tests still passing.
3. Cost per task against a frontier baseline with prompt caching on.
4. A deliberate failure caught by the tests, re-run on the frontier model, and saved as a negative example.

**What judges can see with their own eyes:** a real agent editing real code in the terminal panel, real test exit codes, River's training loss dropping step by step, a real checkpoint path, OpenAI's own usage numbers, and the diagram lighting up from real calls (#39).

**Out:**
- Codex support.
- Tasks that have no test command.
- Multi-tenant hosting.
- Our own model serving.
- Anything that needs a database change.
- UFO, which has no public integration surface (see research).

**Stretch (pick one at 4:35):**
- Claude Code support through `/v1/messages`.
- A QM agent routed through the proxy.
- `GRADUATED.md` in GBrain.
- An MCP status server.
- An Exit Code RL environment on River.

## What the research changed

The pack was written from marketing pages. The four reports in `docs/research/` read the actual docs and source code. Six findings change the build:

| # | The pack assumed | What's actually true | What we do instead |
|---|---|---|---|
| 1 | "One env var, `OPENAI_BASE_URL`, works for every harness" | No major harness reads `OPENAI_BASE_URL`. Claude Code speaks Anthropic Messages (`ANTHROPIC_BASE_URL`). Codex speaks only the Responses API (`wire_api = "chat"` was removed). OpenCode uses `baseURL` in `opencode.json`. Aider reads `OPENAI_API_BASE`. [harness-protocols.md](research/harness-protocols.md) | **The demo harness is OpenCode.** It speaks Chat Completions, has a curated Memorable tool registry, and is a Superset agent preset and a QM harness. The proxy speaks `/v1/chat/completions` only. Claude Code support via `/v1/messages` is a stretch goal (#26). The pitch says "one setting per tool", not "one env var". |
| 2 | River has a "submit dataset, poll job, get model id" fine-tune API | There is no job API and no dataset upload. SFT is **our own Python loop** over River primitives: `create_model(lora)`, `forward_backward`, `optim_step`, `save_weights`. We tokenize and mask the data ourselves. [river.md](research/river.md) | #21 builds tokenized records `{input_ids, target_tokens, weights}` with the base model's chat template. #22 runs the loop. Training is synchronous, so there is no job queue to wait on. |
| 3 | River serves any trained model on an OpenAI-compatible endpoint | The OpenAI-compatible endpoint exists only on **deployments**. These are gated: they need a team key and River has to switch them on. The fallback is `chat_complete_from_checkpoint` over gRPC (not streaming, and tool calls are unconfirmed). | #2 asks River to switch on deployments **tonight**. #37 builds a serving adapter that uses a deployment if we get one, or otherwise calls the checkpoint and fakes the stream. |
| 4 | Memorable's store gives us the training data | The local store is **AES-256-GCM encrypted**, and the CLI is closed source with a no-reverse-engineering licence. A procedure is a *minimized* list of steps with no command output or file contents, so it can't be used for SFT. Failed runs aren't retrievable. [memorable-gbrain.md](research/memorable-gbrain.md) | **The proxy's own session log (#35) is the training data**, because every request and response already passes through it. The **run ledger** (#34) records verify exit codes and is what graduation counts. Memorable is used for what it's best at: `memorable recall` becomes our task-type classifier (#20), and every verified session is sent in with `memorable ingest` (#36), so procedures build up and recall gets better. |
| 5 | Superset has `superset new "…" --agent claude` | The real command is `superset workspaces create --project … --agent opencode --prompt …`. There's no "wait until done" call and no usage or cost API. Setup scripts run *in parallel* with the agent unless an experimental setting is switched on. [superset-qm-ufo.md](research/superset-qm-ufo.md) | #8 uses the real commands. Our run ledger and proxy metrics are the source of truth for completion and cost. |
| 6 | Each run can be verified per call ("verify every graduated call") | A verify command checks the *repo state after a whole session*, not a single model call. | Verification and escalation happen **per session** in the runner (#34, #23). The proxy never blocks a single call waiting on tests. |

## Feasibility verdict

**The core demo is feasible in the window, provided five pre-conditions hold.** Each is its own issue with a named fallback:

| Pre-condition | Risk | Fallback | Issue |
|---|---|---|---|
| River key works and our account can use a small model (Qwen3.6-35B-A3B or Qwen3.5-9B) | Low | Ask River on Discord or at lunch. They're co-hosting and giving out credits (UNCONFIRMED tweet) | #2 |
| A LoRA SFT run on ~5 short sessions finishes in minutes | Medium. No published wall-clock | Pre-train Sunday morning (#7) and demo against that checkpoint | #3, #7 |
| The trained model can be called from the proxy | **High.** Deployments are gated | Use the checkpoint over gRPC with a faked stream (#37). Worst case, the base model plus the Memorable procedure in the prompt, stated honestly | #2, #37 |
| OpenCode can act as the agent on a small model with tool calls | Medium | Qwen3.x models are tool-capable. Keep the demo task tiny (one failing assertion) | #5, #37 |
| The frontier baseline has caching on and reports cached tokens | Low. OpenAI caching is automatic and reports `usage.prompt_tokens_details.cached_tokens` | none needed | #17 |

**Honest limits to say out loud:**
- Five examples is a tiny training set. The design is safe anyway because every graduated session is verified and escalated on failure.
- "Fewer turns" comes both from training and from the task being narrow. Report real measured numbers only.
- RL in the window is a stretch. River's reward code runs in our own process, which makes Exit Code RL genuinely implementable (#30), but no duration numbers exist.

## How each sponsor is used

| Sponsor | Role | Depth | Exactly what we call |
|---|---|---|---|
| **River** | Trains and serves the owned model | Core | `river-client` (`pip install river-client`): `Client()`, `session.create_model(base, lora=LoraConfig(rank=32))`, `train_step(batch, loss_fn="cross_entropy", lr)`, `save_weights(name, mode="inference")`. Then `create_deployment(checkpoint=…)` or `chat_complete_from_checkpoint`. Stretch: `rl.Env` whose `reward()` runs `pytest` and returns the exit-code reward |
| **Memorable** | Procedure memory and the task-type classifier | Core | `memorable recall "<task>" --single` maps each new task to a procedure slug, which is our task type (their exact → lexical → semantic matcher). `memorable ingest trace.json` after every verified session, with `harness: "opencode"` and `tool_calls[].result.exit_code`. `memorable list --json` feeds the dashboard |
| **Superset** | Generates training runs in parallel worktrees | Supporting | `superset projects create --local --import`, then `superset workspaces create --agent opencode --prompt …` in a loop. `.superset/config.json` setup scripts. A custom agent row that carries the proxy env |
| **QM** | The fleet story; stretch live integration | Pitch, plus a stretch goal | A custom provider via `PUT /v1/admin/custom-providers/graduate` with `protocol: "openai"`, `baseUrl: http://localhost:4141/v1`, `validate: false` (Pi harness only) |
| **GBrain** | A human-readable record of what you own | Stretch | Local `gbrain put graduated < GRADUATED.md`, or hosted MCP `put_page` with Full access |
| **UFO** | none | Dropped | No API, SDK or custom endpoint is documented. Ask at lunch, and only add it if they show us a model-endpoint setting |

## Architecture after the research

```
 OpenCode (or any Chat Completions client)
   │  apiKey = session id  →  baseURL http://localhost:4141/v1
   ▼
 ROUTER  /v1/chat/completions ────────────── session log (full req/resp, local only)
   │  task type = memorable recall → slug         metrics (turns, tokens, cached, $, latency)
   │  registry says GRADUATED?
   ├── no  → frontier (OpenAI, caching on, streamed through untouched)
   └── yes → River adapter (deployment, or checkpoint + faked stream)

 RUNNER  graduate run --task … --verify … --repo …
   starts session → launches opencode → waits → runs verify → ledger(exit code)
   → on graduated failure: git reset, rerun forced to frontier, save the negative
   → on pass: memorable ingest(trace)

 WATCHER  ledger → verified count per task type → registry READY
 REGISTRAR  consent → dataset (tokenized, masked) → River SFT loop → checkpoint → registry GRADUATED
 DASHBOARD  /state → mock-up design, live
 UNDER THE HOOD  every component calls trace.emit(...) → /state.trace → the diagram lights up from real calls,
                 the runner streams OpenCode's output → /state.terminal → the live terminal panel
```

## Open questions for River (ask tonight on Discord, again at lunch)

1. Can you switch on **deployments** for our team key, for the base model we'll use?
2. Does the deployment endpoint support **`tools` / function calling** in chat completions?
3. Rough wall-clock for LoRA SFT on about 100 short chat examples with Qwen3.6-35B-A3B?
4. Which base models does a hackathon key get (`get_capabilities()`)? Are there free credits at the event?
5. Is there a renderer or helper that applies the chat template, with tool calls, for SFT?
