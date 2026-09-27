---
title: "Integration Playbook"
project: "GRADUATE"
event: "Own Your Intelligence Hackathon (YC, 2026-09-27)"
purpose: "How GRADUATE stays one-line adoptable, and the per-sponsor integration plan."
updated: "2026-09-26"
related:
  - 01-context/sponsor-stack.md
---

# Integration Playbook

**This is the priority file.** The project is judged by sponsor teams, and the thing that wins is not "we called your API." It is "this makes your product more adoptable, and anyone in this room could turn it on in two minutes."

---

## The golden rule

> Adoption cost must be **one line of config.** Not an SDK. Not a rewrite. Not a new harness.

Every additional required step roughly halves adoption. So GRADUATE ships as an **OpenAI-compatible proxy**, because that is the one integration surface every agent harness on earth already supports.

```bash
export OPENAI_BASE_URL=http://localhost:4141/v1
```

That is the install. Everything else is optional.

This works because River serves owned models through an OpenAI-compatible endpoint, so both sides of the router speak the same protocol. Do not invent a new one.

---

## Integration tiers (ship tier 0, demo tier 1, describe tier 2)

### Tier 0 — Zero-config proxy (must ship)
Point any tool at the base URL. Works with Claude Code, Codex, Cursor, OpenCode, QM, Superset-launched agents, and anything else. No code change in the caller.

### Tier 1 — One-command setup (should ship)
```bash
npx graduate-cli start
```
Mirrors Memorable's ergonomics exactly (`npx memorable-cli@latest`, then `memorable start` which "sets all of this up for you"). Matching the ergonomics of the sponsor whose data you consume is a deliberate compliment and it reads that way to judges.

What `start` does:
1. detects installed harnesses
2. runs `memorable install-hooks` if Memorable is present
3. writes the base URL into the local config
4. starts the router and opens the dashboard

### Tier 2 — MCP server (describe, ship only if time)
Expose GRADUATE over MCP so an agent can ask about its own graduation state:
- `graduate.status()` → task types and states
- `graduate.savings(since)` → cost and turn deltas
- `graduate.graduate(task_type)` → force a training run
- `graduate.demote(task_type)` → roll back to frontier

Both Memorable and Superset already speak MCP, so this fits the room's conventions.

---

## Per-sponsor integration, concretely

### Memorable — the data source (deepest integration, non-negotiable)

**Read path:** consume procedures and run history. Each procedure already carries the files touched, the command that proved it worked, the step order and real exit codes. That is the training record, pre-built.

**What to say to their team:** "You built the world's best source of labeled agent training data and you are currently using it for retrieval. We are using it for training." That sentence is the pitch to Memorable.

**Respect their boundaries in code, and show it:** their transcript never leaves the machine, only prompt and allow-listed tool args are sent, and consent is fail-closed with nothing stored before `memorable enable`. GRADUATE must be equally opt-in per task type, and the dashboard should show exactly what would be sent to River before it is sent. A visible consent screen in the demo is a 10-second slide that earns real trust.

**Fallback if the export path is awkward:** every harness can send one JSON trace to `POST /v1/extract`, so the trace schema is known. Worst case, read the local store directly or ingest your own JSON traces in the same shape.

### River — the training and serving target

**Two calls:** submit a training job, then serve from the returned model id on the OpenAI-compatible endpoint.

**What to say to their team:** "Your pitch is 'train a model on your own examples and your own success criteria.' We automated the part where the customer has to produce the examples and define success. The examples are their agent's successful runs and the success criterion is exit code zero. Zero human labeling."

That is exactly their product thesis with the hardest step removed, which is the most flattering possible use of their API.

**Ask them at lunch:** minimum viable dataset size, realistic fine-tune wall-clock, whether any RL run can finish in an afternoon, and whether a hackathon key has different limits.

### Superset — the corpus generator and the consumption surface

**Corpus generation:** you need N verified runs of the same task type before anything can graduate, and doing that serially will eat your build window. Superset runs agents in parallel isolated worktrees, scriptable from the CLI.

```bash
# seed-corpus.sh
for i in $(seq 1 10); do
  superset new "fix the failing test in module_$i" --agent claude &
done
wait
```

**Consumption:** Superset lets you pick the agent per task while workspaces, branches and review flow stay the same. A graduated model becomes just another selectable agent. Their automations feature (scheduled recurring work like triage, changelog drafts, dep bumps) is the perfect home for graduated models, since scheduled work is by definition repetitive, which is by definition graduatable.

**What to say to their team:** "Your automations run the same job every night. After a week, that job should not need a frontier model. We make your automations get cheaper the longer they run."

### QM — the fleet story

You will likely not integrate QM in code in 4 hours. Integrate it in the **pitch**, which is legitimate as long as you are clear about what is built versus designed.

The story: YC ran into fleet management problems at 50+ agents. In a fleet, graduation compounds. One person's task graduates and **every** agent in the org routes to the owned model immediately, because the registry is shared. The 51st agent starts as good as the fleet's best.

Memorable already measured QM + Codex going from 5 tool calls to 3 on the same fixture, with pass rate 91% vs 80%. Use their number, attributed to them, as evidence the direction is real. Never present their benchmark as your result.

**If you have 20 spare minutes:** point a QM agent at the router. Since it is OpenAI-compatible, this may genuinely be a config line, which turns a pitch slide into a live integration.

### GBrain — the human-readable ownership layer (optional, high polish per minute)

GBrain keeps memory as plain markdown files you can open and change, shared across assistants, and its database is one of Memorable's supported procedure stores.

Write a `GRADUATED.md` into GBrain memory:

```markdown
# Graduated task types
- fix-failing-test — graduated 2026-09-27, 7 runs, 16 turns → 3, $0.42 → $0.011
- update-changelog — graduated 2026-09-27, 5 runs, 9 turns → 2, $0.18 → $0.004
```

Why it is worth 15 minutes: it makes "you own this" tangible. A file you can open, read and delete is ownership in a way an API response is not. And it is cross-assistant by GBrain's design, so it lands the theme.

### UFO — opportunistic

Ask what is hackable. If there is a model endpoint config, point it at the router and you have a fourth live integration for ten minutes of work. Do not plan around it.

---

## The adoptability argument, in one slide

| | Prompt caching | Vendor memory features | GRADUATE |
|---|---|---|---|
| Setup | automatic or a flag | per-vendor | one env var |
| Reduces turns | no | sometimes | yes |
| Reduces output token cost | no | partially | yes |
| Survives vendor switch | no | no | yes |
| You own the artifact | no | no | **yes** |
| Lifetime | 5 min to 1 hr | vendor's choice | permanent |

---

## Anti-goals (say these out loud, they build credibility)

- Not a new agent harness. The room already has QM, Superset and UFO.
- Not a new memory layer. Memorable exists and is better than anything buildable today.
- Not a model provider. River exists.
- Not a replacement for frontier models. It is a graduation path, and the frontier model stays as the fallback forever.
