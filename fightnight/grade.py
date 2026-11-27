"""Score a cleaned CSV against the golden one. Plain code, by id.

The headline is net repair: of the cells that were wrong in the messy file, how many came back
right, minus clean cells the team broke, as a percentage of the problems. Doing nothing scores
0. Wrecking clean data goes negative. Comparison is exact: cleaning means producing the clean form.

Removing duplicates and junk earns nothing, because plain code in the referee can do that on a
model's say-so. Keeping them still costs: a duplicated id scores none of its repairs, and a junk
row kept counts as a row of broken cells.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .corrupt import COLUMNS

SCORED = [c for c in COLUMNS if c != "id"]


@dataclass
class Grade:
    repair_pct: float  # (fixed - broken) / problems * 100
    problems: int = 0  # dirty cells in the messy file
    fixed: int = 0  # dirty cells now exactly right
    broken: int = 0  # clean cells now wrong, plus a row's worth per real row dropped or junk row kept
    accuracy: float = 0.0  # share of golden cells exactly right in the output, for reference
    per_column: dict[str, float] = field(default_factory=dict)  # repair rate per column, percent
    dup_kept: int = 0
    dropped: int = 0
    junk_kept: int = 0
    rows_out: int = 0


def _cell(value) -> str:
    return "" if value is None else str(value)


def _by_id(rows: list[dict]) -> tuple[dict[str, list[dict]], int]:
    by_id: dict[str, list[dict]] = {}
    junk = 0
    for row in rows:
        rid = _cell(row.get("id")).strip() if isinstance(row, dict) else ""
        if not rid:
            junk += 1
            continue
        by_id.setdefault(rid, []).append(row)
    return by_id, junk


def grade(golden: list[dict], messy: list[dict], cleaned: list[dict]) -> Grade:
    messy_by_id, messy_junk = _by_id(messy)
    clean_by_id, junk_kept = _by_id(cleaned)
    golden_ids = {g["id"] for g in golden}
    junk_kept += sum(len(v) for k, v in clean_by_id.items() if k not in golden_ids)

    problems = fixed = broken = correct = 0
    col_problems = {c: 0 for c in SCORED}
    col_fixed = {c: 0 for c in SCORED}
    dup_kept = dropped = 0

    for g in golden:
        before = messy_by_id.get(g["id"], [dict(g)])
        first = before[0]
        dirty = {c for c in SCORED if _cell(first.get(c)) != g[c]}
        problems += len(dirty)
        for c in dirty:
            col_problems[c] += 1

        after = clean_by_id.get(g["id"], [])
        if not after:
            dropped += 1
            broken += len(SCORED)
            continue
        kept_extra = len(after) - 1
        dup_kept += kept_extra
        if kept_extra:
            continue  # a duplicated id scores no repairs
        row = after[0]
        for c in SCORED:
            right = _cell(row.get(c)) == g[c]
            if right:
                correct += 1
            if c in dirty and right:
                fixed += 1
                col_fixed[c] += 1
            elif c not in dirty and not right:
                broken += 1

    broken += junk_kept * len(SCORED)
    total_cells = len(golden) * len(SCORED) + junk_kept * len(SCORED)
    return Grade(
        repair_pct=round((fixed - broken) / problems * 100, 1) if problems else (100.0 if broken == 0 else -100.0),
        problems=problems,
        fixed=fixed,
        broken=broken,
        accuracy=correct / total_cells if total_cells else 0.0,
        per_column={c: round(col_fixed[c] / col_problems[c] * 100, 1) if col_problems[c] else 100.0 for c in SCORED},
        dup_kept=dup_kept,
        dropped=dropped,
        junk_kept=junk_kept,
        rows_out=len(cleaned),
    )
