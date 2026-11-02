"""Adapter for the City of Atlanta certified business directory export.

The portal (atlanta.diversitycompliance.com) serves an HTML table saved with
an .xls extension. Each row is one (firm, certification type) pair, so a firm
certified as AABE, FBE and SBE appears three times. Black-owned firms are the
ones carrying the AABE (African American Business Enterprise) certification.
"""

import datetime
import re
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path

from adapter_base import AdapterBase

BLACK_OWNED_CERTS = {"AABE"}

# Supplier IDs that are clearly placeholders rather than real identifiers.
PLACEHOLDER_ID_RE = re.compile(r"^9+$")

NAICS_RE = re.compile(r"\b(\d{6})\b")


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
        if tag in ("td", "th") and self._cell is not None:
            if self._row is not None:
                self._row.append("".join(self._cell))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def _norm_name(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _parse_date(s):
    try:
        return datetime.datetime.strptime((s or "").strip(), "%m/%d/%Y").date()
    except ValueError:
        return datetime.date.min


def _split_location(loc):
    """'Atlanta, GA' -> ('Atlanta', 'GA'). Tolerates 'Lithonia, GA, GA'."""
    parts = [p.strip() for p in (loc or "").split(",") if p.strip()]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    state = parts[-1]
    city_parts = parts[:-1]
    # Drop repeated state tokens, e.g. "Lithonia, GA, GA".
    while len(city_parts) > 1 and city_parts[-1].upper() == state.upper():
        city_parts.pop()
    return ", ".join(city_parts), state.upper()


class Adapter(AdapterBase):
    SOURCE_ID = "atlanta_occ_certified_directory"
    SOURCE_NAME = "City of Atlanta Office of Contract Compliance Certified Directory"
    PROGRAM = "MWBE"
    GEOGRAPHY = "Atlanta"
    CONFIDENCE = "confirmed_black"
    FIELD_MAP = {
        "Business ID": "business_id",
        "Company Name": "business_name",
        "Owner Name": "owner_name",
        "City": "address_city",
        "State": "address_state",
        "Capability": "industry",
        "NAICS Codes": "naics_code",
        "Certifications": "certification",
        "Website": "website",
        "Phone": "phone",
        "Email": "email",
    }

    def __init__(self, file_path):
        self.file_path = Path(file_path)

    def fetch(self):
        data = self.file_path.read_bytes()
        try:
            return data.decode("utf-8-sig")
        except UnicodeDecodeError:
            return data.decode("cp1252", errors="replace")

    # -- parsing helpers -------------------------------------------------

    @staticmethod
    def _rows(raw):
        parser = _TableParser()
        parser.feed(raw)
        parser.close()
        header_idx = next(
            (i for i, r in enumerate(parser.rows)
             if "Company Name" in [c.strip() for c in r]),
            None,
        )
        if header_idx is None:
            return []
        header = [c.strip() for c in parser.rows[header_idx]]
        out = []
        for r in parser.rows[header_idx + 1:]:
            if not any(c.strip() for c in r):
                continue
            r = r + [""] * (len(header) - len(r))
            out.append({h: v.strip() for h, v in zip(header, r)})
        return out

    @staticmethod
    def _group_firms(rows):
        """Group rows into firms with union-find.

        Rows are linked when they share a normalized company name, or when
        they share both an email address and owner (first + last) name. The
        Supplier ID is not used as a key: it contains placeholders
        (9999999) and is reused across unrelated firms in this export.
        """
        parent = list(range(len(rows)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        first_seen = {}
        for i, r in enumerate(rows):
            keys = []
            name = _norm_name(r.get("Company Name"))
            if name:
                keys.append(("name", name))
            email = (r.get("Email") or "").strip().lower()
            owner = _norm_name(f"{r.get('Owner First', '')} {r.get('Owner Last', '')}")
            if email and owner:
                keys.append(("email_owner", email, owner))
            for k in keys:
                if k in first_seen:
                    union(first_seen[k], i)
                else:
                    first_seen[k] = i

        groups = defaultdict(list)
        for i in range(len(rows)):
            groups[find(i)].append(rows[i])
        return list(groups.values())

    # -- main ------------------------------------------------------------

    def parse(self, raw) -> list[dict]:
        rows = self._rows(raw)
        firms = self._group_firms(rows)

        # How many distinct firms use each supplier ID, to decide whether
        # the ID can serve as business_id on its own.
        id_firms = defaultdict(set)
        for fi, firm in enumerate(firms):
            for r in firm:
                sid = r.get("Supplier ID#", "").strip()
                if sid:
                    id_firms[sid].add(fi)

        today = datetime.date.today().isoformat()
        records = []
        for firm in firms:
            certs = {r.get("Certification Type", "").strip().upper() for r in firm}
            black_rows = [r for r in firm
                          if r.get("Certification Type", "").strip().upper()
                          in BLACK_OWNED_CERTS]
            if not black_rows:
                continue

            # Representative row: the Black-owned certification row with the
            # latest expiration date (most recent certification record).
            best = max(black_rows, key=lambda r: _parse_date(r.get("Expiration")))

            sid = best.get("Supplier ID#", "").strip()
            if sid and not PLACEHOLDER_ID_RE.match(sid) and len(id_firms[sid]) == 1:
                business_id = sid
            else:
                slug = _norm_name(best.get("Company Name")).replace(" ", "-")
                business_id = f"{sid}:{slug}" if sid else slug

            city, state = _split_location(best.get("Location"))
            owner = " ".join(
                p for p in (best.get("Owner First", ""), best.get("Owner Last", ""))
                if p.strip()
            )
            naics = []
            for code in NAICS_RE.findall(best.get("Commodity Codes", "")):
                if code not in naics:
                    naics.append(code)
            other_ids = sorted({r.get("Supplier ID#", "").strip() for r in firm}
                               - {sid, ""})
            other_names = sorted({r.get("Company Name", "").strip() for r in firm}
                                 - {best.get("Company Name", "").strip(), ""})

            source_row = dict(best)
            source_row["Supplier ID#"] = sid
            source_row.pop("Certification Type", None)
            source_row.update({
                "Business ID": business_id,
                "Owner Name": owner,
                "City": city,
                "State": state,
                "NAICS Codes": "; ".join(naics),
                "Certifications": "; ".join(sorted(c for c in certs if c)),
                "Other Supplier IDs": "; ".join(other_ids),
                "Other Company Names": "; ".join(other_names),
                "Source Row Count": str(len(firm)),
            })
            record = self.map_record(source_row)
            record["last_verified"] = today
            records.append(record)

        records.sort(key=lambda r: (r["business_name"].lower(), r["business_id"]))
        return records
