You fix the vendor and category columns of a transactions spreadsheet using this lookup table. Each line is: vendor name -> category.

Whole Harvest Market -> groceries
Corner Grocer -> groceries
Fresh Fields -> groceries
Daily Pantry -> groceries
Blue Fork Bistro -> dining
Taco Lane -> dining
Noodle House -> dining
Sunrise Diner -> dining
Metro Transit -> transport
City Cab Co -> transport
Rapid Rail -> transport
Blue Line Scooters -> transport
Northside Power -> utilities
Clearwater Utility -> utilities
Fiber Net -> utilities
Metro Gas -> utilities
Maple Court Apartments -> rent
Riverside Lofts -> rent
Oak Street Property -> rent
Starlight Cinema -> entertainment
Vinyl Vault -> entertainment
Game Den -> entertainment
Riverside Theater -> entertainment
Greenleaf Pharmacy -> health
Summit Dental -> health
Wellness Clinic -> health
Clear Vision Optics -> health
Paper Trail Supply -> office
Desk Depot -> office
Print Hub -> office
Cable Depot -> office

For each row:
1. Find the table line whose vendor name matches the row's vendor, ignoring upper/lower case, extra spaces, tabs and two swapped letters.
2. Set "vendor" to the name exactly as written in the table.
3. Set "category" to that line's category. Ignore the old category completely: it is often a synonym, a capitalized word or blank, and it is never trusted.

Examples (input vendor, input category -> output):
- "rAPID rAIL", "commute" -> {"vendor": "Rapid Rail", "category": "transport"}
- "  CABLE DEPOT", "work" -> {"vendor": "Cable Depot", "category": "office"}
- "Print Hub", "office supplies" -> {"vendor": "Print Hub", "category": "office"}
- "Oak Street Property", "Rent" -> {"vendor": "Oak Street Property", "category": "rent"}
- "maple court apartments", "apartment" -> {"vendor": "Maple Court Apartments", "category": "rent"}
- "Vinyl Vault", "Movies & Music" -> {"vendor": "Vinyl Vault", "category": "entertainment"}
- "Fiber Net", "power/water" -> {"vendor": "Fiber Net", "category": "utilities"}
- "Taco Lane", "Dining" -> {"vendor": "Taco Lane", "category": "dining"}
- "Summit Dental", "Healthcare" -> {"vendor": "Summit Dental", "category": "health"}
- "Corner Grocer", "food shopping" -> {"vendor": "Corner Grocer", "category": "groceries"}
- "rapi drail", "" -> {"vendor": "Rapid Rail", "category": "transport"}

Reply with a JSON array with one object per row, in order, holding only the keys id, vendor and category, for example:
[{"id": "S0007", "vendor": "Rapid Rail", "category": "transport"}]
Copy each id exactly as given. Do not include the other columns. Every row is real: never drop one.
