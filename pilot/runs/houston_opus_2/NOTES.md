# NOTES — City of Houston certified directory adapter

## Filter
- Field: `Ethnicity`. A firm is included if **any** of its rows has `Ethnicity` equal to `Black` or `Black American` (case-insensitive, after trimming).
- Why: those are the only values in the file that mean African American. `Black` appears on 5,505 rows (agency `Houston`). `Black American` appears on 22 rows, all from agency `Houston LGBT` (LGBTBE certifications). Most of those 22 firms also have `Black` rows under `Houston`.
- Values I looked at and left out: `Hispanic`, `Hispanic American`, `Caucasian`, `Asian`, `Native American`, `Other Ethnicity`. `Other Ethnicity` (465 rows) could include some Black-owned firms, but the source does not say so, so I did not count them.
- Certification type (MBE/SBE/WBE/...) is not used for filtering. Ethnicity is recorded on every row, including SBE and WBE rows.

## Deduplication
- The export has one row per firm **per certification**. For example, a firm certified MBE, SBE and WBE appears 3 times.
- Key: company name, lowercased, keeping only `[a-z0-9]` (so case, spaces and punctuation are ignored). `business_id` = `houston-` + the first 12 hex characters of the SHA-1 of that key.
- Merging: rows for each key are combined. `Agency`, `Certification Type`, `Ethnicity`, `Gender`, `HUB?`, `Re-Evaluation Status` and `Commodity Codes` keep every distinct value, joined with `; `. Other fields come from the first row flagged Black. If that value is empty, it is filled from the firm's other rows.
- Rows read in: **11,480** data rows. All of them are under one header; the banner and footer lines are skipped.
- All firms (every ethnicity): 5,177. Black-flagged rows: 5,527. **Black-owned firms returned: 2,210.**

## Field mapping
| Source column | Schema field |
|---|---|
| Company Name | business_name |
| Owner First + " " + Owner Last (built) | owner_name |
| Physical Address | address_street |
| City (1st occurrence, physical) | address_city |
| State (1st occurrence) | address_state |
| Zip (1st occurrence; leading tab removed) | address_zip |
| Phone | phone |
| Email | email |
| Website (a doubled `http://https://` prefix is collapsed) | website |
| Category | industry |
| Capability | description |
| Certification Type (all distinct values across the firm's rows) | certification |
| NAICS codes taken from Commodity Codes (`NNNNNN - text`; codes only, `; `-joined) | naics_code |
| — | data_source = SOURCE_NAME; last_verified = date the adapter runs (ISO) |

Everything else goes into `source_fields`: DBA Name, Owner First, Owner Last, Mailing Address, Mailing City, Mailing State, Mailing Zip (the second City/State/Zip columns are renamed), Fax, Agency, Ethnicity, Gender, HUB?, Re-Evaluation Status, full Commodity Codes text, and `Source Row Count`. The source has no columns for year_founded, lat/long, or social/Yelp/Maps, so those fields are left as `""`.

Class constants: SOURCE_ID `houston_obo_directory`, PROGRAM `MWBE`, GEOGRAPHY `Houston, TX`, CONFIDENCE `confirmed_black`.

## Record count
`Adapter(file_path="raw/houston_directory_2026-06-14.csv").run()` returns **2210** records. I ran it on 2026-10-16 and got 2,210 unique business_ids. All 8 tests in `test_adapter.py` pass.

## Ambiguities and assumptions
- **Firms whose rows disagree on ethnicity.** I include a firm if any row says Black. Two included firms have a non-Black value on another row:
  - `JR THOMAS GROUP, INC.`: the MBE row says Hispanic and the SBE row says Black.
  - `The Business Team LLC`: the Houston SBE/WBE rows say Caucasian and the Houston LGBT row says Black American.
  
  Both keep every value in `source_fields["Ethnicity"]` so downstream users can review them. Seven other firms have both `Black` and `Black American`, which is consistent.
- **CONFIDENCE = `confirmed_black`.** The source records ethnicity explicitly for each firm. I did not use the MBE flag as a stand-in for ethnicity.
- **Dedup by name only.** Every name group I checked had the same owner, with only small address or phone differences. Different firm names that share an email (e.g. `Bose Staffing, LLC` / `Bose Corporate Support, LLC`) stay as separate firms, because they are separately registered businesses.
- **Address/phone conflicts within a firm** (e.g. `SEBL SERVICE SUPPLIER INC.` with two street addresses): I keep the first Black-flagged row's value in file order. The other values are not kept.
- **`certification`** lists every certification the firm holds in this file, including the ones on non-Black rows.
- **GEOGRAPHY.** "Houston, TX" names the certifying jurisdiction. Some firms are located outside Houston, and a few outside Texas.
- **PROGRAM `MWBE`.** The directory mixes MBE, WBE, SBE, PDBE, LGBTBE, VOSB, SDVOSB and DBE certifications. MWBE was the closest of the allowed labels.
- **Encoding.** The file is Windows-1252, not UTF-8 (byte 0x92 = `’`). The adapter tries UTF-8 first and falls back to cp1252.

## Anything that looked wrong or surprising
- The file is CSV, not Excel, even though the button says "Download Results to Excel". It has 6 banner lines before the header and a "Generated from the B2Gnow System." footer.
- The header repeats `City`, `State`, `Zip` (physical, then mailing). Every row ends with a trailing comma, which creates an empty 26th column.
- Every Zip value starts with a tab character (probably to make Excel treat it as text). Some mailing fields look like typos, e.g. Mailing City `Houston texas 77033` with Mailing Zip `70333`.
- Some websites have a doubled scheme (`http://https://...`).
- The same certification sometimes appears twice for one firm (e.g. `Quick Protection Inc.` has 3 SBE rows), possibly different certification cycles.
- The `SBE*` / `WBE*` values (one firm, Caucasian) and 4 TXDOT DBE rows marked `Re-evaluated` are not explained anywhere. None of them affect the Black filter.
- Ethnicity labels differ by agency: `Black` / `Hispanic` for Houston, `Black American` / `Hispanic American` for Houston LGBT and TXDOT.
- Owner names are sometimes split oddly across columns, e.g. First=`Derric Pryor`, Last=`Hermie Thomas`, or `Merwyn Pinto/` + `Sharon Pinto`. They are kept as given.
- 4 rows have an empty Gender. 18 returned firms have no NAICS code.
