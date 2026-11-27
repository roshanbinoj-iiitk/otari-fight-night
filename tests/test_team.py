import textwrap
from pathlib import Path

import pytest

from fightnight.team import TeamError, load_team

EXAMPLE = """
name: example
stages:
  - name: triage
    type: map
    model: qwen2.5:3b
    batch: 20
    prompt: prompts/triage.md
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
"""


def write(tmp_path: Path, text: str, prompts=("triage", "dates", "clean", "category", "check")) -> Path:
    (tmp_path / "prompts").mkdir(exist_ok=True)
    for p in prompts:
        (tmp_path / "prompts" / f"{p}.md").write_text(f"# {p}\n")
    f = tmp_path / "team.yml"
    f.write_text(textwrap.dedent(text))
    return f


def test_load_example_team(tmp_path):
    team = load_team(write(tmp_path, EXAMPLE))
    assert team.name == "example"
    assert [s.type for s in team.stages] == ["map", "route", "map", "map", "vote", "verify"]
    assert team.models() == ["qwen2.5:3b", "llama3.2:3b", "gemma3:4b"]
    assert team.stages[0].batch == 20 and team.stages[1].to["*"] == "cleaner"
    assert team.stages[5].retry == 1 and team.stages[0].retry == 0
    assert team.stages[0].prompt == tmp_path / "prompts" / "triage.md"
    assert len(team.sha256) == 12


def test_unknown_stage_type_names_stage(tmp_path):
    f = write(tmp_path, "name: x\nstages:\n  - name: weird\n    type: reduce\n    model: m\n    prompt: prompts/clean.md\n")
    with pytest.raises(TeamError, match="weird.*reduce"):
        load_team(f)


def test_route_target_must_exist(tmp_path):
    f = write(tmp_path, EXAMPLE.replace("dates: datefix", "dates: nowhere"))
    with pytest.raises(TeamError, match="route.*nowhere"):
        load_team(f)


def test_map_requires_model_and_prompt_file(tmp_path):
    f = write(tmp_path, "name: x\nstages:\n  - name: a\n    type: map\n    prompt: prompts/clean.md\n")
    with pytest.raises(TeamError, match="a.*model"):
        load_team(f)
    f = write(tmp_path, "name: x\nstages:\n  - name: a\n    type: map\n    model: m\n    prompt: prompts/missing.md\n")
    with pytest.raises(TeamError, match="a.*missing.md"):
        load_team(f)


def test_vote_requires_models_and_column(tmp_path):
    f = write(tmp_path, "name: x\nstages:\n  - name: v\n    type: vote\n    models: [a]\n    prompt: prompts/category.md\n")
    with pytest.raises(TeamError, match="v.*column"):
        load_team(f)


def test_duplicate_stage_names_rejected(tmp_path):
    f = write(tmp_path, "name: x\nstages:\n  - name: a\n    type: map\n    model: m\n    prompt: prompts/clean.md\n  - name: a\n    type: map\n    model: m\n    prompt: prompts/clean.md\n")
    with pytest.raises(TeamError, match="a.*twice"):
        load_team(f)


def test_sha_changes_with_content_and_with_prompts(tmp_path):
    a = load_team(write(tmp_path, EXAMPLE)).sha256
    b = load_team(write(tmp_path, EXAMPLE.replace("batch: 20", "batch: 10"))).sha256
    assert a != b
    f = write(tmp_path, EXAMPLE)
    (tmp_path / "prompts" / "clean.md").write_text("# clean, edited after the fight\n")
    c = load_team(f).sha256
    assert c != a, "the hash covers every prompt the team references"


def test_bad_batch_and_string_models_name_the_stage(tmp_path):
    f = write(tmp_path, "name: x\nstages:\n  - name: a\n    type: map\n    model: m\n    batch: abc\n    prompt: prompts/clean.md\n")
    with pytest.raises(TeamError, match="a.*batch"):
        load_team(f)
    f = write(tmp_path, "name: x\nstages:\n  - name: v\n    type: vote\n    models: qwen2.5:3b\n    column: category\n    prompt: prompts/category.md\n")
    with pytest.raises(TeamError, match="v.*models.*list"):
        load_team(f)


def test_unknown_keys_are_rejected(tmp_path):
    f = write(tmp_path, "name: x\nstages:\n  - name: a\n    type: map\n    modle: m\n    model: m\n    prompt: prompts/clean.md\n")
    with pytest.raises(TeamError, match="a.*modle"):
        load_team(f)


def test_prompt_must_be_a_text_file_outside_data(tmp_path):
    """A prompt is inserted verbatim into the system message, so pointing it at the golden file
    would hand the model the answer key."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "golden.csv").write_text("id,date\nT0001,2026-01-01\n")
    f = write(tmp_path, "name: x\nstages:\n  - name: a\n    type: map\n    model: m\n    prompt: data/golden.csv\n")
    with pytest.raises(TeamError, match="a.*prompt.*\\.md"):
        load_team(f)
    (tmp_path / "prompts" / "notes.txt").write_text("fine\n")
    load_team(write(tmp_path, "name: x\nstages:\n  - name: a\n    type: map\n    model: m\n    prompt: prompts/notes.txt\n"))


def test_cloud_model_names_are_rejected(tmp_path):
    f = write(tmp_path, "name: x\nstages:\n  - name: a\n    type: map\n    model: gpt-oss:120b-cloud\n    prompt: prompts/clean.md\n")
    with pytest.raises(TeamError, match="a.*cloud"):
        load_team(f)
