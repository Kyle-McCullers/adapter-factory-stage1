# City of Atlanta certified directory adapter

## Filter

- Field: `Certification Type`. Value kept: `AABE` (African American Business Enterprise). Matching ignores case and surrounding whitespace.
- Why: the file has exactly six certification values: `SBE` (1293 rows), `AABE` (867), `FBE` (554), `HABE` (108), `APABE` (61), `NABE` (5). AABE is the only one that identifies Black/African American ownership.
- Excluded: `SBE` (small business, says nothing about race), `FBE` (female-owned), `HABE` (Hispanic American), `APABE` (Asian/Pacific American), `NABE` (Native American). A firm that also holds one of these is still included if it holds AABE. Its full list of certifications goes into `certification`, e.g. `AABE; FBE; SBE`.
- The filter applies to firms, not rows. Rows are first grouped into firms (see Deduplication), and a firm qualifies if any of its rows is AABE.

## Deduplication

- The file has one row per (firm, certification type) pair, so a firm with AABE+FBE+SBE appears 3 times.
- Key: rows are grouped with union-find. Two rows are the same firm if they share (a) a normalized company name (lowercased, non-alphanumerics collapsed to a single space), or (b) the same email **and** the same owner first+last name.
- `Supplier ID#` is **not** used as the key. It contains placeholders (`9999999` and `999999`, shared by 19 AABE firms) and reuses real IDs across unrelated firms (`1301932`, `2101681`, `2130557`, `6161088`, among others).
- Representative row: within a firm, the AABE row with the latest `Expiration`.
- Rows read: 2888 (all certifications). That gives 1320 firms in total. AABE rows: 867. **Black-owned firms returned: 864.**
- The 3 merges among AABE firms:
  - GRAHAM HAULING, INC.: IDs 2100436 and 1206435, same owner and email, different city.
  - Knight & Associates, Inc.: IDs P980200-01 and 98020001.
  - "Anointed Professional Enterprise" (ID 9999999, expired 2024) and "Anointed Professional Enterprises Inc dba Glory Professional Cleaning" (ID 1906722): same owner and email.
- One more merge doesn't change the count. The firm GREEN DIAMOND WASTE MANAGEMENT LLC (AABE) absorbed an old SBE-only row under the name "Green Diamond Waste Management" (ID 9999999).
- Other IDs and names that were merged away are kept in `source_fields["Other Supplier IDs"]` and `["Other Company Names"]`. `source_fields["Source Row Count"]` gives the number of raw rows in the firm.

## Field mapping

| Source column | Schema field |
|---|---|
| `Supplier ID#` (whitespace stripped) | `business_id`. If the ID is a placeholder (all 9s) or is used by more than one firm: `<id>:<name-slug>` |
| `Company Name` | `business_name` |
| `Owner First` + `Owner Last` | `owner_name` |
| `Location` ("City, ST"), split on the last comma | `address_city`, `address_state` |
| `Capability` | `industry` |
| `Commodity Codes`: 6-digit codes extracted, de-duplicated, joined with `; ` | `naics_code` |
| all `Certification Type` values for the firm | `certification` |
| `Website` | `website` |
| `Phone` | `phone` |
| `Email` | `email` |

- Everything else goes into `source_fields`: `DBA Name`, `Fax`, `Agency`, `Expiration`, `Market Area`, the raw `Location`/`Owner First`/`Owner Last`/`Commodity Codes`/`Supplier ID#`, plus the merge columns above.
- `data_source` = SOURCE_NAME. `last_verified` = date of the run (ISO).
- Not available in the source, left `""`: street, zip, lat/long, year founded, description, social/maps fields.
- Class constants:
  - `PROGRAM = "MWBE"`
  - `GEOGRAPHY = "Atlanta"`
  - `CONFIDENCE = "confirmed_black"`

## Record count

`Adapter(file_path="raw/atlanta_directory_2026-06-14.xls").run()` returns **864** records (run 2026-10-16). All 13 tests in `test_adapter.py` pass.

## Ambiguities and assumptions

- I read AABE as "African American Business Enterprise". The file has no legend, but this is the City of Atlanta's standard designation, and it fits the pattern of the other codes (HABE, APABE, NABE).
- **Expired certifications are included.** 42 of the 864 firms have an `Expiration` earlier than the download date (2026-06-14), most in 2024. The portal still lists them, so they count as "identified by the source". Filter on `source_fields["Expiration"]` if you only want current certifications.
- `PROGRAM`: Atlanta's program is the Equal Business Opportunity / certified business enterprise program. None of the allowed values fits exactly, and "MWBE" is the closest.
- Dedup by email+owner could in principle merge two separate firms run by the same person with the same email. In this file it only fired for clear name variants of the same firm.
- When firms were merged, the contact and location data come from the most recently expiring AABE row. The older values are not kept, apart from IDs and names.
- City casing is kept as given (`ATLANTA` vs `Atlanta`); it is not normalized.
- `business_id` is unique across all 864 records, but for 28 firms it is synthesized (`<id>:<slug>`) because their Supplier ID is a placeholder or shared.

## Anything that looked wrong or surprising

- The `.xls` file is not a spreadsheet. It's an HTML fragment (header text plus a `<table>`) with CRLF line endings, so openpyxl/xlrd can't read it. The adapter parses it with the standard library `html.parser`.
- Some `Supplier ID#` values have a trailing tab (`2006678\t`, `1108179\t`, …).
- ID formats are mixed: numeric, `P980200-01`, `p727100-01` (lower case), `Q003001`, `2023-28-037`.
- Placeholder IDs `9999999` and `999999` are attached to many unrelated firms. Several real-looking IDs are shared by two unrelated firms, e.g. `1301932` = Acsential Group Inc and American Property Restoration, Inc.
- The same firm appears under two different IDs (Graham Hauling, Knight & Associates).
- One location reads `Lithonia, GA, GA`; the adapter drops the repeated state.
- `Market Area` is empty on every row, and `Agency` is always "Atlanta".
- Knight & Associates' website is malformed (`http://www,.knightsnassociatesinc.com`). It is left as-is.
- Some `DBA Name` values are not DBAs, e.g. `(an affiliate of Keys Medical Staffing, LLC)`. Some company names embed the DBA, e.g. `... dba Preston CPA, P.C.`.
- The file includes certifications that expired in 2024, even though it was downloaded in 2026.
