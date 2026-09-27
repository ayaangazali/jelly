# Mock-up

A bare-bones, clickable front end showing how GRADUATE should look and behave. It's one HTML file with no build step. All data is sample data, and nothing talks to a real model.

## Open it

```sh
open mock-up/index.html
# or, if fonts or hash links misbehave from file://
cd mock-up && python3 -m http.server 8765   # then visit http://localhost:8765
```

## Walk the story (about a minute)

1. **Overview.** Four task types in different states: one learning at 4 of 5, one graduated, one early, and one on probation. The activity log is on the right.
2. Click **Play the demo story**. A fifth passing run comes in, *Fix a failing test* reaches 5 of 5, and a banner asks you to review the training data.
3. Click **Review training data**. This is the consent screen: exactly what gets sent to River, what stays local, and one record as it would be sent.
4. Click **Approve and train**. The row shows training progress, then the task page opens with the **Graduated** stamp. A new run goes to your model: 3 turns instead of 16, verified.
5. Click **Force a failure** (three times to reach probation). Each failure is caught by the tests, re-run on the frontier model, and saved as a negative example. After 3 failures the task type goes on probation.
6. **Setup** shows the one setting each tool needs. It's honest about Codex: that isn't supported yet.
7. **Reset** starts over.

## What to react to

Tell me what you like and don't like on any of these. Every answer changes what gets built.

- **Overall feel.** Cool grey paper, navy ink, indigo for "yours", and a rubber-stamp moment when a task graduates. Too quiet, too loud, or right?
- **The headline number.** Is "$ saved" the right hero? Or should it be turns saved, or runs handled by your models?
- **The roster table.** Do the columns (state, turns, tool calls, cost per run, goes to) answer your first questions?
- **The task page.** Is the lifecycle strip clear? Are the frontier-versus-your-model bars convincing enough for judges?
- **The consent screen.** Right level of detail, or too much?
- **The activity log.** Is its wording clear to someone who has never seen the product?
- **Anything missing** you expected to see, such as a cost chart over time, a per-harness view, or River training loss.

## What's real versus mocked

| In the mock-up | In the real product |
|---|---|
| Sample numbers | Measured by the proxy (#17), baseline with caching on |
| "Training" is a 5-second progress bar | A River SFT loop (#22). Minutes, not seconds |
| Mock-up controls bar | Removed. The real demo is driven by `scripts/demo.sh` (#31) |
| Model ids like `river://run-4c1e/sampler_weights/…` | Real River checkpoint paths, in the format River uses |

The live dashboard (#15, #24) starts from this file.
