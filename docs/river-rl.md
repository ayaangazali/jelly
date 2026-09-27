# Exit Code RL spike (#10)

The question: can the verify command's exit code be the reward for an RL step, and is a step fast enough (under 3 minutes) to show during the demo?

## River

River's `rl.Env` can't be run yet. The one capability call made on 2026-09-27 at 10:15 PT with the `.env` key returned:

```
RiverConnectionError Server capacity exceeded. Try again later. [RESOURCE_EXHAUSTED] - billing: insufficient_funds
```

The key is valid, but the account has no credits (same as in `docs/river-api.md`). River publishes no step durations, so this spike doesn't measure one.

## What ran instead

`graduate/rl_env.py` defines `ExitCodeEnv(rl.Env)`, which is River's own env shape:

- `reset(row)`: the task prompt from `demo-repo/tasks/NN.json`, plus the broken module and its test.
- `reward(traj, row)`: takes the ```` ```python ```` block from `traj.final_text`, writes it over `calc/mod_NN.py` in a temp copy of the planted repo, runs the task's `verify` command and returns `1.0` if the exit code is 0, else `0.0`.

River runs the reward in our own process, so this env can go straight into `rl.RolloutEngine` once the account has credits. Until then, `python -m graduate.rl_env` drives the env locally:

- It plants each broken state with `scripts/reset-demo.sh NN`, then resets the demo repo to clean.
- For each step, it samples a group of K completions from Qwen2.5-Coder-0.5B-Instruct plus a fresh LoRA (r=16 on q/v, T=1.0).
- It scores every completion with the exit code.
- It applies one GRPO-style update: the advantage is the reward minus the group mean, the loss is minus the advantage times the mean token log-prob, and the optimizer is Adam at lr 1e-4.
- When a group's rewards are all equal, the advantage is zero and no update happens (`"updated": false`).

## Run

Run on an Apple M4 with 16 GB, on CPU with 6 threads. The run started at **2026-09-27T17:30:39Z** (10:30 PT).

```
python -m graduate.rl_env --steps 10 --group 8 --tasks 01,02,03,04,05,06,07,08,09,10
```

| step | task | rewards (K=8) | mean reward | updated | wall-clock |
|---|---|---|---|---|---|
| 1 | 01 | 0 0 0 0 0 0 0 0 | 0.0 | no | 7.0 s |
| 2 | 02 | 0 0 0 0 0 0 0 0 | 0.0 | no | 5.8 s |
| 3 | 03 | 0 0 0 0 0 0 0 0 | 0.0 | no | 6.5 s |
| 4 | 04 | 0 0 0 0 0 0 0 0 | 0.0 | no | 9.7 s |
| 5 | 05 | 1 0 0 1 0 1 1 0 | 0.5 | yes | 11.0 s |
| 6 | 06 | 1 0 0 0 0 0 0 0 | 0.125 | yes | 8.9 s |
| 7 | 07 | 1 0 1 1 1 1 1 1 | 0.875 | yes | 16.0 s |
| 8 | 08 | 0 0 0 0 0 0 0 1 | 0.125 | yes | 14.3 s |
| 9 | 09 | 0 0 0 1 0 1 0 0 | 0.25 | yes | 12.1 s |
| 10 | 10 | 0 0 0 0 0 0 0 0 | 0.0 | no | 6.6 s |

The whole run, including model load, took 1 min 43 s. Five steps had mixed rewards and applied a real LoRA update. The slowest step took 16 s.

**What this shows:**

- The exit code works end to end as the reward. It separates passing patches from failing ones.
- A local step is far under 3 minutes.

**What it doesn't show:** that the model improved. Each step used a different broken state, so the rows can't be compared as a curve. The differences in mean reward between rows reflect how hard each task is for the base model. They don't show learning.

On 01, the base model echoes the broken `a - b` back unchanged. An earlier run on 01 alone (2 steps, K=4, 17:16:24Z) scored 0 on every sample and made no update.

## Verdict

**Build #30, locally.** A step takes 6–16 s on this machine, so a few steps fit on stage. Honest framing for the demo: "the reward is the test's exit code; here are N steps with their real start time". Showing an improvement curve would need repeated steps on the same task with a before/after eval, which hasn't been run.

The River step time stays unknown until the account has credits.
