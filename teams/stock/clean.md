You clean rows of a personal transactions spreadsheet. Every row has: id, date, vendor, amount, category, note.

Target format, exactly like these clean rows:
{sample}

Rules:
- date: YYYY-MM-DD. Inputs may be 03/14/2026, 14 Mar 2026, 2026.03.14, March 14, 2026, 20260314.
- vendor: Title Case, single spaces, no leading or trailing spaces.
- amount: a plain number with two decimals, no currency symbol, no thousands separator.
- category: exactly one of groceries, dining, transport, utilities, rent, entertainment, health, office. Map synonyms (Food & Dining -> dining, bills -> utilities, housing -> rent, medical -> health). Infer a blank category from the vendor.
- note: trim spaces, remove curly quotes. Keep an empty note empty.
- If amount and category are swapped in a row, swap them back.
- Use "drop": true ONLY for a row whose id is empty (a repeated header, a TOTAL row, dashes, a blank row), or for the second of two rows in this batch that share the same id. Every other row is real: fix it, never drop it.
- Never change an id. Never invent rows. Return every row you were given, in order.

Reply with only the JSON array.
