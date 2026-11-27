# Otari Fight Night v2: CSV cleanup fight

Date: 2026-11-20. Status: approved in conversation, replaces the Codebreaker game.

## Intent

A two-week mini hackathon ($100 prize) where devs run Otari locally as the router in
front of a small team of local models, point that team at a mundane task on their own
machine, and leave with (a) a working gateway, (b) a team file that is a usable local CSV
cleaner, and (c) knowledge of what their hardware can run. The takeaway: Otari sits in
front of every agent, local or hosted, and the usage log proves what each one touched.

Codebreaker (v1) was dropped because models up to 8B never cracked a 4x6 code, so every
round was decided by latency. Local models should look useful, not dumb.

## Goals

- `make fight` works first try on a laptop with Ollama, Docker and uv. Under 5 minutes
  on an M2 Pro 16 GB with the stock team.
- Entrants edit one file, `team.yml`, and the fight shows whether their split of the job
  beat the stock team on their machine.
- Every fight card is evidence: accuracy, delta vs stock, seconds, tokens, model weight
  loaded, and the share of row-processing requests served by the local provider.
- `make clean FILE=x.csv` runs the entrant's team on any CSV. The tool they keep.

## Non-goals

- A general agent framework. Four stage types, no plugins, no code in team files.
- The blind frontier coach. Stretch goal in the README for round two.
- Connectors to inboxes or Sheets. A CSV export is the connector.
- Comparable absolute scores across machines. Only the delta vs stock and the live
  bracket on the host machine are comparable.

## Anti-goals

- A frontier model doing the rows. The card flags any non-local row request and the
  rubric scores it separately.
- Hand-written fixtures. The messy CSV must be regenerable from a seed.

## Constraints

- Otari 0.54.0 in Docker, Ollama on the host, Python 3.11+, httpx only, stdlib csv.
- Otari facts learned building v1: API under `/api/v1`; `require_pricing: false`
  needed for local models; a config-declared hosted provider starts with an empty
  roster and the referee must refresh and switch models on; every response carries
  `otari-provider` and `otari-model` headers.
- otari.ai is reachable as a hosted provider named `otari-ai` (implementation `otari`),
  models addressed as `otari-ai:<vendor>/<model>`. Marcus has an account with credit;
  the key goes in `.env` as `OTARI_AI_KEY` and is optional.

## Approaches considered for the lever

1. Team file with built-in stage types (chosen). No code, diffable in a minute, real
   architecture decisions (which model, which batch size, route by problem, vote, verify).
2. Python strategy module. Full freedom, but judging five entries in 25 minutes gets
   hard and bad code wrecks the numbers.
3. Fixed roles, prompts only. Simplest, but it is prompt tuning again.

## Design

### Data

`fightnight/corrupt.py` generates `golden.csv` (300 synthetic transaction rows: id,
date, vendor, amount, category, note; ISO dates, title-case vendors, two-decimal amounts,
one of 8 categories) and `messy.csv` from a seed and a preset (easy, medium, brutal).
Corruptions, each with a rate: date formats (5 variants), casing and whitespace, currency
symbols and thousands separators, category synonyms, exact and near duplicates (typo),
blank cells, junk rows (repeated header, TOTAL row, empty row), smart quotes, swapped
amount/category in a row. The `id` column is never corrupted; duplicates share the id.
Junk rows have no id.

### Grading

`fightnight/grade.py` compares a cleaned CSV to golden by id. The headline is **net repair**:
problems = every cell of the first messy copy of each id that differs from golden, plus one per
extra duplicate copy, plus one per junk row; fixed = problems that came back exactly right (a
removed extra copy or junk row counts as fixed); broken = clean cells now wrong, plus five per
real row dropped; net repair = (fixed - broken) / problems as a percentage. Doing nothing scores
0, wrecking clean data goes negative. Comparison is exact: cleaning means producing the clean
form. The card also shows cells-exactly-right for reference, per-column repair rates for both
teams, and counts of duplicates kept, rows dropped and junk kept.

(Revised after review on 2026-11-20: the original lenient cell-accuracy metric gave an untouched
medium file about 72%, so the fight measured dedupe and little else.)

### Team file

```yaml
name: my-team
stages:
  - name: triage
    type: map
    model: qwen2.5:3b
    batch: 20
    prompt: prompts/triage.md     # adds a `tag` to each row
  - name: route
    type: route
    by: tag
    to: {dates: datefix, "*": cleaner}
  - name: datefix
    type: map
    model: llama3.2:3b
    batch: 50
    prompt: prompts/dates.md
  - name: cleaner
    type: map
    model: qwen2.5:3b
    batch: 5
    prompt: prompts/clean.md
  - name: category
    type: vote
    models: [qwen2.5:3b, llama3.2:3b, gemma3:4b]
    column: category
    prompt: prompts/category.md
  - name: check
    type: verify
    model: llama3.2:3b
    prompt: prompts/check.md
    retry: 1
```

Stage types:

- `map`: rows in batches of `batch` to one model with the prompt; the model returns the
  rows as a JSON array of objects with the same keys (plus any new key such as `tag`).
  Rows a batch loses or breaks are kept as they were and counted as `unparsed`. A row may
  be marked `"drop": true` (duplicates, junk).
- `route`: splits rows by the value of a column into named downstream stages; rows the
  map misses go to `"*"`. Downstream stages run on their slice and the slices merge back.
- `vote`: N models each see the same original rows and answer for one column; majority
  wins, ties go to the first voter that answered, an unreadable reply abstains.
- `verify`: one model sees each batch and the golden sample (20 clean rows shipped as
  `sample.csv`), returns corrected rows; `retry` reruns rows it flags.

Stages run in file order. Rows carry through every stage. Prompts are markdown files;
`{sample}` in a prompt is replaced by the shipped sample rows. Any model string is passed
to Otari as `ollama:<model>` unless it already contains a provider prefix, so
`otari-ai:openai/gpt-oss-120b` works and shows up as non-local (otari.ai lists open-weight models, not gpt-4o-mini).

### Otari

`otari.yml` keeps `require_pricing: false` and the `ollama` hosted provider, adds an
optional `otari-ai` hosted provider (`provider: otari`, `api_key: ${OTARI_AI_KEY}`),
drops the fighter aliases, and declares two scoped keys: `team` and `stock`. Before a
fight the referee switches on every model named by both team files under `ollama` at $0,
pulling missing ones from Ollama first. Each request's `otari-provider` header is
recorded; the card reports the share of row-processing requests served by `ollama`.

### Fight

`make fight`: generate messy.csv for the configured seed and preset (default medium, 50 rows
since 3B models produce about one row per second per team, seed random unless `SEED=`), run `teams/stock.yml` with the stock key, run `team.yml`
with the team key, grade both, write `fight-card.md`, `fight-card.json`, `fight-log.jsonl`
(every request: stage, model, provider, rows in, rows out, seconds, tokens). Sequential,
never parallel. `make clean FILE=x.csv` runs `team.yml` on that file and writes
`x.clean.csv`, no grading.

### Fight card

Machine specs (as v1), gateway versions, dataset (seed, preset, rows), then a table with
stock vs yours: accuracy, delta, dup-kept, dropped, junk-kept, per-column accuracy,
seconds, requests, prompt and completion tokens from Otari per key, model weights loaded
(sum of distinct model sizes from Ollama's listing), accuracy per GB, local share.
Then a stage table for your team: stage, model, requests, rows, seconds, unparsed. Team
file sha256.

### Stock team

Two stages: `map` with `qwen2.5:3b`, batch 10, one generic clean prompt, then `verify`
with `qwen2.5:3b` (llama3.2:3b answered in prose and tripled the time). Deliberately simple
so it is beatable.

### Judging (README, not code)

Out of 100: beat the stock team 30, architecture story with log evidence 25, pound for
pound 20, show and tell 15, friction log 10. Scoring seed announced at close. Bracket on
the host machine for top five, teams must fit 16 GB.

## Left to the builder

Prompt wording, JSON parsing leniency, exact corruption rates per preset, how `verify`
flags rows, terminal output format.
