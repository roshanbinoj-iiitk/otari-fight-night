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

## Failure analysis of the baseline (seed 4242, starter team)

Diffed `data/team.clean.csv` and `data/stock.clean.csv` against messy and golden (analysis only).

| column | starter unfixed | starter broken | stock unfixed | stock broken | dominant cause |
|---|---|---|---|---|---|
| category | 20 | 0 | 18 | 0 | synonyms (Travel, commute, work, power/water, Movies & Music) and capitalized words (Rent, Groceries) copied through |
| vendor | 9 | 0 | 8 | 1 | swapcase/upper (rAPID rAIL, CABLE DEPOT) left as is or uppercased |
| note | 3 | 2 | 1 | 2 | curly quotes kept; a note copied from a neighbouring row |
| date | 1 | 3 | 2 | 0 | `2026` rewritten as `2022`; 8/2/26 read as Feb 2 |
| amount | 1 | 0 | 6 | 0 | `USD`/`$` left on whole unparsed batches |
| junk kept | 1 | | 0 | | header row returned with `"id": "drop"` |

Raw replies (captured with a scratch harness that calls Ollama directly with the referee's own
`run_team`) showed two root causes that are not about knowledge at all:

1. The model writes `"id": "drop"` instead of `"drop": true`. `_merge` cannot match that answer to
   a row, so the whole row's fixes are thrown away ("rows lost or garbled").
2. Doing five columns at once, the rule "category is lowercase" bleeds into vendor (`taco lane`)
   and notes drift between rows.

Hypotheses, each tied to a stage type:

| # | hypothesis | stage |
|---|---|---|
| H1 | Generator knowledge (vendor list, vendor->category map, synonyms, date formats, year 2026) fixes category and vendor | map (prompt) |
| H2 | Splitting columns into a format map and a lookup map stops cross-column bleed | map + map |
| H3 | A stage that returns only its own keys cannot break other columns (`_merge` only applies returned keys) | map (output contract) |
| H4 | Duplicates kept forfeit whole rows of repairs; a dedicated whole-file removal stage fixes that | map (dedupe) |
| H5 | The stock-style verify adds time and broken cells once the maps are right | verify (remove?) |
| H6 | A smaller model can do the narrow stages (dedupe, lookup) | model swap |

## Harness iterations (scratch harness, direct Ollama, same referee code and grader; not scored)

Fast loop before confirming with `make fight`. Seed 4242/50 unless noted. Stock on harness: 4242 n/a
(fight: 59.1), 1717 54.9%, 90210 63.1%.

| id | change | 4242 | 1717 | 90210 | note |
|---|---|---|---|---|---|
| H-base | starter | 49.5 | | | |
| E1 | knowledge-rich single cleaner (H1) | 61.3 | | | category 24->62%, but 8 vendors lowercased |
| E2 | split into format + lookup maps, full rows (H2) | 67.7 | | | vendor 89%; format stage 23 rows unparsed (`"id": "drop"`) |
| E3 | + dedupe map, partial-key outputs (H3/H4), stock check kept | 68.8 | | | dedupe echoed rows; check re-broke categories |
| E3b | few-shot lookup, no check stage (H5) | 83.9 | 58.5 | 68.9 | dup kept 4 and 8 on held-out seeds |
| dd | dedupe alone, qwen2.5:3b b80/b20 | dup 3 | dup 4-5 | dup 8 | a 3B does not find repeated ids |
| dd | dedupe alone, gemma3:4b | dup 3 | 6 | 5 | and breaks rows |
| dd | dedupe alone, llama3.2:3b | dup 4 | 1 | 0 | |
| dd | dedupe alone, qwen2.5:1.5b b80 | dup 0 | 0 | 0 | marks nearly every row; plain code keeps unique rows (~44 refused) |
| F1 | dedupe 1.5b + format 3b + lookup 3b | 87.1 | 74.4 | 79.6 | 1717 took 309 s: 1.5b looped on one id to max_tokens |
| F2 | all three stages on qwen2.5:1.5b | 72.0 | 63.4 | 65.0 | 0.99 GB, but category 33-65% |
| F3 | dedupe 1.5b + format 3b + lookup 1.5b | 73.1 | 61.0 | 66.0 | 1.5b cannot do the lookup |
| F1b30 | F1 with dedupe batch 30 (bounds the loop) | 77.4 | 76.8 | 78.6 | 1717 back to 86 s |
| F1b30' | + de-leaked format prompt (placeholders, varied dates, note/tab rules) | 89.2 | 80.5 | 69.9 | 90210: one batch wrote 17.18 as 1718.00, lookup swapped two rows |

## Official fights, seed 4242, PRESET=medium ROWS=50 (`make fight`)

Each fight reruns stock. Stock on the same file swung from 31.2% to 59.1% across these fights
(temperature 0.1 and batch effects), so the delta column is noisy; compare team net repair
across rows, which all ran on the identical messy file (sha `8be9c6cd28d0`).

| run | team | stages | team net | fixed/broken | dup/junk kept | team s | req | weights | stock in same fight | delta |
|---|---|---|---|---|---|---|---|---|---|---|
| 20261127T084734508694Z | starter | clean, check | 52.7 | 59/10 | 0/1 | 112 | 24 | 1.93 | 59.1 | -6.4 |
| 20261127T102347842359Z | E1 knowledge prompt | clean, check | 69.9 | 74/9 | 0/0 | 90 | 23 | 1.93 | 40.9 | +29.0 |
| 20261127T101553122075Z | final minus lookup | dedupe, format | 37.6 | 38/3 | 1/0 | 106 | 13 | 2.92 | 45.2 | -7.6 |
| 20261127T101256776283Z | final minus dedupe | format, lookup | 65.6 | 70/9 | 5/1 | 76 | 24 | 1.93 | 47.3 | +18.3 |
| **20261127T100903389501Z** | **final** | dedupe, format, lookup | **87.1** | 84/3 | 1/0 | 123 | 24 | 2.92 | 52.7 | **+34.4** |
| 20261127T101913707345Z | final plus check | + verify | 89.2 | 89/6 | 0/0 | 182 | 35 | 2.92 | 31.2 | +58.0 |

`uv run fight.py compare runs/20261127T084734508694Z runs/20261127T100903389501Z`:
net repair +34.4, fixed +25, broken penalties -7, request seconds +11.6, requests +0,
prompt tokens +3465, completion tokens -930.

Per-stage evidence (each row differs from final by one stage):
- **lookup** is worth 49.5 points (87.1 vs 37.6): vendor and category are a table lookup.
- **dedupe** is worth 21.5 points (87.1 vs 65.6): without it 5 duplicate ids and a junk row
  survive, and each duplicate forfeits all of that row's repairs.
- **check (verify)** adds 2.1 points for +59 s and +11 requests on this seed; decided on
  held-out seeds below.
- Splitting the work (final) beats the knowledge-rich single cleaner (E1) by 17.2 points on
  the same file.

## Held-out validation (official fights, PRESET=medium ROWS=50)

| seed | stock (same fight) | final | delta | final s | plus-check | delta | plus-check s |
|---|---|---|---|---|---|---|---|
| 4242 | 52.7 / 31.2 | 87.1 | +34.4 | 123 | 89.2 | +58.0 | 182 |
| 1717 | 57.3 / 56.1 | 76.8 | +19.5 | 89 | 82.9 | +26.8 | 121 |
| 90210 | 68.0 / 59.2 | 81.6 | +13.6 | 83 | 82.5 | +23.3 | 121 |
| 31337 | 67.8 / 63.2 | 83.9 | +16.1 | 74 | 85.1 | +21.9 | 127 |
| mean | 58.1 (8 fights) | **82.4** | | **92** | 84.9 | | 138 |

Runs: 1717 `20261127T102724090200Z` / `20261127T103030366958Z`, 90210 `20261127T103406305692Z` /
`20261127T103711177378Z`, 31337 `20261127T104048114778Z` / `20261127T104334689325Z`.

The final team beat stock on every seed with 0 duplicates, 0 junk, 0 real rows dropped on all
held-out seeds. The verify stage helps on 4/4 seeds, but only by 0.9 to 6.1 points (mean +2.5)
for +50% time and +10 requests. **Decision: no verify stage.** Every stage that remains is worth
20+ points in its ablation, and the team stays faster than stock.

## Pound for pound (means over the 4 seeds above)

| team | weights | mean net repair | net repair per GB | mean request s | net repair per 100 s |
|---|---|---|---|---|---|
| stock | 1.93 GB | 58.1 | 30.1 | ~96 | 60.5 |
| **final (dedupe-format-lookup)** | 2.92 GB | 82.4 | 28.2 | 92 | **89.6** |
| final plus check | 2.92 GB | 84.9 | 29.1 | 138 | 61.5 |
| final minus dedupe (4242 only) | 1.93 GB | 65.6 | 34.0 | 76 | 86.3 |
| all qwen2.5:1.5b (harness, 3 seeds) | 0.99 GB | 66.8 | 67.5 | ~200* | - |

*harness timing, includes the 1.5b loop on seed 1717.

Net repair *gained over stock* per GB: final (82.4 - 58.1) / 2.92 = **+8.3 points per GB**. The extra
1 GB (qwen2.5:1.5b for dedupe) is what buys the dedupe stage's ~20 points; dropping it raises
per-GB efficiency but loses ~17 points of repair. The all-1.5b team is the most efficient per
GB but repairs 15 points less than final; I chose repair.

Memory: qwen2.5:3b (1.9 GB on disk, 2.2 GB loaded) + qwen2.5:1.5b (1.0 GB, 1.4 GB loaded),
with stock's qwen2.5:3b shared. Under 4 GB of model memory, far inside 16 GB. On the 4 GB GPU,
`ollama ps` showed qwen2.5:1.5b split 64%/36% CPU/GPU while qwen2.5:3b held the VRAM.

## Final scored run (`make fight`, defaults)

Run `20261127T105124875965Z`, random seed 462585, 59 messy rows, 90 problems. Team 75.6% (73/90
fixed, 5 broken, 0 dup, 0 junk, 0 dropped) in 85 s, 22 requests, 2.92 GB. Stock 24.4% (44/90,
22 broken incl. 2 junk rows kept) in 101 s. Delta +51.2; stock's low score here is noise (see the
4242 spread), the held-out mean delta is about +21. 100% local, stock sha `13571dac3037`, answer-key
check clean, `uv run fight.py check-card fight-card.json` -> PASS. Team sha `e4f20eda099e`.
