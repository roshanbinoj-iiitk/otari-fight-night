"""Make a clean golden CSV and a messy copy of it from a seed. Plain code, no model."""

from __future__ import annotations

import csv
import random
from pathlib import Path

COLUMNS = ["id", "date", "vendor", "amount", "category", "note"]
CATEGORIES = ["groceries", "dining", "transport", "utilities", "rent", "entertainment", "health", "office"]

_VENDORS = {
    "groceries": ["Whole Harvest Market", "Corner Grocer", "Fresh Fields", "Daily Pantry"],
    "dining": ["Blue Fork Bistro", "Taco Lane", "Noodle House", "Sunrise Diner"],
    "transport": ["Metro Transit", "City Cab Co", "Rapid Rail", "Blue Line Scooters"],
    "utilities": ["Northside Power", "Clearwater Utility", "Fiber Net", "Metro Gas"],
    "rent": ["Maple Court Apartments", "Riverside Lofts", "Oak Street Property"],
    "entertainment": ["Starlight Cinema", "Vinyl Vault", "Game Den", "Riverside Theater"],
    "health": ["Greenleaf Pharmacy", "Summit Dental", "Wellness Clinic", "Clear Vision Optics"],
    "office": ["Paper Trail Supply", "Desk Depot", "Print Hub", "Cable Depot"],
}
_NOTES = ["", "", "", "monthly", "reimbursable", "shared with roommate", "receipt attached", "paid by card", "auto-pay", "gift"]
_AMOUNT_RANGE = {"rent": (900, 2400), "utilities": (30, 260), "groceries": (8, 190), "dining": (6, 120), "transport": (2, 80), "entertainment": (5, 150), "health": (10, 400), "office": (3, 220)}

_CATEGORY_SYNONYMS = {
    "groceries": ["Groceries", "GROCERY", "food shopping", "supermarket"],
    "dining": ["Dining", "restaurants", "Food & Dining", "eating out"],
    "transport": ["Transport", "transportation", "Travel", "commute"],
    "utilities": ["Utilities", "bills", "UTILITY", "power/water"],
    "rent": ["Rent", "housing", "RENT", "apartment"],
    "entertainment": ["Entertainment", "fun", "leisure", "Movies & Music"],
    "health": ["Health", "medical", "Healthcare", "pharmacy"],
    "office": ["Office", "office supplies", "work", "Supplies"],
}
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_MONTHS_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

# rate per row for each corruption, by preset
PRESETS: dict[str, dict[str, float]] = {
    "easy": {"date": 0.25, "case": 0.2, "space": 0.15, "amount": 0.2, "category": 0.2, "blank": 0.03, "dup": 0.05, "neardup": 0.03, "quotes": 0.05, "swap": 0.0, "junk": 0.02},
    "medium": {"date": 0.45, "case": 0.35, "space": 0.3, "amount": 0.4, "category": 0.4, "blank": 0.06, "dup": 0.08, "neardup": 0.06, "quotes": 0.1, "swap": 0.03, "junk": 0.04},
    "brutal": {"date": 0.7, "case": 0.5, "space": 0.5, "amount": 0.6, "category": 0.6, "blank": 0.12, "dup": 0.12, "neardup": 0.1, "quotes": 0.2, "swap": 0.08, "junk": 0.08},
}


def make_golden(n: int, rng: random.Random) -> list[dict]:
    rows = []
    for i in range(n):
        cat = rng.choice(CATEGORIES)
        lo, hi = _AMOUNT_RANGE[cat]
        month, day = rng.randint(1, 12), rng.randint(1, 28)
        rows.append({
            "id": f"T{i + 1:04d}",
            "date": f"2026-{month:02d}-{day:02d}",
            "vendor": rng.choice(_VENDORS[cat]),
            "amount": f"{rng.uniform(lo, hi):.2f}",
            "category": cat,
            "note": rng.choice(_NOTES),
        })
    return rows


def _messy_date(iso: str, rng: random.Random) -> str:
    """Seven formats. The day-first slash form is used only when the day is over 12, so every
    messy date has exactly one right reading."""
    y, m, d = iso.split("-")
    mi = int(m)
    variants = [
        f"{m}/{d}/{y}", f"{y}.{m}.{d}", f"{int(d)} {_MONTHS[mi - 1]} {y}",
        f"{_MONTHS_LONG[mi - 1]} {int(d)}, {y}", f"{int(m)}/{int(d)}/{y[2:]}", f"{y}{m}{d}",
    ]
    if int(d) > 12:
        variants.append(f"{int(d)}/{int(m)}/{y}")
    return rng.choice(variants)


def _messy_amount(amount: str, rng: random.Random) -> str:
    v = float(amount)
    return rng.choice([f"${v:,.2f}", f"{v:,.2f}", f"USD {v:.2f}", f"{v:.1f}" if v * 10 == int(v * 10) else f"${v:.2f}", f"{v:.2f} USD", f"$ {v:.2f}", f"{v:.3f}"])


def _messy_case(text: str, rng: random.Random) -> str:
    return rng.choice([text.upper(), text.lower(), text.title(), text.swapcase()])


def _messy_space(text: str, rng: random.Random) -> str:
    return rng.choice([f"  {text}", f"{text}   ", text.replace(" ", "  "), f"\t{text}"])


def _typo(text: str, rng: random.Random) -> str:
    if len(text) < 3:
        return text + "x"
    i = rng.randrange(len(text) - 1)
    return text[:i] + text[i + 1] + text[i] + text[i + 2:]


def corrupt(rows: list[dict], rng: random.Random, preset: str) -> list[dict]:
    """A messy copy of golden rows. Ids are never touched; duplicates share an id; junk rows have id ''."""
    rates = PRESETS[preset]
    out: list[dict] = []
    for row in rows:
        r = dict(row)
        if rng.random() < rates["date"]:
            r["date"] = _messy_date(r["date"], rng)
        if rng.random() < rates["amount"]:
            r["amount"] = _messy_amount(r["amount"], rng)
        if rng.random() < rates["category"]:
            r["category"] = rng.choice(_CATEGORY_SYNONYMS[r["category"]])
        if rng.random() < rates["case"]:
            r["vendor"] = _messy_case(r["vendor"], rng)
        if rng.random() < rates["space"]:
            col = rng.choice(["vendor", "note", "category"])
            r[col] = _messy_space(r[col], rng)
        if r["note"].strip() and rng.random() < rates["quotes"]:
            r["note"] = f"“{r['note']}”"
        if rng.random() < rates["blank"]:
            r[rng.choice(["note", "category"])] = ""
        if rng.random() < rates["swap"]:
            r["amount"], r["category"] = r["category"], r["amount"]
        out.append(r)
        if rng.random() < rates["dup"]:
            out.append(dict(r))
        if rng.random() < rates["neardup"]:
            d = dict(r)
            d["vendor"] = _typo(d["vendor"], rng)
            out.append(d)
        if rng.random() < rates["junk"]:
            out.append(_junk_row(rng))
    if not any(r["id"] == "" for r in out):
        out.append(_junk_row(rng))  # every messy file has at least one junk row to catch
    rng.shuffle(out)
    return out


def _junk_row(rng: random.Random) -> dict:
    return rng.choice([
        {c: c for c in COLUMNS} | {"id": ""},
        {"id": "", "date": "", "vendor": "TOTAL", "amount": f"{rng.uniform(1000, 9000):.2f}", "category": "", "note": ""},
        {c: "" for c in COLUMNS},
        {"id": "", "date": "---", "vendor": "---", "amount": "---", "category": "---", "note": "---"},
    ])


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in columns})


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]
