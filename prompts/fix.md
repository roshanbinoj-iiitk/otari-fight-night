You clean rows of a personal transactions spreadsheet. Every row has: id, date, vendor, amount, category, note.

Target format, exactly like these clean rows:
{sample}

Fix every column of every row with these rules.

date: write YYYY-MM-DD. The year is always 2026.
- 03/14/2026 -> 2026-03-14 (month/day/year)
- 3/14/26 -> 2026-03-14 (month/day/two-digit year)
- 25/3/2026 -> 2026-03-25 (day first only when the first number is over 12)
- 2026.03.14 -> 2026-03-14
- 20260314 -> 2026-03-14
- 14 Mar 2026 -> 2026-03-14
- March 14, 2026 -> 2026-03-14
- A date already in YYYY-MM-DD form stays exactly as it is.

vendor: must be exactly one of these names, spelled and capitalized exactly like this. Fix casing, spacing, tabs and swapped letters to the closest name:
Whole Harvest Market, Corner Grocer, Fresh Fields, Daily Pantry, Blue Fork Bistro, Taco Lane, Noodle House, Sunrise Diner, Metro Transit, City Cab Co, Rapid Rail, Blue Line Scooters, Northside Power, Clearwater Utility, Fiber Net, Metro Gas, Maple Court Apartments, Riverside Lofts, Oak Street Property, Starlight Cinema, Vinyl Vault, Game Den, Riverside Theater, Greenleaf Pharmacy, Summit Dental, Wellness Clinic, Clear Vision Optics, Paper Trail Supply, Desk Depot, Print Hub, Cable Depot

amount: digits with exactly two decimals. Remove $, USD, spaces and thousands commas. $1,234.50 -> 1234.50, USD 12.30 -> 12.30, 12.3 -> 12.30, 15.670 -> 15.67.

category: exactly one lowercase word from groceries, dining, transport, utilities, rent, entertainment, health, office. The category is decided by the vendor:
- groceries: Whole Harvest Market, Corner Grocer, Fresh Fields, Daily Pantry
- dining: Blue Fork Bistro, Taco Lane, Noodle House, Sunrise Diner
- transport: Metro Transit, City Cab Co, Rapid Rail, Blue Line Scooters
- utilities: Northside Power, Clearwater Utility, Fiber Net, Metro Gas
- rent: Maple Court Apartments, Riverside Lofts, Oak Street Property
- entertainment: Starlight Cinema, Vinyl Vault, Game Den, Riverside Theater
- health: Greenleaf Pharmacy, Summit Dental, Wellness Clinic, Clear Vision Optics
- office: Paper Trail Supply, Desk Depot, Print Hub, Cable Depot
Blank, synonyms (Travel, commute, bills, power/water, housing, apartment, fun, leisure, Movies & Music, medical, pharmacy, Healthcare, work, Supplies, office supplies, food shopping, supermarket, restaurants, eating out, Food & Dining) and capitalized words (Rent, GROCERY, UTILITY) all become the vendor's category.

note: one of: monthly, reimbursable, shared with roommate, receipt attached, paid by card, auto-pay, gift, or empty. Remove curly quotes “ ” and straight quotes and outer spaces. Keep each row's own note; never copy a note from another row; an empty note stays empty.

swapped columns: if amount holds a category word and category holds a number, swap them back, then clean both.

Removing rows:
- A row whose id is empty (repeated header, TOTAL, dashes, blank) gets "drop": true.
- If two rows in this batch share the same id, the second gets "drop": true.
- Every other row is real: return it fixed, never drop it.
- Never change an id. Never write "drop" in the id. Never invent rows. Return every row you were given, in order.

Reply with only the JSON array.
