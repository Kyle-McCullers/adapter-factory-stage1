# Notes: City of Atlanta certified directory adapter

## Filter
- Field: `Certification Type`. Value treated as Black-owned: `AABE` (African American Business Enterprise). The source names no other Black-owned category.
- Other values in the file, excluded: `SBE` (1293 rows, small business, no ethnicity), `FBE` (554, female), `HABE` (108, Hispanic), `APABE` (61, Asian Pacific American), `NABE` (5, Native American). The expansions are my reading of the codes; the file has no legend.
- A firm holding both AABE and another code is kept via its AABE row. The other rows are dropped, so those other certifications are not recorded.

## Deduplication
- Key: normalized company name (lowercase, punctuation/whitespace collapsed) + lowercase email. When a key repeats, the row with the latest `Expiration` is kept.
- Rows read: 2888 total, 867 AABE. Firms returned: 865.
- The two merged firms are Graham Hauling, Inc. and Knight & Associates, Inc. Each appears twice with different Supplier IDs and expiration dates, apparently an old and a renewed certification.
- `Supplier ID#` is not used as a key. See below.

## Field mapping
- Company Name -> business_name
- Owner First + Owner Last -> owner_name (joined with a space)
- Location ("City, ST") -> address_city, address_state
- Phone -> phone; Email -> email; Website -> website
- Certification Type -> certification
- Capability -> description
- Commodity Codes -> industry (NAICS code plus text, kept as given; `naics_code` is left empty because rows hold several codes)
- Everything else (DBA Name, Fax, Agency, Expiration, Market Area, Supplier ID#) -> `source_fields`
- `business_id` is left empty. `last_verified` is the run date (2026-10-16). Constants: PROGRAM=MWBE, GEOGRAPHY="Atlanta, GA", CONFIDENCE=confirmed_black.

## Record count
865. This is `Adapter(file_path="raw/atlanta_directory_2026-06-14.xls").run()` on the real file. 2888 rows were read; 867 were AABE.

## Ambiguities and assumptions
- Meaning of AABE: assumed to be African American-owned from the code name, since the file has no legend. SOURCE.md says nothing on this.
- One record per firm, not per certification: the file has one row per firm per certification type.
- Expired certifications are kept. Many AABE rows have an `Expiration` before the 2026-06-14 download date (all of 2024 and 2025, and part of 2026). The directory still lists them, and the source does not say whether they count as certified. The expiration is kept in `source_fields` so a consumer can filter.
- The "xls" file is really an HTML table, so it is parsed with the standard-library HTML parser, not openpyxl or pandas.
- Location has only city and state. There is no street or ZIP.
- Dedup assumes that the same name plus the same email means the same firm.

## Anything that looked wrong or surprising
- The file is HTML with an .xls extension. It has a banner above the table and a footer ("Generated from the B2Gnow System"). The SHA-256 matches SOURCE.md.
- `Supplier ID#` is unreliable. Placeholders such as `9999999` (15 distinct AABE firms), `999999` and `1301932` are shared by unrelated firms. Several ID formats are used (for example `P980200-01` and `98020001` for the same firm). Keying on it would have wrongly merged firms.
- `Market Area` is empty on every row. `Agency` is "Atlanta" on every row.
- Data quality is uneven: inconsistent casing (`RUDOLPH HINES`), malformed websites (`http://https://www.drcontracting.co/`, `http://under construction`), and `Capability` text that is sometimes just a NAICS sector title or contains stray `; ;`.
- Some owner names are odd, such as the last name "V. Quarterman".
