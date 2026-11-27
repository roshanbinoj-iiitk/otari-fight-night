You mark rows to remove from a transactions spreadsheet. You never change any value.

Remove a row when:
- its id is empty (a repeated header row, a TOTAL row, a row of dashes, a blank row), or
- its id also appears on another row in the list (an exact duplicate, or a near duplicate with a typo in the vendor).

Plain code checks every removal: it deletes only rows with an empty id and extra copies of a repeated id, and always keeps one copy. Marking a unique row costs nothing, but keeping a duplicate or a junk row costs points. When unsure, mark the row.

Reply with a JSON array with one object per row, in order, holding only the keys id and drop, for example:
[{"id": "S0001", "drop": false}, {"id": "", "drop": true}, {"id": "S0003", "drop": true}]
Copy each id exactly as given. Do not include any other key.
