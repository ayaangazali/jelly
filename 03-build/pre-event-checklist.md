---
title: "Pre-Event Checklist"
project: "GRADUATE"
event: "Own Your Intelligence Hackathon (YC, 2026-09-27)"
purpose: "Saturday night and Sunday morning setup so the build window is pure building."
updated: "2026-09-26"
related:
  - 03-build/hour-by-hour.md
---

# Pre-Event Checklist

Nothing here is building the product. It is all environment work that would otherwise eat the build window. Anything that can be installed, authenticated or downloaded before 1:15pm must be.

---

## Saturday night (Sep 26)

### Accounts and keys
- [ ] River account at `console.river.ai`, API key in hand, read `docs.river.ai` end to end
- [ ] Make one successful inference call to River and save the exact request/response shape
- [ ] Confirm the fine-tune endpoint: what format the dataset takes, what the minimum size is, what it returns
- [ ] Join the River Discord (linked from their site) in case you get stuck at 3pm Sunday
- [ ] Frontier keys ready (Anthropic and/or OpenAI), with caching enabled in the baseline config

### Tooling installed and authenticated
- [ ] `npx memorable-cli@latest`, then `memorable login`, `memorable install-hooks`, `memorable enable`
- [ ] Run a couple of real tasks so `memorable list` returns actual procedures
- [ ] `memorable show <slug>` — save the exact output shape; this is your input schema
- [ ] `brew install superset-sh/tap/superset`, sign in, launch one agent to confirm it works
- [ ] Read `docs.superset.sh` on the CLI and SDK, especially spawning workspaces programmatically
- [ ] Clone `github.com/yc-software/qm` and skim the README for the config surface
- [ ] Optional: GBrain workspace at `gbrain.io/start` (they claim ~2 minutes)

### The demo repo (do not skip this)
- [ ] Pick a small Python repo with a fast test suite. `pytest` finishes in seconds, install is quick.
- [ ] Verify a cold clone + install + test run takes under 60 seconds. If not, pick another repo.
- [ ] Create 8–10 deliberate broken states of the same shape (a failing test in a different module each time). This is your task type.
- [ ] Script the setup so a broken state can be restored in one command.

### Corpus pre-generation (the highest-leverage pre-work)
- [ ] Run those 8–10 tasks through your agent with Memorable recording, so you arrive with verified procedures already stored
- [ ] Confirm `memorable list` shows them and exit codes are captured
- [ ] Back up the store, so a mistake on Sunday does not destroy your training data

### If going for the RL layer
- [ ] Ask River (Discord, tonight) what an RL job actually needs and how long it runs
- [ ] If a job can be started tonight or tomorrow morning, **start it**. A finished run is the difference between "here is the concept" and "here is the curve."

---

## Sunday morning (before noon)

- [ ] Scaffold the repo from [`architecture.md`](../02-project/architecture.md) §Repo layout, empty files with function signatures
- [ ] Write the OpenAI-compatible passthrough proxy and confirm an agent works through it with zero behavior change. **This is the riskiest 30 minutes of the project. Do it before you arrive.**
- [ ] Write `reward.py` (it is short and it will be on screen)
- [ ] Sketch `ui/index.html` with hardcoded fake data so the layout exists before real data does
- [ ] Charge everything. YC has no spare chargers. Bring your own, plus a backup.

---

## 12:00–1:00 lunch hour (strategy, not building)

- [ ] **River:** realistic fine-tune time, minimum dataset size, can any RL run finish today, hackathon key limits
- [ ] **Memorable:** fastest path from procedures to structured training data; can failed runs be retrieved for negative examples; what the MCP server's five tools expose
- [ ] **Superset:** best CLI pattern for spawning N parallel agents on one task type
- [ ] **UFO:** what is actually hackable, is there a model endpoint config
- [ ] **QM:** can a QM agent be pointed at a custom OpenAI-compatible base URL
- [ ] Tell each team your one-sentence pitch. Judging is at 5:00 and recognition matters.

---

## The rule for 1:15pm

If the passthrough proxy is not working by the time hacking starts, **do not start the training pipeline.** Fix the proxy first. Everything downstream depends on it and nothing can be demoed without it.
