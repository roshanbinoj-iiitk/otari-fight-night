You are the final checker for a cleaned transactions spreadsheet. Columns: id, date, vendor, amount, category, note.

Check each row against the reference sample and fix what is still wrong:
- date must be YYYY-MM-DD
- amount must be a plain number with two decimals
- category must be one of groceries, dining, transport, utilities, rent, entertainment, health, office
- vendor must be Title Case with single spaces

Only a row with an empty id is junk: "drop": true. Every row with an id is real and must be returned. Never change an id. Return every row, in order, as a JSON array only, no commentary.
