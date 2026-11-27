import copy
import json
from types import SimpleNamespace

import pytest

from fightnight.card import build
from fightnight.otari import ChatResult
from fightnight.referee import run_fight
from fightnight.runs import compare, finish_run, read_card, start_run
from fightnight.team import load_team


def make_team(root, name="example"):
    root.mkdir(parents=True)
    (root / "clean.md").write_text("Original instructions: {sample}")
    (root / "team.yml").write_text(f"name: {name}\nstages:\n  - {{name: clean, type: map, model: local, prompt: clean.md}}\n")
    return load_team(root / "team.yml")


class Gateway:
    def chat(self, key, model, messages, max_tokens, timeout):
        rows = json.loads(messages[-1]["content"].split("Rows:\n")[1].split("\n\nReturn")[0])
        return ChatResult(json.dumps(rows), 10, 5, .1, None, "ollama", model)

    def key_usage(self, key, since):
        return {}


def complete_run(root, team, stock, seed=42):
    run = start_run(team, stock, root)
    settings = SimpleNamespace(seed=seed, rows=3, preset="medium", key_stock="s", key_team="t", timeout_seconds=5)
    result = run_fight(settings, Gateway(), team, stock, {}, run / "fight-log.jsonl", run / "data")
    card = build(result, {"cpu": "test"}, {"otari_version": "test"})
    latest = root.parent / "latest"
    latest.mkdir(exist_ok=True)
    finish_run(run, card, latest)
    return run, card


def test_runs_keep_separate_outputs_and_replayable_prompt_snapshots(tmp_path):
    team = make_team(tmp_path / "source")
    stock = make_team(tmp_path / "stock")
    first, card = complete_run(tmp_path / "runs", team, stock)
    log = (first / "fight-log.jsonl").read_bytes()
    # Editing or deleting the original prompt cannot affect saved sources.
    team.stages[0].prompt.write_text("Changed instructions")
    second, _ = complete_run(tmp_path / "runs", load_team(team.path), stock)
    team.stages[0].prompt.unlink()
    saved = load_team(first / "team" / "team.yml")
    assert saved.stages[0].prompt.read_text() == "Original instructions: {sample}"
    assert (first / "team" / "original.yml").read_text() == team.path.read_text()
    assert json.loads((first / "team" / "source.json").read_text())["sha256"] == team.sha256
    assert first != second and read_card(first) == card
    assert (first / "fight-log.jsonl").read_bytes() == log
    assert (first / "data" / "sample.csv").exists()
    assert json.loads((first / "run.json").read_text())["status"] == "complete"
    assert (tmp_path / "latest" / "fight-card.json").read_bytes() == (second / "fight-card.json").read_bytes()
    assert not list(first.rglob(".env"))


def test_compare_reports_whole_team_changes_and_refuses_other_datasets(tmp_path):
    team = make_team(tmp_path / "source")
    run, before = complete_run(tmp_path / "runs", team, team)
    after = copy.deepcopy(before)
    after["team"]["repair_pct"] += 4
    after["team"]["seconds"] += 38
    after["team"]["stages"][0]["prompt_tokens"] += 20
    md = compare(read_card(run / "fight-card.json"), after)
    assert "| Net repair (points)" in md and "+4.0 |" in md and "+38.0 |" in md
    assert "+20 |" in md and "not proof" in md
    assert "| Gateway-reported cost (USD) | n/a | n/a | n/a |" in md
    after["dataset"]["sha256"] = "different"
    with pytest.raises(ValueError, match="Datasets differ"):
        compare(before, after)


def test_comparison_flags_environment_and_timing_changes(tmp_path):
    team = make_team(tmp_path / "source")
    _, before = complete_run(tmp_path / "runs", team, team)
    after = copy.deepcopy(before)
    after["machine"]["cpu"] = "other"
    after["gateway"]["otari_version"] = "other"
    del before["request_timing"]
    del before["team"]["stages"][0]["prompt_tokens"]
    md = compare(before, after)
    assert "Machine differs" in md and "version differs" in md
    assert "Timing definitions differ" in md
    assert "| Prompt tokens | n/a |" in md


def test_partial_run_cannot_be_compared(tmp_path):
    team = make_team(tmp_path / "source")
    run = start_run(team, team, tmp_path / "runs")
    with pytest.raises(ValueError, match="completed fight-card.json"):
        read_card(run)
    (run / "fight-card.json").write_text('{"dataset": {}}')
    with pytest.raises(ValueError, match="completed fight-card.json"):
        read_card(run)


def test_interruption_keeps_finished_calls_and_sources(tmp_path):
    team = make_team(tmp_path / "source")
    run = start_run(team, team, tmp_path / "runs")

    class Interrupted(Gateway):
        calls = 0

        def chat(self, *args):
            self.calls += 1
            if self.calls == 2:
                raise KeyboardInterrupt
            return super().chat(*args)

    settings = SimpleNamespace(seed=42, rows=3, preset="medium", key_stock="s", key_team="t", timeout_seconds=5)
    with pytest.raises(KeyboardInterrupt):
        run_fight(settings, Interrupted(), team, team, {}, run / "fight-log.jsonl", run / "data")
    entries = [json.loads(line) for line in (run / "fight-log.jsonl").read_text().splitlines()]
    assert len(entries) == 1 and entries[0]["team"] == "stock"
    assert (run / "team" / "team.yml").exists()
    assert not (run / "fight-card.json").exists()
    assert json.loads((run / "run.json").read_text())["status"] == "started"


def test_no_golden_file_in_data_while_a_saved_fight_runs(tmp_path, monkeypatch):
    from fightnight import referee

    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "golden.csv").write_text("left over from the last fight")
    seen = []

    class Watching(Gateway):
        def chat(self, *args):
            seen.append((tmp_path / "data" / "golden.csv").exists())
            return super().chat(*args)

    team = make_team(tmp_path / "source")
    stock = make_team(tmp_path / "stock")
    run = start_run(team, stock, tmp_path / "runs")
    settings = SimpleNamespace(seed=1, rows=3, preset="medium", key_stock="s", key_team="t", timeout_seconds=5)
    referee.run_fight(settings, Watching(), team, stock, {}, run / "fight-log.jsonl", run / "data")
    assert seen and not any(seen)


def test_comparison_ignores_per_team_integrity_data(tmp_path):
    team = make_team(tmp_path / "source")
    _, before = complete_run(tmp_path / "runs", team, team)
    after = copy.deepcopy(before)
    before["gateway"]["integrity"] = {"prompt_bytes": {"team": 900}}
    after["gateway"]["integrity"] = {"prompt_bytes": {"team": 400}}
    assert "differs" not in compare(before, after)
