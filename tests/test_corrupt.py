import random
import re

from fightnight.corrupt import CATEGORIES, COLUMNS, PRESETS, corrupt, make_golden, read_csv, write_csv


def test_golden_is_seeded_and_clean():
    a = make_golden(50, random.Random(3))
    b = make_golden(50, random.Random(3))
    assert a == b
    assert len(a) == 50
    assert [k for k in a[0]] == COLUMNS
    for row in a:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["date"])
        assert re.fullmatch(r"\d+\.\d{2}", row["amount"])
        assert row["category"] in CATEGORIES
        assert row["vendor"] == row["vendor"].strip() and row["vendor"]
    assert len({r["id"] for r in a}) == 50


def test_corrupt_keeps_ids_and_adds_junk():
    golden = make_golden(100, random.Random(5))
    ids = {r["id"] for r in golden}
    easy = corrupt(golden, random.Random(1), "easy")
    brutal = corrupt(golden, random.Random(1), "brutal")
    for rows in (easy, brutal):
        for r in rows:
            assert r["id"] == "" or r["id"] in ids
        assert any(r["id"] == "" for r in rows), "junk rows expected"
        assert set(r["id"] for r in rows if r["id"]) == ids, "every golden id survives"
    assert len(brutal) > len(easy) > 100
    assert set(PRESETS) == {"easy", "medium", "brutal"}
    # it actually corrupted something
    assert sum(1 for g, m in zip(golden, easy) if g != m) > 0


def test_csv_roundtrip(tmp_path):
    rows = make_golden(5, random.Random(0))
    p = tmp_path / "x.csv"
    write_csv(p, rows, COLUMNS)
    assert read_csv(p) == rows


def test_date_corruptions_are_unambiguous():
    """A d/m/yyyy date only appears when the day is over 12, so every messy date has one right answer."""
    import datetime
    golden = make_golden(300, random.Random(11))
    messy = corrupt(golden, random.Random(12), "brutal")
    by_id = {r["id"]: r for r in golden}
    for r in messy:
        if not r["id"]:
            continue
        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", r["date"])
        if m and int(m.group(1)) <= 12 and int(m.group(2)) <= 12:
            a, b, y = m.groups()
            assert f"{y}-{int(a):02d}-{int(b):02d}" == by_id[r["id"]]["date"], f"{r['date']} is ambiguous"


def test_quotes_only_wrap_real_notes():
    golden = make_golden(300, random.Random(2))
    messy = corrupt(golden, random.Random(3), "brutal")
    by_id = {r["id"]: r for r in golden}
    for r in messy:
        if r["id"] and r["note"].startswith("\u201c"):
            assert by_id[r["id"]]["note"] != "", "an empty note must stay recoverable"
