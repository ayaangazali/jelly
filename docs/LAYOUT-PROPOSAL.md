# Layout proposal

A tidier tree for after the hackathon freeze. Nothing here has been moved yet: `03-build/` and `SUBMISSION.md` are being edited until the 4:50 PM freeze, and a move would conflict with that work. Each move below lists every file that names the old path, found with a search over `*.md *.py *.sh *.yml *.html *.json *.toml Makefile Dockerfile` on main at `e723076` with the new README, so the move and its link fixes can land in one PR.

## Today

```
README.md  AGENTS.md  CLAUDE.md  SUBMISSION.md  Makefile  Dockerfile  pyproject.toml  registry.example.json
01-context/     event-brief, sponsor-stack
02-project/     graduate-spec, narrative, architecture, integration-playbook, cost-model
03-build/       pre-event-checklist, hour-by-hour, demo-script, risks
04-appendix/    idea-backlog, other-deep-dives, questions-for-sponsors, sources
demo-repo/  fixtures/  graduate/  mock-up/  scripts/  tests/  ui/
docs/
  PROJECT-BRIEF.md  QA.md  corpus.md  demo-repo.md  pretrained-model.md  results.md
  river-api.md  river-rl.md  memorable-shapes.md  qm-config.md  sponsor-answers.md
  research/       harness-protocols, memorable-gbrain, river, superset-qm-ufo
  recordings/  screens/
```

Four pre-event folders sit at the root beside the product, so a visitor sees the hackathon pack before the code.

## Proposed

```
README.md  AGENTS.md  CLAUDE.md  SUBMISSION.md  Makefile  Dockerfile  pyproject.toml  registry.example.json
demo-repo/  fixtures/  graduate/  mock-up/  scripts/  tests/  ui/
docs/
  PROJECT-BRIEF.md  QA.md  corpus.md  demo-repo.md  pretrained-model.md  results.md  LAYOUT-PROPOSAL.md
  research/       harness-protocols, memorable-gbrain, river, superset-qm-ufo,
                  river-api, river-rl, memorable-shapes, qm-config, sponsor-answers
  pack/
    01-context/  02-project/  03-build/  04-appendix/
  recordings/  screens/
```

The pack folders keep their numbered names under `docs/pack/`, so the pack's own `../02-project/...` links keep resolving without edits.

## Move 1: `01-context/ 02-project/ 03-build/ 04-appendix/` to `docs/pack/`

`git mv 01-context 02-project 03-build 04-appendix docs/pack/`, after the freeze.

Links between pack files are relative (`../02-project/narrative.md`) and survive the move. These do not:

**Outside the pack, pointing in** (prefix the path with `docs/pack/`):

| Path | Files and lines |
|---|---|
| `01-context` | `README.md`: 134, 163 |
| `02-project` | `AGENTS.md`: 5; `README.md`: 164 |
| `03-build` | `AGENTS.md`: 5, 56; `README.md`: 165, 168 |
| `04-appendix` | `README.md`: 134, 157, 166 |

`AGENTS.md` line 62 names `hour-by-hour.md` in prose without a path; it needs no change.

**Inside the pack, root-relative frontmatter** (`related:` lists name paths from the repo root; prefix each with `docs/pack/`):

| Path | Files and lines |
|---|---|
| `01-context` | `02-project/integration-playbook.md`: 8; `04-appendix/questions-for-sponsors.md`: 8 |
| `02-project` | `01-context/sponsor-stack.md`: 8; `02-project/cost-model.md`: 8; `02-project/graduate-spec.md`: 8, 9; `02-project/narrative.md`: 9; `03-build/demo-script.md`: 8; `03-build/hour-by-hour.md`: 9 |
| `03-build` | `02-project/architecture.md`: 8; `02-project/narrative.md`: 8; `03-build/hour-by-hour.md`: 8; `03-build/pre-event-checklist.md`: 8; `03-build/risks.md`: 8 |
| `04-appendix` | `01-context/event-brief.md`: 8; `01-context/sponsor-stack.md`: 9; `02-project/cost-model.md`: 9; `04-appendix/idea-backlog.md`: 8; `04-appendix/other-deep-dives.md`: 8 |

**Inside the pack, pointing out** (one more `../` each):

| File | Line | Link today | After the move |
|---|---|---|---|
| `03-build/demo-script.md` | 29 | `../docs/results.md` | `../../results.md` |
| `03-build/demo-script.md` | 31 | `../docs/recordings/offline-rehearsal.mp4` | `../../recordings/offline-rehearsal.mp4` |
| `03-build/demo-script.md` | 31 | `../docs/pretrained-model.md` | `../../pretrained-model.md` |

Line numbers are as of `e723076`; `03-build/` is still changing, so search again before moving.

## Move 2: sponsor notes into `docs/research/`

`git mv docs/river-api.md docs/river-rl.md docs/memorable-shapes.md docs/qm-config.md docs/sponsor-answers.md docs/research/`

None of these five files contains a relative link, so only the files that point at them change:

| File moved | Referenced from |
|---|---|
| `docs/river-api.md` | `README.md`: 149; `docs/river-rl.md`: 13 (prose); `docs/sponsor-answers.md`: 13 (prose) |
| `docs/river-rl.md` | `README.md`: 149; `SUBMISSION.md`: 32 |
| `docs/memorable-shapes.md` | `README.md`: 150; `docs/sponsor-answers.md`: 15 (prose) |
| `docs/qm-config.md` | `README.md`: 150; `SUBMISSION.md`: 35 |
| `docs/sponsor-answers.md` | `SUBMISSION.md`: 33 |

`SUBMISSION.md` is the judged file; move these only after judging, or leave them.

## Do not move

| Path | Why |
|---|---|
| `graduate/`, `ui/`, `fixtures/` | `pyproject.toml` packages all three side by side; the router finds the dashboard and prices through `parents[2]`, which is what makes `uvx ... graduate up --demo` work without a clone |
| `demo-repo/` | Hard-coded in `graduate/runner/__init__.py`, `graduate/bench.py`, `graduate/e2e.py`, `scripts/demo.sh`, `scripts/reset-demo.sh`, `scripts/corpus.sh`, `scripts/live.sh`, `tests/test_cli.py`, `tests/test_runner.py` |
| `scripts/` | Called by the Makefile, CI (`scripts/demo.sh`, `scripts/corpus-dryrun.sh`) and the docs |
| `mock-up/` | Its diagram ids are the ids every `graduate.trace.emit` call uses (AGENTS.md, "Trace every external call") |
| `docs/results.md` | `scripts/demo.sh` rewrites the block between its `demo.sh:begin` and `demo.sh:end` markers on every run |
| `docs/screens/`, `docs/recordings/` | `scripts/screens.py` and `scripts/record.py` write there |
| `registry.example.json` | `graduate/registry.py` reads it from the repo root for its self-check (`make check`) |
| `AGENTS.md`, `CLAUDE.md`, `README.md`, `SUBMISSION.md` | Tools and judges look for them at the root |

## After any move

Run a relative-link check over `README.md`, `AGENTS.md`, `SUBMISSION.md` and `docs/**/*.md`, then `make check && make test`.
