"""Adapter for the Connecticut DAS Supplier Diversity certified directory.

Source: data.ct.gov dataset y4ub-e4dd (CSV export). Each row is one
certification event (a firm can appear once per certification period, and
sometimes twice for the same period under two vendorIds). Rows are collapsed
to one record per firm; see NOTES.md for the rules.
"""

import csv
import datetime
import pathlib
import re

from adapter_base import AdapterBase

BLACK_CLASS_VALUES = {"Black American"}
CLASS_COLUMN = "class_description_detailed"

_VENDOR_ID_RE = re.compile(r"vendorId=([^&#\s]+)")
_POINT_RE = re.compile(r"POINT\s*\(\s*(-?[\d.]+)\s+(-?[\d.]+)\s*\)")


def normalize_name(name: str) -> str:
    """Uppercase, alphanumerics only. Used as a firm-identity key."""
    return re.sub(r"[^A-Z0-9]", "", (name or "").upper())


def extract_vendor_id(link: str) -> str:
    m = _VENDOR_ID_RE.search(link or "")
    return m.group(1).upper() if m else ""


def normalize_zip(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) >= 5:
        return digits[:5]
    if len(digits) == 4:  # leading zero dropped (CT zips start with 0)
        return "0" + digits
    return ""


def parse_point(location: str) -> tuple[str, str]:
    """'POINT (lon lat)' -> (lat, lon) strings, or ('', '')."""
    m = _POINT_RE.search(location or "")
    if not m:
        return "", ""
    return m.group(2), m.group(1)


class _UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


class Adapter(AdapterBase):
    SOURCE_ID = "ct_das_y4ub-e4dd"
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
        "certification_type": "certification",
        "gs_code": "naics_code",
        "goods_and_services": "industry",
        "product": "description",
    }

    def __init__(self, file_path):
        self.file_path = pathlib.Path(file_path)
        self.rows_read = 0

    def fetch(self):
        with open(self.file_path, newline="", encoding="utf-8-sig") as fh:
            return list(csv.DictReader(fh))

    @staticmethod
    def _sort_key(row):
        # Most recent certification first; on ties prefer rows that carry a
        # NAICS code, then rows flagged Black American.
        return (
            row.get("active_date", ""),
            bool((row.get("gs_code") or "").strip()),
            (row.get(CLASS_COLUMN) or "").strip() in BLACK_CLASS_VALUES,
        )

    def parse(self, raw) -> list[dict]:
        rows = list(raw)
        self.rows_read = len(rows)

        # Group rows into firms: rows sharing a vendorId or a normalized
        # vendor name belong to the same firm (transitively).
        uf = _UnionFind()
        row_keys = []
        for i, row in enumerate(rows):
            nn = normalize_name(row.get("vendorname", ""))
            vid = extract_vendor_id(row.get("link_to_company_detail_page", ""))
            name_key = f"n:{nn}" if nn else f"row:{i}"
            uf.find(name_key)
            if vid:
                uf.union(f"v:{vid}", name_key)
            row_keys.append(name_key)

        firms = {}
        for row, key in zip(rows, row_keys):
            firms.setdefault(uf.find(key), []).append(row)

        today = datetime.date.today().isoformat()
        records = []
        for firm_rows in firms.values():
            black_rows = [
                r for r in firm_rows
                if (r.get(CLASS_COLUMN) or "").strip() in BLACK_CLASS_VALUES
            ]
            if not black_rows:
                continue

            rep = max(firm_rows, key=self._sort_key)
            record = self.map_record(rep)

            vendor_ids = sorted({
                v for v in (extract_vendor_id(r.get("link_to_company_detail_page", ""))
                            for r in firm_rows) if v
            })
            rep_vid = extract_vendor_id(rep.get("link_to_company_detail_page", ""))
            firm_id = rep_vid or (vendor_ids[0] if vendor_ids
                                  else normalize_name(rep.get("vendorname", "")))
            record["business_id"] = f"{self.SOURCE_ID}:{firm_id}"
            record["address_zip"] = normalize_zip(rep.get("zip", ""))
            record["latitude"], record["longitude"] = parse_point(rep.get("location", ""))
            record["last_verified"] = today

            sf = record["source_fields"]
            sf["zip_raw"] = (rep.get("zip") or "").strip()
            sf["vendor_ids"] = "; ".join(vendor_ids)
            sf["source_row_count"] = str(len(firm_rows))
            sf["black_american_row_count"] = str(len(black_rows))
            sf["black_american_active_dates"] = "; ".join(sorted(
                {(r.get("active_date") or "").strip() for r in black_rows}))
            sf["names_seen"] = "; ".join(sorted(
                {(r.get("vendorname") or "").strip() for r in firm_rows}))
            records.append(record)

        records.sort(key=lambda r: (r["business_name"].upper(), r["business_id"]))
        return records
