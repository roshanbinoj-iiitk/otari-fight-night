import json
from pathlib import Path

from fightnight.corrupt import read_csv
from fightnight.otari import ChatResult
from fightnight.referee import clean_file
from fightnight.team import load_team


def test_clean_file_assigns_and_strips_id(tmp_path):
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "p.md").write_text("clean\n")
    (tmp_path / "team.yml").write_text("stages:\n  - {name: m, type: map, model: a, batch: 10, prompt: prompts/p.md}\n")
    team = load_team(tmp_path / "team.yml")
    src = tmp_path / "bank.csv"
    src.write_text("when,who,how much\n1/2/2026,ACME,$5\n3/4/2026,Bob,7\n")
    seen = {}

    def chat(model, messages, max_tokens):
        rows = json.loads(messages[-1]["content"].split("Rows:\n", 1)[1].split("\n\nReturn", 1)[0])
        seen["keys"] = list(rows[0])
        for r in rows:
            r["who"] = r["who"].title()
        return ChatResult(json.dumps(rows), 1, 1, 0.1, None, "ollama", model)

    out = clean_file(team, src, sample=[], chat=chat, on_call=lambda c: None)
    assert out == tmp_path / "bank.clean.csv"
    assert "id" in seen["keys"], "rows get an id so the pipeline can match answers"
    rows = read_csv(out)
    assert list(rows[0]) == ["when", "who", "how much"], "no id column leaks into the output"
    assert [r["who"] for r in rows] == ["Acme", "Bob"]


def test_clean_file_lets_models_remove_duplicates_and_junk_without_ids(tmp_path):
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "p.md").write_text("clean\n")
    (tmp_path / "team.yml").write_text("stages:\n  - {name: m, type: map, model: a, batch: 10, prompt: prompts/p.md}\n")
    team = load_team(tmp_path / "team.yml")
    src = tmp_path / "x.csv"
    src.write_text("when,who,how much\n1/2/2026,ACME,$5\n1/2/2026,ACME,$5\nwhen,who,how much\n,,\nTOTAL,,99\n3/4/2026,Bob,7\n")

    def chat(model, messages, max_tokens):
        rows = json.loads(messages[-1]["content"].split("Rows:\n", 1)[1].split("\n\nReturn", 1)[0])
        return ChatResult(json.dumps([{**r, "drop": True} for r in rows]), 1, 1, 0.1, None, "ollama", model)

    out = clean_file(team, src, sample=[], chat=chat, on_call=lambda c: None)
    rows = read_csv(out)
    # exact duplicate, repeated header and blank row may go. The TOTAL row has data, so plain
    # code cannot tell it from a real row and keeps it. The two real rows stay.
    assert [r["when"] for r in rows] == ["1/2/2026", "TOTAL", "3/4/2026"]


def test_clean_file_header_only(tmp_path):
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "p.md").write_text("clean\n")
    (tmp_path / "team.yml").write_text("stages:\n  - {name: m, type: map, model: a, batch: 10, prompt: prompts/p.md}\n")
    team = load_team(tmp_path / "team.yml")
    src = tmp_path / "empty.csv"
    src.write_text("a,b\n")
    out = clean_file(team, src, sample=[], chat=lambda *a: None, on_call=lambda c: None)
    assert out.read_text() == "a,b\n"


def _team(tmp_path):
    (tmp_path / "prompts").mkdir(exist_ok=True)
    (tmp_path / "prompts" / "p.md").write_text("clean\n")
    (tmp_path / "team.yml").write_text("stages:\n  - {name: m, type: map, model: a, batch: 10, prompt: prompts/p.md}\n")
    return load_team(tmp_path / "team.yml")


def _echo(model, messages, max_tokens):
    rows = json.loads(messages[-1]["content"].split("Rows:\n", 1)[1].split("\n\nReturn", 1)[0])
    return ChatResult(json.dumps(rows), 1, 1, 0.1, None, "ollama", model)


def test_clean_file_keeps_semicolon_delimiter_and_decimal_commas(tmp_path):
    src = tmp_path / "bank.csv"
    src.write_text("Datum;Betrag;Text\n01.02.2026;5,00;Miete\n")
    out = clean_file(_team(tmp_path), src, sample=[], chat=_echo, on_call=lambda c: None)
    assert out.read_text() == "Datum;Betrag;Text\n01.02.2026;5,00;Miete\n"


def test_clean_file_strips_bom_and_reads_latin1(tmp_path):
    src = tmp_path / "bom.csv"
    src.write_bytes("\ufeffid,who\n1,Zoë\n".encode("utf-8"))
    out = clean_file(_team(tmp_path), src, sample=[], chat=_echo, on_call=lambda c: None)
    assert read_csv(out) == [{"id": "1", "who": "Zoë"}]
    src2 = tmp_path / "latin.csv"
    src2.write_bytes("who,note\nJos\xe9,caf\xe9\n".encode("latin-1"))
    out2 = clean_file(_team(tmp_path), src2, sample=[], chat=_echo, on_call=lambda c: None)
    assert read_csv(out2) == [{"who": "José", "note": "café"}]


def test_clean_file_rejects_ragged_rows_with_a_clear_error(tmp_path):
    import pytest

    src = tmp_path / "ragged.csv"
    src.write_text("a,b\n1,2,3\n")
    with pytest.raises(ValueError, match="row 2.*3 cells.*2 columns"):
        clean_file(_team(tmp_path), src, sample=[], chat=_echo, on_call=lambda c: None)
