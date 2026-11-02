"""Run the incumbent BBRT adapters on the pilot raw files and save reference outputs.
The incumbent output is a human-reviewed build, NOT ground truth; it is one more build
to compare against."""
import csv, json, sys, io, collections
from pathlib import Path
from unittest.mock import patch, MagicMock
REPO = Path.home() / "Projects/blackbusinessresearchtable/scripts"
sys.path.insert(0, str(REPO))
P = Path("/Users/Shared/orgsci-rebuild-pilot")
RAW = P / "materials/raw"
OUT = P / "results/reference"
from adapters.houston_obo import HoustonOboAdapter
from adapters.atlanta_aabe import AtlantaAabeAdapter
from adapters.ct_das_smbe import CtDasSmbeAdapter
from pipeline.b2gnow_base import read_b2gnow_rows, locate

def save(src, recs, extra):
    keyed = sorted({(r["business_name"].strip().lower(), r["address_street"].strip().lower(), r["address_city"].strip().lower()) for r in recs})
    names = sorted({r["business_name"].strip().lower() for r in recs})
    json.dump({"source": src, "n_records": len(recs), "n_unique_names": len(names),
               "n_unique_name_street_city": len(keyed), "names": names, **extra},
              open(OUT / f"{src}.json", "w"), indent=1)
    print(src, "records", len(recs), "unique names", len(names), "unique name+street+city", len(keyed))

# Houston
f = RAW / "houston_directory_2026-06-14.csv"
rows = read_b2gnow_rows(f); col, _, data = locate(rows, "Ethnicity", f)
eth = collections.Counter(r[col["Ethnicity"]] if len(r) > col["Ethnicity"] else "<short row>" for r in data)
cert = collections.Counter(r[col["Certification Type"]] for r in data if len(r) > col["Certification Type"])
save("houston", HoustonOboAdapter(file_path=f).run(), {"data_rows": len(data), "ethnicity_values": dict(eth), "cert_values": dict(cert)})
print(" houston ethnicity:", dict(eth))

# Atlanta
f = RAW / "atlanta_directory_2026-06-14.xls"
rows = read_b2gnow_rows(f); col, _, data = locate(rows, "Certification Type", f)
cert = collections.Counter(r[col["Certification Type"]] for r in data if len(r) > col["Certification Type"])
save("atlanta", AtlantaAabeAdapter(file_path=f).run(), {"data_rows": len(data), "cert_values": dict(cert)})
print(" atlanta cert:", dict(cert))

# Connecticut (incumbent fetches live; feed it the captured file instead)
f = RAW / "ct_das_y4ub-e4dd_2026-10-15.csv"
text = f.read_text(encoding="utf-8")
resp = MagicMock(); resp.text = text; resp.raise_for_status = MagicMock()
with patch("requests.get", return_value=resp):
    recs = CtDasSmbeAdapter().run()
rdr = list(csv.DictReader(io.StringIO(text)))
cls = collections.Counter(r["class_description_detailed"] for r in rdr)
rg = collections.Counter(r["race_gender_business_detailed"] for r in rdr)
st = collections.Counter(r["status"] for r in rdr)
save("ct", recs, {"data_rows": len(rdr), "class_values": dict(cls), "race_gender_values": dict(rg), "status_values": dict(st)})
print(" ct class:", dict(cls)); print(" ct race_gender:", dict(rg)); print(" ct status:", dict(st))
