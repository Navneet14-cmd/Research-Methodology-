"""Checks that the freshly computed results match every number reported in the paper.

Usage: python3 src/verify_against_paper.py results
"""
import json, os, sys

RES = sys.argv[1]
R = json.load(open(os.path.join(RES, "results.json")))
EX = json.load(open(os.path.join(RES, "extra.json")))
lii = [c["lii"] for c in R["configs"]]
mean = sum(lii) / len(lii)

# (where in the paper, what, computed value, value printed in the paper, tolerance)
checks = [
    ("Abstract/Sec IV", "configurations", R["summary"]["n_configs"], 677, 0),
    ("Abstract/Sec IV", "resource declarations", R["summary"]["n_resources"], 8908, 0),
    ("Abstract/Sec IV", "distinct resource types", R["summary"]["n_types"], 844, 0),
    ("Abstract/Sec IV", "repositories", R["summary"]["n_repos"], 23, 0),
    ("Sec IV", "unclassified share (%)", 100 * R["summary"]["unclassified_share"], 1.3, 0.05),
    ("Sec IV", "median configuration size", EX["n_median"], 6, 0),
    ("Table II", "AWS configs", R["rq1"]["AWS"]["n"], 191, 0),
    ("Table II", "Azure configs", R["rq1"]["Azure"]["n"], 248, 0),
    ("Table II", "GCP configs", R["rq1"]["GCP"]["n"], 238, 0),
    ("Table II", "AWS mean LII", R["rq1"]["AWS"]["mean"], 38.6, 0.05),
    ("Table II", "Azure mean LII", R["rq1"]["Azure"]["mean"], 31.1, 0.05),
    ("Table II", "GCP mean LII", R["rq1"]["GCP"]["mean"], 31.8, 0.05),
    ("Table II", "AWS median LII", R["rq1"]["AWS"]["median"], 41.5, 0.05),
    ("Table II", "Azure median LII", R["rq1"]["Azure"]["median"], 27.2, 0.05),
    ("Table II", "GCP median LII", R["rq1"]["GCP"]["median"], 28.6, 0.05),
    ("Table II", "overall mean LII", mean, 33.5, 0.05),
    ("Sec V-A", "configs above LII 40 (%)", 100 * EX["share_above_40"], 27.2, 0.05),
    ("Sec V-A", "size vs LII Spearman rho", EX["rho_size_lii"], 0.13, 0.005),
    ("Sec V-B", "IAM share of lock-in mass (%)", 100 * R["rq2"]["IAM/identity"]["share_mass"], 21.1, 0.05),
    ("Sec V-B", "IAM share of resources (%)", 100 * R["rq2"]["IAM/identity"]["share_res"], 16.6, 0.05),
    ("Sec V-B", "IAM present in configs (%)", 100 * R["rq2"]["IAM/identity"]["prevalence"], 38.6, 0.05),
    ("Abstract/V-B", "glue share of resources (%)", 100 * EX["glue_res"], 59.7, 0.05),
    ("Abstract/V-B", "glue share of lock-in mass (%)", 100 * EX["glue_mass"], 52.7, 0.05),
    ("Table III", "K8s-centric configs", R["rq3"]["K8s-centric"]["n"], 47, 0),
    ("Table III", "K8s-centric median", R["rq3"]["K8s-centric"]["median"], 25.2, 0.05),
    ("Table III", "Managed-PaaS configs", R["rq3"]["Managed-PaaS-centric"]["n"], 173, 0),
    ("Table III", "Managed-PaaS median", R["rq3"]["Managed-PaaS-centric"]["median"], 41.9, 0.05),
    ("Table III", "Mann-Whitney U", R["rq3"]["test"]["U"], 642.0, 0.05),
    ("Table III", "Cliff's delta", R["rq3"]["test"]["cliffs_delta"], -0.84, 0.005),
    ("Sec V-D", "config ranking rho, median", R["rq4"]["rho_median"], 0.91, 0.005),
    ("Sec V-D", "config ranking rho, 5th pct", R["rq4"]["rho_p05"], 0.71, 0.005),
    ("Sec V-D", "category ranking rho, median", R["rq4"]["cat_rho_median"], 0.97, 0.005),
    ("Sec V-D", "K8s lower in % of trials", 100 * R["rq4"]["k8s_lower_share"], 99.7, 0.05),
    ("Sec VI", "egress 10 TB AWS ($)", EX["egress_10000"]["AWS"], 891, 1),
    ("Sec VI", "egress 10 TB Azure ($)", EX["egress_10000"]["Azure"], 842, 1),
    ("Sec VI", "egress 10 TB GCP ($)", EX["egress_10000"]["GCP"], 1110, 1),
]
ok = 0
print(f"{'Paper section':16s} {'Quantity':34s} {'Computed':>12s} {'In paper':>10s}  Result")
for where, what, got, paper, tol in checks:
    good = abs(got - paper) <= tol
    ok += good
    print(f"{where:16s} {what:34s} {got:12.3f} {paper:10} {'PASS' if good else 'FAIL'}")
print(f"\n{ok}/{len(checks)} checks passed")
sys.exit(0 if ok == len(checks) else 1)
