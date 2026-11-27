# Friction log

Machine: Linux 6.18 (Arch LTS kernel), 16 GB RAM, RTX 3050 Laptop 4 GB VRAM. Ollama 0.34.4,
Docker Compose 5.5.1, uv 0.13.8, GNU Make 4.4.1.

## Setup

1. **Ollama not reachable from the container by default on Linux.** The packaged Ollama binds
   to 127.0.0.1, and nothing in `make fight` checks this up front; the fix lives in
   docs/troubleshooting.md. Started it with:
   `OLLAMA_HOST=0.0.0.0 ollama serve`
2. **Docker daemon was not running.** `docker ps` -> `Cannot connect to the Docker daemon at
   unix:///var/run/docker.sock`. Fixed with `systemctl start docker`. Expected on a laptop
   that does not autostart Docker, but `make fight` would have failed at `docker compose up`.
3. qwen2.5:3b pulled fine, digest `357c53fb659c` (official). `ollama ps` after one call:
   `2.2 GB  100% GPU`, so a single 3B model fits in 4 GB VRAM.

## The fight

4. **The shipped starter loses on this machine.** `SEED=4242 make fight` with the untouched
   `team.yml`: stock 59.1%, starter 52.7% (-6.4). The README says batch 5 "was enough to win" on
   the reference M2 Pro; on an RTX 3050 laptop it was not. Seed 4242/20 rows: -4.9.
5. **No raw model replies anywhere.** `fight-log.jsonl` has rows in/out, tokens and an `unparsed`
   count, but not the text the model returned, and the Otari dashboard shows request metadata,
   not bodies. To learn *why* rows were "lost or garbled" I wrote a scratch harness that calls
   `fightnight.pipeline.run_team` against Ollama directly and saves every reply. That is how I
   found the real cause: qwen2.5:3b writes `"id": "drop"` instead of `"drop": true`, `_merge`
   cannot match it, and the row's fixes are silently dropped.
6. **The answer-key scanner flags innocent example ids.** I wrote an output example with id
   `T0101` in a prompt; it matches `\bT\d{4}\b` and would have flagged the card. Nothing in the
   README says the example id format to use; `fightnight/integrity.py` has a comment that the
   sample uses `S0001..` on purpose. Caught before a fight, but easy to trip.
7. **Few-shot values leak.** An output example `{"date": "2026-03-14", "amount": "54.15", "note":
   "monthly"}` in a prompt made qwen2.5:3b write `2026-03-14`, `54.15` and `monthly` into rows
   that were already clean. Placeholders (`"<YYYY-MM-DD>"`) fixed it.
8. **qwen2.5:1.5b can loop until max_tokens.** At batch 80 the dedupe stage repeated
   `{"id": "T0011", "drop": true}` for ~15 KB on seed 1717 (309-370 s per run in the harness). In a
   real fight that is a TIMEOUT_SECONDS failure. Because `max_tokens = 120 * rows + 200`, smaller
   batches bound it; batch 30 fixed it.
9. **The drop rule rewards marking everything.** A 3B (and gemma3:4b) cannot find repeated ids
   across 57 shuffled rows; recall was near zero. Because the referee refuses drops of unique
   rows and only honors empty ids and repeated ids, the best "dedupe" is a model that marks
   nearly every row and lets plain code decide. The stock team gets "dup kept 0" the same way
   (46 refused drops on seed 4242). It works, but it means the model adds little judgement;
   a `dedupe` stage type in plain code, or showing the model the id counts, would be more honest.
10. **`_merge` applies every key a model returns.** Useful (a stage that returns only
    `id, date, amount, note` cannot touch vendor), but a model that ignores the contract and
    echoes full rows can swap two rows' values, and nothing in the card says which stage did it.
