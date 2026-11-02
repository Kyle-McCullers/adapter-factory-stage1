# NOTES — City of Houston certified directory adapter

## Filter

- Field: `Ethnicity`. Kept values (case-insensitive, whitespace-trimmed): `Black` and `Black American`.
- `Black` (5,505 rows) is the value the City of Houston programs (Agency = `Houston`) use. `Black American` (22 rows) appears only on Agency = `Houston LGBT` / `LGBTBE` rows. Both mean the owner is African American.
- Values seen and left out: `Hispanic` (2,949), `Caucasian` (1,276), `Asian` (1,171), `Other Ethnicity` (465), `Native American` (76), `Hispanic American` (16). None of them means Black. I left out `Other Ethnicity` because the file gives no detail on it.
- I did not filter on `Certification Type`. The ethnicity field is set on every row whatever the certification, including race-neutral SBE rows. So a firm counts if any of its rows says Black. CONFIDENCE = `confirmed_black`.

## Deduplication

- The export has one row per firm per certification type (MBE / SBE / WBE / PDBE / LGBTBE …). There is no firm ID column.
- Key: `Company Name`, case-folded with whitespace collapsed (tabs and double spaces included). I checked looser normalisation (stripping punctuation and LLC/Inc suffixes) and it merged nothing more. Every same-name group has the same owner.
- Merging: the first row supplies the values, and blanks are filled from later rows. Agency, Certification Type, Ethnicity, Gender, HUB?, Re-Evaluation Status, Category and Commodity Codes become the distinct values joined with `; `. All distinct phones and physical addresses are kept in `source_fields`, as is `Source Row Count`.
- Rows read: 11,480 data rows. 5,527 of them match the filter. Firms returned: 2,210.

## Field mapping

| Source column | Schema field |
|---|---|
| (sha1 of the dedup key, `houston-` + 12 hex) | business_id |
| Company Name | business_name |
| Owner First + " " + Owner Last | owner_name |
| Physical Address | address_street |
| City (1st) | address_city |
| State (1st) | address_state |
| Zip (1st, leading tab stripped) | address_zip |
| Category | industry |
| 6-digit codes parsed from Commodity Codes | naics_code (`; `-joined) |
| Certification Type (merged across rows) | certification |
| Capability | description |
| Website (doubled `http://https://` fixed) | website |
| Phone | phone |
| Email | email |

Everything else goes to `source_fields`: DBA Name, Mailing Address, Mailing City/State/Zip (renamed from the duplicate `City`/`State`/`Zip` headers), Fax, Agency, Ethnicity, Gender, HUB?, Re-Evaluation Status, Commodity Codes, All Phones, All Physical Addresses, Source Row Count. `last_verified` is set to the date of the run (2026-10-16 today). `data_source` is set to SOURCE_NAME.

## Record count

`Adapter(file_path="raw/houston_directory_2026-06-14.csv").run()` returns **2210** records. I ran it on 2026-10-16.

## Ambiguities and assumptions

- **No firm ID.** The dedup key is the company name. Two different firms with the same name would be merged, but no such case appears among the Black firms: every same-name group has the same owner. `business_id` is a hash I generated, not a source identifier.
- **Mixed ethnicity within a firm.** Two kept firms have conflicting rows:
  - `The Business Team LLC`: `Caucasian` on its Houston SBE/WBE rows, `Black American` on its LGBTBE row.
  - `JR THOMAS GROUP, INC.`: `Hispanic` on MBE, `Black` on SBE.
  
  I kept both because the source identifies each as Black on at least one row. Only the Black rows are merged into the record, so `certification` shows only those rows' certifications.
- **Conflicting values within a firm.** Some firms have different addresses or phones on different rows, for example D.C. Garrett Group, Houston Kaco, Rapid Labs, SEBL Service Supplier, Table SALT Group, and Your Mind Your Gym. The primary fields take the first row's value. All variants are kept in `source_fields`.
- **PROGRAM.** I set this to `MWBE` because the directory spans MBE/WBE/SBE/PDBE/LGBTBE/DBE. GEOGRAPHY is `Houston, TX`; some firms have out-of-state addresses (NJ, CA, IL …).
- **Encoding.** The file is Windows-1252 and is decoded as such. The adapter tries UTF-8 first.
- **Commodity codes.** They usually appear on only one of a firm's rows (often the WBE row). They are merged across rows. 24 firms have no NAICS code at all.

## Anything that looked wrong or surprising

- The file is a "Download to Excel" CSV with a 6-line preamble (title, timestamp, a usage disclaimer) before the header, and a footer line `Generated from the B2Gnow System.`
- The header repeats `City`, `State`, `Zip` (physical and mailing). Every row also ends with a trailing comma, which creates an empty 26th column.
- Every Zip value has a leading tab character (an Excel text-forcing trick). One mailing record has `Houston texas 77033` in the City field and `70333` as the zip.
- Websites with a doubled scheme, e.g. `http://https://1bodymedspa.com/`.
- 20 of the Black-matched rows are exact duplicate rows (same firm and same certification twice), e.g. `Table SALT Group` SBE.
- Some owner and company fields contain embedded tabs or extra spaces (e.g. `Latisa \t`, `Owner Name III, Inc\t`). Some owner fields hold two people (`Derric Pryor` / `Hermie Thomas`, `Merwyn Pinto/` / `Sharon Pinto`).
- The same LGBT firms are labelled `Black American` by the LGBT program but `Black` by the City programs.
- 31 Black firms hold only an SBE certification, which is race-neutral, yet their Ethnicity is still recorded.
- Small oddities elsewhere in the file: `SBE*` / `WBE*` certification types on one Caucasian firm, and 4 TXDOT DBE rows with Re-Evaluation Status `Re-evaluated`.
