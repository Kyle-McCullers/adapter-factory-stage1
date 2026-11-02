"""Evaluate every completed run: import its adapter, run it on the raw file, compare to
the incumbent reference and to the other runs for the same source. Writes
results/runs.json and prints a summary table."""
import importlib.util, json, sys, traceback, collections, re
from pathlib import Path
P = Path("/Users/Shared/orgsci-rebuild-pilot")
RAW = {"houston": "houston_directory_2026-06-14.csv", "atlanta": "atlanta_directory_2026-06-14.xls",
       "ct": "ct_das_y4ub-e4dd_2026-10-15.csv"}
import unicodedata
_C1 = {0x91: "'", 0x92: "'", 0x93: '"', 0x94: '"', 0x96: "-", 0x97: "-", 0x85: " ", 0xa0: " "}
def norm(s):
    """Lowercase; map C1 control bytes left by a latin-1 decode of cp1252 text to their cp1252
    meaning; unify curly quotes/dashes; collapse all whitespace. Encoding choice is recorded
    separately and must not count as a construction disagreement."""
    s = unicodedata.normalize("NFKC", (s or ""))
    s = "".join(_C1.get(ord(c), c) for c in s)
    s = s.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"').replace("\u2013", "-").replace("\u2014", "-")
    return re.sub(r"[\s\u00a0\u0085]+", " ", s).strip().lower()
def load_adapter(run):
    spec = importlib.util.spec_from_file_location(f"adapter_{run.name}", run / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(run))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.pop(0)
    return mod.Adapter
out = {}
for run in sorted(P.glob("runs/*")):
    src = run.name.split("_")[0]
    rec = {"run": run.name, "source": src, "adapter_exists": (run / "adapter.py").exists(),
           "notes_exists": (run / "NOTES.md").exists(), "tests_exist": (run / "test_adapter.py").exists()}
    if (run / "result.json").exists():
        r = json.loads((run / "result.json").read_text())
        u = r.get("usage", {})
        rec.update(cost_usd=r.get("total_cost_usd"), turns=r.get("num_turns"), duration_s=round(r.get("duration_ms", 0) / 1000),
                   input_tokens=u.get("input_tokens"), cache_read=u.get("cache_read_input_tokens"),
                   cache_create=u.get("cache_creation_input_tokens"), output_tokens=u.get("output_tokens"),
                   is_error=r.get("is_error"), model_usage=list(r.get("modelUsage", {}).keys()))
    if rec["adapter_exists"]:
        try:
            A = load_adapter(run)
            recs = A(file_path=str(run / "raw" / RAW[src])).run()
            rec["n_records"] = len(recs)
            rec["names"] = sorted({norm(x.get("business_name")) for x in recs})
            rec["n_unique_names"] = len(rec["names"])
            rec["confidence"] = getattr(A, "CONFIDENCE", None)
            rec["field_map"] = getattr(A, "FIELD_MAP", None)
            rec["nonempty_fields"] = sorted({k for x in recs for k, v in x.items() if v and k != "source_fields"})
        except Exception:
            rec["run_error"] = traceback.format_exc()[-800:]
    out[run.name] = rec
ref = {s: json.loads((P / f"results/reference/{s}.json").read_text()) for s in RAW}
for name, rec in out.items():
    if "names" in rec:
        R = {norm(x) for x in ref[rec["source"]]["names"]}; N = set(rec["names"])
        rec["vs_incumbent"] = {"incumbent_n": len(R), "only_in_run": len(N - R),
                               "only_in_incumbent": len(R - N), "jaccard": round(len(N & R) / max(1, len(N | R)), 4)}
by_src = collections.defaultdict(list)
for rec in out.values(): by_src[rec["source"]].append(rec)
for src, recs in by_src.items():
    done = [r for r in recs if "names" in r]
    for a in done:
        a["vs_other_runs"] = {b["run"]: round(len(set(a["names"]) & set(b["names"])) / max(1, len(set(a["names"]) | set(b["names"]))), 4)
                              for b in done if b is not a}
json.dump(out, open(P / "results/runs.json", "w"), indent=1)
print(f"{'run':20} {'adapter':7} {'n_rec':>6} {'uniq':>6} {'inc':>6} {'+run':>5} {'+inc':>5} {'jac':>6} {'cost':>6} {'turns':>5} {'min':>4}")
for name, r in out.items():
    v = r.get("vs_incumbent", {})
    print(f"{name:20} {str(r['adapter_exists']):7} {str(r.get('n_records','ERR')):>6} {str(r.get('n_unique_names','')):>6} {str(v.get('incumbent_n','')):>6} "
          f"{str(v.get('only_in_run','')):>5} {str(v.get('only_in_incumbent','')):>5} {str(v.get('jaccard','')):>6} "
          f"{str(round(r.get('cost_usd') or 0,2)):>6} {str(r.get('turns','')):>5} {str(round((r.get('duration_s') or 0)/60)):>4}")
