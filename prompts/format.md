You fix only the date, amount and note columns of a transactions spreadsheet. Every row has: id, date, vendor, amount, category, note.

Target format, exactly like these clean rows:
{sample}

Work on each row by itself. Every value you write comes from that same row's input; never take a value from another row or from the examples below.

date: write YYYY-MM-DD. The year is always 2026.
- If the date is already YYYY-MM-DD, copy it unchanged, digit for digit.
- 07/21/2026 -> 2026-07-21 (month/day/year)
- 5/9/26 -> 2026-05-09 (month/day/two-digit year)
- 25/3/2026 -> 2026-03-25 (day first only when the first number is over 12)
- 2026.11.02 -> 2026-11-02
- 20260418 -> 2026-04-18
- 6 Sep 2026 -> 2026-09-06
- January 30, 2026 -> 2026-01-30

amount: digits with exactly two decimals. Remove $, USD, spaces and thousands commas. $1,234.50 -> 1234.50, USD 12.30 -> 12.30, 8.7 -> 8.70, 15.670 -> 15.67. Always keep the decimal point where it is: 17.18 stays 17.18, never 1718.00. If the amount is already plain with two decimals, copy it unchanged.

note: remove curly quotes “ ”, straight quotes, tabs and spaces at the start or end (also inside the quotes). A note that is empty, or only spaces or a tab, becomes empty "". Otherwise keep the row's own words: monthly, reimbursable, shared with roommate, receipt attached, paid by card, auto-pay or gift. Never fill in an empty note.

swapped columns: if amount holds a word (like rent, health, dining) and category holds a number, the amount is that number from category.

Reply with a JSON array with one object per row, in order, holding only the keys id, date, amount and note:
[{"id": "<same id>", "date": "<YYYY-MM-DD>", "amount": "<number>", "note": "<this row's note or empty>"}]
Copy each id exactly as given. Do not include vendor or category; another step fixes them. Every row is real: never drop one.
