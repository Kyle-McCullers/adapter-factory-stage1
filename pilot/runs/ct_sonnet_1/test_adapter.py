import csv
from datetime import date

from adapter import Adapter

COLS = ["vendorname", "business_address1", "townnamecrosswalk_standardized_town", "zip", "county",
        "business_state", "certification_type", "class_description_detailed", "status", "active_date",
        "link_to_company_detail_page", "product", "gs_code", "goods_and_services", "location"]


def row(name="Firm A", cls="Black American", vid="AAAA-1", status="Certified", active="2025-01-01", **kw):
    r = {c: "" for c in COLS}
    r.update(vendorname=name, class_description_detailed=cls, status=status, active_date=active,
             certification_type="MBE", zip="06106", location="POINT (-72.5 41.7)",
             link_to_company_detail_page=f"https://x/y?templateId=t&vendorId={vid}" if vid else "")
    r.update(kw)
    return r


def run(tmp_path, rows):
    p = tmp_path / "t.csv"
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    return Adapter(file_path=str(p)).run()


def test_filters_only_black(tmp_path):
    recs = run(tmp_path, [row("A"), row("B", cls="Hispanic American", vid="B1"),
                          row("C", cls="No minority race/ethnicity identified", vid="C1")])
    assert [r["business_name"] for r in recs] == ["A"]


def test_dedup_by_vendor_id_and_name(tmp_path):
    recs = run(tmp_path, [
        row("Firm A", status="Expired", active="2020-01-01"),
        row("Firm A", status="Certified", active="2025-01-01"),
        row("Firm A", vid="OTHER", status="Expired", active="2021-01-01"),  # second id, same name
        row("Renamed", vid="AAAA-1", status="Expired", active="2019-01-01"),  # same id, other name
        row("Firm Z", vid="Z"),
    ])
    assert len(recs) == 2
    a = next(r for r in recs if r["business_id"] == "AAAA-1")
    assert a["business_name"] == "Firm A" and a["source_fields"]["source_row_count"] == "4"


def test_firm_with_any_black_row_included_using_black_row(tmp_path):
    recs = run(tmp_path, [row("K", cls="No minority race/ethnicity identified", active="2026-01-01"),
                          row("K", status="Expired", active="2023-01-01")])
    assert len(recs) == 1 and recs[0]["source_fields"]["class_description_detailed"] == "Black American"


def test_mapping_and_cleanup(tmp_path):
    r = run(tmp_path, [row(zip="06605-", gs_code="238110", goods_and_services="Concrete", product="desc")])[0]
    assert r["address_zip"] == "06605"
    assert (r["latitude"], r["longitude"]) == ("41.7", "-72.5")
    assert r["naics_code"] == "238110" and r["industry"] == "Concrete" and r["description"] == "desc"
    assert r["certification"] == "MBE"
    assert r["last_verified"] == date.today().isoformat()
    assert "source_fields" in r


def test_zip_variants(tmp_path):
    zs = [("6106", "06106"), ("067053408", "06705-3408"), ("CT", ""), ("", "")]
    recs = run(tmp_path, [row(f"F{i}", vid=f"V{i}", zip=z) for i, (z, _) in enumerate(zs)])
    assert [r["address_zip"] for r in recs] == [e for _, e in zs]


def test_missing_location_and_vendor_id(tmp_path):
    r = run(tmp_path, [row(vid="", location="")])[0]
    assert r["latitude"] == "" and r["business_id"] == ""
