# NOTES — CT DAS Supplier Diversity directory (data.ct.gov `y4ub-e4dd`)

File: `raw/ct_das_y4ub-e4dd_2026-10-15.csv` (SHA-256 matches SOURCE.md; 7,935 data rows, matching the published row count).

## Filter

- Field: `class_description_detailed`. Value treated as Black-owned: exactly `Black American` (1,001 rows).
- Why: this is the only column that records the owner's race/ethnicity. Its values are `Black American`, `Hispanic American`, `Asian Pacific American and Pacific Islander`, `Iberian Peninsula`, `American Indian`, and `No minority race/ethnicity identified`. Only `Black American` refers to Black/African American ownership.
- Excluded: every other value of that column. `certification_type = MBE` is not used. CT's MBE covers women-owned and other minority firms, and 2,407 MBE rows say "No minority race/ethnicity identified". `race_gender_business_detailed` only says whether race was "identified", not which race, so it was not used either. `woman_owned_business_detailed` and `disability_status_detailed` are unrelated to race.
- A firm is included if **any** of its rows is `Black American`. Status is not filtered, so firms whose certifications are all expired are kept (see Ambiguities).
- 997 of the 1,001 Black American rows are MBE and 4 are SBE.

## Deduplication

- The file has one row per certification event, not one per firm. A firm shows up once per certification period (2020–2026) and sometimes twice for the same period under two different vendorIds.
- Key: rows are grouped with union-find. Two rows belong to the same firm if they share either (a) the `vendorId` in `link_to_company_detail_page`, or (b) the normalized `vendorname` (uppercased, keeping letters and digits only). Groups are transitive. Using vendorId alone would have split 18 Black firms in two, because the same name, address, and date appear under two IDs. Using name alone would have missed renames that share a vendorId, such as Aggie Cleaning → Aggie Service Corp and Michael Davis Trucking → Michael Davis.
- Representative row: the firm's row with the latest `active_date`. On a tie, a row with a NAICS code wins, then a Black American row. This row provides the name, address, and other fields, so each record shows the most recent information.
- `business_id` = `ct_das_y4ub-e4dd:<vendorId of the representative row>`.
- Rows read in: 7,935. Rows belonging to Black-owned firms: 1,038. Firms returned: **516**.

## Field mapping

| Source column | Schema field |
|---|---|
| `vendorname` | `business_name` |
| `business_address1` | `address_street` |
| `townnamecrosswalk_standardized_town` | `address_city` |
| `business_state` | `address_state` |
| `zip` | `address_zip` (cut to 5 digits; a 4-digit ZIP gets its leading 0 back; anything else becomes blank) |
| `certification_type` | `certification` |
| `gs_code` | `naics_code` |
| `goods_and_services` | `industry` |
| `product` | `description` |
| `location` (`POINT (lon lat)`) | `latitude`, `longitude` |
| vendorId parsed from `link_to_company_detail_page` | `business_id` |

- Every other column goes into `source_fields` through `map_record()`. That includes status, dates, the class fields, `link_to_company_detail_page`, and `location`.
- The adapter adds these keys to `source_fields`: `zip_raw`, `vendor_ids`, `source_row_count`, `black_american_row_count`, `black_american_active_dates`, `names_seen`.
- The file has no data for `owner_name`, `year_founded`, `website`, `phone`, `email`, or the social/maps fields. They are left blank.
- `data_source` = SOURCE_NAME. `last_verified` = the run date (ISO).

## Record count

`Adapter(file_path="raw/ct_das_y4ub-e4dd_2026-10-15.csv").run()` returns **516** records. Run on 2026-10-16. Of these, 328 have a currently `Certified` representative row and 188 are `Expired`. All 16 tests pass.

## Ambiguities and assumptions

- **Expired firms are included.** The dataset is called a "certified directory", but 5,903 of its 7,935 rows are `Expired`. The source still identifies those firms as Black-owned, so they are kept. `source_fields.status` is there for anyone who wants only current certifications. Doing that gives 328 firms.
- **Inconsistent classification over time.** 8 firms have both `Black American` rows and `No minority race/ethnicity identified` rows. All are included. For 3 of them (C.C. Security Corp., Hope Plumbing LLC, KraneWorks Inc. Crane Service), the latest row says "No minority", so their record's `source_fields.class_description_detailed` is not `Black American`. The `black_american_*` fields show the evidence.
- **Two names under one vendorId** are treated as one firm (a rename). Example: IMPACT CONSTRUCTION, LLC (2025) and KINGDOM HOME CARE SOLUTIONS LLC (2023) share a vendorId and an address, and both do home remodeling. They could instead be two businesses run by one owner.
- **Same name means same firm**, even when the address or town changed. Examples: MKR LLC (Danbury → East Hartford) and ProShield Glass Tinting (New Britain → Southington). This relies on CT business names being unique, but the names in this file are not verified against the registry.
- `PROGRAM = "MWBE"`, the closest of the base-class options. CT calls it MBE/SBE.
- `CONFIDENCE = "confirmed_black"`, because the race is stated explicitly by the certifying agency.
- `gs_code` is mapped to `naics_code` because its values look like 6-digit NAICS codes and the descriptions match NAICS titles. The file does not call them NAICS.
- `business_state` is left as given and is not filled in. It is blank for every row before 2023, and some coordinates fall outside CT (as far as about 42.36 N, -71.1 W, near Boston), so assuming "CT" could be wrong. 15 records have a blank state.

## Anything that looked wrong or surprising

- `county` is `NA` in every row.
- `business_state` is blank on all 2020–2022 rows and on most 2023 rows (5,176 rows in total).
- `gs_code` / `goods_and_services` are blank for almost every row before 2024. Some codes are 2–5 digits rather than 6.
- `zip` has messy values: ZIP+4, trailing hyphens (`06479-`), 6 digits (`060926`), the literal `CT`, and blanks (24 rows).
- 32 rows have an `active_date` after the 2026-10-15 download date, up to `2028-06-23` (A & B CARTING LLC), with expirations up to 2030. Two of these are Black American firms (DH Bolton, Inc.; C A Howard Consultants LLC). They look like data-entry or pre-dated renewals.
- The same firm often appears twice for the same certification date with two different vendorIds. Usually only one of the pair has a `gs_code`.
- 1,244 rows have an empty `link_to_company_detail_page`, so they have no vendorId. None of them are Black American rows.
- 99 rows have an empty `location`. 6 of the returned records have no coordinates.
- Names are not standardized: `Purposeful Cleaning LLC` vs `llc`, `AmorhomesLLC`, `J mellington fire protection llc.co`. Some earlier rows put only a street number (`381`) in `business_address1`.
