"""Build the disagreement map from results/runs.json and each run's NOTES.md.
Prints a per-source table (counts, agreement) and extracts the Filter / Deduplication /
Record count sections verbatim so the analyst can attribute each difference to a trap class."""
import json, re, collections
from pathlib import Path
P = Path("/Users/Shared/orgsci-rebuild-pilot")
R = json.load(open(P / "results/runs.json"))
def section(md, head):
    m = re.search(rf"^##\s*{head}.*?$(.*?)(?=^##\s|\Z)", md, re.S | re.M | re.I)
    return m.group(1).strip() if m else "(missing)"
by = collections.defaultdict(list)
for k, r in R.items(): by[r["source"]].append(r)
tot_cost = 0
for s, runs in by.items():
    print(f"\n==== {s.upper()} ====")
    print(f"{'run':18} {'firms':>6} {'vs_inc_jac':>10} {'cost$':>6} {'turns':>5} {'sec':>5} {'out_tok':>7}")
    for r in sorted(runs, key=lambda x: x["run"]):
        tot_cost += r.get("cost_usd") or 0
        print(f"{r['run']:18} {str(r.get('n_records','ERR')):>6} {str(r.get('vs_incumbent',{}).get('jaccard','')):>10} "
              f"{round(r.get('cost_usd') or 0,2):>6} {str(r.get('turns','')):>5} {str(r.get('duration_s','')):>5} {str(r.get('output_tokens','')):>7}")
    names = sorted(runs, key=lambda x: x["run"])
    print("pairwise Jaccard on firm-name sets:")
    for a in names:
        print("  ", a["run"], {k: v for k, v in a.get("vs_other_runs", {}).items()})
    for r in names:
        md = (P / "runs" / r["run"] / "NOTES.md").read_text() if (P / "runs" / r["run"] / "NOTES.md").exists() else ""
        print(f"\n--- {r['run']} FILTER ---\n{section(md,'Filter')[:1200]}")
        print(f"--- {r['run']} DEDUP ---\n{section(md,'Dedup')[:900]}")
print(f"\nTOTAL COST USD {round(tot_cost,2)}")
