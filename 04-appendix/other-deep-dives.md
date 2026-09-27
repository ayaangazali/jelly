---
title: "Other Deep Dives — Tournament and Repo Gym"
project: "GRADUATE"
event: "Own Your Intelligence Hackathon (YC, 2026-09-27)"
purpose: "Full write-ups of the two runner-up projects."
updated: "2026-09-26"
related:
  - 04-appendix/idea-backlog.md
---

# Other Deep Dives

Full write-ups of the two runner-up projects, kept so they can be pulled and built later.

---

# Tournament (Idea 12)

**Problem:** you don't know which model is best for a given task, so you guess, and when the agent fails you re-run and hope. Parallel agent tools exist, but people use them to do different tasks at once, not the same task competitively.

**Analogy:** instead of one contractor's quote, you get four, and an inspector checks the work. You pay for four, you ship the one that passes.

**What it does:** an issue arrives. Four agents on four models attempt the same fix in parallel, in isolated copies of the repo. A verifier (tests, lint, whatever you care about) runs against each. The winner opens the PR, the losers are discarded.

**The part that makes it more than a gimmick:** record which model won, on what kind of task, by what path. Over time you learn "Codex wins refactors, Claude wins new features, the cheap model wins test-writing." Then stop running four and run the likely winner, still checked by the verifier. Cost collapses, quality holds.

**Sponsor fit:** Superset already does the hard part — isolated git worktrees, parallel agents, per-task agent switching across Claude Code, Codex, OpenCode and others, plus a CLI, SDK and MCP. You build only the tournament layer: spawn, verify, score, record, route. Memorable records the winning path so the next run starts from a known-good procedure.

**Build order (critical):** verifier first, then **two** agents, then the scoreboard, then more agents if time allows. Two agents competing is a complete demo. Four is a nicer number that makes you miss the deadline.

**Sunday scope:** a CLI taking a GitHub issue URL, spawning N Superset workspaces with different agents, waiting, verifying each, picking a winner, opening the PR, writing to a scoreboard. The scoreboard is the demo.

**Risk:** most moving parts of any idea in the backlog.

**Relationship to GRADUATE:** winning attempts are exactly the verified traces GRADUATE distills. Tournament is the best possible data generator for it.

---

# Repo Gym (Idea 13)

**Problem:** every leaderboard tells you which model is best on somebody else's code. Nobody can tell you which is best on yours, so teams pick on vibes.

**The insight:** your git history is already a labeled benchmark. Every bug-fix commit is a solved exam question. The code before the fix is the problem, the fix is the answer key, the test that shipped with it is the grader.

**What it does:** point it at a repo. It walks git history, finds fix commits, and reconstructs each as a task: check out the parent commit, hand the agent the issue description or commit message, let it attempt the fix, run the tests from the real fix commit. Do that across dozens of historical bugs and several models, in parallel. Out comes a leaderboard for *your* codebase.

**Why people want it immediately:** every engineering leader is paying for multiple agent subscriptions with zero evidence about which to standardize on. This produces evidence from their own history in an afternoon. It is also the clearest demo on the list, because a leaderboard needs no explanation.

**Sponsor fit:** finding fix commits is heuristics (messages mentioning fix/bug, commits closing an issue, commits touching source and tests together, small diffs). Superset runs the attempts in parallel isolated worktrees and swaps agents per run so the comparison is fair. Memorable can capture winning paths so the benchmark doubles as a training corpus.

**Sunday scope:**
> a script that mines git history into a task list
> a runner that checks out the parent commit in a worktree, runs an agent, runs tests, records pass/fail + tokens + time
> a leaderboard UI

**Pre-work matters more here than anywhere:** pick a public repo with a solid test suite and a fast install (a small Python library is ideal) and make the environment reproducible before arriving. If install takes eleven minutes per worktree, the demo is dead.

**The gotcha to raise yourself:** if a model was trained on that public repo it may have memorized the fix. Handle it by scoping to recent commits or offering a private-repo run, and name the weakness before a judge does.

**Relationship to GRADUATE:** this is the evaluation harness that proves a graduated model matches the frontier model on your code. Natural second product.

---

## Ranking (as assessed for a 3h45m window)

| Idea | Theme fit | Buildability | Wow | Risk |
|---|---|---|---|---|
| Graduate (1) | highest | medium | high | medium |
| Exit Code RL (2) | highest | low (needs pre-work) | highest | high |
| Repo Gym (13) | medium | highest | high | low |
| Tournament (12) | high | low | highest | highest |
