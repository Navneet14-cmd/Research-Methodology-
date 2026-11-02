import json, statistics, sys, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from collections import Counter, defaultdict

R = json.load(open(sys.argv[1])); OUT = sys.argv[2]; os.makedirs(OUT, exist_ok=True)
C = R["configs"]
PROV = ["AWS", "Azure", "GCP"]
COL = {"Azure": "#2a78d6", "AWS": "#eb6834", "GCP": "#1baf7a"}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({"font.family": "serif", "font.serif": ["STIXGeneral"], "mathtext.fontset": "stix",
                     "font.size": 8, "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
                     "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.5, "axes.axisbelow": True,
                     "savefig.bbox": "tight", "savefig.pad_inches": 0.02})
W = 3.45
extra = {}

# ---- Fig 2: LII by provider (box + jitter)
import random; random.seed(1)
fig, ax = plt.subplots(figsize=(W, 2.1))
data = [[c["lii"] for c in C if c["provider"] == p] for p in PROV]
bp = ax.boxplot(data, orientation='horizontal', widths=0.5, patch_artist=True, showfliers=False,
                medianprops=dict(color=INK, linewidth=1.2), whiskerprops=dict(color=INK2, linewidth=0.8),
                capprops=dict(color=INK2, linewidth=0.8))
for patch, p in zip(bp["boxes"], PROV):
    patch.set_facecolor(COL[p] + "33"); patch.set_edgecolor(COL[p]); patch.set_linewidth(1)
for i, (p, d) in enumerate(zip(PROV, data), start=1):
    ax.scatter(d, [i + random.uniform(-0.18, 0.18) for _ in d], s=4, color=COL[p], alpha=0.45, linewidths=0)
ax.set_yticks([1, 2, 3], [f"{p}\n(n={len(d)})" for p, d in zip(PROV, data)])
ax.set_xlabel("Lock-In Index (0–100)"); ax.grid(axis="y", visible=False); ax.set_xlim(0, 85)
fig.savefig(f"{OUT}/fig_provider.pdf"); plt.close(fig)

# ---- Fig 3: category share of resources vs share of lock-in mass
rq2 = R["rq2"]
cats = sorted([k for k in rq2 if rq2[k]["resources"] > 0], key=lambda k: rq2[k]["share_mass"])
cats = cats[-12:]
fig, ax = plt.subplots(figsize=(W, 3.0))
y = range(len(cats)); h = 0.38
ax.barh([i + h/2 for i in y], [100*rq2[k]["share_mass"] for k in cats], height=h, color="#2a78d6", label="Share of lock-in mass")
ax.barh([i - h/2 for i in y], [100*rq2[k]["share_res"] for k in cats], height=h, color="#b8b7b1", label="Share of resources")
ax.set_yticks(list(y), cats); ax.set_xlabel("Percent of corpus total"); ax.grid(axis="y", visible=False)
for i, k in enumerate(cats):
    ax.text(100*rq2[k]["share_mass"] + 0.4, i + h/2, f'{100*rq2[k]["share_mass"]:.1f}', va="center", fontsize=6.5, color=INK2)
ax.legend(frameon=False, loc="lower right", fontsize=7)
fig.savefig(f"{OUT}/fig_categories.pdf"); plt.close(fig)

# ---- Fig 4: architecture groups
G = ["K8s-centric", "IaaS/other", "Managed-PaaS-centric"]
fig, ax = plt.subplots(figsize=(W, 1.9))
gd = [[c["lii"] for c in C if c["group"] == g] for g in G]
bp = ax.boxplot(gd, orientation='horizontal', widths=0.5, patch_artist=True, showfliers=True,
                flierprops=dict(marker="o", markersize=2.5, markerfacecolor=INK2, markeredgewidth=0, alpha=0.5),
                medianprops=dict(color=INK, linewidth=1.2), whiskerprops=dict(color=INK2, linewidth=0.8),
                capprops=dict(color=INK2, linewidth=0.8))
for patch in bp["boxes"]:
    patch.set_facecolor("#cde2fb"); patch.set_edgecolor("#2a78d6")
ax.set_yticks([1, 2, 3], [f"{g}\n(n={len(d)})" for g, d in zip(G, gd)])
ax.set_xlabel("Lock-In Index (0–100)"); ax.grid(axis="y", visible=False); ax.set_xlim(0, 85)
fig.savefig(f"{OUT}/fig_groups.pdf"); plt.close(fig)

# ---- Fig 5: sensitivity
fig, ax = plt.subplots(figsize=(W, 1.8))
ax.hist(R["rhos"], bins=40, color="#2a78d6", edgecolor="#fcfcfb", linewidth=0.5, label="Configuration ranking")
ax.hist(R["cat_rhos"], bins=40, color="#eb6834", edgecolor="#fcfcfb", linewidth=0.5, alpha=0.85, label="Category ranking")
ax.axvline(R["rq4"]["rho_p05"], color=INK2, linestyle="--", linewidth=0.8)
ax.text(R["rq4"]["rho_p05"] - 0.01, ax.get_ylim()[1]*0.85, "5th pct.\n(configs)", ha="right", fontsize=6.5, color=INK2)
ax.set_xlabel("Spearman ρ with baseline ranking"); ax.set_ylabel("Trials"); ax.set_xlim(0.2, 1.0)
ax.legend(frameon=False, loc="upper left", fontsize=7)
fig.savefig(f"{OUT}/fig_sensitivity.pdf"); plt.close(fig)

# ---- Fig 6: exit egress cost at list price (no waiver)
def tiered(gb, free, tiers):
    cost, left = 0.0, max(0, gb - free)
    for size, price in tiers:
        take = min(left, size); cost += take*price; left -= take
        if left <= 0: break
    return cost
INF = 1e12
AWS = (100, [(10_240, .09), (40_960, .085), (102_400, .07), (INF, .05)])
GCP = (1, [(1_023, .12), (9_216, .11), (INF, .08)])          # Premium tier, to North America (GiB treated as GB)
AZ = (100, [(10_140, .085), (143_360, .065), (INF, .045)])     # routing-preference rates, as reported in [egressidx]
vols = [10**(k/20) for k in range(60, 121)]  # 1 TB .. 1 PB
fig, ax = plt.subplots(figsize=(W, 2.0))
for name, (f, t), ls in [("AWS", AWS, "-"), ("Azure", AZ, (0, (4, 2))), ("GCP", GCP, (0, (1, 1.5)))]:
    ax.plot([v/1000 for v in vols], [tiered(v, f, t) for v in vols], color=COL[name], linewidth=1.6, linestyle=ls, label=name)
ax.set_xscale("log"); ax.set_yscale("log")
ax.set_xlabel("Data volume moved out (TB)"); ax.set_ylabel("One-time egress cost (USD)")
ax.legend(frameon=False, fontsize=7)
fig.savefig(f"{OUT}/fig_egress.pdf"); plt.close(fig)
for v in (1_000, 10_000, 100_000, 1_000_000):
    extra[f"egress_{v}"] = {n: round(tiered(v, f, t)) for n, (f, t) in [("AWS", AWS), ("Azure", AZ), ("GCP", GCP)]}

# ---- extra stats
GLUE = {"IAM/identity", "Network core", "Governance/org", "Secrets/KMS", "Observability"}
extra["glue_mass"] = sum(rq2[k]["share_mass"] for k in GLUE)
extra["glue_res"] = sum(rq2[k]["share_res"] for k in GLUE)
# per-config glue fraction of the config's score
fr = []
for c in C:
    tot = sum(v for v in c["cats"].values())
    fr.append(sum(c["cats"].get(k, 0) for k in GLUE)/tot)
extra["glue_cfg_median_resource_frac"] = statistics.median(fr)
# size vs LII
def spearman(x, y):
    def rank(v):
        o = sorted(range(len(v)), key=lambda i: v[i]); r = [0]*len(v)
        for pos, i in enumerate(o): r[i] = pos
        return r
    rx, ry = rank(x), rank(y); n = len(x); mx, my = sum(rx)/n, sum(ry)/n
    return sum((a-mx)*(b-my) for a, b in zip(rx, ry))/((sum((a-mx)**2 for a in rx)*sum((b-my)**2 for b in ry))**.5)
extra["rho_size_lii"] = spearman([c["n"] for c in C], [c["lii"] for c in C])
extra["n_median"] = statistics.median([c["n"] for c in C])
# IAM share per provider
for p in PROV:
    cs = [c for c in C if c["provider"] == p]
    tot = sum(sum(c["cats"].values()) for c in cs)
    top = Counter()
    for c in cs: top.update(c["cats"])
    extra[f"top_{p}"] = [(k, round(v/tot, 3)) for k, v in top.most_common(4)]
# share of configs above 40
extra["share_above_40"] = sum(c["lii"] > 40 for c in C)/len(C)
json.dump(extra, open(f"{OUT}/extra.json", "w"), indent=1)
print(json.dumps(extra, indent=1))
