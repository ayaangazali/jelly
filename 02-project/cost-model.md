---
title: "Cost Model and the Caching Objection"
project: "GRADUATE"
event: "Own Your Intelligence Hackathon (YC, 2026-09-27)"
purpose: "Verified caching economics, what caching cannot touch, and what to measure."
updated: "2026-09-26"
related:
  - 02-project/narrative.md
  - 04-appendix/sources.md
---

# Cost Model and the Caching Objection

A judge will ask: *"Doesn't prompt caching already make repeated calls cheap?"* Have the answer ready, and better, say it before they ask.

All figures below were checked on 2026-09-26.

---

## What caching actually does (verified)

**Both major providers now discount cached input by 90%.** The old conventional wisdom (Anthropic 90%, OpenAI 50%) is out of date.

**OpenAI:** automatic on prompts at or above 1,024 tokens, no markers needed. Cached input bills at 10% of the standard input rate. Their own docs describe reused prefixes as discounted up to 90%, and note that on GPT-5.6 and later there is a cache-write charge of 1.25× the uncached input rate, while earlier models have no cache-write charge. Example list prices: GPT-5.6 Sol at $4.00/M input, $0.40/M cached, $20.00/M output.

**Anthropic:** explicit `cache_control` breakpoints, max 4, minimum ~1024 tokens. Cache reads 0.1× base input, 5-minute writes 1.25×, 1-hour writes 2×. Default TTL 5 minutes, extendable to 1 hour, and a read refreshes the entry.

So caching is real and large. **Enable it on your baseline**, then point at what it cannot touch.

---

## The three things caching does not touch

### 1. Output tokens — zero discount, and they are the expensive side
Neither provider discounts output. Output runs roughly 3–6× input across the board: GPT-5.6 Sol $4.00 in / $20.00 out, GPT-5.6 Terra $2.00 in / $12.00 out (6×), Claude Sonnet 5 $2.00 in / $10.00 out (5×).

And for reasoning models, hidden thinking tokens are billed as output, so a 500-token visible answer can consume thousands. An agent loop generates constantly: reasoning, tool arguments, patches, explanations. **The expensive half of an agent's bill gets no caching discount at all.**

### 2. The number of turns
Caching makes each turn cheaper. It does nothing about taking 16 turns where 3 would do. A 90% discount on unnecessary work is still worse than not doing the work.

Evidence (all other people's numbers, cite them as such):
- Memorable: turns per task 16 → 13 on a 3-bug coding fixture with GBrain + Claude Code, 454 runs
- Memorable: tool calls 5 → 3 with QM + Codex, a 40% drop, three replications
- Memorable / gstack: learned procedure 293 tokens vs 15,593 for the equivalent skill, 98% less context
- **Harvey Tenet: tokens in completed trajectories down 58% in production**

Not a discount on those tokens. Not sending them.

### 3. Model tier
Caching does not move you down a tier. A cache hit on a flagship is still flagship-shaped pricing; GPT-5.6 Sol cached input at $0.40/M is still 2× GPT-5.6 Luna's *uncached* input at $0.20/M, and the output gap is far wider. A small owned model is below all of it. Tier change stacks on top of caching rather than competing with it.

### And the part that isn't about money
A cache entry dies in 5 minutes (or an hour), lives on one provider, doesn't cross to a teammate's machine, and vanishes when you switch from Claude to Codex. Owned weights are permanent, portable and shareable. Caching is a better rental agreement. GRADUATE is buying.

---

## The compression trap (use this if anyone brings up context-trimming tools)

Tools that save tokens by compressing or pruning context before the call have a failure mode most people miss: **changing the prompt prefix breaks the cache.**

Cached input bills at ~10% of normal input. So trimming 40% of your input can leave you *worse off*, because the tokens removed were going to bill at a tenth of the price, and the edit turns the remaining prefix from a cache hit into a cache miss at full rate. Net token count down, net bill flat or up.

Meanwhile compression does nothing to output tokens, which is where the money actually is, and nothing to turn count.

This is worth saying out loud because it positions GRADUATE correctly against the whole token-saving category.

---

## How to measure honestly

**Rule: the baseline must have caching enabled.** Beat a cached frontier baseline and the objection is dead. Beat an uncached one and you cheated, and this room will know.

Track per run:

| Metric | Why |
|---|---|
| turns | the headline; caching cannot touch it |
| tool calls | Memorable's own benchmark axis, legible to this room |
| input tokens, cached vs uncached split | proves the baseline was fairly configured |
| output tokens | where caching does nothing and reasoning tokens hide |
| wall-clock latency | small models win here too, free to measure |
| total $ | secondary, not the headline |
| verified pass/fail | without this, everything above is meaningless |

**Report failures too.** Memorable's dashboard shows savings including runs where memory did not help. Matching that honesty is free and reads as rigor.

---

## Order of claims in the pitch

1. Turns and tool calls dropped (caching-proof).
2. The result is still verified (exit 0).
3. Cost dropped, against a cached baseline (money).
4. You own the weights (theme).

Leading with #3 invites the caching argument. Leading with #1 makes it irrelevant.

---

## The one-liner

> "Caching gives you 90% off the input you re-send. It gives you nothing off output, which is 3 to 6 times more expensive, nothing off the number of turns, and it expires in five minutes. We remove the work instead of discounting it, and you keep the thing that removed it."
