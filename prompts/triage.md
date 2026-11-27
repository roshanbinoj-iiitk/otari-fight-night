You sort rows of a messy transactions spreadsheet by what is wrong with them. Do not fix anything.

Add one key "tag" to every row with exactly one of these values:
- "junk" if the id is empty, or the row is a repeated header, a TOTAL row, or all dashes
- "date" if the date is not in YYYY-MM-DD form
- "dirty" for anything else that needs cleaning (currency symbols, odd casing, wrong category word, extra spaces, swapped amount and category)
- "ok" if the row already looks like the clean sample

Clean sample for reference:
{sample}

Return every row you were given, in order, with all its original keys plus "tag". JSON array only.
