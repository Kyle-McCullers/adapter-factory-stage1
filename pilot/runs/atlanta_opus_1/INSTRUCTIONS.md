# Task: build a data adapter for one government business directory

Work only inside the current directory. Do not read, write, or search files outside it, and do not use the network. Everything you need is here.

## Goal

Build a Python adapter that extracts, from the raw export in `raw/`, every firm that the source identifies as Black-owned (African American-owned), and returns those firms as records in the standard schema defined in `adapter_base.py`. Each returned record should represent one firm.

Read `SOURCE.md` first. It says what the file is and where it came from. Then read `adapter_base.py` for the contract your adapter must satisfy.

## Deliverables (all in the current directory)

1. `adapter.py`
   Defines one class named `Adapter` that subclasses `AdapterBase`. Its constructor accepts `file_path` (str or pathlib.Path). `fetch()` reads the file. `parse()` maps the data to the schema. `run()` returns the list of record dicts. Set `SOURCE_ID`, `SOURCE_NAME`, `PROGRAM`, `GEOGRAPHY`, `CONFIDENCE`, and `FIELD_MAP`. Use `map_record()` from the base class for field mapping. Set `last_verified` to today's date as an ISO string.

2. `test_adapter.py`
   Tests you write for your adapter, runnable with `python3 -m pytest -q test_adapter.py`. Use small synthetic inputs you construct in the test, in the same format as the raw file.

3. `NOTES.md`
   Short and factual, under these exact headings:
   - **Filter**: the field or fields and the exact values you treat as marking a Black-owned firm, why, and any values you considered and excluded.
   - **Deduplication**: the key you used, rows read in, firms returned.
   - **Field mapping**: source column to schema field.
   - **Record count**: the number of records `Adapter(file_path="raw/<file>").run()` returns on the actual raw file. Run it and report the real number.
   - **Ambiguities and assumptions**: decisions where the file or the source did not settle the answer.
   - **Anything that looked wrong or surprising** in the file.

## Environment

Python 3.14 with the standard library, plus `requests`, `openpyxl`, `pandas`, and `pytest`. Run `python3`, not `python`.

## Finishing

Run your tests and run the adapter on the raw file before you write the record count. When all three deliverables exist and your tests pass, stop. Do not ask questions; make the best decision you can and record it under Ambiguities and assumptions.
