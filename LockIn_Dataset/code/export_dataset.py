"""Export the analysed dataset: CSV tables + raw Terraform sources of every analysed configuration."""
import csv, os, re, runpy, shutil, sys, json, subprocess
from collections import Counter

CORPUS, OUT = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
sys.argv = ["lii.py", CORPUS, os.path.join(HERE, "out")]
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    G = runpy.run_path(os.path.join(HERE, "lii.py"))
configs, categorise, provider_of, lii_resource, CATS, WEIGHTS = (
    G["configs"], G["categorise"], G["provider_of"], G["lii_resource"], G["CATS"], G["WEIGHTS"])
RES_RE, MOD_RE, SRC_RE = G["RES_RE"], G["MOD_RE"], G["SRC_RE"]

shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(os.path.join(OUT, "tables"))
os.makedirs(os.path.join(OUT, "terraform_sources"))

LIC = {"MIT": "MIT", "Apache": "Apache-2.0", "Mozilla": "MPL-2.0"}
def license_of(d):
    t = open(os.path.join(CORPUS, d, "LICENSE"), errors="ignore").read(600)
    if "Apache License" in t: return "Apache-2.0"
    if "Mozilla Public License" in t: return "MPL-2.0"
    if "MIT License" in t: return "MIT"
    if "Permission is hereby granted" in t: return "MIT-0"
    return "see LICENSE"

# ---- configurations.csv + resources.csv
cats_order = list(CATS)
def sub(p):
    parts = p.split("/", 1)
    return parts[1] if len(parts) > 1 else "."
with open(os.path.join(OUT, "tables", "configurations.csv"), "w", newline="") as f1, \
     open(os.path.join(OUT, "tables", "resources.csv"), "w", newline="") as f2:
    w1, w2 = csv.writer(f1), csv.writer(f2)
    w1.writerow(["config_id", "repository", "path", "provider", "architecture_group", "n_resources", "lii"] + [f"n_{c}" for c in cats_order])
    w2.writerow(["config_id", "repository", "path", "resource_type", "provider", "category", "A", "D", "E", "X", "resource_lii"])
    for i, c in enumerate(sorted(configs, key=lambda c: c["path"]), start=1):
        cid = f"C{i:04d}"; c["cid"] = cid
        k = Counter(categorise(t) for t in c["types"])
        w1.writerow([cid, c["repo"], sub(c["path"]), c["provider"], c["group"], len(c["types"]), round(c["lii"], 2)] + [k.get(x, 0) for x in cats_order])
        for t in c["types"]:
            cat = categorise(t); a, d, e, x = CATS[cat]
            w2.writerow([cid, c["repo"], sub(c["path"]), t, provider_of(t), cat, a, d, e, x, round(100 * lii_resource(cat), 1)])

# ---- rubric.csv
with open(os.path.join(OUT, "tables", "rubric.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["category", "A_api_proprietariness", "D_data_state_lock", "E_equivalence_gap", "X_egress_exposure", "resource_lii"])
    for cat, (a, d, e, x) in sorted(CATS.items(), key=lambda kv: -lii_resource(kv[0])):
        w.writerow([cat, a, d, e, x, round(100 * lii_resource(cat), 1)])
    w.writerow([]); w.writerow(["weights (A,D,E,X)"] + list(WEIGHTS))

# ---- category_summary.csv / provider_summary.csv / groups / sensitivity
R = json.load(open(os.path.join(HERE, "out", "results.json")))
with open(os.path.join(OUT, "tables", "category_summary.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["category", "resources", "share_of_resources_pct", "share_of_lockin_mass_pct", "configs_containing_pct", "resource_lii"])
    for cat, r in sorted(R["rq2"].items(), key=lambda kv: -kv[1]["share_mass"]):
        w.writerow([cat, r["resources"], round(100 * r["share_res"], 2), round(100 * r["share_mass"], 2), round(100 * r["prevalence"], 2), round(r["lii"], 1)])
with open(os.path.join(OUT, "tables", "provider_summary.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["provider", "configs", "mean", "median", "sd", "q1", "q3", "min", "max"])
    for p, r in R["rq1"].items():
        w.writerow([p, r["n"]] + [round(r[k], 2) for k in ("mean", "median", "sd", "q1", "q3", "min", "max")])
with open(os.path.join(OUT, "tables", "architecture_groups.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["group", "configs", "median", "mean"])
    for g, r in R["rq3"].items():
        if g != "test": w.writerow([g, r["n"], round(r["median"], 2), round(r["mean"], 2)])
    t = R["rq3"]["test"]; w.writerow([]); w.writerow(["Mann-Whitney K8s vs PaaS", f"U={t['U']}", f"z={t['z']:.2f}", f"p={t['p']:.2e}", f"cliffs_delta={t['cliffs_delta']:.3f}"])
with open(os.path.join(OUT, "tables", "sensitivity_trials.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["trial_sorted", "spearman_config_ranking", "spearman_category_ranking"])
    for i, (a, b) in enumerate(zip(R["rhos"], R["cat_rhos"]), 1): w.writerow([i, round(a, 4), round(b, 4)])
ex = json.load(open("/home/claude/paper/figs/extra.json"))
with open(os.path.join(OUT, "tables", "egress_exit_cost.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["volume_GB", "AWS_usd", "Azure_usd", "GCP_usd"])
    for v in (1000, 10000, 100000, 1000000):
        e = ex[f"egress_{v}"]; w.writerow([v, e["AWS"], e["Azure"], e["GCP"]])

# ---- raw Terraform sources for analysed configs (+ local modules they reference)
def dirs_used(path, depth=0, seen=None):
    path = os.path.realpath(path); seen = set() if seen is None else seen
    if path in seen or depth > 8 or not os.path.isdir(path): return seen
    seen.add(path)
    for fn in os.listdir(path):
        if fn.endswith(".tf"):
            txt = open(os.path.join(path, fn), errors="ignore").read()
            for body in MOD_RE.findall(txt):
                m = SRC_RE.search(body)
                if m and m.group(1).startswith((".", "/")):
                    dirs_used(os.path.join(path, m.group(1)), depth + 1, seen)
    return seen

used = set()
for c in configs: used |= dirs_used(os.path.join(CORPUS, c["path"]))
corpus_real = os.path.realpath(CORPUS); nfiles = 0
for d in sorted(used):
    rel = os.path.relpath(d, corpus_real)
    if rel.startswith(".."): continue
    for fn in os.listdir(d):
        if fn.endswith(".tf"):
            dst = os.path.join(OUT, "terraform_sources", rel); os.makedirs(dst, exist_ok=True)
            shutil.copy2(os.path.join(d, fn), dst); nfiles += 1

# ---- repositories.csv + licenses
repos_used = Counter(c["repo"] for c in configs)
with open(os.path.join(OUT, "tables", "repositories.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["repository", "url", "commit_sha", "license", "configs_included", "status"])
    for d in sorted(os.listdir(CORPUS)):
        repo = d.replace("_", "/", 1)
        sha = subprocess.run(["git", "-C", os.path.join(CORPUS, d), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        n = repos_used.get(repo, 0)
        status = "included" if n else ("excluded: tfvars-driven framework" if d == "aztfmod_terraform-azurerm-caf" else "no qualifying configuration (uses registry modules)")
        w.writerow([repo, f"https://github.com/{repo}", sha, license_of(d), n, status])
        if n:
            ld = os.path.join(OUT, "terraform_sources", d); os.makedirs(ld, exist_ok=True)
            shutil.copy2(os.path.join(CORPUS, d, "LICENSE"), os.path.join(ld, "LICENSE"))

print("configs", len(configs), "tf files", nfiles, "dirs", len(used))
