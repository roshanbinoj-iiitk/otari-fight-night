# Experiment comparison

Recorded November 20, 2026 on an Apple M5 Pro with 48 GB RAM, Ollama 0.40.15,
Otari 0.54.0, and qwen2.5:3b. Both runs used seed 20261120, preset medium,
and 20 golden rows (25 messy rows). The second team removes the verifier from
an otherwise identical starter.

The first card attributed 52.9% of request time and 47.8% of tokens to the check
stage. Removing it saved time but this pair's quality fell. These are independent
model runs: the unchanged stock also varied from 47.2% to 55.6% net repair.
This is a workshop example, not a repeated estimate of the verifier's contribution.

Reproduce the exercise (scores and times will vary):

```bash
SEED=20261120 ROWS=20 make fight
TEAM=teams/no-verifier.yml SEED=20261120 ROWS=20 make fight
uv run fight.py compare runs/<first-run> runs/<second-run>
```

After minus before, on the same messy dataset. Positive resource deltas mean more work.

| Metric | Before | After | Change |
|---|---|---|---|
| Net repair (points) | 44.4 | 0.0 | -44.4 |
| Dirty cells fixed | 21 | 15 | -6.0 |
| Broken-cell penalties (includes junk) | 5 | 15 | +10.0 |
| Request seconds | 33.9 | 17.9 | -16.0 |
| Requests | 10 | 5 | -5.0 |
| Failed requests | 0 | 0 | +0.0 |
| Prompt tokens | 11977 | 6357 | -5620 |
| Completion tokens | 2862 | 1357 | -1505 |
| Gateway-reported cost (USD) | $0.00 | $0.00 | +0.0000 |

Models: qwen2.5:3b → qwen2.5:3b.
Team and prompt hash: `ae6f6df082b8` → `3f2a61dbe519`.

These are whole-team results, not proof of any individual stage's contribution. Change one thing, repeat the run, and check another seed before drawing a conclusion.
