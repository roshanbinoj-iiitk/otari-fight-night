# Experiments

All runs PRESET=medium. Iteration seed 4242 (ROWS=50 unless noted). Held-out seeds for
validation: 1717, 90210, 31337. Temperature is fixed by the referee at 0.1, so reruns are close
to deterministic but not bit-identical.

Net repair = (fixed - broken) / problems. "Delta" = team minus stock on the same file.

## E0. Baseline (starter `small-batches`: stock with batch 5)

| run | seed/rows | stock | team | delta | fixed/broken (team) | team s | requests | tokens (p/c) | weights |
|---|---|---|---|---|---|---|---|---|---|
| 20261127T084543949498Z | 4242/20 | 51.2% | 46.3% | -4.9 | 24/41, 5 broken | 43 | 10 | - | 1.93 GB |
| 20261127T084734508694Z | 4242/50 | 59.1% | 52.7% | -6.4 | 59/93, 10 broken, 1 junk kept | 112 | 24 | 28596/7104 | 1.93 GB |

Stock on 4242/50: 58/93 fixed, 3 broken, 107 s, 12 requests, 17554/6753 tokens.

The shipped starter loses to stock on this machine and seed. Smaller batches fixed more amounts
and dates but broke more clean cells (notes) and kept a junk row.
