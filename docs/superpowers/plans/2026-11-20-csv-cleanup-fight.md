# CSV Cleanup Fight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Codebreaker with a seeded messy-CSV cleanup fight between a stock team and the entrant's `team.yml` of local models, all routed through Otari, graded by plain code.

**Architecture:** `corrupt.py` makes golden and messy CSVs from a seed; `pipeline.py` runs a validated `team.yml` (map, route, vote, verify stages) through `Otari.chat`; `grade.py` scores the output by id; `fight.py` (referee) runs stock then team and `card.py` writes the card. Everything model-facing goes through the existing `Otari` client, which now records the `otari-provider` header.

**Tech Stack:** Python 3.11+, httpx, pyyaml (new), stdlib csv/json/random, pytest. Otari 0.54.0 in Docker, Ollama on host.

**Spec:** `docs/superpowers/specs/2026-11-20-csv-cleanup-fight-design.md`

## Global Constraints

- No dependency beyond httpx and pyyaml. No pandas.
- Stock team fight under 5 minutes on M2 Pro 16 GB, else shrink `ROWS`.
- Team files contain no code. Four stage types only: map, route, vote, verify.
- The `id` column is never corrupted and never shown as something to clean.
- Model strings without a provider prefix go to Otari as `ollama:<model>`.
- Sequential execution, never parallel model calls.

## Review Focus

- A model returns a JSON array wrapped in prose or a code fence: parser must still find it (Task 3 test).
- A map batch returns fewer rows than it got, or rows missing `id`: originals kept, counted `unparsed` (Task 3 test).
- A team file names a stage type or route target that does not exist: load fails with the stage name in the message (Task 2 test).
- Cleaned CSV has an id twice or a junk row with blank id: grader penalizes, never crashes (Task 1 test).
- `make clean FILE=` on a CSV without an `id` column: ids are assigned on the way in and stripped on the way out (Task 4 test).

---

### Task 1: Data generator and grader

**Files:** Create `fightnight/corrupt.py`, `fightnight/grade.py`, `tests/test_corrupt.py`, `tests/test_grade.py`.

**Produces:**
- `COLUMNS = ["id", "date", "vendor", "amount", "category", "note"]`, `CATEGORIES` (8 names).
- `make_golden(n: int, rng: random.Random) -> list[dict]`
- `PRESETS: dict[str, dict[str, float]]` with keys easy, medium, brutal; rates per corruption name.
- `corrupt(rows: list[dict], rng: random.Random, preset: str) -> list[dict]` returns messy rows including junk rows (id "").
- `write_csv(path: Path, rows: list[dict], columns: list[str]) -> None`, `read_csv(path: Path) -> list[dict]`.
- `grade(golden: list[dict], cleaned: list[dict]) -> Grade` dataclass: `accuracy: float`, `per_column: dict[str, float]`, `dup_kept: int`, `dropped: int`, `junk_kept: int`, `rows_out: int`.
- `normalize(col: str, value: str) -> str` (dates to ISO, amounts to 2 decimals, category lowercased, strip).

- [ ] Tests: `test_golden_is_seeded_and_clean` (same seed same rows; dates match `\d{4}-\d{2}-\d{2}`; amounts have 2 decimals), `test_corrupt_keeps_ids_and_adds_junk` (every non-junk messy row id in golden ids; some rows have id ""; brutal has more rows than easy), `test_normalize_dates_and_amounts` (`"03/14/2026"`, `"14 Mar 2026"`, `"2026.03.14"` -> `"2026-03-14"`; `"$1,234.5"` -> `"1234.50"`), `test_grade_perfect_is_one`, `test_grade_duplicate_and_dropped_and_junk` (one id twice -> dup_kept 1 and that id scores 0; one missing -> dropped 1; one blank-id row -> junk_kept 1), `test_grade_never_crashes_on_garbage` (rows with missing columns).
- [ ] Run `uv run --group dev pytest tests/test_corrupt.py tests/test_grade.py -q`, expect fail, implement, expect pass.
- [ ] Commit `feat: seeded messy CSV generator and grader`.

### Task 2: Team file

**Files:** Create `fightnight/team.py`, `tests/test_team.py`. Modify `pyproject.toml` (add `pyyaml>=6`).

**Produces:** `Stage` dataclass (`name`, `type`, `model: str | None`, `models: list[str]`, `batch: int`, `prompt: Path | None`, `by`, `to: dict[str, str]`, `column`, `retry: int`), `Team` dataclass (`name`, `stages: list[Stage]`, `path`, `sha256: str`, `models() -> list[str]` distinct in order). `load_team(path: Path) -> Team` raises `TeamError(message)` naming the stage.

- [ ] Tests: `test_load_example_team` (the spec's YAML parses, 6 stages, `models()` has 4 distinct), `test_unknown_stage_type_names_stage` (message contains stage name and type), `test_route_target_must_exist`, `test_map_requires_model_and_prompt_file` (missing prompt file fails), `test_sha_changes_with_content`.
- [ ] Fail, implement, pass, commit `feat: team.yml loader`.

### Task 3: Pipeline runner

**Files:** Create `fightnight/pipeline.py`, `tests/test_pipeline.py`. Modify `fightnight/otari.py` (`ChatResult.provider: str`, from `otari-provider` header; `ChatResult.model: str` from `otari-model`).

**Produces:**
- `parse_rows(text: str) -> list[dict] | None` finds the last JSON array in text, fences or prose allowed.
- `Call` dataclass logged per request: `stage, model, provider, rows_in, rows_out, seconds, prompt_tokens, completion_tokens, unparsed: int`.
- `StageStats`: `name, model, requests, rows, seconds, unparsed, local_requests`.
- `run_team(team: Team, rows: list[dict], sample: list[dict], chat: Callable[[str, list[dict], int], ChatResult], on_call: Callable[[Call], None]) -> tuple[list[dict], list[StageStats]]`. `chat(model, messages, max_tokens)`; model string gets `ollama:` prefix if it has no `:`-separated provider prefix from a known set `{ollama, otari-ai}`... rule: prefix if the part before the first `:` is not a configured provider name, i.e. `prefixed = model if model.split(":")[0] in {"ollama", "otari-ai"} else f"ollama:{model}"`.
- Prompt rendering: file text with `{sample}` replaced by CSV text of `sample` rows; user message = "Rows:\n<JSON array>\nReturn the corrected rows as a JSON array with the same keys." Rows marked `"drop": true` are removed after the stage.
- Stage semantics per spec. `verify` user message also carries the sample.

- [ ] Tests with a fake `chat` that returns canned JSON: `test_parse_rows_from_fence_and_prose`, `test_map_batches_and_keeps_rows_on_bad_json` (10 rows, batch 4 -> 3 calls; one call returns garbage -> those 4 rows unchanged, unparsed 4), `test_map_drop_flag_removes_row`, `test_route_splits_and_merges_in_original_order`, `test_vote_majority_and_tie_keeps_first`, `test_verify_retries_flagged_rows` (`"flag": true` rows re-sent once), `test_model_prefix_rule` (`qwen2.5:3b` -> `ollama:qwen2.5:3b`, `otari-ai:openai/gpt-4o-mini` unchanged), `test_local_share_counts_provider`.
- [ ] Fail, implement, pass, commit `feat: team pipeline runner with map, route, vote, verify`.

### Task 4: Referee, card, CLI, config

**Files:** Rewrite `fightnight/referee.py`, `fightnight/card.py`, `fightnight/cli.py`, `tests/test_card.py`; modify `fightnight/config.py` (drop fighter fields; add `rows`, `preset`, `team_path`, `stock_path`, `key_team`, `key_stock`, `otari_ai_key`), `otari.yml`, `.env.example`, `Makefile`, `.gitignore` (add `data/messy.csv`, `data/golden.csv`, `*.clean.csv`); delete `fightnight/game.py`, `tests/test_game.py`.

**Produces:**
- `referee.run_fight(settings, otari, team, stock, log_path) -> FightResult` (`seed, preset, rows, dataset_sha, stock: TeamResult, team: TeamResult`), `TeamResult` (`team: Team, grade: Grade, stages: list[StageStats], seconds, requests, local_share, weights_gb, usage: dict`).
- `referee.clean_file(settings, otari, team, path: Path) -> Path` writes `<stem>.clean.csv`; assigns `id` if absent and strips it after.
- `card.build(result, specs, gateway) -> dict`, `card.render_md(card) -> str`, `card.write(card)`.
- CLI commands: `fight` (default), `clean FILE`, `gen` (write data/golden.csv and data/messy.csv for SEED/PRESET), `init-env`, `wait-otari`, `keys`.
- `otari.yml`: `require_pricing: false`, hosted `ollama`, hosted `otari-ai` (`provider: otari`, `api_key: ${OTARI_AI_KEY}`), api_keys `team` and `stock`. Verify at Task 6 that an empty `OTARI_AI_KEY` is tolerated; if not, generate the block only when set.
- Weights: `ollama.sizes(base_url) -> dict[str, float]` GB from `/api/tags`.
- Makefile: `fight`, `clean` (`FILE=` required), `gen`, `up`, `down`, `keys`, `test`, `reset` (was `clean`).

- [ ] Tests: `test_card_delta_and_local_share` (build with two fake TeamResults; delta = team - stock in points; local_share rendered as percent), `test_render_has_stage_table_and_no_None`, `test_clean_file_assigns_and_strips_id` (fake otari, CSV without id).
- [ ] Fail, implement, pass. `uv run fight.py gen` writes both files. Commit `feat: CSV cleanup referee, card and CLI; drop Codebreaker`.

### Task 5: Stock team, starter team, prompts

**Files:** Create `teams/stock.yml`, `team.yml`, `prompts/clean.md`, `prompts/check.md`, `prompts/triage.md`, `prompts/dates.md`, `prompts/category.md`, `data/sample.csv` (20 golden rows from seed 1, committed).

- Stock: map `qwen2.5:3b` batch 10 `prompts/clean.md`; verify `llama3.2:3b` `prompts/check.md`.
- Starter `team.yml`: triage map (tag rows: dates, dupe, ok) -> route -> datefix map / cleaner map, then verify. Header comment explains the four stage types in ten lines.
- [ ] `ROWS=60 make fight` runs end to end. Tune prompts until stock scores above 50% on medium with 300 rows; record the number in the commit message.
- [ ] Commit `feat: stock and starter teams with prompts`.

### Task 6: Docs, hosted path, full run

**Files:** Rewrite `README.md`, `SUBMISSION.md`; update `examples/` with a real 300-row card; `docs/superpowers/specs` unchanged.

- [ ] README: what, requirements, `make fight`, what you get, the team file (four stage types with the example), bring your own CSV, change models, rules and scoring, judging rubric, stretch goal (blind coach, point a stage at `otari-ai:`), wiring, troubleshooting, tests.
- [ ] With Marcus's `OTARI_AI_KEY` in `.env`: one stage pointed at `otari-ai:openai/gpt-4o-mini` for 20 rows; confirm card shows local share below 100% and the hosted request on the `team` key. Remove before the example run.
- [ ] Full `make fight` on defaults; copy card to `examples/`; `make test`; commit `docs: README and submission for the CSV fight; example card`.
