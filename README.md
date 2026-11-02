# Adapter factory and verification protocol for agent-built administrative datasets

Research artifact accompanying a Stage 1 proposal to the Organization Science special issue "AI-Enabled Frontiers in Organizational Science." This snapshot is anonymized for double-blind review: a single commit with a neutral author, project-management files removed, and personal paths replaced with placeholders.

## What this is

A pipeline in which AI agents, working under test-driven development, convert public certification directories into a national, firm-level, quarterly panel of businesses certified as Black-owned by a government body. The proposal's argument is that agreement between independent agent reconstructions of such a dataset measures reliability, not validity, and that validity has to be designed in from outside the file. The code here is the instrument; the verification protocol and trap catalog (`docs/`) are the contribution.

Current release (October 2026): 24 adapters covering 23 certification programs in 20 states and the District of Columbia; 36,474 listings resolved to 33,577 firms, of which 33,387 are currently certified.

## Layout

```
scripts/adapters/        one adapter per source (subclasses of AdapterBase)
scripts/pipeline/        adapter_base, b2gnow_base (platform family), entity_resolver,
                         firms, geocoder, db, export, run (orchestrator)
scripts/test_pipeline.py test suite (204 tests in this snapshot)
data/                    businesses.csv and .parquet (one row per firm), codebook.csv,
                         sources.csv, meta.json, snapshots/, review/
docs/                    codebook, data-sources catalog, verification protocol,
                         trap catalog, rebuild-pilot report
pilot/                   independent-reconstruction pilot: instruction, provenance notes,
                         raw files with hashes, nine adapters with tests and notes, logs
.github/workflows/       quarterly scheduled run
```

## How to check the work in under an hour

Requirements: Python 3.12 and `pip install duckdb openpyxl rapidfuzz requests pytest`.

1. Run the test suite: `python -m pytest -q scripts/test_pipeline.py`. Expect 204 passing.
2. Read one adapter's docstring for the distinct identity values it observed and the published total it reconciled against, then read the tests that encode those facts, for example `scripts/adapters/ct_das_smbe.py` and the matching tests in `scripts/test_pipeline.py`.
3. Run the orchestrator in a clean checkout: `python -m pipeline.run --snapshot-id test`. The four auto-fetch sources run without credentials or local files; the manual-capture sources are retained from the prior release and flagged in the summary, which is the retention behavior the proposal describes.
4. Open `docs/trap-catalog.md` and find the protocol step and test that guard each trap.
5. Open `pilot/` and re-score firm-set agreement from the nine archived adapters.

## What is and is not reproducible from this repository

- Reproducible: all code, all tests, the public firm-level data, the codebook, and the pilot (instruction, provenance notes, every adapter, every test, every transcript, and the raw files). In the public copies of two raw exports (Houston, Atlanta) the owner-name, phone, fax, and email cells are blank; structure, encoding, and every other cell are unchanged, so the archived adapters return the same firm sets. Hashes of the unredacted originals are in `pilot/materials/raw/SHA256SUMS.txt`; see `REDACTION.md` there.
- Not yet reproducible: the raw manual-capture exports for 19 of 24 sources, which the pipeline reads from the maintainer's machine. Adapter tests run against synthetic fixtures that mimic each export's format. Committing redacted raw exports with hashes is planned before the February workshop.

## What differs from the working repository

This snapshot is the working repository at tag `orgsci-stage1` with project-management files removed, personal paths and names replaced with placeholders, one module belonging to a separate study removed (with its four tests), and three reserved, empty columns dropped from the public data files. The pipeline code is otherwise unchanged.

## Data and license

Public columns exclude owner names, phones, and emails, which are released to researchers on request. Data: CC BY 4.0 (`LICENSE-DATA`). Code: MIT (`LICENSE`). Each certification record is a public government record of a firm that sought certification; the identity attribute is the government's certification, not a classification by the author or a model. Absence of a firm from a later snapshot is not evidence of exit; see the codebook's `last_verified` and `certification_status` fields.

## Contact

Through the journal's editorial office during review.
