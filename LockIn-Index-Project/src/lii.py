"""Lock-In Index (LII) analyzer: the core of the project.

Reads Terraform code, finds every root configuration, extracts the cloud resources
it declares, classifies each resource into one of 21 service categories, scores it
with the rubric (Table I of the paper) and averages the scores into a 0-100 LII.
Then it runs the statistics behind RQ1-RQ4.

    LII(r) = 0.35*A + 0.25*D + 0.25*E + 0.15*X        (Eq. 1, one resource)
    LII(C) = 100 * mean of LII(r) over C's resources  (Eq. 2, one configuration)

Usage:  python3 src/lii.py <corpus_dir> <out_dir>
Writes: <out_dir>/results.json, <out_dir>/tables/{configurations,resources,rubric}.csv,
        <out_dir>/rules.json (rubric + rules, used by the demo)
"""
import json, os, re, sys, random, statistics
from collections import Counter, defaultdict

CORPUS, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)

RES_RE = re.compile(r'^\s*resource\s+"([A-Za-z0-9_\-]+)"\s+"[^"]+"', re.M)
MOD_RE = re.compile(r'^\s*module\s+"[^"]+"\s*\{(.*?)^\}', re.M | re.S)
SRC_RE = re.compile(r'^\s*source\s*=\s*"([^"]+)"', re.M)

EXCLUDE_REPOS = {"aztfmod_terraform-azurerm-caf"}  # tfvars-driven framework

# ---------------------------------------------------------------- taxonomy
# Each category: (A api proprietariness, D data/state lock, E equivalence gap, X egress/data gravity)
CATS = {
    "Compute (VM)":            (0.30, 0.20, 0.10, 0.20),
    "Block storage":           (0.20, 0.40, 0.10, 0.50),
    "Object storage":          (0.30, 0.30, 0.10, 0.90),
    "Network core":            (0.40, 0.00, 0.20, 0.00),
    "Edge (LB/DNS/CDN)":       (0.50, 0.00, 0.30, 0.10),
    "Managed Kubernetes":      (0.30, 0.10, 0.10, 0.10),
    "Container registry":      (0.20, 0.20, 0.10, 0.30),
    "Proprietary containers":  (0.70, 0.10, 0.40, 0.00),
    "Serverless functions":    (0.80, 0.10, 0.40, 0.00),
    "Relational DB":           (0.30, 0.40, 0.10, 0.70),
    "Proprietary NoSQL":       (0.90, 0.80, 0.70, 0.80),
    "Messaging/eventing":      (0.80, 0.30, 0.40, 0.20),
    "API/workflow":            (0.90, 0.20, 0.60, 0.00),
    "IAM/identity":            (0.90, 0.00, 0.50, 0.00),
    "Secrets/KMS":             (0.60, 0.30, 0.30, 0.00),
    "Observability":           (0.70, 0.20, 0.30, 0.10),
    "Analytics/AI":            (0.90, 0.70, 0.60, 0.90),
    "Governance/org":          (0.80, 0.00, 0.40, 0.00),
    "Kubernetes-native":       (0.10, 0.10, 0.00, 0.00),
    "Raw ARM API (azapi)":     (0.90, 0.20, 0.50, 0.10),
    "Other provider":          (0.60, 0.20, 0.40, 0.10),
}
WEIGHTS = (0.35, 0.25, 0.25, 0.15)

# ordered rules: (category, regex over resource type without provider prefix)
RULES = [
    ("Analytics/AI", r"(data_catalog|looker|sagemaker|bedrock|redshift|athena|glue|emr|kinesis_analytics|opensearch|elasticsearch|bigquery|dataflow|dataproc|dataplex|vertex|ml_|machine_learning|cognitive|synapse|databricks|data_factory|datafactory|lakeformation|quicksight|notebooks|composer|stream_analytics|kusto|search_service|comprehend|rekognition|translate|ai_)"),
    ("Proprietary NoSQL", r"(dynamodb|cosmosdb|firestore|bigtable|spanner|datastore|documentdb|docdb|keyspaces|timestream|neptune|memorydb|table_storage|storage_table)"),
    ("Relational DB", r"(^db_|_db_|rds|aurora|sql_database|sql_server|mssql|mysql|postgresql|mariadb|sql_user|sql_ssl|alloydb|elasticache|redis|memcache|database)"),
    ("Managed Kubernetes", r"(^eks_|kubernetes_cluster|container_cluster|container_node_pool|gke_|^aks)"),
    ("Container registry", r"(^ecr_|container_registry|artifact_registry)"),
    ("Proprietary containers", r"(^ecs_|apprunner|container_app|container_group|cloud_run|cloudrun|app_service|web_app|service_plan|elastic_beanstalk|app_engine|spring_cloud|batch_)"),
    ("Serverless functions", r"(^lambda_|function_app|cloudfunctions|cloudfunctions2|^function)"),
    ("API/workflow", r"(automation_account|integration_connectors|integrations_|application_integration|api_gateway|apigatewayv2|apigateway|api_management|apigee|^sfn_|logic_app|workflows|step_function|appsync|endpoints_)"),
    ("Messaging/eventing", r"(eventarc|managedkafka|managed_kafka|^sqs_|^sns_|eventbridge|cloudwatch_event|^kinesis|^mq_|^msk_|servicebus|eventhub|eventgrid|pubsub|^ses_|scheduler|cloud_tasks|cloud_scheduler|notification_hub|iot)"),
    ("Secrets/KMS", r"(disk_encryption_set|privateca|kms|key_vault|secret|secretsmanager|certificate|acm_|ssm_parameter|cloudhsm)"),
    ("IAM/identity", r"(^iam_|_iam_|_iam$|role_assignment|role_definition|user_assigned_identity|^azuread_|service_account|cognito|identity|federated|access_policy|^sso|workload_identity|organizations_policy|lake_permissions|^lambda_permission)"),
    ("Observability", r"(cloudwatch|monitor|log_analytics|application_insights|logging|^log_|_log_|alert|metric|dashboard|xray|diagnostic|flow_log|cloudtrail|insights)"),
    ("Governance/org", r"(essential_contacts|privileged_access_manager|^scc|access_context_manager|assured_workloads|resource_manager_lien|cloud_quotas|cloud_asset|organizations|organization|management_group|resource_group|^project$|^project_|folder|policy|config_rule|budget|tag|resource_provider|subscription|security_center|guardduty|securityhub|blueprint|consumption|billing)"),
    ("Object storage", r"(^s3|storage_notification|storage_bucket|storage_account|storage_container|storage_blob|storage_share|storage_management|data_lake|storage_object|storage_queue)"),
    ("Block storage", r"(ebs_|managed_disk|compute_disk|snapshot|^efs_|^fsx_|netapp|file_share|filestore|backup|compute_image|image$|shared_image)"),
    ("Compute (VM)", r"(compute_project_metadata|^instance|launch_template|launch_configuration|autoscaling|virtual_machine|vm_|compute_instance|instance_template|instance_group|spot|placement_group|key_pair|availability_set|dedicated_host|compute_region_instance|scale_set|ami)"),
    ("Edge (LB/DNS/CDN)", r"(^lb|^alb|^elb|load_balancer|lb_|route53|dns|cdn|cloudfront|front_door|frontdoor|application_gateway|traffic_manager|global_accelerator|forwarding_rule|target_pool|target_http|url_map|backend_service|health_check|ssl_policy|waf|wafv2|armor)"),
    ("Network core", r"(customer_gateway|private_link_service|vpc|subnet|route|security_group|network|nat|internet_gateway|eip|vpn|firewall|peering|private_endpoint|private_dns|public_ip|bastion|transit_gateway|router|address|interconnect|egress_only|dhcp|prefix_list|ec2_|express_route|virtual_hub|virtual_wan|ip_group|service_connect|vpc_endpoint)"),
]
RULES = [(c, re.compile(p)) for c, p in RULES]

UTILITY = {"modtm", "random", "null", "tls", "local", "time", "external", "archive", "http", "cloudinit", "terraform", "template", "assert", "github", "tfe"}

def provider_of(rtype):
    p = rtype.split("_", 1)[0]
    if p in ("aws", "awscc"): return "AWS"
    if p in ("azurerm", "azuread", "azapi"): return "Azure"
    if p in ("google",): return "GCP"
    if p in ("kubernetes", "kubectl", "helm"): return "K8s"
    if p in UTILITY: return "utility"
    return "other"

def categorise(rtype):
    prov = provider_of(rtype)
    if prov == "K8s":
        return "Kubernetes-native"
    if rtype.startswith("azapi_"):
        return "Raw ARM API (azapi)"
    if prov == "Azure" and rtype.startswith("azuread_"):
        return "IAM/identity"
    body = rtype.split("_", 1)[1] if "_" in rtype else rtype
    if body.startswith("beta_"): body = body[5:]
    for cat, rx in RULES:
        if rx.search(body):
            return cat
    return "Other provider"

def lii_resource(cat, w=WEIGHTS, cats=CATS):
    a, d, e, x = cats[cat]
    return w[0]*a + w[1]*d + w[2]*e + w[3]*x

# ---------------------------------------------------------------- parsing
_cache = {}
def dir_resources(path, depth=0, seen=None):
    """Resource types declared in a directory, resolving local module sources."""
    path = os.path.realpath(path)
    seen = set() if seen is None else seen
    if path in seen or depth > 8 or not os.path.isdir(path):
        return []
    seen.add(path)
    out = []
    for f in sorted(os.listdir(path)):
        if not f.endswith(".tf"): continue
        try:
            txt = open(os.path.join(path, f), encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        out += RES_RE.findall(txt)
        for body in MOD_RE.findall(txt):
            m = SRC_RE.search(body)
            if m and m.group(1).startswith((".", "/")):
                out += dir_resources(os.path.join(path, m.group(1)), depth+1, seen)
    return out

def has_tf(d):
    return any(f.endswith(".tf") for f in os.listdir(d))

def root_configs(repo_dir):
    """Root configurations: leaf example dirs, FAST stages, or the repo root for learn-* tutorials."""
    name = os.path.basename(repo_dir)
    roots = []
    if name.startswith("hashicorp_learn-"):
        return [repo_dir]
    if name == "terraform-google-modules_terraform-docs-samples":
        out = []
        for dp, dns, fns in os.walk(repo_dir):
            dns[:] = [d for d in dns if not d.startswith(".") and d not in ("test", "tests")]
            if any(f.endswith(".tf") for f in fns) and not any(has_tf(os.path.join(dp, d)) for d in dns):
                out.append(dp)
        return out
    if name == "aws-samples_serverless-patterns":
        out = []
        for pat in sorted(os.listdir(repo_dir)):
            pd = os.path.join(repo_dir, pat)
            if "terraform" not in pat.lower() or not os.path.isdir(pd):
                continue
            for dp, dns, fns in os.walk(pd):  # shallowest directory with .tf files
                dns.sort()
                if any(f.endswith(".tf") for f in fns):
                    out.append(dp); break
        return out
    for dp, dns, fns in os.walk(repo_dir):
        dns[:] = [d for d in dns if not d.startswith(".") and d not in ("test", "tests", "modules", "fixtures")]
        rel = os.path.relpath(dp, repo_dir).split(os.sep)
        if not any(f.endswith(".tf") for f in fns):
            continue
        in_examples = "examples" in rel
        in_fast = len(rel) == 3 and rel[0] == "fast" and rel[1] == "stages"
        if in_examples or in_fast:
            sub_tf = any(has_tf(os.path.join(dp, d)) for d in dns)
            if not sub_tf or in_fast:
                roots.append(dp)
    return roots

# ---------------------------------------------------------------- main
configs = []
for repo in sorted(os.listdir(CORPUS)):
    rdir = os.path.join(CORPUS, repo)
    if repo in EXCLUDE_REPOS or not os.path.isdir(rdir):
        continue
    for rc in root_configs(rdir):
        types = dir_resources(rc)
        scored = [t for t in types if provider_of(t) in ("AWS", "Azure", "GCP", "K8s", "other")]
        clouds = Counter(provider_of(t) for t in scored if provider_of(t) in ("AWS", "Azure", "GCP"))
        if len(scored) < 3 or not clouds:
            continue
        configs.append({
            "repo": repo.replace("_", "/", 1),
            "path": os.path.relpath(rc, CORPUS),
            "provider": clouds.most_common(1)[0][0],
            "multi_cloud": len(clouds) > 1,
            "types": scored,
        })

def score_config(c, w=WEIGHTS, cats=CATS):
    vals = [lii_resource(categorise(t), w, cats) for t in c["types"]]
    # rounded so that equal scores tie exactly on every Python version (and in the demo)
    return round(100 * sum(vals) / len(vals), 9)

for c in configs:
    c["cats"] = Counter(categorise(t) for t in c["types"])
    c["lii"] = score_config(c)
    c["n"] = len(c["types"])

print("configs", len(configs))
allres = [t for c in configs for t in c["types"]]
print("resources", len(allres), "distinct types", len(set(allres)))
unc = Counter(t for t in allres if categorise(t) == "Other provider")
print("unclassified share", sum(unc.values())/len(allres))
print("top unclassified", unc.most_common(25))

# RQ1 per provider
per_prov = defaultdict(list)
for c in configs: per_prov[c["provider"]].append(c["lii"])
rq1 = {}
for p, v in per_prov.items():
    v = sorted(v)
    q = lambda f: v[int(f*(len(v)-1))]
    rq1[p] = dict(n=len(v), mean=statistics.mean(v), median=statistics.median(v), sd=statistics.pstdev(v), q1=q(.25), q3=q(.75), min=v[0], max=v[-1])
print(json.dumps(rq1, indent=1))

# RQ2 category contribution (share of total lock-in mass) and prevalence
mass, count, prevalence = Counter(), Counter(), Counter()
for c in configs:
    for cat, k in c["cats"].items():
        mass[cat] += k * lii_resource(cat)
        count[cat] += k
        prevalence[cat] += 1
tot = sum(mass.values())
rq2 = {cat: dict(resources=count[cat], share_res=count[cat]/len(allres), share_mass=mass[cat]/tot,
                 prevalence=prevalence[cat]/len(configs), lii=100*lii_resource(cat)) for cat in CATS}
for cat in sorted(rq2, key=lambda k: -rq2[k]["share_mass"]):
    r = rq2[cat]; print(f"{cat:24s} res={r['resources']:5d} resshare={r['share_res']:.3f} mass={r['share_mass']:.3f} prev={r['prevalence']:.2f} lii={r['lii']:.1f}")

# RQ3 known-groups: K8s-centric vs serverless/NoSQL-centric
def group(c):
    k = c["cats"]
    k8s = k["Managed Kubernetes"] + k["Kubernetes-native"]
    svl = k["Serverless functions"] + k["Proprietary NoSQL"] + k["API/workflow"] + k["Proprietary containers"]
    if k8s > 0 and svl == 0: return "K8s-centric"
    if svl > 0 and k8s == 0: return "Managed-PaaS-centric"
    if k8s == 0 and svl == 0: return "IaaS/other"
    return "Mixed"
for c in configs: c["group"] = group(c)

def mann_whitney(a, b):
    allv = sorted([(v, 0) for v in a] + [(v, 1) for v in b])
    ranks, i = {}, 0
    rk = [0.0]*len(allv)
    while i < len(allv):
        j = i
        while j+1 < len(allv) and allv[j+1][0] == allv[i][0]: j += 1
        for k in range(i, j+1): rk[k] = (i+j)/2 + 1
        i = j+1
    r1 = sum(r for r, (v, g) in zip(rk, allv) if g == 0)
    n1, n2 = len(a), len(b)
    u1 = r1 - n1*(n1+1)/2
    mu, sigma = n1*n2/2, (n1*n2*(n1+n2+1)/12) ** 0.5
    z = (u1 - mu)/sigma
    import math
    p = math.erfc(abs(z)/2**0.5)
    cliff = (2*u1)/(n1*n2) - 1  # P(a>b)-P(a<b)
    return u1, z, p, cliff

grp = defaultdict(list)
for c in configs: grp[c["group"]].append(c["lii"])
rq3 = {g: dict(n=len(v), median=statistics.median(v), mean=statistics.mean(v)) for g, v in grp.items()}
u, z, p, d = mann_whitney(grp["K8s-centric"], grp["Managed-PaaS-centric"])
rq3["test"] = dict(U=u, z=z, p=p, cliffs_delta=d)
print(json.dumps(rq3, indent=1))

# RQ4 sensitivity: perturb weights (Dirichlet) and category scores (+-0.15)
def spearman(x, y):
    def rank(v):
        o = sorted(range(len(v)), key=lambda i: v[i]); r = [0]*len(v)
        for pos, i in enumerate(o): r[i] = pos
        return r
    rx, ry = rank(x), rank(y); n = len(x)
    mx, my = sum(rx)/n, sum(ry)/n
    cov = sum((a-mx)*(b-my) for a, b in zip(rx, ry))
    return cov / ((sum((a-mx)**2 for a in rx) * sum((b-my)**2 for b in ry)) ** 0.5)

random.seed(42)
base = [c["lii"] for c in configs]
base_cat_rank = [rq2[c]["share_mass"] for c in CATS]
rhos, cat_rhos, k8s_lower = [], [], 0
N = 1000
for _ in range(N):
    g = [random.gammavariate(4*w, 1) for w in WEIGHTS]; s = sum(g); w = tuple(x/s for x in g)
    cats = {k: tuple(min(1, max(0, v + random.uniform(-0.15, 0.15))) for v in vals) for k, vals in CATS.items()}
    sc = [score_config(c, w, cats) for c in configs]
    rhos.append(spearman(base, sc))
    m = Counter()
    for c in configs:
        for cat, k in c["cats"].items(): m[cat] += k*lii_resource(cat, w, cats)
    cat_rhos.append(spearman(base_cat_rank, [m[c] for c in CATS]))
    a = [s_ for s_, c in zip(sc, configs) if c["group"] == "K8s-centric"]
    b = [s_ for s_, c in zip(sc, configs) if c["group"] == "Managed-PaaS-centric"]
    if statistics.median(a) < statistics.median(b): k8s_lower += 1
rhos.sort(); cat_rhos.sort()
rq4 = dict(N=N, rho_median=rhos[N//2], rho_p05=rhos[int(.05*N)], rho_min=rhos[0],
           cat_rho_median=cat_rhos[N//2], cat_rho_p05=cat_rhos[int(.05*N)], k8s_lower_share=k8s_lower/N)
print(json.dumps(rq4, indent=1))

# top and bottom configurations
ranked = sorted(configs, key=lambda c: -c["lii"])
summary = dict(n_configs=len(configs), n_repos=len({c['repo'] for c in configs}), n_resources=len(allres),
               n_types=len(set(allres)), unclassified_share=sum(unc.values())/len(allres),
               multi_cloud=sum(c["multi_cloud"] for c in configs),
               provider_counts=Counter(c["provider"] for c in configs),
               repo_counts=Counter(c["repo"] for c in configs),
               group_counts=Counter(c["group"] for c in configs))
json.dump(dict(summary=summary, rq1=rq1, rq2=rq2, rq3=rq3, rq4=rq4, rhos=rhos, cat_rhos=cat_rhos,
               top=[(c["path"], round(c["lii"], 1), c["n"]) for c in ranked[:10]],
               bottom=[(c["path"], round(c["lii"], 1), c["n"]) for c in ranked[-10:]],
               configs=[{k: v for k, v in c.items() if k not in ("types",)} for c in configs]),
          open(os.path.join(OUT, "results.json"), "w"), indent=1, default=dict)
print(json.dumps(summary, indent=1, default=dict))

# ---------------------------------------------------------------- per-row tables
import csv
TD = os.path.join(OUT, "tables"); os.makedirs(TD, exist_ok=True)
def _sub(p):
    parts = p.split(os.sep, 1)
    return parts[1] if len(parts) > 1 else "."
cats_order = list(CATS)
with open(os.path.join(TD, "configurations.csv"), "w", newline="") as f1, \
     open(os.path.join(TD, "resources.csv"), "w", newline="") as f2:
    w1, w2 = csv.writer(f1), csv.writer(f2)
    w1.writerow(["config_id", "repository", "path", "provider", "architecture_group", "n_resources", "lii"] + [f"n_{c}" for c in cats_order])
    w2.writerow(["config_id", "repository", "path", "resource_type", "provider", "category", "A", "D", "E", "X", "resource_lii"])
    for i, c in enumerate(sorted(configs, key=lambda c: c["path"]), start=1):
        cid = f"C{i:04d}"
        w1.writerow([cid, c["repo"], _sub(c["path"]), c["provider"], c["group"], c["n"], round(c["lii"], 2)] + [c["cats"].get(x, 0) for x in cats_order])
        for t in c["types"]:
            cat = categorise(t); a, d, e, x = CATS[cat]
            w2.writerow([cid, c["repo"], _sub(c["path"]), t, provider_of(t), cat, a, d, e, x, round(100 * lii_resource(cat), 1)])
with open(os.path.join(TD, "rubric.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["category", "A_api_proprietariness", "D_data_state_lock", "E_equivalence_gap", "X_egress_exposure", "resource_lii"])
    for cat, (a, d, e, x) in sorted(CATS.items(), key=lambda kv: -lii_resource(kv[0])):
        w.writerow([cat, a, d, e, x, round(100 * lii_resource(cat), 1)])
json.dump(dict(weights=WEIGHTS, categories={k: list(v) for k, v in CATS.items()},
               rules=[[c, rx.pattern] for c, rx in RULES], utility=sorted(UTILITY)),
          open(os.path.join(OUT, "rules.json"), "w"), indent=1)
print("wrote", TD)
