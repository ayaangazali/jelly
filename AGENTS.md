# Working on GRADUATE — rules for agents and humans

This repo is built by several agents in parallel against a hard deadline: **Sun 2026-09-27, hacking 1:15–5:00pm PT**. These rules exist so parallel work doesn't collide.

Read first: [`docs/PROJECT-BRIEF.md`](docs/PROJECT-BRIEF.md) (overrides the pack) → [`README.md`](README.md) → [`02-project/graduate-spec.md`](02-project/graduate-spec.md) → [`02-project/architecture.md`](02-project/architecture.md) → [`03-build/hour-by-hour.md`](03-build/hour-by-hour.md).

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
- **End-to-end proofs in parallel:** `:4141` may be another lane's router. Run yours on another port and point both sides at it: `GRADUATE_ROUTER=http://localhost:<port>` for the runner, `OPENCODE_CONFIG_CONTENT='{"provider":{"graduate":{"options":{"baseURL":"http://localhost:<port>/v1"}}}}'` for OpenCode. Run `scripts/reset-demo.sh clean` before committing.
- **Tests:** `pip install -e .[test]`, then `make check && make test` before you push; CI runs both, plus `make e2e-replay` (real OpenCode on `scripts/stub-upstream.py`, $0, ~1 min), on every push and PR. Fully offline: the frontier is the `stub` fixture in `tests/conftest.py`. New behavior gets a test under `tests/`. CI's jq is 1.7: wrap operator expressions in object values in parens (`{k: (a / b)}`); this host's jq 1.8 hides the error. Humans: [`docs/QA.md`](docs/QA.md).

## Decided stack (don't re-litigate)

These decisions come from [`docs/PROJECT-BRIEF.md`](docs/PROJECT-BRIEF.md), which **overrides the original pack wherever they disagree**. The research behind them is in `docs/research/`.

| Concern | Decision |
|---|---|
| Language | Python 3.11+ everywhere |
| Router | FastAPI + httpx, port **4141**, `POST /v1/chat/completions` only (Anthropic `/v1/messages` is stretch #26) |
| Demo harness | **OpenCode**, via a custom `@ai-sdk/openai-compatible` provider in `opencode.json`. Claude Code and Codex don't speak Chat Completions |
| Frontier | An OpenAI model over Chat Completions. Caching is automatic; cached tokens are read from `usage.prompt_tokens_details.cached_tokens` |
| Small model | River LoRA on a small base (Qwen3.6-35B-A3B preferred, Qwen3.5-9B fallback), trained by our own `river-client` SFT loop |
| Session identity | The bearer token *is* the session id: the runner sets OpenCode's apiKey to `sess-<uuid>` |
| Training data | The proxy's local session log (#35). Memorable procedures are minimized and can't be used for SFT |
| Graduation count | The run ledger `ledger.jsonl` (#34), one row per verified session. Not Memorable |
| Task-type classifier | `memorable recall --single` → procedure slug, with an exact normalized-prompt hash as fallback |
| Verification | Per **session**, in the runner, after the agent exits. Never per model call |
| Registry | `registry.json` on disk. No database |
| Dashboard | One `ui/index.html` built from `mock-up/index.html`, both views: the dashboard and Under the hood. No framework, no build step |
| Graduation bar | N = 5 verified runs, configurable |
| Frontier baseline | Prompt caching **on**. Any other comparison is dishonest |

## Hard rules from the build plan

- **No new dependencies after 3:30pm PT.**
- **Code freeze at 4:50pm PT.** Only the submission issue gets touched after that.
- **Fail open.** Every error path ends at "the frontier model handles it."
- **Never trust the small model.** The verify command runs on every graduated call.
- **Trace every external call.** Any component that launches a process, calls a service or changes state calls `graduate.trace.emit(who, call, result, issue, nodes, edges)` using the diagram ids in `mock-up/index.html`. That's what makes the live Under the hood view (#39) real.
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

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
