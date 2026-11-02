"""Adapter for the City of Atlanta Office of Contract Compliance certified directory.

The portal export (atlanta.diversitycompliance.com, B2Gnow) carries an `.xls`
extension but is actually an HTML fragment containing one <table>, encoded in
Windows-1252. The export has one row per (firm, certification type), so a firm
holding AABE + SBE + FBE appears three times. Black-owned firms are those with a
Certification Type of "AABE" (African American Business Enterprise).
"""
import datetime
import re
from html.parser import HTMLParser
from pathlib import Path

from adapter_base import AdapterBase

BLACK_CERT_TYPES = {"AABE"}

# Supplier IDs that are obviously placeholders shared by unrelated firms.
PLACEHOLDER_IDS = {"9999999", "999999"}

# Columns that are derived into schema fields in parse() rather than via FIELD_MAP.
LOCATION_COL = "Location"
OWNER_FIRST_COL = "Owner First"
OWNER_LAST_COL = "Owner Last"
COMMODITY_COL = "Commodity Codes"
CERT_COL = "Certification Type"
SUPPLIER_ID_COL = "Supplier ID#"
NAME_COL = "Company Name"
EXPIRATION_COL = "Expiration"
WEBSITE_COL = "Website"


class _TableParser(HTMLParser):
    """Collect every <tr> as a list of cell strings."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self._row = None
        self._cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._cell = []
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append("".join(self._cell))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def _clean(value):
    return re.sub(r"\s+", " ", value or "").strip()


def _name_key(name):
    """Normalized company name used as the firm dedup key."""
    name = name.lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]", "", name)


def _parse_date(value):
    try:
        return datetime.datetime.strptime(value, "%m/%d/%Y").date()
    except (TypeError, ValueError):
        return datetime.date.min


def _split_location(location):
    """'Atlanta, GA' -> ('Atlanta', 'GA'). Tolerates 'Norcross,, GA' and 'Lithonia, GA, GA'."""
    parts = [p.strip() for p in location.split(",") if p.strip()]
    if not parts:
        return "", ""
    state = ""
    if len(parts) > 1 and re.fullmatch(r"[A-Za-z]{2}", parts[-1]):
        state = parts[-1].upper()
        parts = parts[:-1]
    return parts[0], state


def _naics_codes(commodity):
    """Extract NAICS codes from '238210 - Electrical ...; 541611 - ...'. De-duplicated, in order."""
    codes = re.findall(r"(?:^|;)\s*(\d{2,6})\s*-", commodity)
    return ", ".join(dict.fromkeys(codes))


def _clean_website(value):
    """Drop free-text that the portal stored as a URL ('http://no website', 'http://n/a')."""
    if not value:
        return ""
    candidate = re.sub(r"(?i)www\.\s+", "www.", value)
    host = re.sub(r"(?i)^https?://", "", candidate)
    if " " in host or not re.search(r"\.[A-Za-z]{2,}", host):
        return ""
    return candidate


class Adapter(AdapterBase):
    SOURCE_ID = "atlanta_occ_certified_directory"
    SOURCE_NAME = "City of Atlanta Office of Contract Compliance Certified Directory"
    PROGRAM = "MWBE"
    GEOGRAPHY = "Atlanta, GA"
    CONFIDENCE = "confirmed_black"
    FIELD_MAP = {
        NAME_COL: "business_name",
        SUPPLIER_ID_COL: "business_id",
        "Phone": "phone",
        "Email": "email",
        WEBSITE_COL: "website",
        "Capability": "description",
    }

    def __init__(self, file_path):
        self.file_path = Path(file_path)
        self.rows_read = 0

    def fetch(self):
        data = self.file_path.read_bytes()
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data.decode("cp1252", errors="replace")

    def _rows(self, raw):
        parser = _TableParser()
        parser.feed(raw)
        parser.close()
        table = [r for r in parser.rows if r]
        if not table:
            return []
        header = [_clean(h) for h in table[0]]
        rows = []
        for cells in table[1:]:
            if len(cells) != len(header):
                continue
            row = {h: _clean(c) for h, c in zip(header, cells)}
            if not row.get(NAME_COL):
                continue
            rows.append(row)
        return rows

    @staticmethod
    def _merge_renamed(keyed_groups):
        """Merge name groups that are the same firm listed under a lengthened name,
        e.g. 'Anointed Professional Enterprise' and 'Anointed Professional Enterprises
        Inc dba Glory ...': same owner, same email, and one name key is a prefix of the other."""
        def ident(group):
            r = group[0]
            owner = _name_key(f"{r.get(OWNER_FIRST_COL, '')}{r.get(OWNER_LAST_COL, '')}")
            return owner, r.get("Email", "").lower()

        merged = []  # list of [name_key, rows]
        for key, group in sorted(keyed_groups, key=lambda kg: len(kg[0])):
            owner, email = ident(group)
            target = None
            if owner and email:
                for entry in merged:
                    if key.startswith(entry[0]) and ident(entry[1]) == (owner, email):
                        target = entry
                        break
            if target is None:
                merged.append([key, list(group)])
            else:
                target[1].extend(group)
        return [rows for _, rows in merged]

    def parse(self, raw) -> list[dict]:
        rows = self._rows(raw)
        self.rows_read = len(rows)

        # Group every row (all certification types) by firm, so that the full set of
        # certifications is known for each Black-owned firm.
        groups = {}
        for row in rows:
            groups.setdefault(_name_key(row[NAME_COL]), []).append(row)

        groups = self._merge_renamed(list(groups.items()))

        today = datetime.date.today().isoformat()
        records = []
        for group in groups:
            black_rows = [r for r in group if r.get(CERT_COL, "").upper() in BLACK_CERT_TYPES]
            if not black_rows:
                continue
            # Representative row: the Black-owned certification with the latest expiration.
            rep = max(black_rows, key=lambda r: _parse_date(r.get(EXPIRATION_COL)))

            cert_types = list(dict.fromkeys(r[CERT_COL] for r in group if r.get(CERT_COL)))
            supplier_ids = list(dict.fromkeys(r[SUPPLIER_ID_COL] for r in group if r.get(SUPPLIER_ID_COL)))

            source_row = dict(rep)
            source_row["All Certification Types"] = "; ".join(cert_types)
            source_row["All Supplier IDs"] = "; ".join(supplier_ids)

            record = self.map_record(source_row)
            sf = record["source_fields"]

            if record["business_id"] in PLACEHOLDER_IDS:
                record["business_id"] = ""
            record["address_city"], record["address_state"] = _split_location(rep.get(LOCATION_COL, ""))
            record["owner_name"] = _clean(f"{rep.get(OWNER_FIRST_COL, '')} {rep.get(OWNER_LAST_COL, '')}")
            record["naics_code"] = _naics_codes(rep.get(COMMODITY_COL, ""))
            record["certification"] = "; ".join(cert_types)
            website = _clean_website(record["website"])
            if website != record["website"]:
                sf["Website (raw)"] = record["website"]
                record["website"] = website
            record["last_verified"] = today
            records.append(record)

        records.sort(key=lambda r: r["business_name"].lower())
        return records
