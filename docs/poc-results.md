# POC results: verified traces → Memorable → River Qwen3.5-9B LoRA → draft-and-verify

This proof of concept runs GRADUATE's core loop on real services, outside the router:

1. A frontier model (OpenAI) answers each task. pytest checks the answer before it is used for anything.
2. Each verified answer is ingested into Memorable as a session. Memorable returns a procedure slug for it.
3. `memorable recall` scores every task prompt against the stored procedures. A hit with score ≥ 0.55 marks that task's trace as training data.
4. River trains a LoRA on Qwen/Qwen3.5-9B from those traces.
5. Draft-and-verify: the fine-tuned 9B drafts an answer from a short prompt, pytest accepts or rejects it, and a rejected draft falls back to the frontier answer.

Code: [`scripts/poc_draft_verify.py`](../scripts/poc_draft_verify.py) (stages) and [`scripts/poc_acme.py`](../scripts/poc_acme.py) (the acme SDK, its docs and 30 tasks). Raw evidence is in `data/poc/` and `data/poc-acme/`. `data/` is gitignored, so those files are not part of this PR. Every number below comes from them, and each table names the file it was read from.

## Headline (acme set)

The acme set is a small fake payments SDK (`acme.Money`, `AcmeError` codes, `audit()` events) with house rules that a model can only know from its docs or from training. There are 30 tasks: 25 are trained on and 5 are held out.

| Drafting model | Prompt | Prompt tokens per call (Qwen tokenizer) | Trained-on tasks accepted | Held-out tasks accepted | Source |
|---|---|---|---|---|---|
| Base Qwen3.5-9B | short, no docs | mean 79.9 (68–94) | **0/25** | **0/5** | `data/poc-acme/eval-run4.jsonl`, arm `base` |
| Base Qwen3.5-9B | full SDK docs in the system prompt | mean 514.9 (503–529) | **10/25** | **0/5** | `data/poc-acme/eval-base-docs.jsonl`, field `prompt_tokens` |
| Fine-tuned Qwen3.5-9B, run 4 | short, no docs | mean 79.9 (68–94) | **19/25** | **1/5** (`deposit`) | `data/poc-acme/eval-run4.jsonl`, arm `lora` |
| **Fine-tuned Qwen3.5-9B, run 5 (best)** | short, no docs | mean 79.9 (68–94) | **21/25** | **1/5** (`deposit`) | `data/poc-acme/eval-run5.jsonl`, arm `lora` |
| Fine-tuned Qwen3.5-9B, run 6 (rank 32) | short, no docs | mean 79.9 (68–94) | 18/25 | 1/5 (`deposit`) | `data/poc-acme/eval-run6.jsonl`, arm `lora` |

The docs prompt is 6.4x longer than the short prompt: 514.9 / 79.9 tokens, averaged over all 30 tasks. The docs figure is the `prompt_tokens` that River reported in `eval-base-docs.jsonl` (mean 515.2 on trained-on tasks, 513.2 on held-out tasks). The short-prompt figure isn't logged in the eval files. It was counted offline by rendering `messages(prompt)` with the cached `Qwen/Qwen3.5-9B` chat template (`enable_thinking=False`). Rendering the docs prompt the same way gives 514.9, which matches River's number.

**What the frontier would have cost (run 4).** Each accepted draft replaces one frontier call. The frontier calls were measured in `data/poc-acme/frontier.jsonl` at gpt-4.1-mini list prices (`PRICE` in the script).

| Split | Drafts accepted | Frontier output tokens avoided | Frontier $ avoided | Frontier total for that split |
|---|---|---|---|---|
| Trained-on | 19/25 | 2,803 | $0.00827 | 3,520 tokens, $0.010584 |
| Held-out | 1/5 | 92 | $0.000338 | 722 tokens, $0.002134 |

The frontier was given the full docs on every call: its `prompt_tokens` averaged 494.0 (469–515) on OpenAI's tokenizer. The dollar amounts are fractions of a cent because the tasks are single functions. The ratios matter here, not the absolute numbers.

### All acme runs

All runs used Qwen/Qwen3.5-9B with a LoRA (rank 16 by default, `POC_RANK`) trained with cross-entropy on the last assistant turn. Source: `data/poc-acme/train-runN.jsonl` and `eval-runN.jsonl`.

| Run | Traces | Steps | Train secs | Loss first → last | LoRA trained-on | LoRA held-out | Base trained-on | Base held-out |
|---|---|---|---|---|---|---|---|---|
| 1 | 7 | 14 | 74.3 | 0.588 → 0.334 | 4/10 | 0/5 | 0/10 | 0/5 |
| 2 | 7 | 28 | 140.5 | 0.588 → 0.0048 | 6/10 | 0/5 | 0/10 | 0/5 |
| 3 | 20 | 40 | 180.2 | 0.588 → 0.113 | 18/25 | 0/5 | 0/25 | 0/5 |
| 4 | 20 | 60 | 294.5 | 0.588 → 0.031 | 19/25 | 1/5 | 0/25 | 0/5 |
| 5 | 21 | 90 | 387.5 | 0.588 → 0.0497 | 21/25 | 1/5 | 0/25 | 0/5 |
| 6 (rank 32) | 21 | 60 | 276.7 | 0.588 → 0.0673 | 18/25 | 1/5 | 0/25 | 0/5 |

Runs 1–2 had 10 trained-on tasks and runs 3–4 had 25. The task list was extended between runs 2 and 3 (`TASKS +=` in `poc_acme.py`). `data/poc-acme/eval.jsonl` is byte-identical to `eval-run4.jsonl`.

## Frontier teachers and verification (#153)

- **Mixed teachers.** In `data/poc-acme/frontier.jsonl`, the `model` field is `gpt-4.1-mini-2025-04-14` on 9 rows (7 trained-on, 2 held-out) and `gpt-4o-mini-2024-07-18` on 21 rows (18 trained-on, 3 held-out). gpt-4.1-mini answered the original 15 tasks. gpt-4o-mini (`POC_FRONTIER_MODEL=gpt-4o-mini`) answered the tasks added later and re-sampled the ones gpt-4.1-mini had failed. All 15 easy-set rows (`data/poc/frontier.jsonl`) are gpt-4.1-mini.
- **Rejected by verification.**
  - On the first pass, gpt-4.1-mini with the full docs failed pytest on 6 of 15 acme tasks: `refund`, `transfer`, `cap_withdrawal`, `convert_and_add`, `charge_tax` and `refund_all` (#153). The frontier stage re-asks for any row whose `exit_code` is not 0, so those failed rows were overwritten by the gpt-4o-mini re-samples. The current file therefore holds the re-samples, not the original failures.
  - In the final file, 3 of 30 rows still fail: `pay_invoice`, `average` and `convert_list`. All three are trained-on tasks answered by gpt-4o-mini.
  - `stage_memorable` skips any row with `exit_code != 0`, so none of these 9 failures were ingested or trained on.
- **Easy set:** all 15 verified on the first pass.

## Memorable

- **Separate environment.** Memorable ran in its own environment. `MEMORABLE_HOME` defaults to `$POC_OUT/memorable` under `data/`. Its `config.json` copies only `api_url` and `api_key` (the `mk_` key) from the owner's `~/.memorable/config.json` and sets `consent: read-write`, `record_repos: false`. The owner's own store is never written.
- **Ingest.** Each verified trained-on answer is written as a session trace, `traces/sess-poc-<name>.json`, and ingested with `memorable ingest`. The procedure slug is read from the output. Acme: 22 ingested, 21 distinct slugs (Memorable merged two), 0 missing (`data/poc-acme/memorable.jsonl`). Easy set: 10 ingested, 10 slugs.
- **Selection.** `memorable recall` runs on every task prompt. A trace is selected when a hit scoring ≥ `min_recall` 0.55 (`POC_MIN_RECALL`) maps back to its slug. Acme selected 20 traces. The easy set selected 9: `chunk` topped out at 0.538 and was excluded.
- **Why Memorable isn't the training text (#151).** Memorable returns condensed procedures, not the full turn text. So the SFT text comes from this environment's own trace log, `frontier.jsonl`, joined on the task and session id `sess-poc-<name>`. Memorable decides which traces to use, and the local log supplies their text.
- **Routing new prompts (#152).** Held-out recall tops were 0.0 on all 5 easy-set tasks and 0.585–0.72 on the acme held-out tasks. Memorable recall is not yet a reliable router for new prompts.

## River training and serving

- **Base model.** `Qwen/Qwen3.5-9B`. The name is picked from River's `get_capabilities()` list, or set with `RIVER_BASE_MODEL`.
- **Training.** LoRA SFT with `loss_fn="cross_entropy"`, `TrainOnWhat.LAST_ASSISTANT` (loss on the assistant answer only), one example per step, cycling through the traces. Knobs: `POC_STEPS`, `POC_LR` (default 5e-5), `POC_RANK` (default 16).
- **Thinking off, end to end.** Training renders with `get_renderer(base, thinking=False)`. Serving sends `chat_template_kwargs: {"enable_thinking": False}` and `temperature: 0`.
- **Easy-set run 1 had a mismatch and was worse than base.** Run 1 didn't have that setting (`data/poc/train-run1.jsonl`, 27 steps; `eval-run1.jsonl`). The LoRA accepted 6/10 trained-on and 3/5 held-out, against base 8/10 and 5/5. Run 2 fixed it (`train.jsonl`, 18 steps; `eval.jsonl`): base and LoRA both reached 10/10 and 5/5. The easy set is at ceiling for a 9B, so it proves the plumbing but gives no learning signal. That is why the acme set exists.
- **Local check.** `data/poc/eval-local.jsonl` and `local.log` come from `Qwen/Qwen2.5-Coder-0.5B-Instruct` on the in-repo `LocalBackend`. Base accepted 7/10 trained-on and 5/5 held-out. The LoRA accepted 10/10 and 5/5.

## Honest claims

**Proven:**

- The loop runs on real services end to end: OpenAI frontier, pytest verification, Memorable ingest and recall, River LoRA training and River checkpoint serving.
- For recurring task types, the owned model reproduces the house style from a prompt about 6.4x shorter. It accepts 19/25 against 0/25 for the same base model with the same short prompt. It also beats the same base model given the full docs (19/25 against 10/25) while sending about 80 prompt tokens instead of about 515.
- Verify-before-train is necessary: 9 frontier answers failed the tests and never reached training.

**Not proven:**

- **Generalization to new task compositions.** Held-out tasks: 1/5 at best (run 4), 0/5 in runs 1–3, and 0/5 for the base model even with the docs.
- **Token-level speculative decoding.** This is task-level draft-and-verify: a whole answer is drafted and then accepted or rejected by tests.
- **Scale.** The task set is small (30 acme tasks, 15 easy) and each task is a single function.
- **One teacher.** The acme teachers are mixed: gpt-4.1-mini on 9 rows, gpt-4o-mini on 21.
- **Dollar savings at scale.** The absolute amounts are fractions of a cent.

## Reproduce

Run from the repo root. `OPENAI_API_KEY` and `RIVER_API_KEY` are read from the environment or `.env`. The `memorable` CLI needs to be on `PATH` with an owner config at `~/.memorable/config.json`.

Easy set (`POC_OUT` defaults to `data/poc`):

```sh
PYTHONPATH=$PWD python scripts/poc_draft_verify.py frontier memorable
PYTHONPATH=$PWD RIVER_API_KEY=... python scripts/poc_draft_verify.py train eval
PYTHONPATH=$PWD python scripts/poc_draft_verify.py local
```

Acme set:

```sh
export POC_SET=acme POC_OUT=data/poc-acme
PYTHONPATH=$PWD POC_FRONTIER_MODEL=gpt-4.1-mini python scripts/poc_draft_verify.py frontier
PYTHONPATH=$PWD POC_FRONTIER_MODEL=gpt-4o-mini python scripts/poc_draft_verify.py frontier
PYTHONPATH=$PWD python scripts/poc_draft_verify.py memorable
PYTHONPATH=$PWD RIVER_API_KEY=... POC_STEPS=60 POC_LR=5e-5 POC_RANK=16 python scripts/poc_draft_verify.py train eval
```

- **Frontier stage.** Rows that already pass are kept, and the second `frontier` call only re-asks the failed or missing rows. `POC_FRONTIER_GAP` (default 7 s) spaces the calls.
- **Run numbers.** `train` and `eval` write `train.jsonl` and `eval.jsonl`. The `-runN` files are copies of those, set aside after each run. Runs 1–4 used `POC_STEPS` = 14, 28, 40 and 60.
- **Not reproducible from the script.** `eval-base-docs.jsonl` (base 9B with the docs in the system prompt) isn't a stage in the script, and its settings aren't recorded.

## Related

- Issues: #150, #151, #152, #153
- PR: #149
