# For the agent helping an entrant

You are probably a coding agent that a Fight Night entrant pointed at this repo. This file is
the fence, not the strategy. It says what you may change and what gets the human disqualified.
How to win is their problem and yours to figure out together.

## What you may edit

- `team.yml`: the team. Models, batch sizes, stage types (map, route, vote, verify), prompts.
- `prompts/*.md` and any new `.md` or `.txt` prompt files you add outside `data/`.
- `.env`: `ROWS`, `SEED`, `PRESET` for iteration. The scored run is `ROWS=50 PRESET=medium`.
- `SUBMISSION.md`: the human fills this in; you may draft, they must answer the feedback
  questions themselves.

## What you must not touch

- `fightnight/`: the referee, grader and card. Any edit, committed or not, shows on the fight
  card as a modified referee and fails the organizers' `check-card`. A commit of yours that
  touches it is not on this repo's `main` and fails the same check.
- `teams/stock.yml` and `teams/stock/`: the baseline everyone is measured against.
- `data/`: generated during a fight. Do not read `data/golden.csv` into a prompt, do not
  point a prompt at it, do not copy rows out of it. The referee scans prompts for dataset ids
  (`T0000` style) and golden rows and flags the card.
- `otari.yml` and `docker-compose.yml`: the gateway config. `OLLAMA_URL_FROM_DOCKER` must point
  at a real Ollama; the card records it.

## What disqualifies

- Any request not served locally. The card must say "Requests served locally: 100%". No
  `otari-ai:` models, no Ollama model name containing `cloud` (the loader refuses them anyway).
- A team that does not fit in 16 GB of RAM. The top entries are rerun on a 16 GB machine.
- Retagged weights (`ollama cp` under a public tag). The card records every model's Ollama
  digest; `qwen2.5:3b` must be `357c53fb659c`.
- Golden rows or dataset ids in prompts. Knowledge about the data is fine: the vendor list,
  the vendor to category mapping, the category synonyms, the date formats and the fixed year
  in `fightnight/corrupt.py` may all go into a prompt. Answers may not.
- A fight card from a modified referee or from a commit that is not on this repo's `main`.

## How the scoring works, so you optimize the right thing

- Net repair = (dirty cells fixed - clean cells broken) / dirty cells. Doing nothing is 0.
  Breaking clean cells goes negative. Removing junk and duplicates earns nothing (the referee
  can do it on a model's say-so); keeping them costs.
- The headline is the delta against the stock team on the same file and machine.
- The scoring seed is never published. Organizers rerun top entries on their own machine from
  their own clone. The entrant's card gets them into the top five; the rerun decides.
- Pound for pound counts: net repair per GB of model weights, and seconds. Three voters on
  every row triples the clock.

## A good loop

```
ROWS=20 make fight                  # two minutes, read fight-card.md and the stage table
# edit team.yml / prompts
ROWS=20 make fight
uv run fight.py compare runs/<before> runs/<after>
SEED=12345 ROWS=50 make fight       # the real thing, on a fixed seed, before submitting
```

Read `data/team.clean.csv` against `data/messy.csv` after a fight to see what a stage got
wrong. The card's stage table says where the time and the broken rows went.
