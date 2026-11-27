import random
from pathlib import Path

from fightnight.corrupt import make_golden
from fightnight.integrity import prompt_leaks, referee_fingerprint
from fightnight.team import Stage, Team


def _team(tmp_path, text):
    p = tmp_path / "p.md"
    p.write_text(text)
    return Team("t", [Stage("a", "map", model="m", prompt=p)], tmp_path / "t.yml", "x")


def test_prompt_leaks_flags_dataset_ids_and_golden_rows(tmp_path):
    golden = make_golden(5, random.Random(1))
    g = golden[2]
    clean = _team(tmp_path, "Fix dates to YYYY-MM-DD. Vendors: Taco Lane -> dining.\n")
    assert prompt_leaks(clean, golden) == []
    with_ids = _team(tmp_path, "When you see T0003 the answer is 2026-01-27.\n")
    leaks = prompt_leaks(with_ids, golden)
    assert any("dataset id" in x for x in leaks)
    with_row = _team(tmp_path, f"Lookup: {g['vendor']},{g['amount']},{g['category']}\n")
    leaks = prompt_leaks(with_row, golden)
    assert any("golden row" in x for x in leaks)


def test_prompt_leaks_ignores_sample_ids(tmp_path):
    golden = make_golden(5, random.Random(7))  # a real fight never uses the sample's seed
    t = _team(tmp_path, "Example clean row: S0001,2026-10-28,Metro Transit,21.90,transport,paid by card\n")
    assert prompt_leaks(t, golden) == []


def test_referee_fingerprint_is_stable_and_names_files():
    a = referee_fingerprint()
    b = referee_fingerprint()
    assert a["code_sha256"] == b["code_sha256"] and len(a["code_sha256"]) == 12
    assert "grade.py" in a["files"] and "pipeline.py" in a["files"]
    assert "git" in a


def test_fingerprint_git_is_last_commit_touching_referee_code():
    import subprocess

    fp = referee_fingerprint()
    expected = subprocess.run(["git", "log", "-1", "--format=%h", "--", "fightnight"], capture_output=True, text=True).stdout.strip()
    assert fp["git"].split()[0] == expected
    assert fp["git"] == expected or fp["git"] == expected + " (modified)"


def test_fingerprint_at_commit_matches_working_tree_when_clean(tmp_path):
    import subprocess

    from fightnight.integrity import fingerprint_at, stock_sha_at

    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "fightnight", "teams"], capture_output=True, text=True).stdout.strip()
    if dirty:
        import pytest

        pytest.skip("working tree has uncommitted referee or stock changes")
    assert fingerprint_at(head) == referee_fingerprint()["code_sha256"]
    from fightnight.team import load_team

    assert stock_sha_at(head) == load_team(Path("teams/stock.yml")).sha256


def test_verify_card_catches_tampering(tmp_path):
    import json
    import subprocess

    from fightnight.integrity import verify_card

    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    card = {
        "dataset": {"preset": "medium", "rows": 50},
        "stock": {"sha256": stock_sha_at_head(), "failed_requests": 0},
        "team": {"local_requests_pct": 100.0, "models": ["qwen2.5:3b"]},
        "gateway": {"integrity": {"referee": {"code_sha256": fingerprint_at_head(), "git": head}, "model_digests": {"qwen2.5:3b": "357c53fb659c"},
                                  "prompt_leaks": {"team": [], "stock": []}}},
    }
    p = tmp_path / "card.json"
    p.write_text(json.dumps(card))
    ok, findings = verify_card(p, upstream="HEAD", official_digests={"qwen2.5:3b": "357c53fb659c"})
    assert ok, findings
    card["gateway"]["integrity"]["referee"]["code_sha256"] = "deadbeef0000"
    card["team"]["local_requests_pct"] = 90.0
    card["gateway"]["integrity"]["prompt_leaks"]["team"] = ["p.md: mentions dataset id(s) T0001"]
    p.write_text(json.dumps(card))
    ok, findings = verify_card(p, upstream="HEAD", official_digests={"qwen2.5:3b": "357c53fb659c"})
    assert not ok
    text = "\n".join(findings)
    assert "referee code" in text and "locally" in text and "answer-key" in text


def stock_sha_at_head():
    import subprocess

    from fightnight.integrity import stock_sha_at

    return stock_sha_at(subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip())


def fingerprint_at_head():
    import subprocess

    from fightnight.integrity import fingerprint_at

    return fingerprint_at(subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip())
