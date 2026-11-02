import csv
import re
from datetime import date
from pathlib import Path

from adapter_base import AdapterBase

BLACK_VALUES = {"black american"}
VENDOR_ID_RE = re.compile(r"vendorId=([0-9A-Fa-f-]+)")
POINT_RE = re.compile(r"POINT\s*\(\s*(-?[\d.]+)\s+(-?[\d.]+)\s*\)")


def _norm_name(name):
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def _clean_zip(z):
    z = (z or "").strip()
    if not z or not any(c.isdigit() for c in z):
        return ""
    z = z.rstrip("-")
    if re.fullmatch(r"\d{9}", z):
        return f"{z[:5]}-{z[5:]}"
    if re.fullmatch(r"\d{4}", z):
        return "0" + z
    return z


class Adapter(AdapterBase):
    SOURCE_ID = "ct_das_supplier_diversity"
    SOURCE_NAME = "CT DAS Supplier Diversity Certified Directory (data.ct.gov y4ub-e4dd)"
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
        "goods_and_services": "industry",
        "gs_code": "naics_code",
        "product": "description",
    }

    def __init__(self, file_path):
        self.file_path = Path(file_path)

    def fetch(self):
        with open(self.file_path, newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))

    @staticmethod
    def _is_black(row):
        return (row.get("class_description_detailed") or "").strip().lower() in BLACK_VALUES

    @staticmethod
    def _vendor_id(row):
        m = VENDOR_ID_RE.search(row.get("link_to_company_detail_page") or "")
        return m.group(1).upper() if m else ""

    @staticmethod
    def _rank(row):
        # best representative: currently certified, then most recent active_date
        return (row.get("status") == "Certified", row.get("active_date") or "")

    def _group(self, rows):
        """Union rows sharing a vendorId or a normalized vendor name."""
        parent = list(range(len(rows)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        seen = {}
        for i, r in enumerate(rows):
            keys = [("n", _norm_name(r.get("vendorname") or ""))]
            vid = self._vendor_id(r)
            if vid:
                keys.append(("v", vid))
            for k in keys:
                if k[1] == "":
                    continue
                if k in seen:
                    parent[find(i)] = find(seen[k])
                else:
                    seen[k] = i
        groups = {}
        for i in range(len(rows)):
            groups.setdefault(find(i), []).append(rows[i])
        return list(groups.values())

    def parse(self, raw):
        black = [r for r in raw if self._is_black(r)]
        today = date.today().isoformat()
        out = []
        for grp in self._group(black):
            best = max(grp, key=self._rank)
            rec = self.map_record(best)
            rec["address_zip"] = _clean_zip(rec["address_zip"])
            m = POINT_RE.search(best.get("location") or "")
            if m:
                rec["longitude"], rec["latitude"] = m.group(1), m.group(2)
            vid = self._vendor_id(best)
            rec["business_id"] = vid
            rec["last_verified"] = today
            sf = rec["source_fields"]
            sf["source_row_count"] = str(len(grp))
            sf["vendor_ids"] = sorted({v for v in map(self._vendor_id, grp) if v})
            out.append(rec)
        return out
