---
title: "Sponsor answers (lunch, 12:00–1:00 PT)"
purpose: "#16. Ask in this order, write each answer on its line at the table, then comment it on the issue it unblocks. Questions are updated with what the build found overnight."
updated: "2026-09-27"
---

# Sponsor answers

Ask the blocking question first; small talk after. Write the answer and the person's name or role on the line. Anything that changes the plan goes on #71 by 12:45.

## What we already know (don't spend lunch re-asking)

- **River:** the key authenticates, but every call, `get_capabilities()` included, returns `RESOURCE_EXHAUSTED billing: insufficient_funds`. The SDK (`river-client` 0.12.0) needs Python ≥ 3.12. The training record is `{input_ids, attention_mask, weights}` from `renderer.build_training_example(...).to_dict()`, and it renders tool calls. The OpenAI-compatible endpoint exists only on deployments, which are gated (`docs/river-api.md`).
- **OpenAI:** the key returns `429 insufficient_quota`. So the fleet trains a local Qwen2.5-Coder-0.5B LoRA as the stand-in (#71).
- **Memorable:** logged in on Ayaan's Mac with write consent. Each ingested trace becomes its own procedure, titled from its steps. Same-shape prompts recall at 0.60–0.66, and a cold CLI call takes 490–720 ms. The matcher field is comma-separated (`docs/memorable-shapes.md`).
- **UFO:** no public API, SDK or endpoint setting. Dropped unless they show us one.

## River (first: it decides whether the owned model is River's or the local stand-in)

| # | Question | Answer | Who | Unblocks |
|---|---|---|---|---|
| 1 | Can you put **hackathon credits** on our account now? The key authenticates but every call says `insufficient_funds`. | | | #2, #3, #7, #22 |
| 2 | Can you **enable deployments** for our team, on Qwen3.6-35B-A3B or whichever small model you recommend? | | | #37 |
| 3 | Does the deployment's `chat/completions` endpoint accept **`tools`** (function calling)? Our agent needs it every turn. | | | #37 |
| 4 | Realistic **wall-clock** for LoRA SFT on ~10 sessions (~2k tokens each)? We train live at 2:15 and fall back to a checkpoint at 3:00. | | | #22, #31 |
| 5 | Is `chat_complete_from_checkpoint` fine to call per request from a proxy, or is a deployment expected for that? | | | #37 |

## Memorable

| # | Question | Answer | Who | Unblocks |
|---|---|---|---|---|
| 1 | Is there a **JSON flag for `recall`**? We parse `0.66  procedures/<slug>  [lexical,semantic]` today. | | | #20 |
| 2 | Each ingested session becomes its **own** procedure (`add-test-mod-05…`, `fix-scale-function…`). Is there a way to group same-task sessions under one procedure? | | | #20, #36 |
| 3 | Does `ingest` store locally, on your service, or both? The docs say both ways; we want to say it correctly on stage. | | | pitch (#32) |
| 4 | Can failed sessions be stored as (negative) procedures? | | | #23 |

## OpenAI (if anyone from the host teams can help)

| # | Question | Answer | Who | Unblocks |
|---|---|---|---|---|
| 1 | Any event credits? Our key is at `insufficient_quota`, which blocks the real corpus, bench and live e2e. | | | #6, #56, #59 |

## Superset

| # | Question | Answer | Who | Unblocks |
|---|---|---|---|---|
| 1 | Can the CLI or API create a **custom agent row with env vars**, so each workspace runs OpenCode pointed at our proxy? | | | #8 |
| 2 | Is there a completion event for a workspace's agent, or do we poll? | | | #8 |

## QM

| # | Question | Answer | Who | Unblocks |
|---|---|---|---|---|
| 1 | Does a custom `openai`-protocol provider work with harnesses other than Pi? | | | #27 |

## GBrain

| # | Question | Answer | Who | Unblocks |
|---|---|---|---|---|
| 1 | Fastest way for a local process to write one markdown note into a workspace's memory: MCP `put_page` with Full access, or something simpler? | | | #28 |

## UFO

| # | Question | Answer | Who | Unblocks |
|---|---|---|---|---|
| 1 | Is there anything with a model-endpoint setting we could point at `localhost:4141`? If not, we'll leave UFO out rather than fake it. | | | none |

## One-sentence pitch to tell every team

> Your agent's test-verified runs become training data for a small model you own, and every graduated run is still checked by your tests. Caching discounts the call; graduation removes it.
