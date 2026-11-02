import re
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path

from adapter_base import AdapterBase

BLACK_CODES = {"AABE"}  # African American Business Enterprise


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self._row, self._cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag == "td" and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag == "td" and self._cell is not None:
            self._row.append("".join(self._cell).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def _norm(s):
    return re.sub(r"\W+", " ", s.lower()).strip()


def _exp(s):
    try:
        return datetime.strptime(s, "%m/%d/%Y").date()
    except ValueError:
        return date.min


class Adapter(AdapterBase):
    SOURCE_ID = "atlanta_occ"
    SOURCE_NAME = "City of Atlanta Office of Contract Compliance Certified Directory"
    PROGRAM = "MWBE"
    GEOGRAPHY = "Atlanta, GA"
    CONFIDENCE = "confirmed_black"
    FIELD_MAP = {
        "Company Name": "business_name",
        "Owner Name": "owner_name",
        "Phone": "phone",
        "Email": "email",
        "Website": "website",
        "Certification Type": "certification",
        "Capability": "description",
        "City": "address_city",
        "State": "address_state",
        "Commodity Codes": "industry",
    }

    def __init__(self, file_path):
        self.file_path = Path(file_path)

    def fetch(self):
        text = self.file_path.read_text(encoding="utf-8", errors="replace")
        parser = _TableParser()
        parser.feed(text)
        if not parser.rows:
            return []
        header = parser.rows[0]
        return [dict(zip(header, r)) for r in parser.rows[1:] if len(r) == len(header)]

    def parse(self, raw):
        self.rows_read = len(raw)
        firms = {}
        for row in raw:
            if row.get("Certification Type", "").strip().upper() not in BLACK_CODES:
                continue
            key = (_norm(row.get("Company Name", "")), row.get("Email", "").strip().lower())
            if key in firms and _exp(row.get("Expiration", "")) <= _exp(firms[key].get("Expiration", "")):
                continue
            firms[key] = row
        today = date.today().isoformat()
        out = []
        for row in firms.values():
            row = dict(row)
            row["Owner Name"] = " ".join(
                p for p in (row.pop("Owner First", ""), row.pop("Owner Last", "")) if p.strip()
            )
            loc = row.pop("Location", "")
            city, _, state = loc.rpartition(",")
            if not city:
                city, state = loc, ""
            row["City"], row["State"] = city.strip(), state.strip()
            rec = self.map_record(row)
            rec["last_verified"] = today
            out.append(rec)
        return out
