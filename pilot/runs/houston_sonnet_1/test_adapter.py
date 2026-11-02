import csv

from adapter import Adapter

HEADER = ["Company Name", "DBA Name", "Owner First", "Owner Last", "Physical Address", "City",
          "State", "Zip", "Mailing Address", "City", "State", "Zip", "Phone", "Fax", "Email",
          "Website", "Agency", "Certification Type", "Ethnicity", "Gender", "Capability",
          "Category", "HUB?", "Re-Evaluation Status", "Commodity Codes", ""]


def row(name, eth, cert="MBE", first="A", last="B", phone="1", zip_="\t77001"):
    r = [""] * 26
    r[0], r[2], r[3], r[4], r[5], r[6], r[7] = name, first, last, "1 Main", "Houston", "TX", zip_
    r[12], r[17], r[18] = phone, cert, eth
    r[24] = "541611 - Admin"
    return r


def build(tmp_path, rows):
    p = tmp_path / "d.csv"
    with open(p, "w", encoding="cp1252", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Certified Directory"])
        w.writerow([])
        w.writerow(["As of today"])
        w.writerow([])
        w.writerow(["note"])
        w.writerow([])
        w.writerow(HEADER)
        w.writerows(rows)
        w.writerow([])
        w.writerow(["Generated from the B2Gnow System."])
    return p


def test_filter_and_dedup(tmp_path):
    p = build(tmp_path, [
        row("Acme LLC", "Black", "MBE"),
        row("Acme LLC", "Black", "SBE", phone=""),
        row("Acme LLC", "Black American", "LGBTBE"),
        row("Other Co", "Hispanic"),
        row("Third Co", "Other Ethnicity"),
        row("Fourth", "Black", first="C", last="D"),
    ])
    recs = Adapter(file_path=p).run()
    assert sorted(r["business_name"] for r in recs) == ["Acme LLC", "Fourth"]
    acme = next(r for r in recs if r["business_name"] == "Acme LLC")
    assert acme["certification"] == "MBE, SBE, LGBTBE"
    assert acme["address_zip"] == "77001"
    assert acme["owner_name"] == "A B"


def test_normalized_name_and_distinct_owners(tmp_path):
    p = build(tmp_path, [
        row("Acme, LLC", "Black"),
        row("ACME LLC\t", "Black"),
        row("Acme LLC", "Black", first="Z", last="Q"),
    ])
    assert len(Adapter(file_path=p).run()) == 2


def test_schema_fields(tmp_path):
    from datetime import date
    r = Adapter(file_path=build(tmp_path, [row("X", "Black")])).run()[0]
    assert r["last_verified"] == date.today().isoformat()
    assert r["naics_code"].startswith("541611")
    assert "Mailing Address" in r["source_fields"]
    assert "Mailing Zip" in r["source_fields"]
