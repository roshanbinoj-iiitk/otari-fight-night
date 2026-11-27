# Otari Fight Night

⭐️ Before you start, please star the Otari repo, it helps: https://github.com/mozilla-ai/otari ⭐️

📝 Register for the jam on DoraHacks: https://dorahacks.io/hackathon/mozilla-jam-sesh-1/detail 📝

💬 Then join the Mozilla OSAI Discord through this link: https://discord.gg/TqvzGH9mwz. It gives you the `devs-wilding` role, which is how we reach entrants with updates, answers and results. 💬

Two teams of local models. One messy spreadsheet. One gateway. Whose team cleans it best on your machine?

[Otari](https://github.com/mozilla-ai/otari) is Mozilla.ai's open-source model gateway, which
can run as a container on your own machine. Here it sits in front of a few small Ollama models, and
every model call goes through it. ([otari.ai](https://otari.ai) is the hosted version; this kit
does not need it.)

**The challenge.** A *team* here is a pipeline of models, not people: one short YAML file,
`team.yml`, that says which model does which part of the job, in what batch sizes, with which
prompts. The referee (a Python script in this repo) generates a deliberately terrible CSV, runs the
*stock team* (`teams/stock.yml`, the fixed pipeline everyone is measured against) and then yours on
the same file and the same hardware, and grades both. Edit `team.yml` and its prompts until yours
beats the stock team by as much as you can, then submit the fight card that shows it.
The jam runs online from November 25 to December 2, 2026, 11:59 PM ET, for one $100 prize ([details below](#submit)).

Bring your coding agent. It will read [AGENTS.md](AGENTS.md), which says what it may edit and what
gets you disqualified. The fight itself stays local: every model call goes through Otari on your
machine, and the card proves it.

Nothing leaves your machine unless you decide it should, and the card shows which provider served
every request, taken from the header Otari stamps on each response.

```
Otari Fight Night: CSV cleanup
  stock: teams/stock.yml (qwen2.5:3b)
  yours: team.yml (qwen2.5:3b)
  Ollama 0.40.2, models present
  Otari 0.54.0 at http://localhost:8000, roster ready
  preflight qwen2.5:3b: served by ollama in 0.3s
  dataset: 50 clean rows -> 63 messy rows, preset medium, seed 20261120
  stock (stock): net repair 40.9% (54/88 fixed, 18 broken) in 130s, 14 requests, 1.93 GB of models, dup kept 0, dropped 0, junk kept 3
  team (small-batches): net repair 47.7% (57/88 fixed, 15 broken) in 124s, 26 requests, 1.93 GB of models, dup kept 0, dropped 0, junk kept 2

small-batches net repair 47.7% vs stock 40.9%: +6.8 points.
wrote fight-card.md, fight-card.json, fight-log.jsonl and data/{stock,team}.clean.csv
```

That is a real run on an M2 Pro with 16 GB, about four minutes end to end. The full card is in
[examples/fight-card-m2pro-16gb.md](examples/fight-card-m2pro-16gb.md).

## You need

- [Otari](https://github.com/mozilla-ai/otari), the gateway every model call goes through. You do
  not install it: `make fight` pulls the `mzdotai/otari:0.54.0` image and runs it with Docker
  compose, configured by `otari.yml`. It is the point of the exercise, so it is worth a look at
  `docker compose logs otari` and the dashboard at http://localhost:8000 once it is up.
- [Ollama](https://ollama.com) running on the host (`ollama serve`, or the app). This serves the
  models; Otari sits in front of it.
- Docker (Desktop or Engine with compose), to run Otari.
- [uv](https://docs.astral.sh/uv/), to run the referee.
- `make` (macOS and Linux have it; Windows see below)

Nothing in this kit talks to a model except through Otari. The referee holds one scoped Otari
key per team, the dashboard shows every request, and the fight card is built from Otari's usage
API and response headers.

## Run it

```bash
make fight
```

First run: writes `.env` with generated keys, starts Otari, pulls the models your team files name
(the defaults are about 2 GB each), switches them on in Otari, generates the messy file, runs the
stock team, runs yours, grades both, writes the card. A quick check:

```bash
ROWS=20 make fight
```

No `make`? The same thing is three commands:

```
uv run fight.py init-env
docker compose up -d
uv run fight.py
```

## What you get

- `fight-card.md`: machine specs, stock vs yours (net repair, delta, problems fixed, clean cells
  broken, duplicates kept, rows dropped, junk kept, seconds, requests, model weights loaded,
  repair per GB, share of requests served locally), Otari's own per-key usage, and a
  stage-by-stage table for your team. This is what you
  submit.
  Its "Where the work went" table gives each stage's tokens, share of request time and
  tokens, and which provider served it, so you can see which stage costs the most before you
  decide whether it earns its place.
- `fight-card.json`: the same data for the community "what runs on what" table.
- `fight-log.jsonl`: every request (stage, model, provider, rows in and out, seconds, tokens).
- `data/team.clean.csv` and `data/stock.clean.csv` next to `data/messy.csv` and `data/golden.csv`,
  so you can diff what each team got wrong.
- `runs/<timestamp>/`: every fight saved whole (card, log, data, and a copy of both teams' YAML
  and prompts), so editing `team.yml` never loses a result. Compare two on the same seed with
  `uv run fight.py compare runs/<before> runs/<after>`: change in net repair, broken cells, time,
  requests and tokens. Try `TEAM=teams/no-verifier.yml` against the starter to see whether the
  check stage earns its time ([one measured pair](examples/verifier-comparison.md)). Runs stay
  until you delete them; `make reset` keeps them.
- The Otari dashboard at http://localhost:8000 with one API key per team. Sign in with the admin
  key from `make keys`.

## The one lever: `team.yml`

Rows flow through stages in order. Four stage types, no code. The shipped `team.yml` is the
stock team with batches of 5 instead of 10, which on the reference machine was enough to win.
A bigger example, `teams/triage-and-route.yml`, sorts rows by what is wrong with them and sends
each kind to a specialist:

```yaml
name: triage-and-route
stages:
  - name: triage          # tag each row with what is wrong with it
    type: map
    model: qwen2.5:3b
    batch: 15
    prompt: ../prompts/triage.md
  - name: route           # send each tag to a specialist; rows tagged ok pass through
    type: route
    by: tag
    to: {junk: junk, date: dates, dirty: cleaner}
  - name: junk
    type: map
    model: qwen2.5:3b
    batch: 20
    prompt: ../prompts/clean.md
  - name: dates
    type: map
    model: llama3.2:3b
    batch: 10
    prompt: ../prompts/dates.md
  - name: cleaner
    type: map
    model: qwen2.5:3b
    batch: 5
    prompt: ../prompts/clean.md
  - name: check           # re-read everything against the clean sample
    type: verify
    model: qwen2.5:3b
    batch: 10
    prompt: ../prompts/check.md
```

It lost to the stock team on the reference machine, and the card's stage table shows exactly
why: a 3B triage model tags dirty rows `ok`, and they skip every model. That is the hackathon in
one card. Run it with `TEAM=teams/triage-and-route.yml make fight` and make it win.

| Type | What it does | Knobs |
|---|---|---|
| `map` | One model gets rows in batches and returns them corrected. It may add keys (like `tag`) or mark junk and duplicates `"drop": true`. | `model`, `batch`, `prompt` |
| `route` | Splits rows by a column's value and sends each group to a named stage. Those stages run only on their group. `"*"` catches the rest; without it, unmatched rows pass through untouched, which is how rows tagged `ok` skip every model. | `by`, `to` |
| `vote` | Several models answer for one column. Majority wins, ties go to the first model. | `models`, `column`, `prompt`, `batch` |
| `verify` | One model re-checks rows with the clean sample in view. Rows it marks `"flag": true` are re-sent `retry` times. | `model`, `prompt`, `batch`, `retry` |

Prompts are markdown files. `{sample}` in a prompt is replaced by 20 clean reference rows. The
referee reads the last JSON array in each reply. The team sha256 on the card covers `team.yml`
and every prompt it references, so a submission ties to exact prompts. Things the models cannot do, by design: change an
id, or delete a real row. A `drop` is honored only for a row with no id (junk) or an id another row
shares (a duplicate). The card counts how often a model tried anyway.

Any model Ollama can pull works and is pulled on first use. Both teams' models are loaded
during a fight, so pick a set that fits your RAM.

| RAM | Fits |
|---|---|
| 8 GB | one 3B model, or two 1B-2B |
| 16 GB | two 3B, or one 7B/8B |
| 32 GB or a real GPU | 7B/8B pairs, a 14B |

## Bring your own CSV

```bash
make clean FILE=~/Downloads/bank-export.csv
```

Runs your team on any CSV and writes `bank-export.clean.csv` beside it. No grading, no golden
file. This is the tool you keep after the fight. Without an id column the referee assigns ids on
the way in, so models may remove exact duplicate rows, repeated header rows and empty rows, and
nothing else: a row with data in it is never deleted on a model's say-so. Prompts that know about dates, vendors and
categories will need editing for other shapes of data, which is the point.

## Rules and scoring

The messy file is generated from a seed: 50 synthetic transaction rows by default (`ROWS=` for more) (id, date, vendor, amount,
category, note) with seven date formats, random casing and spacing, currency symbols, category
synonyms, exact and near duplicates, blanks, curly quotes, swapped columns, and junk rows
(repeated headers, a TOTAL row, dashes). `PRESET=easy|medium|brutal` sets the rates.

Score is net repair: of the dirty cells in the messy file (every cell that differs from the golden
file), how many the team fixed, minus clean cells it broke, as a percentage. Comparison is exact,
so `03/14/2026` is not credit for `2026-03-14`. Doing nothing scores 0. Wrecking clean data goes
negative. A real row dropped counts as five broken cells, and so does a junk row kept. Removing
duplicates and junk earns nothing by itself, because the referee can do that whenever a model
asks; a duplicated id left in the output scores none of its repairs. The card shows per-column
repair rates for both teams.

The headline is the delta: your team minus the stock team, same file, same machine. Raw scores are
not comparable across machines, and the card does not pretend they are. `SEED=12345 make fight`
replays the exact file. `ROWS`, `PRESET`, `TEAM`, `TIMEOUT_SECONDS` are all in `.env`. The stock
team is always `teams/stock.yml` with its own prompts in `teams/stock/`; the card prints its
sha256 so judges can see it was the real one.

### What is allowed, and what is not

This is a $100 jam, so the rules are short and the checks exist mostly so the livestream rerun is
never awkward. Judges reproduce the method: they run your team file on their machine, and that run
is the score. Your card gets you into the top five; the rerun decides.

The generator is public. Everything in `fightnight/corrupt.py` (the vendor list, the vendor to
category map, the category synonyms, the date formats, the fixed year) is knowledge about the
data, and knowledge about the data is what a good cleaning prompt is made of. **You may put any
of it in a prompt.** A lookup table is a legitimate strategy; the model still has to apply it to
every row.

What you may not do is hand the model the answers:

- **No golden rows or dataset ids in prompts or team files.** The referee writes `data/golden.csv`
  only after both teams have run, scans every prompt for `T0000`-style ids and for lines that match
  a golden row of the current dataset, and prints the result on the card. A flagged card is not
  scored.
- **No file but a `.md` or `.txt` as a prompt**, and nothing under `data/`. A prompt goes into the
  system message verbatim, so `prompt: ../data/golden.csv` would be the answer key.
- **No fake Ollama.** `OLLAMA_URL_FROM_DOCKER` must point at a real Ollama; the card records the URL
  and every model's Ollama digest, and the rerun uses the organizers' machine anyway.
- **No retagged models.** `ollama cp` can put any weights under any name. The card records the
  digest Ollama reports for each model; the official digest for `qwen2.5:3b` is `357c53fb659c`.
  A stock team running on different weights is a different stock team.
- **No edited referee.** The card prints a sha256 of the referee's own source and the last commit
  that touched it, with `(modified)` if the working tree differs. Organizers check that commit is
  on this repo's `main` and that the hashes match it.
- **No cloud models.** Ollama's `-cloud` tags run remotely and would still show as local; the
  team loader refuses any model name containing `cloud`.

None of this stops someone determined, and it does not have to: the scoring seed is never
published and the organizers run every contender on their own machine with their own clone. A
cheated card falls over on the rerun in about four minutes.

## Judging

Out of 100, scored from the card, the team file, the log and your write-up:

| Criterion | Points | What judges look for |
|---|---|---|
| Beat the stock team | 30 | The net-repair delta on your machine, and whether it holds on a second seed |
| Architecture story | 25 | Why this split. The log should show the stages mattered |
| Pound for pound | 20 | Net repair per GB of local model weights, and seconds |
| Show and tell | 15 | A screen recording of up to 3 minutes, with your voice: the fight, the card, and what you changed and why |
| Friction log | 10 | Specific, honest answers to the three feedback questions in SUBMISSION.md |

To be eligible: every request served locally (the card must show 100%), plain public Ollama tags,
a team that fits in 16 GB, `PRESET=medium` and `ROWS=50`, the official stock sha256
`13571dac3037` on your card, and a clean answer-key check. The scoring seed is never published;
top entries are rerun on it on a 16 GB machine, and the rerun is what counts. The winner is announced on the
Mozilla OSAI livestream on December 8, where the winning team runs live.

## Stretch goals

Neither of these is eligible for the Jam Sesh #1 prize, which is local models only. Jam Sesh #2
opens things up to remote models.

- **Frontier through the same gateway.** With an [otari.ai](https://otari.ai) key in `.env` as
  `OTARI_AI_KEY`, any stage can use `model: otari-ai:openai/gpt-oss-120b`. Same team file, same
  referee, same dashboard. Those requests cost money, and the card's "requests served locally"
  drops below 100%. Hosted reasoning models spend the per-request token
  budget thinking, so check the "broken rows" column before you trust a hosted stage. The interesting version is a stage that touches
  no rows at all: a coach that reads the scores and rewrites a prompt. Not built yet; that is
  round two.
- **Connectors.** A Sheets export or a bank download is a CSV. If you wire a real source up,
  show it in the video.

## Submit

The deadline is December 2, 2026, 11:59 PM ET. Submit on
[DoraHacks](https://dorahacks.io/hackathon/mozilla-jam-sesh-1/detail):

1. A link to your public GitHub repo, made from this template, with your `team.yml`, every prompt
   it uses, and [SUBMISSION.md](SUBMISSION.md) filled in.
2. A link to your video (up to 3 minutes, a screen recording with your voice, no AI-generated
   video).
3. An email address to reach you if you win. Put it in the DoraHacks form, not in your repo.

## More

- [How it is wired](docs/wiring.md): compose, Otari config, what each module does, tests.
- [Troubleshooting](docs/troubleshooting.md): Ollama on Linux, timeouts, slow fights, fresh start.
- [For organizers](docs/organizers.md): the scored config, `check-card`, the rerun, noise.
- [Design doc](docs/superpowers/specs/2026-11-20-csv-cleanup-fight-design.md): why it is built this way.

## License

Apache 2.0.
