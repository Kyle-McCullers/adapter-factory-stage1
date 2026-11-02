from adapter import Adapter

HEAD = ["Company Name", "DBA Name", "Owner First", "Owner Last", "Location", "Phone", "Fax", "Email",
        "Website", "Agency", "Certification Type", "Expiration", "Capability", "Market Area",
        "Supplier ID#", "Commodity Codes"]


def row(name, cert, email="a@x.com", exp="1/1/2030", sid="1", loc="Atlanta, GA"):
    return [name, "", "Jo", "Doe", loc, "555", "", email, "", "Atlanta", cert, exp, "cap", "", sid, "238210 - X"]


def make(tmp_path, rows):
    cells = lambda r, t: "<tr>" + "".join(f"<td>{t(c)}</td>" for c in r) + "</tr>"
    html = "<strong>Certified Directory</strong><br/><table>" + cells(HEAD, lambda c: f"<strong>{c}</strong>")
    html += "".join(cells(r, lambda c: c.replace("&", "&amp;")) for r in rows) + "</table>"
    p = tmp_path / "t.xls"
    p.write_text(html)
    return p


def test_filters_aabe_only(tmp_path):
    p = make(tmp_path, [row("A", "AABE"), row("B", "SBE", "b@x.com"), row("C", "HABE", "c@x.com"),
                        row("D", "NABE", "d@x.com")])
    recs = Adapter(file_path=p).run()
    assert [r["business_name"] for r in recs] == ["A"]
    assert recs[0]["certification"] == "AABE"


def test_dedup_same_firm_keeps_latest(tmp_path):
    p = make(tmp_path, [row("Foo, Inc.", "AABE", exp="1/1/2026", sid="1", loc="X, GA"),
                        row("FOO INC", "AABE", exp="1/1/2031", sid="2", loc="Y, GA")])
    recs = Adapter(file_path=p).run()
    assert len(recs) == 1 and recs[0]["address_city"] == "Y"


def test_shared_placeholder_id_not_merged(tmp_path):
    p = make(tmp_path, [row("A", "AABE", "a@x.com", sid="9999999"), row("B", "AABE", "b@x.com", sid="9999999")])
    assert len(Adapter(file_path=p).run()) == 2


def test_mapping_and_entities(tmp_path):
    p = make(tmp_path, [row("S & W Sales", "AABE", loc="East Point, GA")])
    r = Adapter(file_path=p).run()[0]
    assert r["business_name"] == "S & W Sales"
    assert r["owner_name"] == "Jo Doe"
    assert (r["address_city"], r["address_state"]) == ("East Point", "GA")
    assert r["last_verified"] and r["data_source"] == Adapter.SOURCE_NAME
    assert r["source_fields"]["Expiration"] == "1/1/2030"
