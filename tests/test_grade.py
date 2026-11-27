import random

from fightnight.corrupt import corrupt, make_golden
from fightnight.grade import grade


def test_grade_is_strict_about_format():
    """Cleaning means producing the clean form. Formatting differences are errors, not noise."""
    golden = make_golden(1, random.Random(1))
    g = golden[0]
    for col, bad in (("date", "03/14/2026"), ("date", f" {g['date']} "), ("amount", "$" + g["amount"]), ("amount", g["amount"] + "0"),
                     ("vendor", g["vendor"].upper()), ("vendor", "  " + g["vendor"]), ("category", g["category"].title()), ("note", "\u201c" + g["note"] + "\u201d")):
        messy = [dict(g)]
        messy[0][col] = bad
        unfixed = grade(golden, messy, [dict(messy[0])])
        assert unfixed.problems == 1 and unfixed.fixed == 0 and unfixed.repair_pct == 0.0, (col, bad)
        fixed = grade(golden, messy, [dict(g)])
        assert fixed.fixed == 1 and fixed.repair_pct == 100.0 and fixed.per_column[col] == 100.0


def test_untouched_messy_file_scores_zero_and_fixing_everything_scores_full():
    for preset in ("easy", "medium", "brutal"):
        golden = make_golden(50, random.Random(1))
        messy = corrupt(golden, random.Random(2), preset)
        noop = grade(golden, messy, [dict(r) for r in messy])
        assert noop.fixed == 0 and noop.problems > 20, preset
        assert noop.dup_kept > 0 or noop.junk_kept > 0
        assert noop.repair_pct <= 0.0  # junk kept costs, so doing nothing is zero or worse
        perfect = grade(golden, messy, [dict(r) for r in golden])
        assert perfect.repair_pct == 100.0 and perfect.fixed == perfect.problems and perfect.broken == 0


def test_dedupe_and_junk_removal_earn_nothing_by_themselves():
    """Plain code can drop junk and duplicates, so a team gets no credit for it. Keeping them still costs."""
    golden = make_golden(30, random.Random(4))
    messy = corrupt(golden, random.Random(5), "medium")
    only_cleanup = [dict(r) for r in messy if r["id"]]
    seen = set()
    only_cleanup = [r for r in only_cleanup if not (r["id"] in seen or seen.add(r["id"]))]
    g = grade(golden, messy, only_cleanup)
    assert g.fixed == 0 and g.repair_pct == 0.0 and g.dup_kept == 0 and g.junk_kept == 0


def test_breaking_clean_cells_costs_and_can_go_negative():
    golden = make_golden(10, random.Random(3))
    messy = [dict(r) for r in golden]
    messy[0]["amount"] = "$" + messy[0]["amount"]  # one problem
    cleaned = [dict(r) for r in golden]
    cleaned[1]["vendor"] = "WRONG"
    cleaned[2]["vendor"] = "WRONG"  # fixed 1, broke 2
    g = grade(golden, messy, cleaned)
    assert (g.problems, g.fixed, g.broken) == (1, 1, 2)
    assert g.repair_pct == -100.0
    assert g.accuracy < 1.0


def test_grade_perfect_is_one():
    golden = make_golden(10, random.Random(1))
    g = grade(golden, [dict(r) for r in golden], [dict(r) for r in golden])
    assert g.accuracy == 1.0 and g.problems == 0 and g.repair_pct == 100.0
    assert g.dup_kept == 0 and g.dropped == 0 and g.junk_kept == 0
    assert set(g.per_column) == {"date", "vendor", "amount", "category", "note"}


def test_grade_duplicate_and_dropped_and_junk():
    golden = make_golden(10, random.Random(1))
    junk = {"id": "", "date": "TOTAL", "vendor": "", "amount": "999", "category": "", "note": ""}
    messy = [dict(r) for r in golden] + [dict(golden[0]), dict(golden[5]), junk]  # two dup problems, one junk problem
    cleaned = [dict(r) for r in golden]
    cleaned.append(dict(golden[0]))  # duplicate of id 0 kept
    cleaned.pop(1)  # id 1 dropped
    cleaned.append(dict(junk))  # junk kept
    g = grade(golden, messy, cleaned)
    assert g.dup_kept == 1 and g.dropped == 1 and g.junk_kept == 1
    assert g.problems == 0 and g.fixed == 0  # no dirty cells; removals earn nothing
    assert g.broken == 5 + 5  # the dropped row's five clean cells, and a junk row kept
    assert g.accuracy == (8 * 5) / (10 * 5 + 5)
    assert g.rows_out == len(cleaned)


def test_grade_never_crashes_on_garbage():
    golden = make_golden(4, random.Random(2))
    g = grade(golden, [dict(r) for r in golden], [{"id": golden[0]["id"]}, {"nonsense": 1}, {"id": None}])
    assert 0.0 <= g.accuracy < 1.0
    assert g.dropped == 3 and g.broken >= 15
