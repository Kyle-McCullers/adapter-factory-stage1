"""Adapter for the City of Houston (Office of Business Opportunity) certified
business directory export (B2Gnow "Download Results to Excel" CSV)."""

import csv
import datetime
import hashlib
import io
import pathlib
import re

from adapter_base import AdapterBase

# Ethnicity values that mark a Black-owned firm. "Black" is used by the
# Houston agency rows; "Black American" by the Houston LGBT agency rows.
BLACK_ETHNICITIES = {"black", "black american"}

# The export repeats City/State/Zip for the mailing address; csv headers are
# positional, so the second occurrence gets a "Mailing " prefix.
MAILING_DUPES = ("City", "State", "Zip")

# Columns whose values can differ across a firm's rows; all distinct values
# are kept (joined with "; ") rather than only the first row's.
MULTI_VALUE_COLUMNS = ("Agency", "Certification Type", "Ethnicity", "Gender",
                       "HUB?", "Re-Evaluation Status")

NAICS_RE = re.compile(r"(?:^|;)\s*(\d{2,6})\s*-")


def _norm_name(name):
    """Case-, whitespace- and punctuation-insensitive firm-name key."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _clean_website(url):
    url = url.strip()
    # The portal prepends "http://" to values that already have a scheme.
    return re.sub(r"^https?://(?=https?://)", "", url, flags=re.I)


def _join_unique(values):
    seen = []
    for v in values:
        v = v.strip()
        if v and v not in seen:
            seen.append(v)
    return "; ".join(seen)


class Adapter(AdapterBase):
    SOURCE_ID   = "houston_obo_directory"
    SOURCE_NAME = "City of Houston Office of Business Opportunity Certified Directory"
    PROGRAM     = "MWBE"
    GEOGRAPHY   = "Houston, TX"
    CONFIDENCE  = "confirmed_black"
    FIELD_MAP   = {
        "Company Name":       "business_name",
        "Owner Name":         "owner_name",
        "Physical Address":   "address_street",
        "City":               "address_city",
        "State":              "address_state",
        "Zip":                "address_zip",
        "Phone":              "phone",
        "Email":              "email",
        "Website":            "website",
        "Category":           "industry",
        "Capability":         "description",
        "Certification Type": "certification",
        "NAICS Codes":        "naics_code",
    }

    def __init__(self, file_path):
        self.file_path = pathlib.Path(file_path)
        self.rows_read = 0

    def fetch(self):
        data = self.file_path.read_bytes()
        try:
            return data.decode("utf-8-sig")
        except UnicodeDecodeError:
            # The B2Gnow export is Windows-1252 (e.g. 0x92 for ’).
            return data.decode("cp1252", errors="replace")

    def _read_rows(self, text):
        """Yield dicts for data rows, skipping the banner above the header
        and the footer below the data."""
        header = None
        for row in csv.reader(io.StringIO(text)):
            if header is None:
                if row and row[0].strip() == "Company Name":
                    header, seen = [], set()
                    for col in row:
                        col = col.strip()
                        if col in seen and col in MAILING_DUPES:
                            col = "Mailing " + col
                        seen.add(col)
                        header.append(col)
                continue
            if not any(c.strip() for c in row) or len(row) < len(header) - 1:
                continue  # blank lines and "Generated from the B2Gnow System."
            d = {h: (row[i] if i < len(row) else "") for i, h in enumerate(header) if h}
            if not d.get("Company Name", "").strip():
                continue
            yield d

    def parse(self, raw):
        firms = {}  # normalized name -> list of rows, in file order
        self.rows_read = 0
        for row in self._read_rows(raw):
            self.rows_read += 1
            firms.setdefault(_norm_name(row["Company Name"]), []).append(row)

        today = datetime.date.today().isoformat()
        records = []
        for key, rows in firms.items():
            black_rows = [r for r in rows
                          if r.get("Ethnicity", "").strip().lower() in BLACK_ETHNICITIES]
            if not black_rows:
                continue
            # Scalar fields come from the first row flagged Black; empty
            # values are back-filled from the firm's other rows.
            ordered = black_rows + [r for r in rows if r not in black_rows]
            merged = {}
            for col in ordered[0]:
                if col in MULTI_VALUE_COLUMNS:
                    merged[col] = _join_unique(r.get(col, "") for r in rows)
                else:
                    merged[col] = next((r[col] for r in ordered if r.get(col, "").strip()), "")
            merged["Owner Name"] = " ".join(
                p for p in (merged.get("Owner First", "").strip(),
                            merged.get("Owner Last", "").strip()) if p)
            merged["Website"] = _clean_website(merged.get("Website", ""))
            merged["NAICS Codes"] = _join_unique(
                NAICS_RE.findall(_join_unique(r.get("Commodity Codes", "") for r in rows)))
            merged["Commodity Codes"] = _join_unique(
                c for r in rows for c in r.get("Commodity Codes", "").split(";"))
            merged["Source Row Count"] = str(len(rows))

            record = self.map_record(merged)
            record["business_id"] = "houston-" + hashlib.sha1(key.encode()).hexdigest()[:12]
            record["last_verified"] = today
            records.append(record)
        return records
