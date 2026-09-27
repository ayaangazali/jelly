---
title: "Sources"
project: "GRADUATE"
event: "Own Your Intelligence Hackathon (YC, 2026-09-27)"
purpose: "Every external claim in this pack with its origin, so anything can be re-checked."
updated: "2026-09-26"
---

# Sources

Nothing in this pack should be said on stage without knowing where it came from. Checked 2026-09-26.

**Tiers:** `PRIMARY` = the company's own site or docs. `PRESS` = journalism, generally tracing to Bloomberg. `THIRD-PARTY` = aggregators and doc sites; directionally right, verify before a slide.

---

## Sponsor facts

| Claim | Source | Tier |
|---|---|---|
| River trains open-source models on your data and tasks; weights are yours; OpenAI-compatible endpoint; LoRA + RL; pay per token | river.ai | PRIMARY |
| River raised $1.1B across Seed and Series A (Aug 11, 2026), led by General Catalyst and AMP PBC | river.ai/blog | PRIMARY |
| Memorable: procedural graph memory; stores files touched, verify command, step order, real exit codes; transcript never sent | memorable.sh | PRIMARY |
| Memorable: recall ~60ms, three matchers (exact, lexical, semantic); only prompt and allow-listed tool args leave the machine; consent fail-closed | memorable.sh | PRIMARY |
| Memorable benchmarks: 16→13 turns (GBrain + Claude Code, 454 runs); 5→3 tool calls (QM + Codex, 3 replications); 91% vs 80% pass rate | memorable.sh, case studies | PRIMARY |
| gstack: 293 tokens vs 15,593 for the `/investigate` skill (98% less context) | memorable.sh/case-studies/gstack | PRIMARY |
| Memorable is YC S27; integrates with Claude Code, Codex, Cursor, Claude Cowork, gbrain, QM; `POST /v1/extract` for any harness; read-only MCP server with 5 tools | memorable.sh | PRIMARY |
| GBrain: cloud machine of its own, plain-markdown memory shared across assistants, permission levels, circuit breakers, activity log, skills directory | gbrain.io | PRIMARY |
| QM: open-source agent harness from YC, July 2026; YC ran 50+ Hermes agents before building it; code at github.com/yc-software/qm | qm.ycombinator.com | PRIMARY |
| Superset: parallel agents in isolated git worktrees, agent-swappable, automations, CLI/SDK/MCP, ELv2 source-available, SOC 2 Type II | superset.sh | PRIMARY |
| UFO: "next-generation agent operating system" and nothing else public | ufo.ai | PRIMARY |

---

## Harvey precedent

| Claim | Source | Tier |
|---|---|---|
| Gross margins ~50% → ~-50% by June 2026 as token usage rose ~20x under OpenAI/Anthropic usage-based enterprise pricing | Bloomberg, via multiple outlets | PRESS |
| Margins turned positive again in August after Tenet launched, with no reported price change | Bloomberg, via multiple outlets | PRESS |
| Harvey Tenet is a Kimi K3 base post-trained with Fireworks research for long-horizon legal work | harvey.ai/blog/post-training-update-harvey-tenet | PRIMARY |
| Post-trained via asynchronous reinforcement learning in realistic legal work settings | harvey.ai blog | PRIMARY |
| Cost per query down ~90%; tokens in completed trajectories down 58%; criteria pass rate up >15%; 190.8 vs 129.3 intelligence-per-token | harvey.ai blog, via MarkTechPost summary | PRIMARY / THIRD-PARTY |
| Corpus was synthetic data, publicly available legal data, and human expert data; no customer data used | harvey.ai blog | PRIMARY |
| Harvey still routes hardest matters to frontier models; no published split | press summarizing Bloomberg | PRESS |
| Stated goal includes giving law firms a path to own their own specialized models | harvey.ai blog | PRIMARY |
| ~150 NVIDIA B300 GPUs over ~2 months | one outlet only (BigGo) | THIRD-PARTY — **soft, attribute as "reported"** |
| Abridge, Decagon, Ramp making similar open-weight moves | Bloomberg, via outlets | PRESS |
| Thomson Reuters shipped in-house model on an open-source base; reportedly 2+ years and ~$40M, final run ~$450K | press | PRESS |

**Rule:** always say "Harvey reported." These numbers are evidence the ceiling is real, never evidence about GRADUATE.

---

## Pricing and caching

| Claim | Source | Tier |
|---|---|---|
| OpenAI cached input billed at 10% of standard rate (90% off), automatic at ≥1,024 tokens | developers.openai.com prompt caching guide | PRIMARY |
| OpenAI cache-write charge of 1.25× uncached input on GPT-5.6 and later; no cache-write charge on earlier models | developers.openai.com | PRIMARY |
| OpenAI improved caching for GPT-6 with higher default hit rates, discounts up to 90% | @OpenAIDevs | PRIMARY |
| Anthropic cache read 0.1×, 5-min write 1.25×, 1-hr write 2×; 5-min default TTL extendable to 1 hr; max 4 breakpoints | docs.anthropic.com prompt caching | PRIMARY |
| Output tokens receive no caching discount from either provider | both providers' pricing tables | PRIMARY |
| Output runs ~3–6× input (GPT-5.6 Terra $2/$12; Claude Sonnet 5 $2/$10) | provider pricing pages via aggregators | THIRD-PARTY |
| Reasoning tokens billed as output, so a short visible answer can cost thousands | OpenAI docs and aggregators | PRIMARY / THIRD-PARTY |
| The old "OpenAI 50% / Anthropic 90%" split is out of date; both are 90% | multiple, mid-2026 onward | THIRD-PARTY |

**Before any slide:** re-check specific per-model prices on openai.com/api/pricing and anthropic.com/pricing. Prices move; the structure does not.

---

## Claims that are yours and need no citation

- Exit codes stored alongside procedures constitute an automatic reward signal.
- Graduation lifecycle with verifier-gated routing and demotion on failure.
- Speculative decoding as the framing for task-level drafting and verification.
- Compression tools breaking the cache prefix and eroding their own savings. *(Reasoning from published cache mechanics; state it as an argument, not a measurement, unless you measure it.)*

---

## Open, unverified

Everything under **[VERIFY]** in [`sponsor-stack.md`](../01-context/sponsor-stack.md), which is the lunch-hour list in [`questions-for-sponsors.md`](questions-for-sponsors.md). River's minimum dataset size and fine-tune wall-clock are the two that can change the plan.
