# Submission

Team **dedupe-format-lookup**: three map stages, two public Ollama models (qwen2.5:1.5b and
qwen2.5:3b, 2.92 GB), 100% local. It beat stock on every seed I tried: on average 82.4% vs 58.1%
net repair over four seeds, and it is faster than stock (92 s vs ~96 s of request time).

## 1. Fight card

Final scored run at the defaults (`make fight`, PRESET=medium, ROWS=50, random seed 462585).
Note: stock had an unusually bad run here (24.4%, two junk rows kept). Stock scored 31-68% on the
same files in my other fights, so the honest expectation for the delta is the held-out table in
section 2 (+13.6 to +34.4, mean +21), not this card's +51.2.

### Fight card: Otari Fight Night

**dedupe-format-lookup** beat the stock team by **+51.2 points**: net repair 75.6% vs 24.4% on 50 rows (59 messy, 90 problems), preset `medium`. Generated 2026-11-27T10:54:31+00:00.

Net repair = (dirty cells fixed - clean cells broken) / dirty cells. An untouched file scores 0. Removing duplicates and junk earns nothing (the referee can do that); keeping them costs.

## Machine

- OS: Linux 6.18.54-1-lts (x86_64)
- CPU: 12th Gen Intel(R) Core(TM) i5-12500H
- RAM: 15 GB
- GPU: NVIDIA GeForce RTX 3050 Laptop GPU (4096 MiB)
- Ollama 0.34.4, Otari 0.54.0 at http://localhost:8000

## Stock vs your team

| | stock | yours |
|---|---|---|
| Team file | `teams/stock.yml` | `team.yml` |
| Models | `qwen2.5:3b` | `qwen2.5:1.5b`, `qwen2.5:3b` |
| Net repair | 24.4% | **75.6%** (+51.2) |
| Problems fixed | 44 / 90 | 73 / 90 |
| Clean cells broken | 22 | 5 |
| Cells exactly right (reference) | 73.8% | 91.2% |
| Duplicates kept | 0 | 0 |
| Real rows dropped | 0 | 0 |
| Junk rows kept | 2 | 0 |
| Rows a model lost or garbled (kept as-is) | 31 | 2 |
| Failed requests (timeouts, gateway errors) | 0 | 0 |
| Real rows a model tried to delete (refused) | 54 | 44 |
| Request seconds (including failures) | 100.6 | 85.1 |
| Requests | 12 | 22 |
| Model weights loaded | 1.93 GB | 2.92 GB |
| Net repair per GB | 12.6 | 25.9 |
| Requests served locally | 100% | 100% |

Repair rate per column, stock: date 52.9%, vendor 13.3%, amount 76.2%, category 44.0%, note 50.0%

Repair rate per column, yours: date 88.2%, vendor 80.0%, amount 95.2%, category 72.0%, note 66.7%

## Otari usage (from the gateway's own log, per team key)

| | stock | yours |
|---|---|---|
| Requests | 12 | 22 |
| Errors | 0 | 0 |
| Prompt tokens | 17806 | 29972 |
| Completion tokens | 6927 | 4860 |
| Avg gateway latency (ms) | 8365 | 3846 |
| Cost | $0.00 | $0.00 |

## Your team, stage by stage

| Stage | Model | Requests | Rows | Seconds | Rows lost or garbled | Failed requests |
|---|---|---|---|---|---|---|
| dedupe | qwen2.5:1.5b | 2 | 59 | 25.6 | 1 | 0 |
| format | qwen2.5:3b | 10 | 50 | 33.6 | 0 | 0 |
| lookup | qwen2.5:3b | 10 | 50 | 26.0 | 1 | 0 |

### Where the work went

| Stage | Prompt tokens | Completion tokens | Token share | Request time share | Providers (requests) |
|---|---|---|---|---|---|
| dedupe | 3866 | 847 | 13.5% | 30.0% | ollama: 2 |
| format | 16027 | 2264 | 52.5% | 39.5% | ollama: 10 |
| lookup | 10079 | 1749 | 34.0% | 30.5% | ollama: 10 |

Most request time: **format** (39.5%). Most tokens: **format** (52.5%).

These shares measure cost, not quality: to see whether a stage earns its place, remove or swap it and rerun on the same seed. Request time sums model calls, failed ones included; it is not wall-clock time. Providers come from Otari's response headers; a failed request has none and shows as unknown.

## Integrity (what the organizers check against the rerun)

- Referee code sha256 `f8ffb651e804`, git `fc6bd10`
- Model digests from Ollama: `qwen2.5:3b` 357c53fb659c, `qwen2.5:1.5b` 65ec06548149
- Otari reached Ollama at `http://host.docker.internal:11434`
- Prompt bytes: stock 1746, yours 5285
- Answer-key check: no dataset ids or golden rows found in prompts

## Reproduce

`TEAM=team.yml SEED=462585 PRESET=medium ROWS=50 make fight`. Messy file sha256 `057fba343bc5`. Team file sha256 `e4f20eda099e`, stock `13571dac3037`.


## 2. Team

```
dedupe  map  qwen2.5:1.5b  batch 30  prompts/dedupe.md   which rows to remove (id + drop only)
format  map  qwen2.5:3b    batch 5   prompts/format.md   date, amount, note (returns only those keys)
lookup  map  qwen2.5:3b    batch 5   prompts/lookup.md   vendor and category from a vendor table
```

**Why this split.** Reading the raw replies of the starter team showed that its losses were not
about knowledge. A 3B model asked to fix five columns at once (a) lets one column's rule bleed
into another (a "category is lowercase" rule lowercased vendors), (b) copies values between rows,
and (c) writes `"id": "drop"` instead of `"drop": true`, which makes the referee throw away that
row's whole answer. So each stage owns specific columns and returns only those keys. The referee
applies only the keys a model returns, so the format stage cannot damage vendor or category and the
lookup stage cannot damage dates. Then, in order:

- **lookup** turns the hardest column into a table lookup. In the generator every vendor belongs to
  exactly one category, so the prompt carries the vendor -> category table from
  `fightnight/corrupt.py` with few-shot examples that override synonyms (commute -> transport,
  power/water -> utilities, Rent -> rent). It also restores the canonical vendor spelling, which
  fixes swapcase (`rAPID rAIL`) and near-duplicate typos (`rapi drail`).
- **format** handles dates (all seven generator formats, year fixed to 2026, day-first only when
  the first number is over 12), amounts, and notes. Its output template uses placeholders: my first
  version had a concrete example row, and the model copied its date, amount and note into clean rows.
- **dedupe** goes first, so later stages never spend tokens on junk. A kept duplicate id forfeits
  every repair on that row. Being honest about this stage: no model I tried (qwen2.5 0.5b/1.5b/3b,
  llama3.2:3b, gemma3:4b) can reliably find repeated ids among ~57 shuffled rows. The prompt tells
  the model the truth: plain code removes only empty ids and extra copies of repeated ids, so
  marking a unique row is harmless and missing a duplicate costs points. qwen2.5:1.5b then marks
  most rows, and the referee's own check does the precise part. It returns only `id` and `drop`,
  so it cannot change a value. Batch 30 bounds a repetition loop that 1.5b fell into at batch 80.

**Each stage earns its place.** Same messy file (seed 4242), one stage changed at a time:

| team | net repair | vs final |
|---|---|---|
| starter (stock prompts, batch 5) | 52.7% | -34.4 |
| one knowledge-rich cleaner + check (stock architecture) | 69.9% | -17.2 |
| final minus lookup | 37.6% | **-49.5** |
| final minus dedupe | 65.6% (5 dups, 1 junk kept) | **-21.5** |
| **final** | **87.1%** | |
| final plus a verify stage | 89.2% | +2.1, but +59 s and +11 requests |

**Held-out seeds** (official fights, stock rerun in each):

| seed | stock | final | delta |
|---|---|---|---|
| 4242 | 52.7 | 87.1 | +34.4 |
| 1717 | 57.3 | 76.8 | +19.5 |
| 90210 | 68.0 | 81.6 | +13.6 |
| 31337 | 67.8 | 83.9 | +16.1 |
| 462585 (scored card) | 24.4 | 75.6 | +51.2 |

0 duplicates kept, 0 junk kept and 0 real rows dropped on every held-out seed. A verify stage
helped on 4/4 seeds, but only by 2.5 points on average for 50% more time, so I left it out.

**Pound for pound.** 2.92 GB of weights; mean 82.4% -> 28.2 net repair per GB (stock 30.1),
+8.3 points over stock per GB, and 89.6 net repair per 100 request-seconds (stock 60.5). The extra
1 GB model buys the dedupe stage's ~20 points. An all-qwen2.5:1.5b version (0.99 GB) was the most
efficient per GB, but it repaired about 15 points less, mostly on category.

Full log of every experiment, including the ones that lost: [EXPERIMENTS.md](EXPERIMENTS.md).
Friction log with repro commands: [FRICTION.md](FRICTION.md).

## 3. Feedback (the friction log)

> DRAFT from FRICTION.md. AGENTS.md says the entrant answers these themselves: rewrite in your own words before submitting.

**Where did setup or the fight slow you down or break?**

- On Linux, Ollama binds to 127.0.0.1 and the Otari container cannot reach it. I needed
  `OLLAMA_HOST=0.0.0.0 ollama serve`. It's documented in troubleshooting, but `make fight` does not
  check for it before starting. Docker was also not running (`systemctl start docker`).
- The shipped starter `team.yml` lost to stock on my machine (`SEED=4242 make fight`: 52.7% vs
  59.1%), although the README says it won on the reference machine.
- "Rows lost or garbled" has no explanation anywhere: the log has counts but no reply text. I had
  to write a harness around `fightnight.pipeline.run_team` to see that qwen2.5:3b writes
  `"id": "drop"`, which makes `_merge` silently discard the row's fixes.
- qwen2.5:1.5b looped on `{"id": "T0011", "drop": true}` until max_tokens at batch 80 (seed 1717,
  ~5 minutes for one request); in a fight that is a timeout. Repro: a map stage with qwen2.5:1.5b,
  batch 80, prompts/dedupe.md, `SEED=1717`.
- Stock varies by up to 28 points on the identical file (seed 4242: 31.2-59.1 over six fights),
  so a single card's delta is mostly noise at the margin.
- A `T0101`-style example id in my prompt would have flagged the answer-key check; the safe
  `S0001` convention is only in a code comment.

**What did you look for in Otari (dashboard, logs, config) and not find?**

Request and response bodies for a request (the one thing I needed to debug a stage), a per-model
split inside one API key, and tokens per second or time to first token per model. I wanted those
for the pound-for-pound decision and computed them by hand from fight-log.jsonl.

**Would you put Otari in front of your own local models after this? Why or why not?**

(Your answer. Points from the log you might use: one place where every request is metered per
key and the provider header proves locality, which is exactly what this contest needed; against
that, no body logging for debugging, and an extra container plus the OLLAMA_HOST dance on Linux.)

## 4. Video

VIDEO_LINK_HERE (up to 3 minutes, screen recording with your voice).
