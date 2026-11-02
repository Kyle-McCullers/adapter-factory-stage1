import csv
import datetime

import pytest

from adapter import Adapter, normalize_zip
from adapter_base import AdapterBase, BBRT_FIELDS

COLUMNS = [
    "vendorname", "business_address1", "townnamecrosswalk_standardized_town", "zip", "county",
    "business_state", "certification_type", "class_description_detailed",
    "woman_owned_business_detailed", "race_gender_business_detailed", "disability_status_detailed",
    "active_date", "expiration_date", "active_year", "status", "link_to_company_detail_page",
    "product", "das_prequalified", "business_structure", "no_of_employees", "new_certification",
    "gs_code", "goods_and_services", "location",
]
LINK = "https://ct-gateway.formverse5.com/AUTOCENESERVER/WebApp/FillFormWO.aspx?templateId=x&vendorId="


def row(name, vid, race="Black American", date="2025-01-01", status="Certified", **kw):
    r = {c: "" for c in COLUMNS}
    r.update({
        "vendorname": name,
        "business_address1": "1 Main St",
        "townnamecrosswalk_standardized_town": "Hartford",
        "zip": "06106",
        "county": "NA",
        "certification_type": "MBE",
        "class_description_detailed": race,
        "active_date": f"{date}T00:00:00.000",
        "expiration_date": "2027-01-01T00:00:00.000",
        "status": status,
        "link_to_company_detail_page": LINK + vid if vid else "",
        "product": "Stuff",
        "gs_code": "238210",
        "goods_and_services": "Electrical Contractors",
        "location": "POINT (-72.68 41.76)",
    })
    r.update(kw)
    return r


def write_csv(tmp_path, rows):
    p = tmp_path / "sample.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(rows)
    return p


def run(tmp_path, rows):
    return Adapter(file_path=write_csv(tmp_path, rows)).run()


def test_class_attributes():
    assert issubclass(Adapter, AdapterBase)
    for attr in ("SOURCE_ID", "SOURCE_NAME", "PROGRAM", "GEOGRAPHY", "CONFIDENCE", "FIELD_MAP"):
        assert getattr(Adapter, attr)
    assert Adapter.CONFIDENCE == "confirmed_black"


def test_filters_to_black_american_only(tmp_path):
    recs = run(tmp_path, [
        row("Black Co", "A1"),
        row("Hispanic Co", "B1", race="Hispanic American"),
        row("None Co", "C1", race="No minority race/ethnicity identified"),
        row("Asian Co", "D1", race="Asian Pacific American and Pacific Islander"),
    ])
    assert [r["business_name"] for r in recs] == ["Black Co"]


def test_schema_and_mapping(tmp_path):
    (rec,) = run(tmp_path, [row("Black Co", "abc-1", zip="06106-1234")])
    assert set(BBRT_FIELDS) <= set(rec)
    assert rec["business_id"] == "ct_das:ABC-1"
    assert rec["address_street"] == "1 Main St"
    assert rec["address_city"] == "Hartford"
    assert rec["address_state"] == "CT"  # blank in source, inferred from 06 zip
    assert rec["address_zip"] == "06106"
    assert rec["naics_code"] == "238210"
    assert rec["industry"] == "Electrical Contractors"
    assert rec["certification"] == "MBE"
    assert rec["latitude"] == "41.76" and rec["longitude"] == "-72.68"
    assert rec["data_source"] == Adapter.SOURCE_NAME
    assert rec["last_verified"] == datetime.date.today().isoformat()
    assert rec["source_fields"]["status"] == "Certified"
    assert "vendorname" not in rec["source_fields"]


def test_dedup_certification_history_by_vendor_id(tmp_path):
    recs = run(tmp_path, [
        row("Black Co", "A1", date="2021-01-01", status="Expired", business_address1="Old St"),
        row("Black Co", "A1", date="2023-01-01", status="Expired", business_address1="Old St"),
        row("Black Co LLC", "a1", date="2025-01-01", business_address1="New St"),
    ])
    assert len(recs) == 1
    assert recs[0]["address_street"] == "New St"  # latest row wins
    assert recs[0]["source_fields"]["source_row_count"] == "3"


def test_dedup_fanned_out_vendor_ids_by_name(tmp_path):
    recs = run(tmp_path, [
        row("Shawn's LLC", "V1", date="2022-01-01", status="Expired"),
        row("SHAWNS LLC", "V2", date="2022-01-01", status="Expired"),
        row("Shawn's LLC", "V1", date="2024-01-01"),
    ])
    assert len(recs) == 1
    assert recs[0]["source_fields"]["vendor_ids"] == "V1;V2"


def test_firm_with_black_row_and_later_unidentified_row_is_kept(tmp_path):
    recs = run(tmp_path, [
        row("Krane Co", "K1", date="2023-01-01", status="Expired"),
        row("Krane Co", "K1", race="No minority race/ethnicity identified", date="2025-01-01"),
    ])
    assert len(recs) == 1
    assert recs[0]["source_fields"]["firm_latest_class_description"] == "No minority race/ethnicity identified"
    assert recs[0]["source_fields"]["class_description_detailed"] == "Black American"


def test_expired_firms_included(tmp_path):
    recs = run(tmp_path, [row("Old Co", "O1", status="Expired")])
    assert len(recs) == 1


def test_blank_fields_filled_from_older_black_rows(tmp_path):
    (rec,) = run(tmp_path, [
        row("Black Co", "A1", date="2021-01-01", gs_code="561720"),
        row("Black Co", "A1", date="2024-01-01", gs_code="", location=""),
    ])
    assert rec["naics_code"] == "561720"
    assert rec["latitude"] == "41.76"


def test_distinct_firms_stay_separate(tmp_path):
    recs = run(tmp_path, [row("Alpha LLC", "A1"), row("Beta LLC", "B1")])
    assert len(recs) == 2
    assert len({r["business_id"] for r in recs}) == 2


@pytest.mark.parametrize("raw,expected", [
    ("06106", "06106"), ("061061234", "06106"), ("06106-", "06106"),
    ("6106", "06106"), ("CT", ""), ("", ""), ("Ethnic Onl", ""),
])
def test_normalize_zip(raw, expected):
    assert normalize_zip(raw) == expected
