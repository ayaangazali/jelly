---
title: "Demo Script and Q&A Prep"
project: "GRADUATE"
event: "Own Your Intelligence Hackathon (YC, 2026-09-27)"
purpose: "The 3-minute demo, sponsor-specific closers, and answers to the hard questions."
updated: "2026-09-27"
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

## The 3-minute demo (no-credit storyline, final)

**What changed.** No OpenAI credit arrived, so there is no real frontier baseline and no savings ratio. The owned model was trained locally on 8 stub sessions (broken states 01–08). **It passes a repeat of a task it trained on (07) and fails a state it never saw (09).** So the feature on stage is verification and escalation: the repeat pass is real, and the new-state failure is caught and fixed by the frontier. Call 07 "a repeat of a trained task", never "held-out". Never quote a savings percentage: the frontier numbers are stub numbers ([`docs/results.md`](../docs/results.md)). The pitch is still about output tokens, because caching can't cut those. Say that is what graduation goes after, not something we measured against a real frontier today.

**Setup.** Either play [`docs/recordings/offline-rehearsal.mp4`](../docs/recordings/offline-rehearsal.mp4) (labelled *offline rehearsal* in every frame) or run it live: `scripts/demo.sh --offline --use-checkpoint "$GRADUATE_CHECKPOINT"` (the v3 adapter, [`docs/pretrained-model.md`](../docs/pretrained-model.md)), click Approve on `http://localhost:4141/`, then switch to `http://localhost:4141/?present`. In presenter mode, keys 1–4 switch screens: 1 `#/show` (showcase), 2 `#/compare`, 3 `#/` (overview), 4 `#/system` (Under the hood).

### 0:00–0:20 · The problem · screen: `?present#/show`
> "Coding agents pay frontier prices to redo the same kind of task every time. Prompt caching discounts re-sent input. It does nothing for output tokens or turns, and nothing the agent does teaches the model anything."

### 0:20–0:40 · The label nobody uses · screen: `#/show`, the "Every run checked by …" line
> "In software the label already exists: the test suite exits 0 or it doesn't. GRADUATE sits between the agent and its model, runs the verify command after every session, and counts the passes per task type."

### 0:40–1:10 · Graduation · screen: `#/system` (Under the hood) during the run, then `#/show` for the stamp
- 4 of 5 passing runs, restored. Broken state 05 runs on the frontier and passes: **5 of 5, READY**.
- Consent names the backend that will train (local on this machine). Approve. **TRAINING.**
- Say it out loud: **"This checkpoint was trained before the demo, on this CPU, from 8 verified sessions. A scripted stub played the frontier in those sessions, because we had no OpenAI credit."** Then the GRADUATED stamp.

### 1:10–1:50 · Your model on a repeat · screen: `#/system`, then the "Your model" column on `#/show`
- Broken state 07 is a task type it graduated on, and one of the states it trained on. It routes to **your model** (local CPU, ~40 s, real time), which reads the file and fixes it. **Verified, exit 0, zero frontier calls.**
> "That's the product's claim: a task it has seen before now runs on a model you own, checked by the same tests."

### 1:50–2:30 · The feature: never trust the small model · screen: `#/system`, then the Safety net panel on `#/show`
- Broken state 09 is new: the model never saw it. It reads the right file, makes an edit, and says "Fixed."
- **The verify command fails it (exit 1).** The escalator resets the repo and reruns the session on the frontier: **exit 0**. The failed session is kept as a negative example for the next training round.
> "That's the failure we built for. The small model is wrong on a task it hasn't learned, and the user still gets a passing result, because every graduated session is verified and a failure escalates."

### 2:30–2:50 · Honest numbers · screen: `#/show` table, then `docs/results.md`
- The Your-model numbers are real (the 07 session). The frontier column is stub numbers. The showcase still prints a Change and a "saved" total against that stub: **don't read them out.** Say "the frontier side is a stub today, so there's no ratio to claim."
> "We're not going to show you a savings number we didn't earn. With credit, one command collects the real corpus, retrains and reruns this demo: `scripts/live.sh`."

### 2:50–3:00 · Adoption · screen: `#/setup`
```bash
uvx --from git+https://github.com/ayaangazali/jelly graduate up --demo
```
> "One command gets you the router and the dashboard. Point your agent's base URL at it and nothing else changes."

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
The most likely question. Full answer in [`cost-model.md`](../02-project/cost-model.md). Short version: caching discounts re-sent prefixes, not turns, not output tokens, and it expires in five minutes. The baseline is measured with caching on. We have no real before/after today (no OpenAI credit), so don't quote a number: output tokens and turns are what graduation targets, and caching can't cut those at any discount.

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
You shouldn't by default, which is why it is opt-in per task type, the dashboard shows exactly what would be sent before it is sent, and the posture follows Memorable's: transcripts stay local, only allow-listed content moves. Today the weights stay on this machine; with River funded they'd land in your own River account.

**"What's the business?"**
It gets cheaper the more it is used, which is the opposite of every rented-intelligence product. Priced against measured savings. The moat is that the data is generated by work the customer already pays for and cannot be bought elsewhere.

---

## Failure drills

- **Live demo breaks:** play `docs/recordings/offline-rehearsal.mp4` (labelled offline rehearsal) and narrate over it. Do not debug in front of judges.
- **River asks why it isn't on River:** the key authenticates, the account has no credits (`insufficient_funds`), so the same trainer interface ran locally on this CPU. `GRADUATE_OWNED_BACKEND=river` swaps River in.
- **Asked something you don't know:** "I don't know, here's how I'd find out." That answer has never lost a hackathon.
