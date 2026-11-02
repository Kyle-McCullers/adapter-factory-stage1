import csv
import re
from datetime import date
from pathlib import Path

from adapter_base import AdapterBase

BLACK_VALUES = {"black", "black american"}


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


class Adapter(AdapterBase):
    SOURCE_ID = "houston_mwdbe_directory"
    SOURCE_NAME = "City of Houston Certified Business Directory (OBO, houston.mwdbe.com)"
    PROGRAM = "MWBE"
    GEOGRAPHY = "Houston, TX"
    CONFIDENCE = "confirmed_black"
    FIELD_MAP = {
        "Company Name": "business_name",
        "Owner Name": "owner_name",
        "Physical Address": "address_street",
        "City": "address_city",
        "State": "address_state",
        "Zip": "address_zip",
        "Phone": "phone",
        "Email": "email",
        "Website": "website",
        "Certification Type": "certification",
        "Category": "industry",
        "Capability": "description",
        "Commodity Codes": "naics_code",
    }

    def __init__(self, file_path):
        self.file_path = Path(file_path)

    def fetch(self):
        """Return a list of row dicts (header located by 'Company Name')."""
        with open(self.file_path, encoding="cp1252", newline="") as f:
            rows = list(csv.reader(f))
        start = next(i for i, r in enumerate(rows) if r and r[0].strip() == "Company Name")
        header = []
        seen = set()
        for name in rows[start]:
            name = name.strip()
            if not name:
                continue
            if name in seen:  # second City/State/Zip block is the mailing address
                name = "Mailing " + name
            seen.add(name)
            header.append(name)
        out = []
        for r in rows[start + 1:]:
            if len(r) < len(header) or not r[0].strip():
                continue  # blank lines and the trailing footer
            out.append(dict(zip(header, r)))
        self.rows_read = len(out)
        return out

    def parse(self, raw):
        firms = {}
        for row in raw:
            row = {k: (v or "").strip() for k, v in row.items()}
            if row.get("Ethnicity", "").lower() not in BLACK_VALUES:
                continue
            row["Owner Name"] = " ".join(
                p for p in (row.get("Owner First"), row.get("Owner Last")) if p)
            key = (_norm(row["Company Name"]), _norm(row["Owner Name"]))
            if key not in firms:
                firms[key] = {"row": row, "certs": []}
            entry = firms[key]
            for k, v in row.items():  # fill blanks from later rows of the same firm
                if v and not entry["row"].get(k):
                    entry["row"][k] = v
            cert = row.get("Certification Type", "")
            if cert and cert not in entry["certs"]:
                entry["certs"].append(cert)
        today = date.today().isoformat()
        records = []
        for entry in firms.values():
            row = entry["row"]
            row["Certification Type"] = ", ".join(entry["certs"])
            rec = self.map_record(row)
            rec["last_verified"] = today
            records.append(rec)
        return records
