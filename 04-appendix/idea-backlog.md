---
title: "Idea Backlog — 27 Ideas"
project: "GRADUATE"
event: "Own Your Intelligence Hackathon (YC, 2026-09-27)"
purpose: "The full brainstorm, kept so future projects can be pulled from it."
updated: "2026-09-26"
related:
  - 04-appendix/other-deep-dives.md
---

# Idea Backlog — 27 Ideas

The full brainstorm, kept for pulling future projects. Each is scoped as a short build. Ideas 1, 2, 12 and 13 have deeper write-ups (1 and 2 became GRADUATE; 12 and 13 are in `other-deep-dives.md`).

---

## Distill: rented intelligence → owned intelligence

**1. Graduate** ⭐ *chosen*
Watches agent runs via Memorable. Once a task type succeeds N times with a passing verify command, auto fine-tunes a small River model on those traces and routes that type to it. Pain: agent bills exploding on repetitive work.

**2. Exit Code RL** ⭐ *merged into chosen*
Use Memorable's stored verify command and exit code as the literal reward function for River RL. Your test suite becomes the trainer. Pain: fine-tuning needs labeled data nobody has.

**3. Intelligence Passport**
One command exports GBrain memory + Memorable procedures + a River LoRA as a portable bundle importable into any harness. Pain: switching harnesses means starting from zero.

**4. Taste Model**
Train on every PR review comment your senior engineers left, run it as a reviewer inside Superset. Pain: agents open 50 PRs a day and human review is the bottleneck.

**5. Sounds Like You**
Fine-tune on your own sent mail (via GBrain's read-only Gmail scope) so drafts sound like you. Pain: AI replies are instantly recognizable.

## Fleets and multiplayer

**6. Merge Radar**
Detects semantic conflicts between parallel Superset agents before merge (two agents both changing auth logic in different files). Pain: worktrees prevent git conflicts, not logic conflicts.

**7. Day-One Senior**
A new employee's QM agent inherits every team procedure from Memorable on day one. Pain: every new agent starts cold.

**8. Relay**
When Claude Code hits a rate limit or context wall, the task hands to Codex or a River model in Superset carrying GBrain memory and the Memorable procedure, mid-task. Pain: lost agent work.

**9. Procedure Hub**
Public registry of verified Memorable procedures, each proven by an exit code. npm for how-to. Pain: every agent re-derives the same setup steps.

**10. Fleet CFO**
Watches spend across QM agents and Superset workspaces, kills runaway loops, reports cost per shipped PR. Pain: surprise agent bills.

**11. Agent Standup**
One daily brief for the whole fleet: shipped, blocked, waiting on a human, cost. Pain: at 50+ agents nobody knows what is happening.

## Software factory

**12. Tournament** *(deep dive available)*
Issue arrives, Superset spawns N agents on N models in parallel, verifier picks the winner, Memorable records the winning path, River distills it. Learns which model wins which task type.

**13. Repo Gym** *(deep dive available)*
Mines your git history for fix commits, reconstructs them as benchmark tasks, runs every agent in parallel, produces a leaderboard for *your* codebase. Pain: public benchmarks say nothing about your repo.

**14. Prod to PR Overnight**
Sentry error triggers an agent that reproduces it, writes a failing test, opens a fix PR by morning.

**15. Upgrade Once**
Fix a breaking dependency upgrade in one repo, Memorable captures it, Superset replays it across every repo in the org. Pain: major bumps across 30 services take a quarter.

**16. Spec-First Factory**
PM writes a spec in a GBrain multiplayer thread, agents turn it into acceptance tests first, coding agents must pass them before a PR opens. Pain: agents confidently build the wrong thing.

**17. Red Team Nightly**
A Superset automation where agents try to break your own app nightly and file repro PRs.

**18. Meeting to Merged**
GBrain meeting notes turn action items into Superset tasks, PR links post back into the thread.

## Beyond coding

**19. Portal Autopilot**
Browser agent for insurance prior-auth and government portals that learns each portal once and replays it, falling back to reasoning on layout change. Memorable explicitly supports this: known segments replay, a layout change is detected and the agent falls back.

**20. 3am Runbook**
An SRE fixes an incident once with an agent; next time that alert fires the agent replays the verified fix with human approval.

**21. Ticket Cost Curve**
A support agent whose cost per ticket visibly drops run over run. The chart is the demo.

**22. Month-End Close Agent**
Accounting close is the same 40 steps monthly. Record once, replay with verification.

**23. Recruiter Replay**
Sourcing workflows learned once per role type and replayed.

## Trust, memory, debugging

**24. Memory Mirror**
A UI over GBrain's plain-file memory showing what every AI has learned about you, with diff, expire and forget controls. Pain: vendor memory is a black box.

**25. Flight Recorder**
Time-travel debugger for agent runs: scrub a failed trace, fork from any step with a different model, compare outcomes.

**26. Least Privilege Linter**
Scans what each QM agent can access versus what it actually used, suggests tightening. GBrain already exposes permission levels and activity logs to build on.

**27. Second Brain Model**
Distill your notes into a LoRA so the model reasons like you, instead of RAG pasting chunks.

---

## Natural follow-ons from GRADUATE

If GRADUATE works, these become the roadmap rather than separate projects:

- **#12 Tournament** generates better training data (the winning attempt of four is a stronger example than the only attempt of one).
- **#13 Repo Gym** becomes the evaluation harness proving a graduated model is actually as good as the frontier one.
- **#9 Procedure Hub** becomes a marketplace of graduated models per framework.
- **#7 Day-One Senior** is GRADUATE applied at fleet scale.
- **#19 Portal Autopilot** is GRADUATE outside of coding, wherever a verifier exists.
