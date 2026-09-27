---
title: "Questions for Sponsors"
project: "GRADUATE"
event: "Own Your Intelligence Hackathon (YC, 2026-09-27)"
purpose: "The lunch-hour question list, ordered by what unblocks the build."
updated: "2026-09-26"
related:
  - 01-context/sponsor-stack.md
---

# Questions for Sponsors (12:00–1:00 Lunch)

Each block opens with a one-sentence pitch, then the questions that actually unblock the build. Ask the blocking questions first; a friendly conversation is worthless if you leave without the answer that determines whether the project is feasible.

---

## River AI (highest priority — the project's feasibility depends on these)

**Pitch:** "You train models on a customer's own examples and their own success criteria. We automated producing both: the examples are the agent's successful runs, and the success criterion is exit code zero."

1. What is the minimum dataset size for a LoRA fine-tune that actually behaves differently?
2. Realistic wall-clock for a small fine-tune on a few dozen examples? **This determines whether I train live or arrive pre-trained.**
3. Can *any* RL run produce a visible signal in an afternoon, or is that strictly overnight?
4. What exactly does the RL interface want — a reward per episode, a reward function, or a scored dataset?
5. Are hackathon keys rate-limited differently from normal ones?
6. Is the serving endpoint fully OpenAI-compatible including streaming and tool calls? **The router depends on this.**
7. Which base models are available, and which is best for short structured coding outputs?

---

## Memorable (second priority — the data source)

**Pitch:** "You've built the best source of labeled agent training data in existence and you're using it for retrieval. We're using it for training."

1. Fastest path from stored procedures to structured JSON suitable for training? CLI, MCP server, or reading the store directly?
2. Are **failed** runs retrievable? I need negative examples for the reward signal.
3. What exactly do the five MCP tools expose — can I get run counts and exit codes per procedure?
4. Does a procedure keep the full winning action sequence, or a summarized form? Training needs the sequence.
5. Since procedures can live in a local file, a GBrain database or Postgres — which is easiest to read programmatically today?
6. Would you be interested in a "procedures → training data" export as a feature? (If yes, that is a partnership conversation, not just a hackathon answer.)

---

## Superset (third priority — corpus generation)

**Pitch:** "Your automations run the same job nightly. After a week that job shouldn't need a frontier model. We make automations get cheaper the longer they run."

1. Best CLI pattern for spawning 10 parallel agents on variations of one task and collecting results programmatically?
2. Does the SDK expose per-run token and cost data, or do I measure at the proxy?
3. Can an agent be configured with a custom OpenAI-compatible base URL per workspace?
4. Any way to script worktree setup so environment install doesn't run ten times?

---

## QM

**Pitch:** "In a 50-agent fleet, one person's task graduating upgrades everyone instantly. The 51st agent starts as good as your best one."

1. Can a QM agent point at a custom OpenAI-compatible base URL with a config change?
2. Where does model selection live in the codebase?
3. At 50+ agents internally, what fraction of tasks are genuinely repetitive? (This is the market-size question and their answer is a quotable data point.)

---

## GBrain

**Pitch:** "The record of what your AI has learned should be a file you can open, read and delete."

1. Can an external process write markdown directly into workspace memory? Via MCP, CLI, or API?
2. Since Memorable can store procedures in a GBrain database, how do I read that store?
3. Would a `GRADUATED.md` appearing in memory show up automatically in the workspace UI?

---

## UFO

**Pitch:** "What are you hoping people build with you today?" (Their site says almost nothing, so lead with a genuine question.)

1. What is the hackable surface — API, CLI, SDK?
2. Is there a model endpoint configuration? If so, I can point it at my router for free.
3. What does "agent operating system" mean concretely for what runs on it?

---

## General rules for the hour

- Lead with the blocking question. Charm later.
- Write answers down immediately. You will not remember at 3pm.
- Tell every team your one sentence. Recognition at 5:00 judging is worth more than an extra feature.
- If a team says an approach won't work, **believe them and adapt at 1:15**, not at 4:00.
