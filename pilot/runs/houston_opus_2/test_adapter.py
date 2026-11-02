import datetime

import pytest

from adapter import Adapter
from adapter_base import BBRT_FIELDS

HEADER = ('"Company Name","DBA Name","Owner First","Owner Last","Physical Address","City",'
          '"State","Zip","Mailing Address","City","State","Zip","Phone","Fax","Email",'
          '"Website","Agency","Certification Type","Ethnicity","Gender","Capability",'
          '"Category","HUB?","Re-Evaluation Status","Commodity Codes",')

BANNER = ("Certified Directory\r\nAs of 6/14/2026 1:25:36 PM\r\n"
          "Results filtered by search parameters\r\n\r\n"
          '"The information provided in this file is not to be used for unsolicited '
          'advertising, spam, or any other unauthorized use."\r\n\r\n')

FOOTER = "\r\n\r\nGenerated from the B2Gnow System.\r\n"


def row(name, cert, eth, agency="Houston", phone="713-555-0100", street="1 Main St",
        codes="", website="", first="Owner", last="Name", category="Other Services"):
    vals = [name, "", first, last, street, "Houston", "TX", "\t77002", "PO Box 1",
            "Houston", "TX", "\t77001", phone, "", "a@b.com", website, agency, cert,
            eth, "Female", "Consulting", category, "", "", codes]
    return ",".join('"%s"' % v.replace('"', '""') for v in vals) + ","


def write(tmp_path, rows, encoding="cp1252"):
    p = tmp_path / "dir.csv"
    p.write_bytes((BANNER + HEADER + "\r\n" + "\r\n".join(rows) + FOOTER).encode(encoding))
    return p


def run(tmp_path, rows, **kw):
    return Adapter(file_path=write(tmp_path, rows, **kw)).run()


def test_filters_black_and_black_american_only(tmp_path):
    recs = run(tmp_path, [
        row("Alpha LLC", "MBE", "Black"),
        row("Beta LLC", "LGBTBE", "Black American", agency="Houston LGBT"),
        row("Gamma LLC", "MBE", "Hispanic"),
        row("Delta LLC", "MBE", "Other Ethnicity"),
        row("Epsilon LLC", "WBE", "Caucasian"),
    ])
    assert sorted(r["business_name"] for r in recs) == ["Alpha LLC", "Beta LLC"]


def test_dedupes_one_record_per_firm_and_merges_certs(tmp_path):
    a = Adapter(file_path=write(tmp_path, [
        row("Alpha LLC", "MBE", "Black", phone=""),
        row("Alpha LLC", "SBE", "Black"),
        row("ALPHA, LLC", "WBE", "Black"),
        row("Alpha LLC", "SBE", "Black"),
    ]))
    recs = a.run()
    assert a.rows_read == 4
    assert len(recs) == 1
    r = recs[0]
    assert r["certification"] == "MBE; SBE; WBE"
    assert r["phone"] == "713-555-0100"  # back-filled from a later row
    assert r["source_fields"]["Source Row Count"] == "4"


def test_firm_with_any_black_row_is_included_and_conflict_kept(tmp_path):
    recs = run(tmp_path, [
        row("Mixed Inc", "MBE", "Hispanic", street="9 Other St"),
        row("Mixed Inc", "SBE", "Black"),
    ])
    assert len(recs) == 1
    assert recs[0]["source_fields"]["Ethnicity"] == "Hispanic; Black"
    assert recs[0]["address_street"] == "1 Main St"  # taken from the Black-flagged row


def test_field_mapping_and_cleaning(tmp_path):
    recs = run(tmp_path, [row(
        "Alpha LLC", "MBE", "Black", website="http://https://alpha.com/",
        codes="611710 - Educational support services; 541611 - Admin consulting")])
    r = recs[0]
    assert set(BBRT_FIELDS) <= set(r)
    assert r["owner_name"] == "Owner Name"
    assert r["address_zip"] == "77002"
    assert r["address_city"] == "Houston"
    assert r["source_fields"]["Mailing Zip"] == "77001"
    assert r["website"] == "https://alpha.com/"
    assert r["naics_code"] == "611710; 541611"
    assert r["industry"] == "Other Services"
    assert r["description"] == "Consulting"
    assert r["data_source"] == Adapter.SOURCE_NAME
    assert r["last_verified"] == datetime.date.today().isoformat()
    assert r["business_id"].startswith("houston-")


def test_cp1252_characters_decode(tmp_path):
    recs = run(tmp_path, [row("Vivian’s Academy", "MBE", "Black")])
    assert recs[0]["business_name"] == "Vivian’s Academy"


def test_utf8_input_also_works(tmp_path):
    recs = run(tmp_path, [row("Café Noir", "MBE", "Black")], encoding="utf-8")
    assert recs[0]["business_name"] == "Café Noir"


def test_business_id_stable_across_name_variants(tmp_path):
    r1 = run(tmp_path, [row("Alpha LLC", "MBE", "Black")])[0]
    r2 = run(tmp_path, [row("ALPHA, L.L.C", "MBE", "Black")])[0]
    assert r1["business_id"] == r2["business_id"]


def test_empty_directory(tmp_path):
    assert run(tmp_path, []) == []
