import datetime

import pytest

from adapter import Adapter
from adapter_base import BBRT_FIELDS

HEADER = [
    "Company Name", "DBA Name", "Owner First", "Owner Last", "Location", "Phone", "Fax",
    "Email", "Website", "Agency", "Certification Type", "Expiration", "Capability",
    "Market Area", "Supplier ID#", "Commodity Codes",
]


def row(name, cert, sid="1000001", first="Ann", last="Lee", location="Atlanta, GA",
        phone="404-555-0100", email=None, website="http://www.example.com",
        expiration="3/11/2029", capability="Trucking",
        commodity="484220 - Dump trucking; 484110 - General Freight Trucking, Local"):
    email = email if email is not None else f"{name.split()[0].lower()}@example.com"
    return [name, "", first, last, location, phone, "", email, website, "Atlanta", cert,
            expiration, capability, "", sid, commodity]


def build(rows, encoding="cp1252"):
    def tr(cells, head=False):
        if head:
            tds = "".join(f"<td align='center'><strong>{c}</strong></td>" for c in cells)
        else:
            tds = "".join(f"<td align='left' valign='top'>{c}</td>" for c in cells)
        return f"<tr>{tds}</tr>\r\n"
    html = (
        "<strong>Certified Directory</strong><br/>\r\nAs of 6/14/2026 1:22:45 PM<br/>\r\n"
        "<table role='presentation' border=1 cellspacing=0 cellpadding=0>\r\n"
        + tr(HEADER, head=True) + "".join(tr(r) for r in rows)
        + "</table>\r\n<br/><br/>Generated from the B2Gnow System."
    )
    return html.encode(encoding)


@pytest.fixture
def run(tmp_path):
    def _run(rows, encoding="cp1252"):
        p = tmp_path / "dir.xls"
        p.write_bytes(build(rows, encoding))
        adapter = Adapter(file_path=str(p))
        return adapter, adapter.run()
    return _run


def test_filters_to_aabe_only(run):
    _, recs = run([
        row("Black Co", "AABE", sid="1"),
        row("Black Co", "SBE", sid="1"),
        row("Hispanic Co", "HABE", sid="2"),
        row("Asian Co", "APABE", sid="3"),
        row("Native Co", "NABE", sid="4"),
        row("Woman Co", "FBE", sid="5"),
        row("Small Co", "SBE", sid="6"),
    ])
    assert [r["business_name"] for r in recs] == ["Black Co"]


def test_one_record_per_firm_with_all_certifications(run):
    adapter, recs = run([
        row("Acme LLC", "AABE", sid="10"),
        row("Acme LLC", "FBE", sid="10"),
        row("Acme LLC", "SBE", sid="10"),
    ])
    assert adapter.rows_read == 3
    assert len(recs) == 1
    assert recs[0]["certification"] == "AABE; FBE; SBE"


def test_shared_supplier_id_does_not_merge_distinct_firms(run):
    _, recs = run([
        row("Alpha Inc", "AABE", sid="9999999", first="A", last="One"),
        row("Beta Inc", "AABE", sid="9999999", first="B", last="Two"),
        row("Gamma Inc", "AABE", sid="1701842", first="C", last="Three"),
        row("Delta Inc", "SBE", sid="1701842", first="D", last="Four"),
    ])
    names = sorted(r["business_name"] for r in recs)
    assert names == ["Alpha Inc", "Beta Inc", "Gamma Inc"]
    by_name = {r["business_name"]: r for r in recs}
    assert by_name["Alpha Inc"]["business_id"] == ""  # placeholder ID blanked
    assert by_name["Gamma Inc"]["certification"] == "AABE"  # Delta's SBE not attached


def test_same_firm_under_two_ids_merged_latest_expiration_wins(run):
    _, recs = run([
        row("GRAHAM HAULING, INC.", "AABE", sid="2100436", location="Fayetteville, GA", expiration="1/8/2026"),
        row("GRAHAM HAULING, INC.", "SBE", sid="2100436", location="Fayetteville, GA", expiration="1/8/2026"),
        row("Graham Hauling Inc", "AABE", sid="1206435", location="College Park, GA", expiration="2/11/2031"),
    ])
    assert len(recs) == 1
    r = recs[0]
    assert r["business_id"] == "1206435"
    assert r["address_city"] == "College Park"
    assert r["source_fields"]["All Supplier IDs"] == "2100436; 1206435"


def test_firm_relisted_under_longer_name_merged(run):
    _, recs = run([
        row("Anointed Professional Enterprise", "AABE", sid="9999999", email="a@glory.com", expiration="11/15/2024"),
        row("Anointed Professional Enterprises Inc dba Glory", "AABE", sid="1906722", email="a@glory.com"),
    ])
    assert len(recs) == 1
    assert recs[0]["business_id"] == "1906722"


def test_affiliates_with_same_owner_kept_separate(run):
    _, recs = run([
        row("Khafra Engineering", "AABE", sid="1", email="vb@example.com"),
        row("Khafra Operations", "AABE", sid="2", email="vb@example.com"),
    ])
    assert len(recs) == 2


def test_field_mapping_and_schema(run):
    _, recs = run([row("Acme LLC", "AABE", sid="1303394\t", first="Owner", last="Name",
                       location="Norcross,, GA", phone="404-555-0101", email="s@acme.com",
                       capability="Electrical work",
                       commodity="23821 - Electrical; 238210 - Electrical Contractors; 238210 - Wiring")])
    r = recs[0]
    assert set(BBRT_FIELDS) <= set(r)
    assert r["business_id"] == "1303394"
    assert r["owner_name"] == "Owner Name"
    assert (r["address_city"], r["address_state"]) == ("Norcross", "GA")
    assert r["phone"] == "404-555-0101"
    assert r["email"] == "s@acme.com"
    assert r["description"] == "Electrical work"
    assert r["naics_code"] == "23821, 238210"
    assert r["data_source"] == Adapter.SOURCE_NAME
    assert r["last_verified"] == datetime.date.today().isoformat()
    sf = r["source_fields"]
    assert sf["Fax"] == "" and sf["Agency"] == "Atlanta" and sf["Expiration"] == "3/11/2029"
    assert "Company Name" not in sf


def test_location_with_repeated_state(run):
    _, recs = run([row("Acme LLC", "AABE", location="Lithonia, GA, GA")])
    assert (recs[0]["address_city"], recs[0]["address_state"]) == ("Lithonia", "GA")


@pytest.mark.parametrize("raw_site,expected", [
    ("http://www.acme.com", "http://www.acme.com"),
    ("http://www. acme.com", "http://www.acme.com"),
    ("http://no website", ""),
    ("http://n/a", ""),
    ("http://under construction", ""),
    ("", ""),
])
def test_website_cleaning(run, raw_site, expected):
    _, recs = run([row("Acme LLC", "AABE", website=raw_site)])
    assert recs[0]["website"] == expected
    if raw_site != expected:
        assert recs[0]["source_fields"]["Website (raw)"] == raw_site


def test_cp1252_and_entities_decoded(run):
    _, recs = run([row("Sugar Shane’s LLC", "AABE"), row("A &amp; B Co", "AABE", sid="2")])
    names = {r["business_name"] for r in recs}
    assert names == {"Sugar Shane’s LLC", "A & B Co"}


def test_utf8_input_also_works(run):
    _, recs = run([row("Café Noir", "AABE")], encoding="utf-8")
    assert recs[0]["business_name"] == "Café Noir"


def test_empty_table(run):
    adapter, recs = run([])
    assert recs == [] and adapter.rows_read == 0
