import datetime

import pytest

from adapter import Adapter, _split_location
from adapter_base import BBRT_FIELDS

HEADER = [
    "Company Name", "DBA Name", "Owner First", "Owner Last", "Location",
    "Phone", "Fax", "Email", "Website", "Agency", "Certification Type",
    "Expiration", "Capability", "Market Area", "Supplier ID#", "Commodity Codes",
]


def row(name, cert, sid, first="Ann", last="Lee", loc="Atlanta, GA",
        email=None, exp="1/1/2030", phone="404-555-0100", codes="238210 - Electrical"):
    email = email if email is not None else f"{name.split()[0].lower()}@x.com"
    return [name, "", first, last, loc, phone, "", email, "http://x.com",
            "Atlanta", cert, exp, "Electrical work", "", sid, codes]


def make_file(tmp_path, rows):
    """Write rows in the portal's HTML-table-as-.xls format."""
    def td(v):
        return f"<td align='left' valign='top'>{v}</td>"
    lines = [
        "<strong>Certified Directory</strong><br/>",
        "As of 6/14/2026 1:22:45 PM<br/>",
        "<table role='presentation' border=1 cellspacing=0 cellpadding=0>",
        "<tr>" + "".join(
            f"<td align='center' bgcolor='#CCCCCC'><strong>{h}</strong></td>"
            for h in HEADER) + "</tr>",
    ]
    for r in rows:
        lines.append("<tr>" + "".join(td(v) for v in r) + "</tr>")
    lines.append("</table>")
    p = tmp_path / "dir.xls"
    p.write_text("\r\n".join(lines), encoding="utf-8")
    return p


def run(tmp_path, rows):
    return Adapter(file_path=make_file(tmp_path, rows)).run()


def test_only_aabe_firms_returned(tmp_path):
    recs = run(tmp_path, [
        row("Alpha LLC", "AABE", "1"),
        row("Alpha LLC", "SBE", "1"),
        row("Beta Inc", "SBE", "2"),
        row("Gamma Co", "FBE", "3"),
        row("Delta Co", "HABE", "4"),
        row("Eps Co", "APABE", "5"),
        row("Zeta Co", "NABE", "6"),
    ])
    assert [r["business_name"] for r in recs] == ["Alpha LLC"]
    assert recs[0]["certification"] == "AABE; SBE"


def test_schema_and_metadata(tmp_path):
    recs = run(tmp_path, [row("Alpha &amp; Sons, LLC", "AABE", "1", first="Jo",
                              last="Doe", loc="Decatur, GA",
                              codes="541611 - Mgmt; 541618 - Other; 541611 - Mgmt")])
    r = recs[0]
    for f in BBRT_FIELDS:
        assert f in r
    assert r["business_name"] == "Alpha & Sons, LLC"
    assert r["business_id"] == "1"
    assert r["owner_name"] == "Jo Doe"
    assert r["address_city"] == "Decatur"
    assert r["address_state"] == "GA"
    assert r["naics_code"] == "541611; 541618"
    assert r["phone"] == "404-555-0100"
    assert r["email"] == "alpha@x.com"
    assert r["website"] == "http://x.com"
    assert r["industry"] == "Electrical work"
    assert r["last_verified"] == datetime.date.today().isoformat()
    assert r["data_source"] == Adapter.SOURCE_NAME
    assert r["source_fields"]["Location"] == "Decatur, GA"
    assert r["source_fields"]["Expiration"] == "1/1/2030"
    assert "Certification Type" not in r["source_fields"]


def test_supplier_id_trailing_tab_stripped(tmp_path):
    recs = run(tmp_path, [row("Alpha LLC", "AABE", "2006678\t"),
                          row("Alpha LLC", "SBE", "2006678\t")])
    assert recs[0]["business_id"] == "2006678"


def test_placeholder_and_shared_ids_not_merged(tmp_path):
    recs = run(tmp_path, [
        row("Alpha LLC", "AABE", "9999999"),
        row("Beta Inc", "AABE", "9999999", first="Bo", last="Ng"),
        row("Gamma Co", "AABE", "555", first="Cy", last="Oh"),
        row("Delta Co", "AABE", "555", first="Di", last="Po"),
    ])
    assert len(recs) == 4
    ids = {r["business_id"] for r in recs}
    assert len(ids) == 4
    assert "9999999:alpha-llc" in ids
    assert "555:gamma-co" in ids


def test_same_firm_two_ids_merged_keeps_latest(tmp_path):
    recs = run(tmp_path, [
        row("GRAHAM HAULING, INC.", "AABE", "2100436", loc="Fayetteville, GA", exp="1/8/2026"),
        row("Graham Hauling Inc", "AABE", "1206435", loc="College Park, GA", exp="2/11/2031"),
    ])
    assert len(recs) == 1
    r = recs[0]
    assert r["business_id"] == "1206435"
    assert r["address_city"] == "College Park"
    assert r["source_fields"]["Other Supplier IDs"] == "2100436"


def test_name_variant_merged_by_email_and_owner(tmp_path):
    recs = run(tmp_path, [
        row("Anointed Professional Enterprise", "AABE", "9999999",
            first="Alisa", last="Clark", email="a@g.com", exp="11/15/2024"),
        row("Anointed Professional Enterprises Inc dba Glory", "AABE", "1906722",
            first="Alisa", last="Clark", email="a@g.com", exp="3/31/2030"),
    ])
    assert len(recs) == 1
    assert recs[0]["business_id"] == "1906722"


def test_same_email_different_owner_not_merged(tmp_path):
    recs = run(tmp_path, [
        row("Alpha LLC", "AABE", "1", first="Ann", email="info@shared.com"),
        row("Beta LLC", "AABE", "2", first="Bob", email="info@shared.com"),
    ])
    assert len(recs) == 2


def test_merged_firm_qualifies_if_any_row_is_aabe(tmp_path):
    # The SBE-only row under an old name still belongs to the AABE firm.
    recs = run(tmp_path, [
        row("Green Diamond Waste Management", "SBE", "9999999", email="m@g.com"),
        row("GREEN DIAMOND WASTE MANAGEMENT LLC", "AABE", "1400883", email="m@g.com"),
    ])
    assert len(recs) == 1
    assert recs[0]["business_name"] == "GREEN DIAMOND WASTE MANAGEMENT LLC"


@pytest.mark.parametrize("loc,expected", [
    ("Atlanta, GA", ("Atlanta", "GA")),
    ("Lithonia, GA, GA", ("Lithonia", "GA")),
    ("Atlanta", ("Atlanta", "")),
    ("", ("", "")),
])
def test_split_location(loc, expected):
    assert _split_location(loc) == expected


def test_empty_table(tmp_path):
    assert run(tmp_path, []) == []
