---
title: "Risks and Fallbacks"
project: "GRADUATE"
event: "Own Your Intelligence Hackathon (YC, 2026-09-27)"
purpose: "Ranked failure modes, each with a mitigation decided in advance."
updated: "2026-09-26"
related:
  - 03-build/hour-by-hour.md
---

# Risks and Fallbacks

Ordered by probability × damage.

---

### 1. Training does not finish in the window
**Likely.** Fine-tuning is wall-clock you cannot compress, and RL is far worse.

**Mitigations:**
- Train a model on the pre-generated corpus **Saturday night**. Arrive with a graduated model in hand.
- Submit a real job live at ~2:30 so judges see the real call, then demo against the pre-trained model.
- Be explicit: "this job is running now, this model finished this morning." Honesty here costs nothing and buys credibility.

---

### 2. Memorable's export path is not what you assumed
**Moderate.** The site documents `list`, `show`, `recall` and an MCP server, but not necessarily a clean bulk export into training format.

**Mitigations:**
- Ask their team at lunch. They are in the room and want you to succeed.
- Their traces are documented as one JSON blob to `POST /v1/extract`, so the schema is known. Worst case, read the local store directly.
- Absolute fallback: your own thin trace logger in the router, since every call already passes through it. Costs ~30 minutes and loses the deep Memorable integration, so it is a last resort.

---

### 3. Task-type classification is worse than expected
**Moderate.** Clustering agent prompts into types is genuinely hard and easy to sink an hour into.

**Mitigations:**
- Ship exact-template matching only. Add embeddings if time allows.
- The demo repo uses one deliberate task type, so classification barely matters on stage.
- Say it out loud as future work. Judges respect a named limitation more than a hidden one.

---

### 4. The graduated model is bad and fails on stage
**Moderate, and survivable if you plan for it.**

**Mitigation:** the escalator makes this a *feature*. A failure caught by the verifier and escalated to the frontier model is a planned part of the demo. Rehearse it deliberately so an unplanned one looks identical.

---

### 5. The proxy breaks an agent's behavior
**Low probability, high damage.** Streaming, tool-call formats and provider-specific fields are where OpenAI-compatible proxies break.

**Mitigations:**
- Build and test it **Sunday morning**, not during the window.
- Pass through unknown fields untouched. Do not parse what you do not need.
- Test with the exact harness used in the demo, not a curl command.

---

### 6. Scope creep
**High probability.** Six sponsors, and a temptation to touch all of them.

**Mitigations:**
- Follow the cut-line table in `hour-by-hour.md` literally.
- One stretch item at 4:35, not two.
- No new dependencies after 3:30.

---

### 7. The environment eats the window
**Common killer.** A slow `pip install` per worktree, a repo whose tests take 4 minutes, a flaky auth flow.

**Mitigation:** the 60-second cold-start requirement in the pre-event checklist. Test it Saturday, not Sunday.

---

### 8. Overclaiming
**Low probability, fatal damage.** Judges built these tools and will know instantly.

**Rules:**
- Never present Memorable's benchmark numbers as your results. Cite them as theirs.
- Never say a model was RL-trained today unless it was.
- Use only verified numbers. Caching figures were confirmed 2026-09-26 (both providers 90% off cached input, output undiscounted); re-check per-model prices before a slide.
- Say "designed, not built" for the QM fleet story if you did not build it.

---

### 9. Someone else builds something similar
**Low.** The exit-code-as-reward framing is not obvious, and most teams will build agent apps rather than infrastructure under the fleet.

**Mitigation:** if it happens, your differentiator is the verified escalation path and the one-env-var integration. Lead harder on those.

---

## Single biggest failure mode

Spending the window on the training pipeline and arriving at 4:55 with no dashboard. **The demo is the product.** If it comes down to it, a pre-trained model plus a beautiful live graduation beats a real training run nobody can see.
