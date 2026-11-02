import datetime

import pytest

from adapter import Adapter
from adapter_base import AdapterBase, BBRT_FIELDS

HEADER = ('"Company Name","DBA Name","Owner First","Owner Last","Physical Address","City",'
          '"State","Zip","Mailing Address","City","State","Zip","Phone","Fax","Email","Website",'
          '"Agency","Certification Type","Ethnicity","Gender","Capability","Category","HUB?",'
          '"Re-Evaluation Status","Commodity Codes",')

PREAMBLE = ('Certified Directory\r\nAs of 6/14/2026 1:25:36 PM\r\nResults filtered by search parameters\r\n'
            '\r\n"The information provided in this file is not to be used for unsolicited advertising, '
            'spam, or any other unauthorized use."\r\n\r\n')

FOOTER = '\r\n\r\nGenerated from the B2Gnow System.\r\n'


def row(name, cert, eth, phone="713-555-0100", codes="", category="", owner=("Ann", "Lee"),
        website="http://www.example.com", agency="Houston", street="1 Main St"):
    vals = [name, "", owner[0], owner[1], street, "Houston", "TX", "\t77002",
            street, "Houston", "TX", "\t77002", phone, "", "a@example.com", website,
            agency, cert, eth, "Female", "Consulting", category, "", "", codes]
    return ",".join('"' + v.replace('"', '""') + '"' for v in vals) + ","


def write(tmp_path, rows, encoding="cp1252"):
    p = tmp_path / "dir.csv"
    p.write_bytes((PREAMBLE + HEADER + "\r\n" + "\r\n".join(rows) + FOOTER).encode(encoding))
    return p


def test_contract(tmp_path):
    a = Adapter(file_path=str(write(tmp_path, [row("A LLC", "MBE", "Black")])))
    assert isinstance(a, AdapterBase)
    for attr in ("SOURCE_ID", "SOURCE_NAME", "PROGRAM", "GEOGRAPHY", "CONFIDENCE"):
        assert getattr(Adapter, attr)
    assert Adapter.CONFIDENCE == "confirmed_black"
    recs = a.run()
    assert len(recs) == 1
    r = recs[0]
    assert set(BBRT_FIELDS) <= set(r)
    assert r["last_verified"] == datetime.date.today().isoformat()
    assert r["data_source"] == Adapter.SOURCE_NAME


def test_filter_keeps_black_and_black_american_only(tmp_path):
    p = write(tmp_path, [
        row("Black Co", "MBE", "Black"),
        row("LGBT Co", "LGBTBE", "Black American", agency="Houston LGBT"),
        row("Hisp Co", "MBE", "Hispanic"),
        row("Hisp Am Co", "DBE", "Hispanic American"),
        row("Cauc Co", "WBE", "Caucasian"),
        row("Asian Co", "MBE", "Asian"),
        row("Other Co", "MBE", "Other Ethnicity"),
        row("Native Co", "MBE", "Native American"),
    ])
    names = {r["business_name"] for r in Adapter(file_path=p).run()}
    assert names == {"Black Co", "LGBT Co"}


def test_dedup_one_record_per_firm_with_merged_certs(tmp_path):
    p = write(tmp_path, [
        row("Acme LLC", "MBE", "Black", phone=""),
        row("Acme LLC", "SBE", "Black", phone="713-555-0199"),
        row("ACME  LLC", "WBE", "Black", codes="611710 - Educational support services; "
                                           "541611 - Consulting", category="Other Services"),
        row("Beta Inc", "MBE", "Black"),
    ])
    a = Adapter(file_path=p)
    recs = a.run()
    assert a.rows_read == 4
    assert len(recs) == 2
    acme = next(r for r in recs if r["business_name"] == "Acme LLC")
    assert acme["certification"] == "MBE; SBE; WBE"
    assert acme["phone"] == "713-555-0199"  # filled from a later row
    assert acme["naics_code"] == "611710; 541611"
    assert acme["industry"] == "Other Services"
    assert acme["source_fields"]["Source Row Count"] == "3"
    assert len({r["business_id"] for r in recs}) == 2


def test_firm_with_mixed_ethnicity_rows_is_kept(tmp_path):
    p = write(tmp_path, [
        row("Mixed LLC", "SBE", "Caucasian"),
        row("Mixed LLC", "LGBTBE", "Black American", agency="Houston LGBT"),
    ])
    recs = Adapter(file_path=p).run()
    assert len(recs) == 1
    assert recs[0]["certification"] == "LGBTBE"


def test_field_mapping_and_cleanup(tmp_path):
    p = write(tmp_path, [row("Smith’s Group\t", "MBE", "Black", owner=("Jo", "Smith"),
                             website="http://https://smith.example.com/")])
    r = Adapter(file_path=p).run()[0]
    assert r["business_name"] == "Smith’s Group"
    assert r["owner_name"] == "Jo Smith"
    assert r["address_street"] == "1 Main St"
    assert r["address_city"] == "Houston"
    assert r["address_state"] == "TX"
    assert r["address_zip"] == "77002"  # leading tab removed
    assert r["website"] == "https://smith.example.com/"
    assert r["email"] == "a@example.com"
    assert r["description"] == "Consulting"
    sf = r["source_fields"]
    assert sf["Mailing City"] == "Houston" and sf["Mailing Zip"] == "77002"
    assert sf["Ethnicity"] == "Black"
    assert "business_name" not in sf and "Company Name" not in sf


def test_utf8_input_also_reads(tmp_path):
    p = write(tmp_path, [row("Café – Co", "MBE", "Black")], encoding="utf-8")
    assert Adapter(file_path=p).run()[0]["business_name"] == "Café – Co"


def test_empty_directory(tmp_path):
    assert Adapter(file_path=write(tmp_path, [])).run() == []
