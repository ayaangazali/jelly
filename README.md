---
title: "Project Pack Index"
project: "GRADUATE"
event: "Own Your Intelligence Hackathon (YC, 2026-09-27)"
purpose: "Entry point. What this pack is, what to read, and the verified claims."
updated: "2026-09-26"
---

# Own Your Intelligence Hackathon — Project Pack

**Event** · Own Your Intelligence Hackathon, hosted by River AI, GBrain, Memorable, QM, Superset and UFO
**Where** · 560 20th Street, San Francisco, CA 94107
**When** · Sunday, September 27, 2026 · doors 12:00pm · hacking 1:15–5:00pm · judging 5:00–5:45pm · prizes 6:00pm
**Builder** · Ayaan Gazali, 42nights

---

## Building this as a team

Work is split into GitHub issues. **Start at the pinned tracker issue #1**, then read [`AGENTS.md`](AGENTS.md) for how to claim an issue, which files you own, and the decided stack. Milestones follow the timeline: Saturday night prep → Sunday morning and lunch → build window (1:15–5:00pm) → demo and submission.

---

## The project in one paragraph

**GRADUATE** is a drop-in router that watches your agent work. Once a task type has been solved several times and verified each time, it trains a small model you own on those runs and routes that task type to it from then on. Exit code zero is the only label, so no human annotates anything. The frontier model stays on as the verifier and the fallback, which means quality never depends on trusting the small model.

It merges two ideas from the original brainstorm:

- **Idea 1 · Graduate** — distill repeated, verified agent work into an owned small model and route to it.
- **Idea 2 · Exit Code RL** — use the verify command's exit code as an automatic reward signal, making the test suite the trainer.

Harvey did this manually over six months and reported cost per query dropping ~90%. GRADUATE is that move as a background process with a one-line install.

---

## Quickstart

The repo is private: these installs work for collaborators with GitHub access only.

**See it in 30 seconds, no key:**

```bash
uvx --from git+https://github.com/ayaangazali/jelly graduate up --demo
# open http://localhost:4141/ (the dashboard on fixture data); Ctrl-C stops
```

Or in Docker, from a clone: `docker build -t graduate . && docker run --rm -p 4141:4141 graduate` (same dashboard, 220 MB image).

**Run it for real** (Python 3.11+, [OpenCode](https://opencode.ai): `curl -fsSL https://opencode.ai/install | bash`):

```bash
git clone https://github.com/ayaangazali/jelly && cd jelly   # the demo repo and its tasks live here
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[test]'                                     # editable: graduate bench reads demo-repo/ from here
graduate init          # checks Python + OpenCode, asks for OPENAI_API_KEY (hidden), validates it with the free GET /v1/models
graduate up            # router + watcher on :4141, dashboard at http://localhost:4141/; leave it running
```

In a second terminal, from the same directory, run one task:

```bash
. .venv/bin/activate
scripts/reset-demo.sh 01                                     # plant a failing test in demo-repo/
graduate run --task-file demo-repo/tasks/01.json --repo demo-repo
```

OpenCode fixes the test through the router, the verify command runs, and a ledger row lands on the dashboard.

`graduate init` writes, in the current directory: `.env` (mode 600, added to `.gitignore` in a git repo: `OPENAI_API_KEY`, `GRADUATE_OWNED_BACKEND`), `prices.json`, an empty `registry.json` and the `graduate` provider in `opencode.json`. Rerunning it is safe: it keeps other `.env` lines, other providers and an existing registry. CI: `OPENAI_API_KEY=… graduate init --no-input [--backend river|local|none]`. The owned backend defaults to `river` if `RIVER_API_KEY` is set (environment or `.env`), else `local` if `transformers` and `torch` import, else `none`.

**What still works when something is missing:**

| Missing | What happens |
|---|---|
| OpenAI key | `graduate up --demo` only: the dashboard on fixture data |
| River key | Training runs locally (`local`), or nothing graduates (`none`); everything routes to the frontier meanwhile |
| OpenCode | Dashboard and router still work; `graduate run` needs it |
| Memorable | The classifier names the task type from the normalized prompt instead (#45) |

---

## Start here

**Building it?** → [`graduate-spec.md`](02-project/graduate-spec.md) → [`architecture.md`](02-project/architecture.md) → [`hour-by-hour.md`](03-build/hour-by-hour.md)

**Pitching it?** → [`narrative.md`](02-project/narrative.md) → [`demo-script.md`](03-build/demo-script.md) → [`cost-model.md`](02-project/cost-model.md)

**Setting up tonight?** → [`pre-event-checklist.md`](03-build/pre-event-checklist.md)

**Pulling a different project?** → [`idea-backlog.md`](04-appendix/idea-backlog.md)

---

## Full contents

### 01 · Context

| File | What it gives you |
|---|---|
| [`event-brief.md`](01-context/event-brief.md) | Logistics, agenda, the 3h45m constraint, how judging works |
| [`sponsor-stack.md`](01-context/sponsor-stack.md) | What each sponsor tool actually is and how it plugs in |

### 02 · Project

| File | What it gives you |
|---|---|
| [`graduate-spec.md`](02-project/graduate-spec.md) | **The spec.** Problem, insight, precedent, lifecycle, success criteria |
| [`narrative.md`](02-project/narrative.md) | **The story.** Harvey precedent, speculative-decoding framing, the compression trap |
| [`architecture.md`](02-project/architecture.md) | Components, data flow, schemas, repo layout |
| [`integration-playbook.md`](02-project/integration-playbook.md) | How it stays one-line adoptable, per-sponsor integration plan |
| [`cost-model.md`](02-project/cost-model.md) | Verified caching economics and what to measure honestly |

### 03 · Build

| File | What it gives you |
|---|---|
| [`pre-event-checklist.md`](03-build/pre-event-checklist.md) | Saturday night and Sunday morning setup |
| [`hour-by-hour.md`](03-build/hour-by-hour.md) | The 3h45m plan, checkpointed, with cut lines |
| [`demo-script.md`](03-build/demo-script.md) | The 3-minute demo, sponsor closers, hard-question answers |
| [`risks.md`](03-build/risks.md) | Ranked failure modes, each with a decided mitigation |

### 04 · Appendix

| File | What it gives you |
|---|---|
| [`idea-backlog.md`](04-appendix/idea-backlog.md) | All 27 original ideas, for future projects |
| [`other-deep-dives.md`](04-appendix/other-deep-dives.md) | Full write-ups of Tournament and Repo Gym |
| [`questions-for-sponsors.md`](04-appendix/questions-for-sponsors.md) | The lunch-hour question list |
| [`sources.md`](04-appendix/sources.md) | Every external claim with its origin |

---

## Using this with an agent

Every file carries YAML frontmatter with a `purpose` and `related` links, so an agent can navigate without reading everything.

> Read README.md, then 02-project/graduate-spec.md and 02-project/architecture.md. We're building this today in under four hours. Follow 03-build/hour-by-hour.md and respect the cut lines.

For pitch help instead:

> Read 02-project/narrative.md and 03-build/demo-script.md. Help me rehearse, and push back on anything that overclaims.

---

## Glossary

| Term | Meaning here |
|---|---|
| **Task type** | A cluster of requests that are the same shape ("fix a failing test"), the unit that graduates |
| **Graduation** | A task type crossing the verified-run bar and getting its own trained model |
| **Verifier** | The command that proves a task succeeded, usually the test suite. Exit 0 or not |
| **Escalation** | Routing back to the frontier model when the graduated model fails verification |
| **Procedure** | Memorable's stored record of a successful run: steps, files touched, verify command, exit code |
| **Trace** | The raw record of an agent session, before it becomes a procedure |
| **Harness** | The thing running the agent loop (Claude Code, Codex, QM, Superset) |

---

## Verified claims

Fact-checked 2026-09-26. Safe to use **with attribution**. Full citations in [`sources.md`](04-appendix/sources.md).

**Harvey**
- Gross margins went from ~50% to ~-50% by June 2026 as token usage rose ~20x under usage-based enterprise pricing (Bloomberg).
- Harvey Tenet, shipped August 2026, is a Kimi K3 base post-trained with Fireworks via asynchronous reinforcement learning in realistic legal work settings (Harvey's own blog).
- Harvey reported cost per query down ~90%, tokens in completed trajectories down 58%, criteria pass rate up more than 15%.
- Margins turned positive after launch with no reported price change. They changed the model, not the price.

**Pricing**
- OpenAI and Anthropic both discount cached input by 90% (0.1×). The old "OpenAI 50%" figure is out of date.
- Output tokens get no caching discount from either provider, and run roughly 3–6× input.
- Anthropic cache writes cost 1.25× (5 min) or 2× (1 hr); OpenAI adds a 1.25× cache-write charge on GPT-5.6 and later.

**Never present as yours:** Harvey's numbers or Memorable's benchmarks. Always name whose they are.

---

## Accuracy discipline

Sponsor facts in [`sponsor-stack.md`](01-context/sponsor-stack.md) came from public sites on 2026-09-26. Anything marked **[VERIFY]** is an open question for the sponsor team at lunch, not a fact. The two that can change the build plan are River's minimum dataset size and realistic fine-tune wall-clock.

Three things never to say: that a model was RL-trained in four hours unless it was, that the output is lossless (it's verifier-gated), and that any of this is free (there's an upfront training cost that pays itself back).
