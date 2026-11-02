import csv
import datetime

import pytest

from adapter import Adapter, normalize_zip, parse_point
from adapter_base import AdapterBase, BBRT_FIELDS

COLUMNS = [
    "vendorname", "business_address1", "townnamecrosswalk_standardized_town", "zip",
    "county", "business_state", "certification_type", "class_description_detailed",
    "woman_owned_business_detailed", "race_gender_business_detailed",
    "disability_status_detailed", "active_date", "expiration_date", "active_year",
    "status", "link_to_company_detail_page", "product", "das_prequalified",
    "business_structure", "no_of_employees", "new_certification", "gs_code",
    "goods_and_services", "location",
]
LINK = ("https://ct-gateway.formverse5.com/AUTOCENESERVER/WebApp/FillFormWO.aspx"
        "?templateId=be7593ed-a2d5-481b-9bbd-8691262425cf&vendorId={}")
NO_MINORITY = "No minority race/ethnicity identified"


def row(name, cls="Black American", vid="", date="2025-01-01", **kw):
    r = {c: "" for c in COLUMNS}
    r.update({
        "vendorname": name,
        "business_address1": "1 Main St",
        "townnamecrosswalk_standardized_town": "Hartford",
        "zip": "06103",
        "county": "NA",
        "business_state": "CT",
        "certification_type": "MBE" if cls != NO_MINORITY else "SBE",
        "class_description_detailed": cls,
        "active_date": f"{date}T00:00:00.000",
        "status": "Certified",
        "link_to_company_detail_page": LINK.format(vid) if vid else "",
        "product": "Stuff",
        "gs_code": "561720",
        "goods_and_services": "Janitorial Services",
        "location": "POINT (-72.68 41.76)",
    })
    r.update(kw)
    return r


def write_csv(tmp_path, rows):
    p = tmp_path / "sample.csv"
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(rows)
    return p


def run(tmp_path, rows):
    return Adapter(file_path=write_csv(tmp_path, rows)).run()


def test_class_attributes():
    assert issubclass(Adapter, AdapterBase)
    for attr in ("SOURCE_ID", "SOURCE_NAME", "PROGRAM", "GEOGRAPHY", "CONFIDENCE"):
        assert getattr(Adapter, attr)
    assert Adapter.CONFIDENCE == "confirmed_black"
    assert set(Adapter.FIELD_MAP.values()) <= set(BBRT_FIELDS)


def test_filters_only_black_american(tmp_path):
    recs = run(tmp_path, [
        row("Black Co", vid="A1"),
        row("Hispanic Co", cls="Hispanic American", vid="A2"),
        row("Asian Co", cls="Asian Pacific American and Pacific Islander", vid="A3"),
        row("Iberian Co", cls="Iberian Peninsula", vid="A4"),
        row("Native Co", cls="American Indian", vid="A5"),
        row("Plain Co", cls=NO_MINORITY, vid="A6"),
    ])
    assert [r["business_name"] for r in recs] == ["Black Co"]


def test_accepts_str_path(tmp_path):
    p = write_csv(tmp_path, [row("Black Co", vid="A1")])
    assert len(Adapter(file_path=str(p)).run()) == 1


def test_dedup_by_vendor_id_and_name(tmp_path):
    recs = run(tmp_path, [
        # same firm across three certification periods
        row("Acme LLC", vid="V1", date="2020-01-01", status="Expired"),
        row("Acme LLC", vid="V1", date="2022-01-01", status="Expired"),
        row("ACME, LLC", vid="V1", date="2024-01-01"),
        # same name, second vendorId, same period -> same firm
        row("Acme LLC", vid="V2", date="2022-01-01", status="Expired"),
        # renamed firm linked by vendorId
        row("Beta Cleaning Corp", vid="V3", date="2021-01-01", status="Expired"),
        row("Beta Services Corp", vid="V3", date="2023-01-01"),
    ])
    assert len(recs) == 2
    acme = next(r for r in recs if r["business_name"].upper().startswith("ACME"))
    assert acme["business_name"] == "ACME, LLC"  # most recent row wins
    assert acme["source_fields"]["source_row_count"] == "4"
    assert acme["source_fields"]["vendor_ids"] == "V1; V2"
    beta = next(r for r in recs if r["business_name"].startswith("Beta"))
    assert beta["business_name"] == "Beta Services Corp"


def test_firm_included_if_any_row_black(tmp_path):
    recs = run(tmp_path, [
        row("Mixed Co", vid="M1", date="2021-01-01", status="Expired"),
        row("Mixed Co", cls=NO_MINORITY, vid="M1", date="2025-01-01",
            business_address1="9 New Rd"),
    ])
    assert len(recs) == 1
    r = recs[0]
    assert r["address_street"] == "9 New Rd"
    assert r["source_fields"]["black_american_row_count"] == "1"


def test_field_mapping(tmp_path):
    recs = run(tmp_path, [row(
        "  Mapped Co  ", vid="abc-123", zip="06106-1234",
        location="POINT (-72.68588 41.74832)", product="Cleaning services",
    )])
    r = recs[0]
    assert set(BBRT_FIELDS) <= set(r)
    assert r["business_name"] == "Mapped Co"
    assert r["business_id"] == "ct_das_y4ub-e4dd:ABC-123"
    assert r["address_street"] == "1 Main St"
    assert r["address_city"] == "Hartford"
    assert r["address_state"] == "CT"
    assert r["address_zip"] == "06106"
    assert r["latitude"] == "41.74832" and r["longitude"] == "-72.68588"
    assert r["naics_code"] == "561720"
    assert r["industry"] == "Janitorial Services"
    assert r["certification"] == "MBE"
    assert r["description"] == "Cleaning services"
    assert r["data_source"] == Adapter.SOURCE_NAME
    assert r["last_verified"] == datetime.date.today().isoformat()
    sf = r["source_fields"]
    assert sf["status"] == "Certified"
    assert sf["zip_raw"] == "06106-1234"
    assert "vendorname" not in sf


def test_row_without_vendor_id(tmp_path):
    recs = run(tmp_path, [row("No Link LLC", vid="")])
    assert len(recs) == 1
    assert recs[0]["business_id"] == "ct_das_y4ub-e4dd:NOLINKLLC"


def test_empty_file(tmp_path):
    assert run(tmp_path, []) == []


@pytest.mark.parametrize("raw,expected", [
    ("06103", "06103"), ("06103-1234", "06103"), ("6103", "06103"),
    ("06479-", "06479"), ("CT", ""), ("", ""), ("060926", "06092"),
])
def test_normalize_zip(raw, expected):
    assert normalize_zip(raw) == expected


def test_parse_point():
    assert parse_point("POINT (-73.25911 41.3498)") == ("41.3498", "-73.25911")
    assert parse_point("") == ("", "")
