# For organizers

Scores are self-reported and the machines differ, so trust comes from process, not from the card:

- **Fix the scored config** in the announcement: `PRESET=medium`, `ROWS=50`, the stock team as
  it is on `main`. If you change the stock team or its prompts after the announcement, say so;
  `check-card` accepts whatever stock was at the card's commit, so an entrant on an older
  `main` still passes.
- **The rerun, step by step.** When submissions close: pick the scoring seed by rolling it in
  front of a witness and write it down. Run `make check-card CARD=<their fight-card.json>` on every
  submission; the ones that pass and have the highest self-reported delta are the top five. For
  each: clone their repo, copy their `team.yml` and prompts over a clean checkout of this repo's
  `main`, run `SEED=<the seed> make fight`. About five minutes per entry on a 16 GB machine. Rank
  by the rerun's delta. The self-reported card is evidence for the other rubric lines, not the
  score.
- **Never publish the scoring seed.** The generator is deterministic and public, so a seed is an
  answer key: anyone with it can run `make gen` and paste the golden file into a prompt. Pick it
  when submissions close, rerun every contender yourself from your own clone and your own `.env`,
  and keep it. Cards are markdown and can be edited by hand; the rerun is the check.
- **Check every card before you rerun it:** `make check-card CARD=their-fight-card.json`. It
  verifies that the referee commit on the card is a commit on this repo's `main` and that the
  referee code and stock team hashes match that commit, that `qwen2.5:3b` ran on the official
  weights (digest `357c53fb659c`), that every team request was local, that the scored config was
  used, and that no answer-key flag or stock-side failure is present. Because the check is
  against `main`'s history, you can keep editing the repo: any card made from a clean checkout of
  any `main` commit passes, a fork that edited the grader does not, and an uncommitted edit shows
  as `(modified)`. PASS means rerun it; FAIL lists why.
- **Measure the noise first.** Run `TEAM=teams/stock.yml make fight` a few times and publish the
  stock-vs-stock spread. Only deltas outside that band mean anything. On the reference machine
  the stock team scored 42.0 and 40.9 on the same seed in two runs, so expect a point or two.
- **Models must be plain public Ollama tags.** No `-cloud` tags (they leave the machine through
  Ollama and still show as local), no custom Modelfiles (not reproducible). A team has to fit
  in 16 GB.
- **Local only for Jam Sesh #1.** A card with "requests served locally" below 100% is not
  eligible.
