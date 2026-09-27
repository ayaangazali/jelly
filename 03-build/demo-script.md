---
title: "Demo Script and Q&A Prep"
project: "GRADUATE"
event: "Own Your Intelligence Hackathon (YC, 2026-09-27)"
purpose: "The 3-minute demo, sponsor-specific closers, and answers to the hard questions."
updated: "2026-09-26"
related:
  - 02-project/narrative.md
---

# Demo Script and Q&A Prep

Judging is 5:00–5:45. Assume roughly 3 minutes and a hostile-in-a-friendly-way audience who built the tools you are using.

---

## The 30-second version (use this at lunch and in the hallway)

> Harvey's gross margins went to negative fifty percent because agents got popular. They fixed it by post-training their own model on their own work and reported cost per query dropping ninety percent. It took six months and a GPU fleet, so nobody else can copy it.
>
> Memorable already records every agent run that worked, including the command that proved it and its exit code. That's a reward signal being used for retrieval instead of training. We turn it into a small River model you own and route that task type to it. The frontier model stays as the fallback. Install is one environment variable.

Fuller versions of both framings, plus the compression trap, are in [`narrative.md`](../02-project/narrative.md).

---

## The 3-minute demo

### 0:00–0:25 · The problem, concretely
Show a real trace on screen: an agent taking 16 turns to fix a failing test.

> "This is the fourth time this week this agent has fixed this exact kind of test. It took 16 turns every single time. It has learned nothing, because it cannot."

### 0:25–0:50 · The insight
> "Fine-tuning needs labeled data nobody has. Except in software, the labels have existed for fifty years. This is a test suite. It returns exit code zero or it doesn't. No ambiguity, no human. Memorable already stores that exit code next to every procedure. So there is a stream of automatically graded training examples being produced by work you are already doing, and right now it is being thrown away."

### 0:50–1:40 · The live moment
Dashboard on screen. A task type at 4 of 5 verified runs.

- Run the task once more. It passes. Counter hits 5.
- **State flips to READY, then TRAINING.** Say out loud that a River job just got submitted.
- Cut to the pre-trained (or just-finished) graduated model.
- Run the same task again through the router.
- **3 turns instead of 16. Verified. Exit code zero.**

This is the whole project. Let the screen do the talking.

### 1:40–2:10 · The safety path (do not skip)
Trigger a deliberate failure on the graduated model.

> "It fails. The verifier catches it, the frontier model takes over, the user gets a correct result anyway, and that failure becomes a negative example for the next training round. We never trust the small model. We verify every single call."

### 2:10–2:40 · Ownership and cost
- Show `registry.json` and the `GRADUATED.md` file if it exists.
- > "These weights are yours. They are not a cache entry that expires in five minutes, and they do not disappear when you switch from Claude to Codex."
- Numbers, honestly, against a cached baseline.

### 2:40–3:00 · Adoption
```bash
export OPENAI_BASE_URL=http://localhost:4141/v1
```
> "That is the entire install. Every harness in this room already speaks this protocol, including River's serving endpoint. Nothing else changes."

---

## Sponsor-specific closers (use the right one for who is in front of you)

- **River:** "Your pitch is train on your own examples and your own success criteria. We removed the part where the customer has to produce either one."
- **Memorable:** "You built the best source of labeled agent training data in existence and you are using it for retrieval. We use it for training."
- **Superset:** "Your automations run the same job every night. After a week, that job shouldn't need a frontier model. We make automations get cheaper the longer they run."
- **QM:** "At a 50-agent fleet, one person's task graduating upgrades everyone instantly. The 51st agent starts as good as your best one."
- **GBrain:** "The record of what your AI has learned is a markdown file you can open, read and delete."

---

## Q&A prep

**"Doesn't prompt caching already make this cheap?"**
The most likely question. Full answer in [`cost-model.md`](../02-project/cost-model.md). Short version: caching discounts re-sent prefixes, not turns, not output tokens, and it expires in five minutes. Our baseline had caching on. We cut turns 16 to 3, which caching cannot do at any discount.

**"Isn't this just what Harvey did?"**
Yes, and that's the point. Harvey proved the economics at production scale with real liability. It cost them six months, a Fireworks partnership and a GPU fleet. We're making it a background process that any team can turn on with one env var, using traces they're already generating.

**"How is this different from speculative decoding?"**
It's the same shape one level up. There the small model drafts tokens and the big model verifies; here the graduated model drafts the whole task and the test suite verifies. The difference worth naming: speculative decoding is output-equivalent to the big model, and ours isn't, because a test suite is a weaker judge. So we call it verifier-gated, and failures escalate.

**"How much data do you need to graduate a task type?"**
Five verified runs in the demo. Honest answer: this is the open research question and it varies by task type. The architecture handles it by never trusting the model, since every graduated call is still verified and failures demote automatically. So being wrong about N costs latency, not correctness.

**"What about tasks with no test suite?"**
Out of scope today, deliberately. Coding is where the verifier is free and unambiguous, which is why we started there. The same shape works anywhere a verifier exists: a browser agent confirming a form submitted, an ops agent whose alert cleared.

**"Isn't the small model just going to be worse?"**
Yes, off-distribution. That is why we only route task types with a track record, verify every call, and escalate on failure. The design assumes the small model is worse and makes that safe.

**"Did you really RL-train a model in four hours?"**
No, and say exactly that. Either: the run was started before the event and this is the result; or: the pipeline is complete and running, and here is the reward function, with real training being an overnight job. **Never fudge this.** River's team is judging.

**"What stops overfitting to the test suite?"**
Real risk. A model could learn to make tests pass in degenerate ways. Mitigations: the reward penalizes files touched outside scope, human PR review remains in the loop, and held-out tests not shown during training are a straightforward next step.

**"Why would I trust you with my traces?"**
You shouldn't by default, which is why it is opt-in per task type, the dashboard shows exactly what would be sent before it is sent, and the posture follows Memorable's: transcripts stay local, only allow-listed content moves. The weights land in your own River account.

**"What's the business?"**
It gets cheaper the more it is used, which is the opposite of every rented-intelligence product. Priced against measured savings. The moat is that the data is generated by work the customer already pays for and cannot be bought elsewhere.

---

## Failure drills

- **Live demo breaks:** screen recording from 4:35 is on the desktop. Narrate over it and move on. Do not debug in front of judges.
- **River API down:** demo the pipeline against the pre-trained model and say the training call is stubbed because the API is down. Judges understand; flailing is what loses points.
- **Asked something you don't know:** "I don't know, here's how I'd find out." That answer has never lost a hackathon.
