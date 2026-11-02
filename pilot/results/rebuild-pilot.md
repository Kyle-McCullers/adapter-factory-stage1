# Independent-rebuild pilot: results

Run 2026-10-16. Nine headless agent sessions rebuilt adapters for three government business directories from the same raw files, with no access to the existing adapters or tests. This note records the design as executed, every number, and how each difference was attributed. Results are reported in full whether or not they favor the proposal's thesis.

## Design as executed

**Sources.** Three raw files already in hand, chosen to span three capture formats.

| Source | File | Format trap | Rows |
|---|---|---|---|
| Houston (city certified directory, platform tenant) | `houston_directory_2026-06-14.csv` | six-line preamble before the header, duplicated City/State/Zip columns, leading tabs in zip codes, Windows-1252 bytes, one row per firm per certification | 11,480 data rows |
| Atlanta (city certified directory, platform tenant) | `atlanta_directory_2026-06-14.xls` | an HTML table delivered with a `.xls` extension, no ethnicity column (Black ownership encoded as certification type AABE), single "City, ST" location field, unreliable supplier IDs | 2,888 data rows |
| Connecticut (state supplier-diversity dataset, open-data API) | `ct_das_y4ub-e4dd_2026-10-15.csv` | one row per certification period and product code, 74 percent of rows expired, two vendor IDs for the same firm, renames under one ID | 7,935 data rows |

SHA-256 of each file is in `materials/raw/SHA256SUMS.txt`.

**What each agent received.** The raw file; a one-page provenance note (publisher, portal, how a person obtained the file, capture date, hash, and what totals the publisher does or does not report); the adapter contract (`adapter_base.py`, 59 lines); and one shared instruction asking for an `Adapter` class, a test file, and a `NOTES.md` with fixed headings: filter, deduplication, field mapping, record count, ambiguities, surprises. Agents did not receive the platform-family base class, because it encodes the solutions to the parsing traps; the proposal's appendix had said "contract and base classes," and this is a deliberate narrowing recorded here. Web tools were disabled. Each run was a fresh session in its own directory outside any project that carries instructions, with user-level settings and plugins excluded.

**Runs.** Per source: Opus 5.5, Sonnet 5.5, Opus 5.5 again, giving one same-model replicate and one cross-model comparison. Model identifiers as billed: `claude-opus-5-5`, `claude-sonnet-5-5`. Harness: Claude Code 2.1.300 in headless mode, cap of 100 turns and $15 per run, API billing with per-run usage recorded from the session's own result record.

**Reference.** The incumbent adapters from the June 2026 build, run on the same files. The incumbent is a human-supervised build, not ground truth; it is one more build to compare against.

## Cost and time

| Run | Model | Turns | Seconds | Output tokens | Cost (USD) |
|---|---|---|---|---|---|
| houston_opus_1 | Opus 5.5 | 12 | 115 | 12,640 | 0.49 |
| houston_sonnet_1 | Sonnet 5.5 | 10 | 60 | 7,968 | 0.15 |
| houston_opus_2 | Opus 5.5 | 11 | 122 | 12,132 | 0.47 |
| atlanta_opus_1 | Opus 5.5 | 16 | 158 | 16,061 | 0.59 |
| atlanta_sonnet_1 | Sonnet 5.5 | 10 | 58 | 7,252 | 0.16 |
| atlanta_opus_2 | Opus 5.5 | 16 | 160 | 17,769 | 0.70 |
| ct_opus_1 | Opus 5.5 | 17 | 161 | 17,919 | 0.73 |
| ct_sonnet_1 | Sonnet 5.5 | 9 | 63 | 8,483 | 0.18 |
| ct_opus_2 | Opus 5.5 | 18 | 155 | 16,905 | 0.75 |
| **Total** | | | **1,052** | | **4.21** |

Input tokens per run were 220,000 to 690,000, almost all served from cache. The budget options priced the pilot at $50 to $100; the realized cost was $4.21.

## Deliverables

All nine runs produced all three deliverables. All nine test files pass under pytest (3 to 17 tests each). All nine adapters run on the full raw file without error.

## Firm-set agreement

Agreement is measured on the set of normalized firm names each adapter returns, after removing differences that come only from text decoding or whitespace.

| Source | Run | Firms | Pairwise agreement with other runs (Jaccard) | Incumbent | Agreement with incumbent |
|---|---|---|---|---|---|
| Houston | opus_1 | 2,210 | 1.000, 1.000 | 2,224 records, 2,210 names | 1.000 |
| Houston | sonnet_1 | 2,210 | 1.000, 1.000 | | 1.000 |
| Houston | opus_2 | 2,210 | 1.000, 1.000 | | 1.000 |
| Atlanta | opus_1 | 864 | 1.000, 0.999 | 866 records, 865 names | 0.999 |
| Atlanta | sonnet_1 | 865 | 0.999, 0.999 | | 1.000 |
| Atlanta | opus_2 | 864 | 1.000, 0.999 | | 0.999 |
| Connecticut | opus_1 | 516 | 1.000, 1.000 | 1,001 records, 521 names | 0.990 |
| Connecticut | sonnet_1 | 516 | 1.000, 1.000 | | 0.990 |
| Connecticut | opus_2 | 516 | 1.000, 1.000 | | 0.990 |

## Identity filter

Nine of nine runs chose exactly the labels the incumbent uses: Houston, Ethnicity in {Black, Black American}; Atlanta, Certification Type = AABE; Connecticut, class_description_detailed = Black American. Nine of nine listed every excluded value with its row count. Nine of nine set CONFIDENCE to confirmed_black. All nine declined to filter on certification type (MBE versus SBE), reasoning that the ethnicity field is populated on race-neutral certifications too. No run treated "Other Ethnicity" (Houston, 465 rows) as Black-owned.

## Where the builds differed

**Deduplication keys.** Six distinct keys across nine runs: company name only (whitespace-collapsed); company name only (alphanumerics); name plus owner; name plus email; union-find over name or (owner and email); union-find over vendor ID or name. The keys converged on the same firm sets because the files contain few collisions. The one within-pilot difference, Atlanta 864 versus 865, is a single merge: two Opus runs joined "Anointed Professional Enterprise" (placeholder supplier ID, expired 2024) with "Anointed Professional Enterprises Inc dba Glory Professional Cleaning" on matching owner and email; the Sonnet run kept them apart.

**Against the incumbent.** Houston: the incumbent deduplicates on name plus physical address and returns 2,224; all nine-run builds deduplicate on name and return 2,210; the 14 extra incumbent records are 14 firms listed at two addresses. Atlanta: the incumbent keys on name plus location and keeps Graham Hauling twice (two cities, same owner). Connecticut: all three builds merged five firms the incumbent counts twice because the directory renamed them under one vendor ID (Aggie Cleaning Corporation to Aggie Service Corp; Michael Davis Trucking to Michael Davis; Kingdom Home Care Solutions sharing an ID and address with Impact Construction; Magic Mop Cleaning Services; Ruspini Realty).

**Expired certifications (Connecticut).** The dataset's status column marks 5,903 of 7,935 rows Expired. The incumbent adapter never reads it and does not deduplicate, so it returns 1,001 records of which 676 are expired and many are repeats. All three pilot builds noticed the field, made an explicit choice to keep expired firms because the instruction asked for every firm the source identifies as Black-owned, documented the choice under Ambiguities, and reported the active count alongside (328, 328, and 325 at row level). The incumbent's silence on this field is a defect found by the pilot, logged for repair.

**Text decoding.** All nine builds decoded the Houston file as Windows-1252. The incumbent decodes it as Latin-1, which turns curly apostrophes into control characters in 14 firm names. A second incumbent defect, minor, logged for repair.

**Representation.** Field maps differed where the schema gave room: Atlanta "Capability" went to industry in one run and description in two; NAICS codes were parsed from commodity-code text in six runs and left as raw text in two and unmapped in one; one Atlanta run dropped a firm's non-AABE certifications, the other eight kept them; three runs set no business_id; SOURCE_ID strings differed across all nine. GEOGRAPHY was "Atlanta" or "Atlanta, GA", "CT", "Houston, TX". All nine set PROGRAM to MWBE. These differences do not change who is in the dataset; they change how the dataset describes them, and they are what a downstream merge would trip on.

**Source contradictions surfaced by the agents.** Houston: two firms carry different ethnicities on different certification rows (one Hispanic on its MBE row and Black on its SBE row; one Caucasian on two rows and Black American on a third); all nine builds included both and documented them. Connecticut: eight firms have both Black American and "No minority race/ethnicity identified" rows across years. Atlanta: supplier IDs include placeholders (9999999 shared by 27 firms) and real IDs reused across unrelated firms, so the only identifier the portal publishes cannot serve as a key. None of these is recorded in the incumbent build's documentation.

## Reading the result

The pilot's main result is high agreement among machine builds on the firm set: identical for two sources, one firm apart for the third. The risk named in the proposal, that agreement would be high, materialized. Three things survive it. First, nine builds at $4.21 found two defects in a human-supervised build that had passed its tests for four months, which makes independent rebuild a cheap audit even where it finds no disagreement among machines. Second, disagreement concentrated in entity resolution and representation, not in the identity filter, which points the trap-detection benchmark at deduplication and schema choices rather than label matching. Third, where the source was ambiguous, the builds disagreed with the incumbent by documenting a choice the incumbent made silently; the value was in the documentation, not the decision.

The pilot's boundary is its starting point. Agents received a captured file, so the capture-stage traps in the catalog (filters honored in the browser and ignored in the export, truncation outside a session, documentation that diverges from data) were outside the experiment by construction. Those are where the worst catalog entries live. The full experiment must start one step earlier, at the portal, which is also where the published totals exist to reconcile against.

## Reproducibility

Everything needed to rerun the pilot is in `/Users/Shared/orgsci-rebuild-pilot`: `materials/` (raw files with hashes, instruction, provenance notes, contract), `harness/run_one.sh` (one run), `harness/evaluate.py` and `harness/summarize.py` (analysis), `runs/<run>/` (each sandbox with adapter, tests, notes, and the session's result record), `logs/<run>.jsonl` (full event log of every tool call), `results/reference/` (incumbent outputs), `results/runs.json` (evaluation). Before any of this is released, the logs must be scrubbed: they contain local paths that include a user name, and the raw files contain owner contact fields that the project withholds from bulk release.
