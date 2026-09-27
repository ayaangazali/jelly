---
title: "Sponsor Stack"
project: "GRADUATE"
event: "Own Your Intelligence Hackathon (YC, 2026-09-27)"
purpose: "What each sponsor tool is, with citations, and how it plugs into the build."
updated: "2026-09-26"
related:
  - 02-project/integration-playbook.md
  - 04-appendix/sources.md
---

# Sponsor Stack

Pulled from public sites on 2026-09-26. Items marked **[VERIFY]** are assumptions, not confirmed facts.

---

## River AI — https://river.ai · https://docs.river.ai · console.river.ai

**What it is:** a new stack for personal AI, starting with an API to train models you own.

Per their site, the River API takes state-of-the-art open-source models and trains them on your data and your tasks, so the AI running your support queue, document pipeline, or coding workflow gets more accurate, dramatically cheaper per call, and is owned by you outright. Three claims they make:

- **Reliable on your tasks** — train on your own examples and your own success criteria until it handles workflows generic models get wrong.
- **A fraction of the cost** — a small specialized model matches a frontier giant on your task, faster and cheaper per call, priced per token.
- **An asset you own** — the trained weights are yours to keep, version, and serve, through an OpenAI-compatible endpoint, with no lock-in.

Their tag line stack: LoRA fine-tuning, reinforcement learning, open models, pay per token. They raised $1.1B across Seed and Series A (announced Aug 11, 2026), led by General Catalyst and AMP PBC. Mission language is explicitly about personal AI owned and shaped by each individual.

**Why this matters to GRADUATE:**
1. They support **both** SFT-style fine-tuning **and** RL. That is what makes the Idea 1 + Idea 2 merge possible on one vendor.
2. **The serving endpoint is OpenAI-compatible.** This is the single most important technical fact in this pack, because it means the router can swap a graduated model in without the caller changing anything but a base URL.

**Integration surface:** `console.river.ai` for keys, `docs.river.ai` for the API. Discord is linked from their site for support.

**[VERIFY] at the event:** minimum dataset size for a useful LoRA; wall-clock time for a small fine-tune; whether an RL run of any kind can complete inside an afternoon; rate limits on a hackathon key.

---

## Memorable — https://www.memorable.sh · https://www.memorable.sh/doc

**What it is:** procedural, graph-based memory for agents. It records the tool calls an agent made to run a task, and reuses that workflow on similar tasks instead of re-deriving it.

Their four layers:
- **L1 Traces** — the raw record of an agent session: a prompt, then the tool calls it produced, files read, commands run, results returned, in order.
- **L2 Workflow Synthesis** — turns a successful run into a reusable workflow by removing dead ends and keeping the sequence that reached the goal.
- **L3 Graph Assembly** — shared steps and prefixes connect workflows, letting it compose them and learn implicit skills.
- **L4 Retrieval** — when an agent starts a task, it finds the relevant workflow and guides the agent through it.

**What it stores per procedure:** the files touched, the command that proved it worked, the order of steps, and real exit codes. The transcript itself is never sent. Recall runs three matchers in order (exact, lexical, semantic) and adds roughly 60ms to a prompt.

**Privacy model:** procedures live in your own store — a local file, your GBrain database, or your Postgres. Only the prompt and allow-listed tool arguments leave the machine. Session id, user email, cwd, file contents and results are never sent. Consent is fail-closed and nothing is stored before `memorable enable`.

**CLI (from their site):**
```
npx memorable-cli@latest
memorable login          # opens browser, approves this machine
memorable install-hooks  # recall runs on every new prompt
memorable enable         # explicit write consent
memorable recall "fix the failing auth test"
memorable show procedures/<slug>
memorable disable        # read-only; recall still works, nothing new recorded
memorable start          # sets all of this up for you
```
Other command groups listed: `record ingest backfill recall show list chain`, `prune enable disable forget flush`, `status doctor eval notices`.

**Harness support:** Claude Code, Codex, Cursor, Claude Cowork, GBrain, and QM have curated tool registries. Any other harness sends one JSON trace to `POST /v1/extract`. A read-only MCP server exposes five tools.

**Their published benchmark numbers (useful as baseline citations, cite as theirs not yours):**
- GBrain + Claude Code, 3-bug coding fixture: turns per task 16 → 13, a 19% drop, 454 runs, all passed.
- QM + Codex, same fixture: tool calls per task 5 → 3, a 40% drop, three replications.
- Quartermaster case study: pass rate 91% with memory vs 80% without.
- gstack case study: learned procedure is 293 tokens against 15,593 for the `/investigate` skill, a 98% context reduction.
- OpenHome case study: 100% task completion, up from 70%.

They are YC S27 and list GBrain, gstack and QM as live integrations.

**Why this matters to GRADUATE:** Memorable is the data layer. It is already recording exactly what GRADUATE needs — repeated tasks, the successful path, and the verify command with its exit code. **Do not build a trace recorder.** That is hours you do not have.

**[VERIFY] at the event:** the cleanest way to export procedures + underlying traces as structured JSON for training; whether the MCP server's five read tools can list procedures with run counts; whether failed runs are retrievable too (needed as negative examples for RL).

---

## GBrain — https://gbrain.io · https://gbrain.io/docs · github.com/garrytan/gbrain

**What it is:** a personal assistant that works while you sleep. Like ChatGPT or Claude, but it runs on a machine of its own in the cloud, remembers everything you give it, and comes loaded with skills. Built by Garry Tan, backed by YC.

Relevant capabilities:
- **Multiplayer workspace** — one conversation the whole team is in, not five separate ones. Threads, watch-it-think, model choice, roles, SSO, private server.
- **Memory as plain files** — everything you tell it is kept as markdown notes you can read and change. One memory, not one per AI: Claude, ChatGPT and OpenClaw work from the same memory. Semantic search, access levels, day and person views.
- **Tools / credential custody** — connect Gmail, Calendar, the web once, with per-scope permission levels (Off / Read / Draft / Manage / Full). Described as a password manager built for AI: GBrain holds the account, you set how far it can go, and it never sees your password. Also: one MCP address, CLI, circuit breakers with daily limits, activity log, expiring-access kill switch.
- **Skills** — pre-built scheduled setups: Team Daily Sync, Deep Person Brief, Meeting Notes, Inbox Cleanup, News Watch, Pitch Scorecard. One-click install, scheduled runs.

**Why this matters to GRADUATE:** two optional roles. (a) The GBrain database is one of Memorable's supported procedure stores, so it can be where graduated-model metadata lives. (b) GBrain's plain-markdown memory is the natural place to write a human-readable `GRADUATED.md` record of which task types have graduated and what they cost. Use it if time allows; it is not on the critical path.

---

## QM (Quartermaster) — https://qm.ycombinator.com · github.com/yc-software/qm

**What it is:** an open-source agent harness from YC, open-sourced July 2026. Short for quartermaster, the person on a ship who coordinates belowdecks.

It lets startups and YC work with a fleet of OpenClaw-like agents, with every employee and project getting one as needed. Designed to be easy to administer and especially helpful for work-related tasks. YC's path to it: first a basic agent loop in Ruby with internal-data tools, extended with crons and webhook triggers, then over 50 Hermes agents provisioned for individual employees, which became hard to manage at that scale. They wanted Hermes flexibility with the simplicity of the original system, self-hosted and owned. Contact is labs@ycombinator.com.

**Why this matters to GRADUATE:** QM is the fleet case. One developer graduating their own tasks is a nice demo; an org where every employee's agent shares one graduated-model registry is the business. It is also the harness where Memorable measured the 5 → 3 tool call drop, so QM + Memorable + River is a story its own authors have partially validated.

---

## Superset — https://superset.sh · https://docs.superset.sh · github.com/superset-sh/superset

**What it is:** one workspace to orchestrate any coding agent. macOS app, mobile app, CLI, SDK, MCP. Source-available under ELv2, SOC 2 Type II, 14.4k GitHub stars.

Capabilities that matter:
- **Agent independence** — Claude Code, Codex, OpenCode, Cursor Agent, Gemini, Mistral Vibe, Kimi Code, Grok CLI, Hermes, Devin and others, swappable per task while workspaces, branches and review flow stay the same.
- **Parallel execution** — scale to 100+ agents across features, fixes and refactors, with at-a-glance status for working / blocked / waiting on you.
- **Isolation** — each agent runs in its own isolated git worktree.
- **Automations** — recurring work on a schedule (daily triage, changelog drafts, dependency bumps) that open PRs for review.
- **Remote access** — add any machine as a host; workspaces keep running when the laptop sleeps.
- **CLI & SDK** — everything is scriptable: `superset new "fix onboarding crash" --agent claude`, `superset ls`, `superset status`, `superset automations`, `superset connect <host>`. An agent can drive it over MCP.
- **Local first** — repos, worktrees, terminal output and agent sessions stay on your machine; your own API keys, never proxied.

Install: `brew install superset-sh/tap/superset`

**Why this matters to GRADUATE:** Superset is how you generate a training corpus fast. To fine-tune you need N successful runs of the same task type. Running them one at a time takes longer than the hackathon. Running 10 in parallel worktrees takes minutes. Superset is the corpus generator **and** the place a graduated model gets used, since it lets you pick the agent per task.

---

## UFO — https://ufo.ai

**What it is:** publicly, only "next-generation agent operating system" and `curl https://ufo.ai/ufo | sh`. No documented surface.

**Action:** ask at lunch what is hackable. If it exposes an agent runtime with a model endpoint config, it becomes another place to plug the graduated model in, which is a free extra sponsor with almost no work. Do not design anything around it in advance.

---

## The one-paragraph synthesis

Memorable already records verified successful runs including the command that proved success and its exit code. River already trains models on your examples and your success criteria, with RL, and serves them on an OpenAI-compatible endpoint. Superset and QM already run the agents that produce those runs. **Nobody has connected the last wire: the exit codes Memorable stores are a reward signal, and River can train on them.** GRADUATE is that wire.
