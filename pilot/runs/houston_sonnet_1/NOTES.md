# NOTES

## Filter
Field: `Ethnicity`. Treated as Black-owned: exactly `Black` (5,505 rows) and `Black American` (22 rows), case-insensitive. These are the source's own ethnicity labels for the owner. Excluded: `Hispanic`, `Hispanic American`, `Caucasian`, `Asian`, `Native American`, `Other Ethnicity`. I did not filter on `Certification Type` (MBE/SBE/WBE/etc.): the file has one row per certification, and Black ethnicity is recorded on SBE, WBE, PDBE, LGBTBE, VOSB rows too, so restricting to MBE would drop firms the source labels Black.

## Deduplication
The file has one row per firm per certification type. Key: normalized company name (lowercase, alphanumerics only) + normalized owner name (first + last). Rows are merged; `certification` is the comma-joined list of distinct certification types across the firm's Black rows. Other fields come from the first Black row, with blanks filled from later rows. Rows read in: 11,480 data rows (5,527 with a Black ethnicity label). Firms returned: 2,210.

## Field mapping
- Company Name → business_name
- Owner First + Owner Last → owner_name (combined, via synthetic "Owner Name" column)
- Physical Address → address_street; City → address_city; State → address_state; Zip → address_zip
- Phone → phone; Email → email; Website → website
- Certification Type → certification (merged)
- Category → industry; Capability → description
- Commodity Codes → naics_code (raw string; contains "code - description" entries separated by semicolons)
- Everything else (DBA Name, Mailing Address / Mailing City / Mailing State / Mailing Zip, Fax, Agency, Ethnicity, Gender, HUB?, Re-Evaluation Status, Owner First/Last) → `source_fields`.
- The second City/State/Zip column group is renamed with a "Mailing " prefix. `last_verified` = run date.

## Record count
`Adapter(file_path="raw/houston_directory_2026-06-14.csv").run()` returns **2210** records.

## Ambiguities and assumptions
- "Black American" is treated as Black. It appears only on LGBTBE rows (the Houston LGBT agency's certification), apparently a different label vocabulary for the same thing.
- Same-name firms with different owners would be kept as separate firms; none exist among the Black rows. Two firms were not merged by name alone to avoid collapsing distinct businesses.
- Conflicting labels for one firm: `JR THOMAS GROUP, INC.` (MBE row Hispanic, SBE row Black) and `The Business Team LLC` (SBE/WBE rows Caucasian, LGBTBE row Black American). I included both because at least one row labels the firm Black, but the source disagrees with itself; these are uncertain. 7 firms have more than one Black-variant label (Black vs Black American) across rows, which is harmless.
- `CONFIDENCE` is set to "confirmed_black" because the source states ethnicity directly. `PROGRAM` = "MWBE", `GEOGRAPHY` = "Houston, TX".
- Latitude/longitude, year founded, etc. are not in the source and stay empty. Black-firm count cannot be checked against a published total (none exists).
- Records with `Ethnicity` Black but only an SBE/WBE-type certification are included (see Filter).

## Anything that looked wrong or surprising
- The file is not UTF-8; it is cp1252 (a 0x92 apostrophe byte). The adapter reads it as cp1252.
- It has a 6-line preamble before the header, a footer ("Generated from the B2Gnow System."), and a trailing empty column on every row.
- Duplicate column names (City/State/Zip appear twice) make it unreadable by name with pandas/DictReader without renaming.
- Zip values carry a leading tab, and some company names carry trailing tabs; values are stripped. Some mailing zips look like typos (e.g. physical 77033 vs mailing 70333; mailing City sometimes holds "Houston texas 77033").
- The same firm's address and phone differ between certification rows (e.g. suite number typos, different phone numbers); the first row's value is used.
- City casing is inconsistent ("Houston" vs "HOUSTON"); not normalized.
- A few non-Texas states appear among Black firms (NJ, AL) despite the Houston program.
- Gender is blank for 4 rows overall.
