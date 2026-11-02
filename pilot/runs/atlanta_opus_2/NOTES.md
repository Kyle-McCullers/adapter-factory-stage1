# NOTES — City of Atlanta certified directory adapter

## Filter

- Field: `Certification Type`. Value treated as Black-owned: `AABE` (exact, case-insensitive), the City of Atlanta's "African American Business Enterprise" certification.
- The file has no separate ethnicity column. `Certification Type` is the only field that records the owner's ethnicity, and AABE is the only value that names African American ownership.
- Values seen and excluded: `SBE` (small business, 1293 rows), `FBE` (female-owned, 554), `HABE` (Hispanic American, 108), `APABE` (Asian/Pacific American, 61), `NABE` (Native American, 5). None of them says anything about Black ownership.
- A firm counts as Black-owned if any of its rows is AABE. The record then lists all of that firm's certifications (for example `AABE; FBE; SBE`).
- Expired certifications are not filtered out (see Ambiguities).

## Deduplication

- The export has one row per firm per certification type, so most firms appear 2–3 times.
- `Supplier ID#` cannot serve as the firm key. Placeholder IDs `9999999` and `999999` are shared by 27 and 4 unrelated firms. At least 9 other IDs are each shared by two unrelated firms (e.g. `1701842` = A. Ritz Interiors / Legend Roofing; `908743` = H. J. Russell / Charter Construction). Some single firms also appear under two IDs (Graham Hauling `2100436`/`1206435`, Knight & Associates `P980200-01`/`98020001`, Momentum Supply `2004998`/`204998`).
- Key used: the normalized company name (lowercased, `&` turned into "and", everything except letters and digits removed).
- A second pass merges a name group into an earlier one when the owner name and email match exactly and one normalized name is a prefix of the other. This catches one case: "Anointed Professional Enterprise" (placeholder ID, expired 2024) and "Anointed Professional Enterprises Inc dba Glory Professional Cleaning" (`1906722`).
- Firms that share an owner or phone but have different names (e.g. Khafra Engineering / Khafra Operations) stay separate, because they are distinct affiliated firms.
- When a firm has several AABE rows, the representative row is the one with the latest `Expiration`.
- Rows read: 2888 data rows (2889 `<tr>` including the header). Firms returned: 864.

## Field mapping

| Source column | Schema field |
|---|---|
| Company Name | business_name |
| Supplier ID# | business_id (whitespace/tabs stripped; placeholder `9999999`/`999999` → "") |
| Owner First + Owner Last | owner_name (derived) |
| Location ("City, ST") | address_city, address_state (derived) |
| Phone | phone |
| Email | email |
| Website | website (junk values blanked; original kept in `source_fields["Website (raw)"]`) |
| Capability | description |
| Commodity Codes | naics_code (derived: unique numeric codes, comma-joined); raw text kept in source_fields |
| Certification Type (all rows of the firm) | certification, e.g. `AABE; SBE` |
| — | data_source = SOURCE_NAME; last_verified = today's ISO date |

- All other columns go into `source_fields`: DBA Name, Owner First, Owner Last, Location, Fax, Agency, Certification Type, Expiration, Market Area, Commodity Codes.
- `source_fields` also gets two added entries: `All Certification Types` and `All Supplier IDs`.
- Not available in the source, so left "": address_street, address_zip, lat/long, year_founded, industry, social and maps fields.
- Class constants: `SOURCE_ID="atlanta_occ_certified_directory"`, `PROGRAM="MWBE"`, `GEOGRAPHY="Atlanta, GA"`, `CONFIDENCE="confirmed_black"`.

## Record count

`Adapter(file_path="raw/atlanta_directory_2026-06-14.xls").run()` returns **864** records (run on 2026-10-16). Tests: 17 passed.

## Ambiguities and assumptions

- **Expired certifications are included.** 42 of the 864 firms have an `Expiration` before the download date of 2026-06-14, with some dating to 2024. The portal still listed them, and the task asks for firms the source identifies as Black-owned, not for currently active certifications. The expiration date is kept in `source_fields["Expiration"]` so downstream users can filter on it.
- **Confidence.** I set `CONFIDENCE` to `confirmed_black` because AABE is an ethnicity-specific certification issued by the city, not a generic MBE flag.
- **PROGRAM.** I set it to `"MWBE"`. Atlanta's EBO program certifications (AABE/FBE/etc.) fit the "MWBE" category best among the options in the base-class comment.
- **Name-based dedup.** This assumes two different firms do not share an exact normalized name. In this file, every name that appeared under more than one Supplier ID was the same firm (same owner, phone, and email).
- **Shared Supplier IDs.** Non-placeholder IDs that are shared by unrelated firms are kept as `business_id`. As a result, `business_id` is not unique across records: 1301932, 2101681, 2130557, and 6161088 each appear on two Black-owned firms. The 18 firms with placeholder IDs have an empty `business_id`.
- **Website clean-up.** Website values with no domain-like text are blanked, e.g. `http://no website`, `http://n/a`, a company name, a street address, or a list of NAICS codes. `http://www. x.com` is repaired to `http://www.x.com`.
- **naics_code.** A few commodity codes have only 5 digits (e.g. `23891`, `54133`, `49211`, which look like truncated 6-digit codes). They are passed through as given, not corrected.
- **Encoding.** The adapter decodes the file as UTF-8 if it can, and otherwise as Windows-1252. This file needs Windows-1252 because of `\x92` curly apostrophes.

## Anything that looked wrong or surprising

- The `.xls` file is not an Excel file. It is an HTML fragment containing a single `<table>` (B2Gnow export) with CRLF line endings, encoded in Windows-1252. Excel readers such as openpyxl and xlrd cannot open it.
- Supplier IDs are unreliable:
  - The placeholders `9999999`/`999999` cover 31 firms.
  - Unrelated firms share real-looking IDs.
  - Some IDs have trailing tab characters (`'1108179\t'`).
  - The formats are mixed: `P388400-01`, `Q003001`, `2023-28-037`, lowercase `p727100-01`.
- Some IDs look like typos of each other (`204998` vs `2004998` for Momentum Supply Services). That firm's AABE and SBE rows are split across the two IDs.
- Location values are malformed in places: `Norcross,, GA`, `Lithonia, GA, GA`. Two rows are in TX.
- The `Market Area` column is empty in every row, and `Agency` is always "Atlanta".
- 10 company names have stray leading, trailing, or doubled whitespace.
- The `DBA Name` field sometimes holds affiliate notes instead of a DBA, e.g. "(an affiliate of Keys Medical Staffing, LLC)". Company names sometimes do the same, e.g. "ZTZ LOGISTICS, LLC (an affiliate of Cipher 360, LLC)".
- The Website field often holds free text with `http://` in front, e.g. `http://we are delighted to introduce ourselves…`.
- Some firms appear twice with different locations and expiration dates under different IDs. For example, Graham Hauling shows Fayetteville with an expiration of 1/8/2026, and College Park with 2/11/2031.
