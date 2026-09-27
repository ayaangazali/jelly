# The owned model (#7, #22, #37)

River has no key for this team and the OpenAI project has no credit, so the graduated model is trained and served **on this machine**, behind the interface River would use. `graduate/registrar/train.py` has two backends with one shape, `train(chats, name, log)` and `complete(model, messages, tools)`: `LocalBackend` (CPU, torch + peft) and `RiverBackend` (river-client, picked when `RIVER_API_KEY` is set or the checkpoint is `river://...`). The router (`graduate/router/river.py`) chooses the backend from the registry's `model` field, so a River key swaps River in with no router change.

Pitch line: **"Trained on this machine from verified sessions; River would host the same thing."**

## Model: picked by measurement

Same prompt (OpenCode's `<env>` block, six task tools, broken state 09), greedy, 6 torch threads on the shared 8-core CPU, fp32:

| Base | Prefill | Decode | Tool call before training |
|---|---|---|---|
| **Qwen2.5-Coder-0.5B-Instruct** | 211 tok/s (1273 tok in 6.0 s) | 10.7 tok/s | none: prose about the test |
| Qwen2.5-Coder-1.5B-Instruct | 60 tok/s (21.1 s) | 2.1 tok/s | none: prose about pip |

Neither base model calls a tool unprompted, so neither wins on capability before training; the 1.5B is 4-5x slower per call. The 0.5B is the base. `GRADUATE_LOCAL_MODEL` overrides it.

## What the small model sees

`train.compact()` is applied in training and serving alike: OpenCode's ~25k-token system prompt becomes one line plus its `<env>` block, and its ten tools become the six the task uses (`bash edit glob grep read write`) with one-line descriptions. A session renders to ~1.5k tokens instead of ~27k, which is what makes CPU prefill usable. Loss is on assistant turns only (tool calls in Qwen's `<tool_call>` format, and the final answer), like River's `TrainOnWhat.ALL_ASSISTANT`.

## Run it

```bash
python -m graduate.registrar.dataset fix-failing-test          # data/fix-failing-test.chat.jsonl (#21)
graduate train fix-failing-test                                # or the consent endpoint (#25) launches it
graduate train fix-failing-test --use-checkpoint data/checkpoints/fix-failing-test-v1   # graduate without training
graduate train fix-failing-test --corpus                      # rebuild the data from /home/ubuntu/jelly-corpus/, then train
```

Writes `data/<task>.loss.jsonl` (step, loss, secs, peak RSS), `data/checkpoints/<task>-v<n>/` (LoRA adapter + tokenizer), and moves the registry TRAINING -> GRADUATED with `model` (checkpoint path), `serving: "checkpoint"`, `trained_on_runs`, `graduated_at`. Any failure or SIGTERM goes back to READY with an event; a TRAINING entry older than an hour is reset on the next start. Memory: LoRA r=16 on all projections plus the two tool-call token rows, gradient checkpointing, logits only at labelled positions, sessions capped at 3072 tokens (`GRADUATE_MAX_LEN`). Run it under a cgroup cap on a shared box: `systemd-run --user --scope -p MemoryMax=5G ...`.

## Reproduce the demo state

From any checkout of main with the `[train]` extra installed, the task type READY, and consent given:

```bash
graduate train fix-failing-test --use-checkpoint /home/ubuntu/jelly-corpus/checkpoints/fix-failing-test-v3   # GRADUATED in 0.07 s
```

The router then serves `fix-failing-test` sessions from that path, and `scripts/demo.sh --use-checkpoint /home/ubuntu/jelly-corpus/checkpoints/fix-failing-test-v3` does the same move on stage. Use v3: v1 and v2 learned this worktree's absolute paths.

Paths: `dataset.relative()` rewrites every path under OpenCode's working directory and workspace root to a relative one, and the directories themselves to `.`. It runs on the chat records and on every live request before the model sees it. So v3 and later learn `read calc/mod_09.py`, and the same checkpoint works from any checkout (checked from a second clone, below). v1 and v2 were trained on this worktree's absolute paths and only work from `/home/ubuntu/.treehouse/jelly-f3f5da/6/jelly`.

## Results

**Data.** 8 verified sessions of `fix-failing-test`, broken states 01-08, from the runner through the router to OpenCode. The model in those sessions is `scripts/stub-upstream.py` (a scripted `read`, `edit`, "Fixed."), not a frontier model: the OpenAI project has no credit, so no real corpus exists yet (`/home/ubuntu/jelly-corpus/` is empty). Retrain on the real corpus when it lands, with the task type READY and consent given: `graduate train fix-failing-test --corpus`. It reads `ledger.jsonl`, `stage-ledger.jsonl` and `sessions/` from `/home/ubuntu/jelly-corpus/` (another directory: `--corpus DIR`), rebuilds `data/fix-failing-test.chat.jsonl` from them, and trains.

**Training.** Every run: 24 steps (3 epochs), batch 1, AdamW lr 2e-4, 6 threads, under a cgroup memory cap.

| Checkpoint | Trainable | Wall clock | Peak RSS | Loss, step 1 -> 24 | Emits tool calls |
|---|---|---|---|---|---|
| `fix-failing-test-v1` | LoRA r16 | 631 s | 3.8 GB | 1.56 -> 0.29 | no: `<\|im_start\|>` where `<tool_call>` belongs |
| `fix-failing-test-v2` | LoRA r16 + the `<tool_call>` `</tool_call>` token rows | 708 s | 4.7 GB | 1.56 -> 0.002 | yes, with this worktree's absolute paths |
| **`fix-failing-test-v3`** | same as v2, records with relative paths | **602 s** | 4.7 GB | 2.35 -> 0.003 | yes, `calc/mod_09.py` |

v1 answered `<|im_start|>` where `<tool_call>` belongs, and the JSON inside was right. v2 also trains those two token rows (peft `trainable_token_indices`, +0.9 GB peak) and emits real tool calls. That fix is what we observed; the cause is not pinned down. All three checkpoints (45 MB adapters) and the v2 and v3 loss logs are kept at **`/home/ubuntu/jelly-corpus/checkpoints/`**. v3 finished 2026-09-27 10:21Z. Worktrees are disposable, and `data/` is not in git.

**Serving.** 3.2 GB RSS, 10 s to load on the first call. Each call is a 1.3-1.5k-token prompt and 3-86 output tokens, and takes 6-31 s on the shared 8-core box.

**Held-out result.** OpenCode sessions routed through the router (`graduate run`, frontier = the stub), on states the model never saw:

| Checkpoint, state | Owned session | Wall | Output tokens | Calls | Verify |
|---|---|---|---|---|---|
| v3, 09, **from a second clone** | title, `read calc/mod_09.py`, a no-op `edit`, "Fixed." | 48.4 s | 84 | 4 | exit 1 |
| v2, 09 | title, `read calc/mod_09.py`, `edit` (`"split"` -> `"join"`), "Fixed." | 55.4 s | 119 | 4 | exit 1 |
| v2, 10 | title, `read calc/mod_10.py`, `edit` (garbled line), "Fixed." | 68.9 s | 146 | 4 | exit 1 |

OpenCode parsed every synthesized stream and ran every tool call without an error. The v3 run came from a fresh `git clone` at another path, with 0 frontier calls in the owned session. OpenCode resolved the model's relative `calc/mod_09.py` inside that clone's `demo-repo` and returned the planted bug. The model learned the procedure (read the failing module, edit it, stop) but not how to fix a bug it never saw: 8 scripted sessions teach a swap of one planted line. Both failures went to the escalator (#23), which reset the repo and reran on the frontier (stub), exit 0.

**For the pitch.** A live owned session takes about a minute, so the demo replays a recorded one and the live one is optional. Say: "trained on this machine from verified sessions; River would host the same thing." Don't claim the owned model fixes new bugs: on held-out states it didn't.
