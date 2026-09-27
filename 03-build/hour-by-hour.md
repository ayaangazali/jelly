---
title: "Hour-by-Hour Build Plan"
project: "GRADUATE"
event: "Own Your Intelligence Hackathon (YC, 2026-09-27)"
purpose: "1:15pm to 5:00pm, checkpointed, with an explicit cut-line order."
updated: "2026-09-26"
related:
  - 03-build/risks.md
  - 02-project/architecture.md
---

# Hour-by-Hour Build Plan

**Window: 1:15pm → 5:00pm. 3 hours 45 minutes.** Projects due at 5:00 sharp.

Order is chosen so that **you have a demoable artifact at every checkpoint.** If time runs out at any point after 3:15, you still have something to show.

---

## 1:15 – 1:45 · Router proves out (30 min)

**Goal:** an agent runs a real task through your proxy and behaves identically.

- Start the passthrough proxy (pre-written Sunday morning)
- Point Claude Code or Codex at `OPENAI_BASE_URL=http://localhost:4141/v1`
- Run one task end to end
- Add per-call metrics logging: turns, tokens in/out, cached vs uncached, latency, cost

**Checkpoint:** transparent proxy with metrics. Already demoable as "we measure what your agents actually cost."

> If this is not working at 1:45, stop and fix it. Do not proceed.

---

## 1:45 – 2:15 · Watcher + registry (30 min)

**Goal:** the graduation state machine is real and visible.

- Read Memorable procedures, group into task types, count verified runs
- Write `registry.json` with states: LEARNING / READY / TRAINING / GRADUATED / PROBATION
- Router reads the registry on each call (cache it, reload on change)
- Wire the graduation bar (N = 5)

**Checkpoint:** a task type sitting at READY because of your pre-generated corpus.

---

## 2:15 – 3:00 · Registrar and the River job (45 min)

**Goal:** dataset built and a real training job submitted.

- Convert verified procedures into River's dataset format
- Submit the fine-tune job, store the job id, poll for status
- Update registry TRAINING → GRADUATED on completion with the returned model id
- **Kick this off as early in the window as possible.** Training is wall-clock you cannot compress, so it should be running in the background while you build the UI.

**Checkpoint:** a real job running against River's API.

> **Contingency:** if training will not finish by 4:30, switch to the pre-trained model from Saturday night and demo the pipeline submitting a job live without waiting on it. Say so plainly in the pitch.

---

## 3:00 – 3:30 · Escalator (30 min)

**Goal:** the safety path, which is what makes this credible rather than cute.

- After a graduated call, run the task type's verify command
- On non-zero exit: retry on frontier, return that result, log a negative example, increment failure count
- Past the threshold, demote to PROBATION and stop routing

**Checkpoint:** you can now demo the failure path, which most teams will not have.

---

## 3:30 – 4:15 · Dashboard (45 min)

**Goal:** the thing on the projector.

- Single HTML file polling `/state`
- Card per task type with state and progress toward the bar
- Before/after bars: turns, tool calls, cost
- Live event log
- Running total: "$X saved across Y runs"
- Make the graduation transition **visually loud**. The state flipping to GRADUATED is the moment the room understands the project.

**Checkpoint:** full demo exists.

---

## 4:15 – 4:35 · Route the graduated model and capture the numbers (20 min)

- Run the same task through the graduated model
- Confirm it verifies
- Record real before/after numbers into the registry
- Take screenshots and a short screen recording as backup in case live fails at 5:15

**Checkpoint:** you have real numbers, and a recording so a live failure cannot kill you.

---

## 4:35 – 4:50 · Stretch, pick exactly one (15 min)

In priority order. Do not attempt two.

1. **QM pointed at the router** — a second harness working proves the "any agent" claim. Highest value if the config line exists.
2. **`GRADUATED.md` written to GBrain memory** — makes ownership tangible and adds a sponsor cheaply.
3. **MCP server** exposing `graduate.status()` and `graduate.savings()`.
4. **RL reward curve** on screen, if a pre-started run has results.

---

## 4:50 – 5:00 · Freeze and submit (10 min)

- **Stop writing code.** No exceptions.
- Commit and push
- Write the submission text: one sentence on the problem, one on the mechanism, the numbers, the sponsors used
- Reset the demo to its clean starting state
- Close everything unrelated, silence notifications, plug in

---

## Cut lines, in the order things get dropped

If you are behind, drop from the bottom up:

| Priority | Component | Drop? |
|---|---|---|
| 1 | Router + metrics | never |
| 2 | Registry + state machine | never |
| 3 | Dashboard | never (this is the demo) |
| 4 | Real River training job | can swap to pre-trained |
| 5 | Escalator | can be a hardcoded demo path |
| 6 | Classifier beyond exact match | drop to exact match only |
| 7 | RL layer | describe, do not build |
| 8 | Second harness, GBrain, MCP | drop entirely |

---

## Two rules for the day

**Rule 1: the demo is the product.** A beautiful backend nobody sees scores zero. If forced to choose between a real training job and a working dashboard, choose the dashboard and pre-train the model.

**Rule 2: no new dependencies after 3:30.** Anything introduced after that point is how projects die at 4:55.
