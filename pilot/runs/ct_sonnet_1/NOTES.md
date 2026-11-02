# NOTES

## Filter
- Field: `class_description_detailed`. Kept value: `Black American` (exact, case-insensitive). It is the only column naming a race/ethnicity group, and the source's wording for Black/African American.
- Considered and excluded: `race_gender_business_detailed` (only says "Race/ethnicity identified/unidentified", not which group); `certification_type` (MBE is not Black-specific); `woman_owned_business_detailed`; all other class values (Hispanic American, Asian Pacific American and Pacific Islander, Iberian Peninsula, American Indian, No minority race/ethnicity identified).
- 4 `Black American` rows have `certification_type` SBE; they are kept because the race field says Black American.

## Deduplication
- The file has one row per certification cycle x goods/services code, so the same firm repeats.
- Key: connected components over (a) vendorId parsed from `link_to_company_detail_page` and (b) normalized vendor name (lowercase, non-alphanumerics collapsed). Applied only to Black American rows.
- Rows read: 7,935 total; 1,001 Black American rows; 534 distinct vendorIds; 522 distinct names. Firms returned: 516.
- Merged record = the best row of the group (currently `Certified` first, then latest `active_date`). `source_fields` has `source_row_count` and `vendor_ids`.

## Field mapping
vendorname -> business_name; business_address1 -> address_street; townnamecrosswalk_standardized_town -> address_city; business_state -> address_state; zip -> address_zip (cleaned); certification_type -> certification; goods_and_services -> industry; gs_code -> naics_code; product -> description; `location` ("POINT (lon lat)") -> longitude/latitude; vendorId -> business_id; `last_verified` = run date; `data_source` = SOURCE_NAME. Everything else (class, status, dates, detail link, employees, etc.) stays in `source_fields`. Not populated: owner_name, year_founded, website, phone, email, socials (not in source).

## Record count
`Adapter(file_path="raw/ct_das_y4ub-e4dd_2026-10-15.csv").run()` returns **516** records (191 of them have status Expired as their best row; 325 Black rows were Certified at row level).

## Ambiguities and assumptions
- Expired firms are included: the task asks for firms the source identifies as Black-owned, not only currently certified ones. Filter on `source_fields["status"]` downstream if only active firms are wanted.
- A firm is included if ANY of its rows says Black American. Some firms (e.g. KraneWorks, C.C. Security, Hope Plumbing) have later rows classed "No minority race/ethnicity identified". The representative record is the best Black-classed row, not the latest row overall. This inclusion is an assumption.
- Name-merging could in principle merge two different firms with the same name; vendorId merging alone left 534 firms, and the extra merges (18 names with 2 vendorIds, same address) looked like duplicate IDs for one firm.
- Variant names under one vendorId (e.g. "Michael Davis" / "Michael Davis Trucking") are treated as one firm.
- `link_to_company_detail_page` is a state portal page, not a firm website, so not mapped to `website`.
- `gs_code` is assumed to be a NAICS code (6-digit values) though the source does not say so; it is empty for about half of the Black rows.
- ZIP cleanup: 9 digits -> ZIP+4 with hyphen; 4 digits -> leading zero added; trailing hyphen stripped; non-numeric ("CT") -> empty. Truncated "0660" values are left as-is.

## Anything that looked wrong or surprising
- Published count 7,935 is rows, not firms (3,736 distinct names).
- 1,244 rows have no detail link (no vendorId); none are Black American rows.
- `business_state` is blank on about half of rows (41 of the 516 returned records); `county` is "NA" on every row.
- The same firm often has two vendorIds with identical dates and address (e.g. MCM Acoustics, Division 5), and some vendorIds carry several names.
- Some `active_date` values are in the future or odd for "active" (2027, 2028 in the file overall); `active_year` 2026 rows exist although the file was downloaded 2026-10-15.
- Several firms changed address between expired and current rows; the best (current) row's address is used.
- Malformed ZIPs (`CT`, `0660`, `06605-`, 9 digits without hyphen) and 12 Black rows without a location.
