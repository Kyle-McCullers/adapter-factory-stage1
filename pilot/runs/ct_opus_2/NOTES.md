# NOTES — CT DAS Supplier Diversity adapter (data.ct.gov y4ub-e4dd)

## Filter

- Field: `class_description_detailed`. Value kept: exactly `Black American` (1,001 of 7,935 rows).
- Why: it is the only column in the file that records owner race/ethnicity. Its six values are `No minority race/ethnicity identified` (5,912), `Black American` (1,001), `Hispanic American` (622), `Asian Pacific American and Pacific Islander` (278), `Iberian Peninsula` (88), `American Indian` (34). `Black American` is the only one that means Black/African American-owned.
- Excluded: all other values. `certification_type = MBE` was not used as a signal (it covers every minority group, and many MBE rows say "No minority race/ethnicity identified"). `race_gender_business_detailed` only says whether race was "identified", not which race, so it was not used.
- Firm-level rule: a firm is kept if **any** of its rows says `Black American`. No firm has `Black American` on one row and a different minority group on another. Three firms have an older `Black American` row and a newer row that says `No minority race/ethnicity identified` (C.C. Security Corp., Hope Plumbing LLC, KraneWorks Inc. Crane Service). They are kept: I read that value as "not recorded", not as a contradiction.
- Expired certifications are kept. The task asks for every firm the source identifies as Black-owned, not only firms that are currently certified. Status is kept in `source_fields`.

## Deduplication

- The file has one row per certification period, not one per firm. Rows are grouped into firms with union-find over two keys:
  1. `vendorId`, taken from the `link_to_company_detail_page` URL and upper-cased (two IDs differ only by case).
  2. Normalized `vendorname` (upper-cased, with every non-alphanumeric character removed).
  Rows that share either key belong to the same firm.
- The name key is needed because many certifications appear twice with identical content and two different vendorIds (see below). Within the Black subset, all 35 firms that end up with more than one vendorId share a street address across those IDs. I found no case where a name match joined two firms at different addresses.
- Representative row: the firm's most recent `Black American` row by `active_date`. Blank fields on that row are filled from the firm's older `Black American` rows.
- Rows read: 7,935, matching the published total. `Black American` rows: 1,001, with 534 distinct vendorIds. **Firms returned: 516.**

## Field mapping

| Source column | Schema field |
|---|---|
| vendorname | business_name |
| business_address1 | address_street |
| townnamecrosswalk_standardized_town | address_city |
| business_state | address_state (when blank and the zip starts with `06`, set to `CT`) |
| zip | address_zip (cut to 5 digits; a 4-digit zip gets its leading 0 back; anything else becomes blank) |
| goods_and_services | industry |
| gs_code | naics_code |
| certification_type | certification |
| product | description |
| location (`POINT (lon lat)`) | longitude, latitude (parsed after mapping) |
| vendorId in link_to_company_detail_page | business_id (`ct_das:<vendorId>`) |

`last_verified` is today's date. `data_source` is `SOURCE_NAME`. Every other column goes into `source_fields`. I also added these to `source_fields`: `vendor_ids`, `source_row_count`, `black_row_count`, `firm_latest_status`, `firm_latest_expiration_date`, `firm_latest_class_description`. No owner name, phone, email, or website appears in the file, so those fields are blank.

## Record count

`Adapter(file_path="raw/ct_das_y4ub-e4dd_2026-10-15.csv").run()` returns **516** records. Of these, 328 are currently Certified and 188 are Expired, judged by each firm's latest row.

## Ambiguities and assumptions

- Expired firms are included, as described above. Filter on `source_fields["firm_latest_status"] == "Certified"` to get only active firms.
- When a firm has a Black-identified row and a later "No minority race/ethnicity identified" row, I treat it as Black-owned (3 firms).
- A vendorId is trusted as a firm identity even when the name changes across periods. Examples: "Aggie Cleaning Corporation" → "Aggie Service Corporation", "Michael Davis Trucking" → "Michael Davis", "MAGIC MOP CLEANING SERVICES" → "...SOLUTIONS LLC". One pair is less certain: "KINGDOM HOME CARE SOLUTIONS LLC" (2023) and "IMPACT CONSTRUCTION, LLC" (2025) share a vendorId and an address (2 Hillside St, West Haven). They are merged into one record named after the latest row.
- `gs_code` is mapped to `naics_code`. Most values are 6-digit NAICS codes, but some are truncated (2–5 digits, e.g. `2383`). They are passed through unchanged.
- PROGRAM is set to "MWBE". The source's own term is MBE/SBE, and that is kept in `certification`. GEOGRAPHY is set to "CT".
- `CONFIDENCE = "confirmed_black"`, because the state certifier records the race classification directly.

## Anything that looked wrong or surprising

- **Fan-out duplicates:** many certification rows appear two or three times, identical except for `vendorId`, often on adjacent lines (e.g. Division 5, LLC; SEET Consultants LLC; MCM Acoustics). This looks like a join artifact in the export.
- 1,244 rows (all Expired, 2020–2023, all "No minority race/ethnicity identified") have no detail link and therefore no vendorId.
- `county` is `NA` on every row. `business_state` is blank on 5,176 rows. Some rows marked `CT` have non-CT zips.
- `zip` is messy: 9-digit zips without a hyphen, trailing hyphens (`06479-`), 4-digit zips with the leading 0 dropped, 6-digit values (`060926`), `CT`, and fragments of other fields (`Ethnic Onl`, `225 Asylum`).
- 34 rows have an `active_date` after the 2026-10-15 download date, some as late as 2028. `active_year` includes 2027 and 2028.
- 4 `Black American` rows have `certification_type = SBE` rather than MBE.
- 1,001 Black rows collapse to only 516 firms. Most firms appear 2–4 times, once per certification period plus the fan-out duplicates.
- There is a test-looking record, "NAT TESTING 4.21" (Bronx zip 10457). It is not Black-identified and does not affect the output.
- `gs_code` and `goods_and_services` are blank on most older rows (5,211 rows overall). After back-filling, 31 returned firms still have no NAICS code. 5 have no coordinates.
