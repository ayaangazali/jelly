# Working on GRADUATE — rules for agents and humans

This repo is built by several agents in parallel against a hard deadline: **Sun 2026-09-27, hacking 1:15–5:00pm PT**. These rules exist so parallel work doesn't collide.

Read first: [`README.md`](README.md) → [`02-project/graduate-spec.md`](02-project/graduate-spec.md) → [`02-project/architecture.md`](02-project/architecture.md) → [`03-build/hour-by-hour.md`](03-build/hour-by-hour.md).

---

## Picking work

1. Open issues labelled **`agent-ready`** with no **`blocked`** label, in the current milestone, highest priority first (`P0` → `P3`).
2. Every issue lists **Depends on**. Every dependency has to be closed before you start. If one isn't, pick something else.
3. Claim the issue: assign yourself and comment `claiming`. One issue per agent at a time.
4. `human-required` issues need accounts, keys or an in-person conversation. Agents don't take them.

## Doing work

- **Branch:** `issue-<number>-<short-slug>`, e.g. `issue-12-passthrough-proxy`.
- **Stay in your files.** Each issue has an **Owns** list. Touch only those paths. If you need a change elsewhere, comment on the issue that owns the file, or open a new issue.
- **Contracts are law.** Shared shapes (registry, metrics record, task-type record, dataset records) are defined in `graduate/contracts.md` (issue #11). Don't change a shape unilaterally. Propose it on #11.
- **PR:** one PR per issue, body starts with `Closes #<n>`, and explains *why* as well as what.
- **After merge:** open each issue that listed yours under **Depends on**. If all its dependencies are now closed, remove its `blocked` label.
- **Done means:** every box in the issue's **Acceptance criteria** is ticked and shown in the PR (a command plus its output, or a screenshot for UI).

## Decided stack (don't re-litigate)

| Concern | Decision |
|---|---|
| Language | Python 3.11+ everywhere |
| Router | FastAPI + httpx, port **4141**, OpenAI-compatible `/v1/chat/completions` |
| Registry | `registry.json` on disk. No database |
| Dashboard | One `ui/index.html`. No framework, no build step |
| Classifier v1 | Exact normalized-prompt hash only. Embeddings are a stretch goal |
| Graduation bar | N = 5 verified runs, configurable |
| Frontier baseline | Prompt caching **on**. Any other comparison is dishonest |

## Hard rules from the build plan

- **No new dependencies after 3:30pm PT.**
- **Code freeze at 4:50pm PT.** Only the submission issue gets touched after that.
- **Fail open.** Every error path ends at "the frontier model handles it."
- **Never trust the small model.** The verify command runs on every graduated call.
- **Honesty:** don't claim RL training in 4 hours, "lossless", or Harvey's or Memorable's numbers as ours. See [`03-build/risks.md`](03-build/risks.md) §8.

## Labels

| Label | Meaning |
|---|---|
| `P0 never-cut` / `P1 swap-ok` / `P2 nice` / `P3 stretch` | The cut-line table in `hour-by-hour.md`. Drop from the bottom up |
| `agent-ready` | Self-contained. An agent can finish it with repo access alone |
| `human-required` | Needs an account, a key, a physical demo or a sponsor conversation |
| `blocked` | A dependency is still open |
| `needs-sponsor-answer` | Waiting on an answer from a sponsor team (lunch, 12–1pm) |
| `area:*` | Which component. Also who owns which files |
| `sponsor:*` | Which sponsor integration it exercises |
| `size:S/M/L` | Under 30 min / 30–60 min / over 60 min |

The pinned issue **#1** is the master tracker and dependency map.
