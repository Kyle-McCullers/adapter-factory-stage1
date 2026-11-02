"""Adapter for the Connecticut DAS Supplier Diversity certified directory
(data.ct.gov dataset y4ub-e4dd).

The export holds one row per certification period (plus some fan-out
duplicates), not one row per firm. This adapter keeps rows whose
class_description_detailed is "Black American", groups rows into firms,
and returns one record per firm.
"""

import csv
import datetime
import pathlib
import re

from adapter_base import AdapterBase

BLACK_VALUES = {"Black American"}
RACE_COLUMN = "class_description_detailed"

_VENDOR_ID_RE = re.compile(r"vendorId=([0-9A-Za-z-]+)")
_POINT_RE = re.compile(r"^POINT \((-?[\d.]+) (-?[\d.]+)\)$")


def vendor_id(row: dict) -> str:
    m = _VENDOR_ID_RE.search(row.get("link_to_company_detail_page") or "")
    return m.group(1).upper() if m else ""


def normalize_name(name: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (name or "").upper())


def normalize_zip(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) >= 5:
        return digits[:5]
    if len(digits) == 4:  # leading zero dropped, e.g. "6106"
        return "0" + digits
    return ""


class _UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))

    def find(self, i):
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


class Adapter(AdapterBase):
    SOURCE_ID = "ct_das_supplier_diversity"
    SOURCE_NAME = "Connecticut DAS Supplier Diversity Certified Directory (data.ct.gov y4ub-e4dd)"
    PROGRAM = "MWBE"
    GEOGRAPHY = "CT"
    CONFIDENCE = "confirmed_black"
    FIELD_MAP = {
        "vendorname": "business_name",
        "business_address1": "address_street",
        "townnamecrosswalk_standardized_town": "address_city",
        "business_state": "address_state",
        "zip": "address_zip",
        "goods_and_services": "industry",
        "gs_code": "naics_code",
        "certification_type": "certification",
        "product": "description",
    }

    def __init__(self, file_path):
        self.file_path = pathlib.Path(file_path)
        self.rows_read = 0

    def fetch(self):
        with open(self.file_path, newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))

    def _group_firms(self, rows):
        """Union rows that share a vendorId or a normalized firm name."""
        uf = _UnionFind(len(rows))
        first_by_key = {}
        for i, row in enumerate(rows):
            for key in (("vid", vendor_id(row)), ("name", normalize_name(row.get("vendorname")))):
                if not key[1]:
                    continue
                if key in first_by_key:
                    uf.union(first_by_key[key], i)
                else:
                    first_by_key[key] = i
        groups = {}
        for i in range(len(rows)):
            groups.setdefault(uf.find(i), []).append(i)
        return list(groups.values())

    def parse(self, raw) -> list[dict]:
        rows = list(raw)
        self.rows_read = len(rows)
        today = datetime.date.today().isoformat()
        records = []
        for idxs in self._group_firms(rows):
            firm_rows = [rows[i] for i in idxs]
            black_rows = [r for r in firm_rows if (r.get(RACE_COLUMN) or "").strip() in BLACK_VALUES]
            if not black_rows:
                continue
            # Most recent Black-identified certification row is the representative.
            black_rows.sort(key=lambda r: (r.get("active_date") or "", r.get("status") == "Certified"), reverse=True)
            rep = dict(black_rows[0])
            # Fill blank fields from older Black-identified rows of the same firm.
            for col in rep:
                if not (rep[col] or "").strip():
                    for older in black_rows[1:]:
                        if (older.get(col) or "").strip():
                            rep[col] = older[col]
                            break

            record = self.map_record(rep)
            record["address_zip"] = normalize_zip(record["address_zip"])
            if not record["address_state"] and record["address_zip"].startswith("06"):
                record["address_state"] = "CT"
            m = _POINT_RE.match(rep.get("location") or "")
            if m:
                record["longitude"], record["latitude"] = m.group(1), m.group(2)

            vids = sorted({vendor_id(r) for r in firm_rows} - {""})
            rep_vid = vendor_id(rep)
            record["business_id"] = f"ct_das:{rep_vid}" if rep_vid else f"ct_das:name:{normalize_name(rep.get('vendorname'))}"
            record["last_verified"] = today

            latest_any = max(firm_rows, key=lambda r: r.get("active_date") or "")
            sf = record["source_fields"]
            sf["vendor_ids"] = ";".join(vids)
            sf["source_row_count"] = str(len(firm_rows))
            sf["black_row_count"] = str(len(black_rows))
            sf["firm_latest_status"] = latest_any.get("status", "")
            sf["firm_latest_expiration_date"] = latest_any.get("expiration_date", "")
            sf["firm_latest_class_description"] = latest_any.get(RACE_COLUMN, "")
            records.append(record)

        records.sort(key=lambda r: (r["business_name"].upper(), r["business_id"]))
        return records
