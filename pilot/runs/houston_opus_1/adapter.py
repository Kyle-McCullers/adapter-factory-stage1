"""Adapter for the City of Houston (Office of Business Opportunity) certified
business directory export (B2Gnow "Download Results to Excel" CSV).

The export has one row per (firm, certification type), so a firm certified as
MBE, SBE and WBE appears three times. This adapter keeps rows whose Ethnicity
is a Black/African American value, collapses them to one record per firm, and
maps them to the BBRT schema.
"""

import csv
import datetime
import hashlib
import io
import pathlib
import re

from adapter_base import AdapterBase

# Ethnicity values that the source uses for Black-owned firms. "Black" is used
# by the City of Houston programs; "Black American" by the Houston LGBT program.
BLACK_ETHNICITIES = {"black", "black american"}

# The raw header repeats City/State/Zip for the mailing address; rename them so
# every column has a unique key.
HEADER_RENAMES = {
    ("City", 1): "Mailing City",
    ("State", 1): "Mailing State",
    ("Zip", 1): "Mailing Zip",
}

# Columns whose values are combined across all rows of a firm.
MULTI_VALUE_COLUMNS = ["Agency", "Certification Type", "Ethnicity", "Gender",
                       "HUB?", "Re-Evaluation Status", "Category",
                       "Commodity Codes"]

NAICS_RE = re.compile(r"(?:^|;)\s*(\d{6})\s*-")


def _clean(value):
    """Strip whitespace (the export prefixes zips with a tab) and collapse runs."""
    if value is None:
        return ""
    return " ".join(str(value).split())


def firm_key(company_name):
    """Dedup key: company name, case-folded with whitespace collapsed."""
    return _clean(company_name).casefold()


def _unique(values):
    out = []
    for v in values:
        if v and v not in out:
            out.append(v)
    return out


def _split_codes(value):
    return [c.strip() for c in value.split(";") if c.strip()]


def _clean_website(url):
    # Some entries have a doubled scheme, e.g. "http://https://example.com/".
    return re.sub(r"^https?://(?=https?://)", "", url, flags=re.I)


class Adapter(AdapterBase):
    SOURCE_ID = "houston_obo_directory"
    SOURCE_NAME = "City of Houston Office of Business Opportunity Certified Directory"
    PROGRAM = "MWBE"
    GEOGRAPHY = "Houston, TX"
    CONFIDENCE = "confirmed_black"
    FIELD_MAP = {
        "Business ID": "business_id",
        "Company Name": "business_name",
        "Owner Name": "owner_name",
        "Physical Address": "address_street",
        "City": "address_city",
        "State": "address_state",
        "Zip": "address_zip",
        "Category": "industry",
        "NAICS Codes": "naics_code",
        "Certification Type": "certification",
        "Capability": "description",
        "Website": "website",
        "Phone": "phone",
        "Email": "email",
    }

    def __init__(self, file_path):
        self.file_path = pathlib.Path(file_path)
        self.rows_read = 0

    def fetch(self):
        data = self.file_path.read_bytes()
        try:
            return data.decode("utf-8-sig")
        except UnicodeDecodeError:
            # The portal delivers Windows-1252 (curly apostrophes as 0x92 etc.).
            return data.decode("cp1252", errors="replace")

    def _read_rows(self, text):
        """Yield dicts for each data row, skipping the preamble and footer."""
        reader = csv.reader(io.StringIO(text))
        header = None
        for row in reader:
            if header is None:
                if row and row[0].strip() == "Company Name":
                    header = []
                    seen = {}
                    for col in row:
                        col = col.strip()
                        n = seen.get(col, 0)
                        seen[col] = n + 1
                        header.append(HEADER_RENAMES.get((col, n), col))
                continue
            # Blank lines and the "Generated from the B2Gnow System." footer.
            if len(row) < 2 or not any(c.strip() for c in row):
                continue
            row = row + [""] * (len(header) - len(row))
            yield {col: val for col, val in zip(header, row) if col}

    def parse(self, raw):
        firms = {}
        self.rows_read = 0
        for row in self._read_rows(raw):
            self.rows_read += 1
            if _clean(row.get("Ethnicity")).casefold() not in BLACK_ETHNICITIES:
                continue
            key = firm_key(row.get("Company Name"))
            if not key:
                continue
            firms.setdefault(key, []).append(row)

        today = datetime.date.today().isoformat()
        records = []
        for key, rows in firms.items():
            records.append(self._build_record(key, rows, today))
        return records

    def _build_record(self, key, rows, today):
        first = rows[0]
        merged = {col: _clean(val) for col, val in first.items()}

        # Fill fields blank on the first row from later rows of the same firm.
        for row in rows[1:]:
            for col, val in row.items():
                if not merged.get(col) and _clean(val):
                    merged[col] = _clean(val)

        for col in MULTI_VALUE_COLUMNS:
            if col == "Commodity Codes":
                codes = _unique(c for r in rows
                                for c in _split_codes(_clean(r.get(col))))
                merged[col] = "; ".join(codes)
            else:
                merged[col] = "; ".join(_unique(_clean(r.get(col)) for r in rows))

        naics = _unique(NAICS_RE.findall(merged.get("Commodity Codes", "")))
        merged["NAICS Codes"] = "; ".join(naics)
        merged["Owner Name"] = " ".join(
            p for p in (merged.pop("Owner First", ""), merged.pop("Owner Last", "")) if p)
        merged["Website"] = _clean_website(merged.get("Website", ""))
        merged["Business ID"] = "houston-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
        # Distinct phone numbers / addresses across rows, kept for traceability.
        merged["All Phones"] = "; ".join(_unique(_clean(r.get("Phone")) for r in rows))
        merged["All Physical Addresses"] = "; ".join(_unique(
            ", ".join(p for p in (_clean(r.get("Physical Address")), _clean(r.get("City")),
                                  _clean(r.get("State")), _clean(r.get("Zip"))) if p)
            for r in rows))
        merged["Source Row Count"] = str(len(rows))

        record = self.map_record(merged)
        record["last_verified"] = today
        return record


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "raw/houston_directory_2026-06-14.csv"
    a = Adapter(file_path=path)
    recs = a.run()
    print(f"rows read: {a.rows_read}; firms returned: {len(recs)}")
