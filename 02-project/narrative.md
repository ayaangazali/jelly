---
title: "Narrative and Framing"
project: "GRADUATE"
event: "Own Your Intelligence Hackathon (YC, 2026-09-27)"
purpose: "The story: speculative decoding at task level, the Harvey precedent, the compression trap."
updated: "2026-09-26"
related:
  - 03-build/demo-script.md
  - 02-project/cost-model.md
---

# Narrative — How to Tell This Story

The technical design is in `graduate-spec.md`. This file is the story that makes people care, and the two framings that do the most work.

---

## Framing 1: This is speculative decoding, one level up

Speculative decoding: a small cheap model drafts tokens, and the big model verifies them. If the draft is right you keep it and you paid almost nothing. If it's wrong the big model corrects it. The output is as good as the big model's because the big model is the judge.

**GRADUATE is that pattern moved from the token level to the task level.**

| | Speculative decoding | GRADUATE |
|---|---|---|
| Drafter | small model, next tokens | your graduated model, the whole task |
| Verifier | the big model | your test suite |
| On accept | keep the cheap result | ship the PR |
| On reject | big model takes over | frontier model takes over |
| Cost of being wrong | a little latency | a little latency |

Why this framing is worth leading with:

1. Anyone technical instantly gets it, because the mental model already exists.
2. It explains **why the quality doesn't drop**. People hear "small model" and assume degradation. The answer is that the small model never gets the final word; the verifier does. Speculative decoding is provably output-equivalent to the big model. GRADUATE is not provably equivalent, since a test suite is a weaker judge than a full model, so say "verifier-gated," not "lossless." But the intuition transfers.
3. It's a bridge to a distributed-inference audience: NVIDIA's Dynamo does KV-aware smart routing, sending a request to the worker that already holds the relevant cache. GRADUATE routes a request to the model that has already internalized the task. Same instinct, different layer.

**The line:** "Speculative decoding drafts with a small model and lets the big one verify. We do that at the task level, and the verifier is your test suite."

---

## Framing 2: Harvey already proved this works, the hard way

This is the strongest external proof point available, it is recent, and it is public.

**What happened** (Bloomberg reporting, plus Harvey's own engineering blog):

- Harvey's gross margins went from roughly 50% to roughly **-50% by June 2026** as token usage rose about twentyfold under OpenAI and Anthropic usage-based enterprise pricing. Every dollar of usage was costing them more than a dollar.
- In August they shipped **Harvey Tenet**, their first post-trained open-weight model, a Kimi K3 base post-trained with Fireworks.
- Margins turned positive again after Tenet launched, with no reported price change. They changed the model, not the price.

**How they trained it, and why it matters enormously here:** Harvey post-trained via **asynchronous reinforcement learning in realistic legal work settings**. Not a labeled dataset. RL on the actual work, scored by whether the work came out right.

That is exactly the Idea 2 thesis, executed by an $11B+ company, published a month before this hackathon.

**Their reported results:**
- cost per query down roughly **90%**
- tokens in completed trajectories down **58%**
- criteria pass rate up more than **15%**
- intelligence-per-token 190.8 versus 129.3 for the best frontier configuration

Note the second number especially. Tokens in completed trajectories fell 58%. That is the turn-reduction argument, measured at production scale, and no amount of caching produces it.

**And the escalation path exists there too.** Reporting notes Harvey still needs frontier models for the hardest matters, and no published number says what share of work still routes to GPT and Claude. That is GRADUATE's escalator, in production, at a company with real liability.

**Their stated goal includes giving law firms a path to own their own specialized models.** Same sentence as this hackathon's title.

**The trend is not one company.** Bloomberg named Abridge, Decagon and Ramp pursuing similar open-weight pivots, and Thomson Reuters shipped its own in-house model on an open-source base in the same month.

### The gap GRADUATE fills

Harvey spent six months of research, partnered with Fireworks, and by one report used around 150 NVIDIA B300 GPUs over two months. Thomson Reuters reportedly spent more than two years and roughly $40M in staff and compute, with a final training run around $450K.

**So the playbook is proven and completely out of reach for everyone else.** That is the opening.

> "Harvey fixed negative fifty percent gross margins by post-training their own model on their own work. It took six months, a partnership with Fireworks, and a GPU fleet. GRADUATE is that same move as a background process. Your agent's verified runs are the corpus, exit code zero is the reward, and the install is one environment variable."

**Pitch hygiene:** these are Harvey's and the press's numbers, never yours. Say "Harvey reported" every time. Do not imply GRADUATE achieves 90%; say the precedent shows the ceiling is real.

---

## Framing 3: The trap that makes the competition look good and isn't

There's a category of tools that save tokens by compressing or trimming context before the call. Summarize the history, prune the transcript, drop old turns.

The problem: **compressing context changes the prompt prefix, which breaks the cache.** Cached input is billed around 10% of the normal input rate. So a compressor that removes 40% of your input can easily leave you worse off, because the tokens it removed were going to be billed at a tenth of the price, and the act of removing them converts the remaining prefix from a cache hit into a cache miss at full rate.

Meanwhile the compressor did nothing to output tokens, which are billed at roughly 3–6x input on every major model and get no caching discount at all. And it did nothing to the number of turns.

So the honest hierarchy of token-cost strategies:

| Strategy | Cuts input $ | Cuts output $ | Cuts turns | Survives vendor switch | You own it |
|---|---|---|---|---|---|
| Prompt caching | yes (90% on hits) | no | no | no | no |
| Context compression | sometimes, and can backfire via cache misses | no | no | no | no |
| Procedural memory (Memorable) | yes | yes | yes | partly | yes (local store) |
| **GRADUATE** | yes | yes | yes | yes | **yes (weights)** |

**The line:** "Every other token-saving strategy makes the same call cheaper. We make the call unnecessary, and you keep the thing that made it unnecessary."

---

## Putting it together: the 40-second open

> "Harvey's gross margins went to negative fifty percent because agents got popular. They fixed it by post-training their own model on their own work, and reported cost per query dropping ninety percent. It took them six months and a GPU fleet, which means nobody else in this room can do it.
>
> Here's the thing nobody's connected. Memorable already records every agent run that worked, including the command that proved it worked and its exit code. That's a reward signal, sitting there, being used for retrieval instead of training.
>
> So: your agent's verified runs become the corpus, exit code zero becomes the reward, River trains a small model you own, and we route that task type to it. The frontier model stays as the verifier and the fallback, exactly like speculative decoding. Install is one environment variable."

---

## Things to never say

- "We trained a model in four hours" unless you did.
- Harvey's numbers as yours.
- Memorable's benchmarks as yours.
- "Lossless" or "as good as the frontier model, guaranteed." Say verifier-gated, with escalation on failure.
- "Free." There's an upfront training cost. Say it costs something once and then keeps paying you back.
