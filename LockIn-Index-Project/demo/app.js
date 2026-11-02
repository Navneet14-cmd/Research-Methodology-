/* Lock-In Index demo. Uses the same rules, rubric and data as src/lii.py (loaded from data.js). */
(function () {
  "use strict";
  const D = window.LII_DATA;
  const W0 = D.rules.weights.slice();
  const CATS0 = D.rules.categories;
  const RULES = D.rules.rules.map(([c, p]) => [c, new RegExp(p)]);
  const UTIL = new Set(D.rules.utility);
  const PROV_COL = { AWS: "var(--aws)", Azure: "var(--azure)", GCP: "var(--gcp)" };
  const GROUPS = ["K8s-centric", "IaaS/other", "Managed-PaaS-centric"];
  const GLUE = ["IAM/identity", "Network core", "Governance/org", "Secrets/KMS", "Observability"];
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const f1 = x => (Math.round(x * 10) / 10).toFixed(1);

  // ------------------------------------------------------------ the analyzer (port of src/lii.py)
  function providerOf(t) {
    const p = t.split("_")[0];
    if (p === "aws" || p === "awscc") return "AWS";
    if (p === "azurerm" || p === "azuread" || p === "azapi") return "Azure";
    if (p === "google") return "GCP";
    if (p === "kubernetes" || p === "kubectl" || p === "helm") return "K8s";
    if (UTIL.has(p)) return "utility";
    return "other";
  }
  function categorise(t) {
    const prov = providerOf(t);
    if (prov === "K8s") return "Kubernetes-native";
    if (t.startsWith("azapi_")) return "Raw ARM API (azapi)";
    if (prov === "Azure" && t.startsWith("azuread_")) return "IAM/identity";
    let body = t.includes("_") ? t.slice(t.indexOf("_") + 1) : t;
    if (body.startsWith("beta_")) body = body.slice(5);
    for (const [c, rx] of RULES) if (rx.test(body)) return c;
    return "Other provider";
  }
  const resScore = (cat, w = W0, cats = CATS0) => { const [a, d, e, x] = cats[cat]; return w[0] * a + w[1] * d + w[2] * e + w[3] * x; };
  function parseTF(text) {
    const out = []; const rx = /^\s*resource\s+"([A-Za-z0-9_\-]+)"\s+"[^"]+"/gm; let m;
    while ((m = rx.exec(text))) out.push(m[1]);
    return out;
  }

  // ------------------------------------------------------------ statistics
  const mean = v => v.reduce((a, b) => a + b, 0) / v.length;
  const sorted = v => v.slice().sort((a, b) => a - b);
  function median(v) { const s = sorted(v), n = s.length; return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2; }
  function q(v, f) { const s = sorted(v); return s[Math.floor(f * (s.length - 1))]; }
  function erfc(x) {
    if (x > 4) { const x2 = x * x; return Math.exp(-x2) / (x * Math.sqrt(Math.PI)) * (1 - 1 / (2 * x2) + 3 / (4 * x2 * x2) - 15 / (8 * x2 * x2 * x2)); }
    const t = 1 / (1 + 0.3275911 * x);
    return t * (0.254829592 + t * (-0.284496736 + t * (1.421413741 + t * (-1.453152027 + t * 1.061405429)))) * Math.exp(-x * x);
  }
  function mannWhitney(a, b) {
    const all = a.map(v => [v, 0]).concat(b.map(v => [v, 1])).sort((x, y) => x[0] - y[0]);
    const rk = new Array(all.length); let i = 0;
    while (i < all.length) { let j = i; while (j + 1 < all.length && all[j + 1][0] === all[i][0]) j++; for (let k = i; k <= j; k++) rk[k] = (i + j) / 2 + 1; i = j + 1; }
    let r1 = 0; all.forEach((x, k) => { if (x[1] === 0) r1 += rk[k]; });
    const n1 = a.length, n2 = b.length, u = r1 - n1 * (n1 + 1) / 2;
    const z = (u - n1 * n2 / 2) / Math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12);
    return { U: u, z, p: erfc(Math.abs(z) / Math.SQRT2), delta: 2 * u / (n1 * n2) - 1 };
  }
  function spearman(x, y) {
    const rank = v => { const o = v.map((_, i) => i).sort((a, b) => v[a] - v[b]); const r = new Array(v.length); o.forEach((i, p) => r[i] = p); return r; };
    const rx = rank(x), ry = rank(y), n = x.length, mx = mean(rx), my = mean(ry);
    let c = 0, sx = 0, sy = 0; for (let i = 0; i < n; i++) { c += (rx[i] - mx) * (ry[i] - my); sx += (rx[i] - mx) ** 2; sy += (ry[i] - my) ** 2; }
    return c / Math.sqrt(sx * sy);
  }
  const fmtP = p => { if (p >= 1e-4) return p.toFixed(3); const [m, e] = p.toExponential(1).split("e"); return `${m} × 10<sup>${e.replace("-", "−")}</sup>`; };
  const pctBelow = (v, x) => 100 * v.filter(y => y < x).length / v.length;

  // ------------------------------------------------------------ scoring the corpus
  const CFG = D.configs;
  function scoreAll(w = W0, cats = CATS0) {
    return CFG.map(c => { const v = c.resources.map(r => resScore(r[1], w, cats)); return Math.round(1e9 * 100 * pysum(v) / v.length) / 1e9; }); // same rounding as lii.py
  }
  // Python 3.12+ sum() uses Neumaier compensated summation; mirror it so tied scores tie exactly as in lii.py
  function pysum(v) { let s = 0, c = 0; for (const x of v) { const t = s + x; c += Math.abs(s) >= Math.abs(x) ? (s - t) + x : (x - t) + s; s = t; } return c ? s + c : s; }
  const BASE = scoreAll();
  function catMass(w = W0, cats = CATS0) {
    const mass = {}, count = {}, prev = {}; let tot = 0, totN = 0;
    CFG.forEach(c => {
      const seen = new Set();
      c.resources.forEach(([, cat]) => { const s = resScore(cat, w, cats); mass[cat] = (mass[cat] || 0) + s; count[cat] = (count[cat] || 0) + 1; tot += s; totN++; seen.add(cat); });
      seen.forEach(k => prev[k] = (prev[k] || 0) + 1);
    });
    return Object.keys(mass).map(k => ({ cat: k, mass: mass[k] / tot, res: count[k] / totN, prev: prev[k] / CFG.length, n: count[k], lii: 100 * resScore(k, w, cats) }))
      .sort((a, b) => b.mass - a.mass);
  }

  // ------------------------------------------------------------ tooltip
  const tip = $("#tip");
  function bindTips(root) {
    $$("[data-tip]", root).forEach(el => {
      el.addEventListener("mousemove", e => { tip.innerHTML = el.getAttribute("data-tip"); tip.style.opacity = 1; tip.style.left = Math.min(e.clientX + 14, innerWidth - 300) + "px"; tip.style.top = (e.clientY + 14) + "px"; });
      el.addEventListener("mouseleave", () => tip.style.opacity = 0);
    });
  }

  // ------------------------------------------------------------ charts (SVG)
  function boxPlot(groups, opts = {}) {
    const W = 760, rowH = 74, L = 170, R = 20, T = 10, B = 40, H = T + B + rowH * groups.length, xmax = opts.xmax || 85;
    const X = v => L + (W - L - R) * v / xmax;
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(opts.label || "Box plot")}">`;
    for (let t = 0; t <= xmax; t += 10) s += `<line x1="${X(t)}" x2="${X(t)}" y1="${T}" y2="${H - B}" stroke="var(--line)"/><text x="${X(t)}" y="${H - B + 18}" text-anchor="middle">${t}</text>`;
    s += `<text x="${(L + W - R) / 2}" y="${H - 6}" text-anchor="middle">Lock-In Index (0–100)</text>`;
    let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    groups.forEach((g, i) => {
      const y = T + rowH * i + rowH / 2, v = g.values.map(o => o.v), q1 = q(v, .25), q3 = q(v, .75), md = median(v), iqr = q3 - q1;
      const lo = Math.min(...v.filter(x => x >= q1 - 1.5 * iqr)), hi = Math.max(...v.filter(x => x <= q3 + 1.5 * iqr));
      s += `<text x="${L - 12}" y="${y - 3}" text-anchor="end" style="font-weight:600;fill:var(--ink)">${esc(g.label)}</text><text x="${L - 12}" y="${y + 13}" text-anchor="end">n = ${v.length}</text>`;
      s += `<line x1="${X(lo)}" x2="${X(hi)}" y1="${y}" y2="${y}" stroke="var(--muted)"/><line x1="${X(lo)}" x2="${X(lo)}" y1="${y - 8}" y2="${y + 8}" stroke="var(--muted)"/><line x1="${X(hi)}" x2="${X(hi)}" y1="${y - 8}" y2="${y + 8}" stroke="var(--muted)"/>`;
      s += `<rect x="${X(q1)}" y="${y - 17}" width="${Math.max(1, X(q3) - X(q1))}" height="34" rx="4" fill="${g.color}" fill-opacity=".16" stroke="${g.color}" stroke-width="1.5" data-tip="${esc(g.label)}<br>median ${f1(md)} · IQR ${f1(q1)}–${f1(q3)}"/>`;
      g.values.forEach(o => { s += `<circle cx="${X(o.v)}" cy="${y + (rnd() - .5) * 26}" r="3.2" fill="${g.color}" fill-opacity=".55" stroke="var(--surface)" stroke-width=".8" data-tip="${esc(o.t)}"/>`; });
      s += `<line x1="${X(md)}" x2="${X(md)}" y1="${y - 19}" y2="${y + 19}" stroke="var(--ink)" stroke-width="2.5"/>`;
    });
    return s + "</svg>";
  }
  function pairedBars(items) {
    const W = 760, rowH = 34, L = 190, R = 50, T = 6, B = 34, H = T + B + rowH * items.length;
    const xmax = Math.ceil(Math.max(...items.map(d => Math.max(d.mass, d.res))) * 100 / 5) * 5, X = v => L + (W - L - R) * v / xmax;
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Category shares">`;
    for (let t = 0; t <= xmax; t += 5) s += `<line x1="${X(t)}" x2="${X(t)}" y1="${T}" y2="${H - B}" stroke="var(--line)"/><text x="${X(t)}" y="${H - B + 16}" text-anchor="middle">${t}%</text>`;
    items.forEach((d, i) => {
      const y = T + i * rowH, tipTxt = `${esc(d.cat)}<br>${f1(100 * d.mass)}% of lock-in · ${f1(100 * d.res)}% of resources<br>${d.n} resources · in ${f1(100 * d.prev)}% of configs · ${f1(d.lii)} each`;
      s += `<text x="${L - 10}" y="${y + 19}" text-anchor="end" style="fill:var(--ink)">${esc(d.cat)}</text>`;
      s += `<rect x="${L}" y="${y + 5}" width="${Math.max(1, X(100 * d.mass) - L)}" height="12" rx="3" fill="var(--bar)" data-tip="${tipTxt}"/>`;
      s += `<rect x="${L}" y="${y + 19}" width="${Math.max(1, X(100 * d.res) - L)}" height="8" rx="2" fill="var(--bar2)" data-tip="${tipTxt}"/>`;
      s += `<text x="${X(100 * d.mass) + 6}" y="${y + 15}" style="font-size:11px">${f1(100 * d.mass)}</text>`;
    });
    return s + "</svg>";
  }
  function histogram(series, opts) {
    const W = 760, H = 300, L = 50, R = 20, T = 14, B = 44, lo = .2, hi = 1, bins = 40, bw = (hi - lo) / bins;
    const counts = series.map(sr => { const c = new Array(bins).fill(0); sr.values.forEach(v => { const k = Math.min(bins - 1, Math.max(0, Math.floor((v - lo) / bw))); c[k]++; }); return c; });
    const ymax = Math.ceil(Math.max(...counts.flat()) / 50) * 50, X = v => L + (W - L - R) * (v - lo) / (hi - lo), Y = v => H - B - (H - B - T) * v / ymax;
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Sensitivity histogram">`;
    for (let t = 0; t <= ymax; t += 50) s += `<line x1="${L}" x2="${W - R}" y1="${Y(t)}" y2="${Y(t)}" stroke="var(--line)"/><text x="${L - 8}" y="${Y(t) + 4}" text-anchor="end">${t}</text>`;
    for (let t = 2; t <= 10; t++) s += `<text x="${X(t / 10)}" y="${H - B + 18}" text-anchor="middle">${(t / 10).toFixed(1)}</text>`;
    s += `<text x="${(L + W - R) / 2}" y="${H - 6}" text-anchor="middle">Spearman ρ between perturbed and original ranking</text>`;
    counts.forEach((c, si) => c.forEach((n, k) => { if (n) s += `<rect x="${X(lo + k * bw) + 1 + si * (bw * (W - L - R) / (hi - lo) / 2 - 1)}" y="${Y(n)}" width="${bw * (W - L - R) / (hi - lo) / 2 - 1}" height="${Y(0) - Y(n)}" fill="${series[si].color}" data-tip="${esc(series[si].name)}: ${n} trials with ρ ${(lo + k * bw).toFixed(2)}–${(lo + (k + 1) * bw).toFixed(2)}"/>`; }));
    if (opts && opts.mark) s += `<line x1="${X(opts.mark)}" x2="${X(opts.mark)}" y1="${T}" y2="${H - B}" stroke="var(--ink2)" stroke-dasharray="4 3"/><text x="${X(opts.mark) - 6}" y="${T + 12}" text-anchor="end">5th percentile</text>`;
    return s + "</svg>";
  }
  function egressCost(gb, free, tiers) { let cost = 0, left = Math.max(0, gb - free); for (const [size, price] of tiers) { const t = Math.min(left, size); cost += t * price; left -= t; if (left <= 0) break; } return cost; }
  const EG = { AWS: [100, [[10240, .09], [40960, .085], [102400, .07], [1e12, .05]]], Azure: [100, [[10140, .085], [143360, .065], [1e12, .045]]], GCP: [1, [[1023, .12], [9216, .11], [1e12, .08]]] };
  function egressChart() {
    const W = 760, H = 320, L = 70, R = 20, T = 14, B = 44;
    const X = tb => L + (W - L - R) * Math.log10(tb) / 3, Y = c => H - B - (H - B - T) * (Math.log10(c) - 1.5) / 3.5;
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Egress cost">`;
    [1, 10, 100, 1000].forEach(t => s += `<line x1="${X(t)}" x2="${X(t)}" y1="${T}" y2="${H - B}" stroke="var(--line)"/><text x="${X(t)}" y="${H - B + 18}" text-anchor="middle">${t} TB</text>`);
    [100, 1000, 10000, 100000].forEach(c => s += `<line x1="${L}" x2="${W - R}" y1="${Y(c)}" y2="${Y(c)}" stroke="var(--line)"/><text x="${L - 8}" y="${Y(c) + 4}" text-anchor="end">$${c.toLocaleString()}</text>`);
    s += `<text x="${(L + W - R) / 2}" y="${H - 6}" text-anchor="middle">Data moved out (log scale)</text>`;
    Object.entries(EG).forEach(([p, [f, t]]) => {
      let d = ""; for (let k = 0; k <= 60; k++) { const tb = 10 ** (k / 20); d += (k ? "L" : "M") + X(tb).toFixed(1) + "," + Y(egressCost(tb * 1000, f, t)).toFixed(1); }
      s += `<path d="${d}" fill="none" stroke="${PROV_COL[p]}" stroke-width="2.5"/>`;
      [1, 10, 100, 1000].forEach(tb => { const c = egressCost(tb * 1000, f, t); s += `<circle cx="${X(tb)}" cy="${Y(c)}" r="5" fill="${PROV_COL[p]}" stroke="var(--surface)" stroke-width="1.5" data-tip="${p}, ${tb} TB: $${Math.round(c).toLocaleString()}"/>`; });
    });
    return s + "</svg>";
  }
  const legend = items => `<div class="legend">${items.map(([c, l]) => `<span><i style="background:${c}"></i>${esc(l)}</span>`).join("")}</div>`;

  // ------------------------------------------------------------ tabs
  function show(tab) {
    $$(".tabs button").forEach(b => b.setAttribute("aria-selected", b.dataset.tab === tab));
    $$(".panel").forEach(p => p.classList.toggle("active", p.id === tab));
    window.scrollTo({ top: 0 });
  }
  $$(".tabs button").forEach(b => b.addEventListener("click", () => show(b.dataset.tab)));
  $$("[data-goto]").forEach(b => b.addEventListener("click", () => { show(b.dataset.goto); if (b.dataset.rq) renderRQ(b.dataset.rq); }));

  // ------------------------------------------------------------ overview
  const S = D.summary, cm0 = catMass();
  const glueMass = cm0.filter(d => GLUE.includes(d.cat)).reduce((a, d) => a + d.mass, 0);
  const grp = g => CFG.map((c, i) => [c, BASE[i]]).filter(([c]) => c.group === g).map(([, v]) => v);
  $("#tiles").innerHTML = [[S.n_configs, "Terraform configurations"], [S.n_resources.toLocaleString(), "resource declarations"], [S.n_types, "distinct resource types"], [S.n_repos, "public GitHub repositories"], [f1(mean(BASE)), "mean Lock-In Index"]]
    .map(([b, s]) => `<div class="tile"><b>${b}</b><span>${s}</span></div>`).join("");
  const iam = cm0.find(d => d.cat === "IAM/identity");
  $("#f1").textContent = `Identity, networking, governance, secrets and monitoring make up ${f1(100 * glueMass)}% of all measured lock-in. IAM alone is the biggest single source, at ${f1(100 * iam.mass)}%.`;
  $("#f2").textContent = `Median LII is ${f1(median(grp("K8s-centric")))} for Kubernetes-centric configurations, against ${f1(median(grp("Managed-PaaS-centric")))} for designs built on managed PaaS services.`;
  $("#f3").textContent = `Across 1,000 random changes to the rubric, the ranking of configurations stayed ${f1(100 * D.rq4.rho_median)}% similar (median Spearman ρ = ${D.rq4.rho_median.toFixed(2)}).`;
  $("#footdata").textContent = `${S.n_configs} configurations from ${S.n_repos} repositories, cloned Oct. 29, 2026`;

  // ------------------------------------------------------------ analyze
  const SAMPLES = {
    serverless: `# Real example from aws-samples/serverless-patterns (dynamodb-streams-lambda-terraform)
resource "aws_dynamodb_table" "dynamodb_table_users" {
  name             = "UsersIds"
  hash_key         = "UserId"
  stream_enabled   = true
  stream_view_type = "NEW_AND_OLD_IMAGES"
}

resource "aws_lambda_function" "lambda_dynamodb_stream_handler" {
  function_name = "process-usersids-records"
  role          = aws_iam_role.iam_for_lambda.arn
  runtime       = "nodejs24.x"
}

resource "aws_lambda_event_source_mapping" "lambda_dynamodb" {
  event_source_arn = aws_dynamodb_table.dynamodb_table_users.stream_arn
  function_name    = aws_lambda_function.lambda_dynamodb_stream_handler.arn
}

resource "aws_iam_role" "iam_for_lambda" {
  name = "iam_for_lambda"
}

resource "aws_iam_role_policy" "dynamodb_read_log_policy" {
  role = aws_iam_role.iam_for_lambda.id
}
`,
    gke: `# Real example from hashicorp/learn-terraform-provision-gke-cluster
resource "google_compute_network" "vpc" {
  name                    = "\${var.project_id}-vpc"
  auto_create_subnetworks = "false"
}

resource "google_compute_subnetwork" "subnet" {
  name          = "\${var.project_id}-subnet"
  network       = google_compute_network.vpc.name
  ip_cidr_range = "10.10.0.0/24"
}

resource "google_container_cluster" "primary" {
  name                     = "\${var.project_id}-gke"
  remove_default_node_pool = true
  initial_node_count       = 1
}

resource "google_container_node_pool" "primary_nodes" {
  cluster    = google_container_cluster.primary.name
  node_count = var.gke_num_nodes
}
`,
    iaas: `# Illustrative web app on virtual machines
resource "aws_vpc" "main"            { cidr_block = "10.0.0.0/16" }
resource "aws_subnet" "public"       { vpc_id = aws_vpc.main.id }
resource "aws_security_group" "web"  { vpc_id = aws_vpc.main.id }
resource "aws_lb" "web"              { load_balancer_type = "application" }
resource "aws_launch_template" "web" { instance_type = "t3.micro" }
resource "aws_autoscaling_group" "web" { min_size = 2 }
resource "aws_db_instance" "app"     { engine = "postgres" }
resource "aws_s3_bucket" "assets"    { bucket = "my-app-assets" }
resource "random_password" "db"      { length = 20 }
`,
  };
  $("#tf").value = SAMPLES.serverless;
  $$("[data-sample]").forEach(b => b.addEventListener("click", () => { $("#tf").value = SAMPLES[b.dataset.sample]; $("#fileinfo").textContent = ""; analyze(); }));
  $("#run").addEventListener("click", analyze);
  $("#files").addEventListener("change", async e => {
    const files = Array.from(e.target.files); if (!files.length) return;
    const texts = await Promise.all(files.map(f => f.text()));
    $("#tf").value = texts.map((t, i) => `# ---- ${files[i].name}\n${t}`).join("\n");
    $("#fileinfo").textContent = `${files.length} file(s) loaded`;
    analyze();
  });
  function analyze() {
    const types = parseTF($("#tf").value);
    const kept = types.filter(t => providerOf(t) !== "utility"), ignored = types.filter(t => providerOf(t) === "utility");
    const box = $("#scorebox"), bd = $("#breakdown");
    if (!kept.length) { box.className = "scorebox empty"; box.innerHTML = `<p class="muted">No cloud resources found. Terraform resources look like <code>resource "aws_s3_bucket" "name" { ... }</code>.</p>`; bd.innerHTML = ""; return; }
    const rows = kept.map(t => { const cat = categorise(t); return { t, prov: providerOf(t), cat, sc: CATS0[cat], lii: 100 * resScore(cat) }; });
    const lii = mean(rows.map(r => r.lii)), pct = pctBelow(BASE, lii);
    const refs = [["K8s median", median(grp("K8s-centric"))], ["IaaS median", median(grp("IaaS/other"))], ["PaaS median", median(grp("Managed-PaaS-centric"))]];
    box.className = "scorebox";
    box.innerHTML = `<div class="muted small">Lock-In Index</div><div class="bignum">${f1(lii)}</div>
      <div class="scale" aria-hidden="true"><div class="mark" style="left:calc(${Math.min(100, lii)}% - 1px)"></div>${refs.map(([, v]) => `<span class="tick" style="left:${v}%"></span>`).join("")}</div>
      <p class="small muted" style="margin:-14px 0 12px">Dataset medians (grey ticks): ${refs.map(([l, v]) => `${l.replace(" median", "")} ${f1(v)}`).join(" · ")}</p>
      <p>Higher than <b>${f1(pct)}%</b> of the ${CFG.length} configurations in our dataset.</p>
      <div class="formula">LII = (${rows.map(r => f1(r.lii)).join(" + ")}) / ${rows.length} = ${f1(lii)}</div>
      ${rows.length < 3 ? `<p class="small muted" style="margin-top:8px">Note: the study only included configurations with at least 3 resources.</p>` : ""}
      ${ignored.length ? `<p class="small muted" style="margin-top:8px">Ignored ${ignored.length} utility resource(s) that create no cloud infrastructure: ${ignored.map(esc).join(", ")}.</p>` : ""}`;
    const top = rows.slice().sort((a, b) => b.lii - a.lii)[0];
    const [a, d, e, x] = top.sc;
    const byCat = {}; rows.forEach(r => byCat[r.cat] = (byCat[r.cat] || 0) + r.lii);
    const totMass = rows.reduce((s, r) => s + r.lii, 0);
    bd.innerHTML = `<h3>Step by step</h3>
      <div class="two"><div class="tablewrap"><table><thead><tr><th>Resource type</th><th>Category</th><th class="num">A</th><th class="num">D</th><th class="num">E</th><th class="num">X</th><th class="num">Score</th></tr></thead><tbody>
      ${rows.map(r => `<tr><td class="mono"><span class="dot" style="background:${PROV_COL[r.prov] || "var(--muted)"}"></span>${esc(r.t)}</td><td>${esc(r.cat)}</td>${r.sc.map(v => `<td class="num">${v}</td>`).join("")}<td class="num"><b>${f1(r.lii)}</b></td></tr>`).join("")}
      </tbody></table></div>
      <div class="card explain"><h4>How the most locked-in resource was scored</h4>
      <p><span class="mono">${esc(top.t)}</span> is classified as <b>${esc(top.cat)}</b>. That category's rubric scores are A = ${a}, D = ${d}, E = ${e}, X = ${x}.</p>
      <div class="formula">0.35×${a} + 0.25×${d} + 0.25×${e} + 0.15×${x} = ${(resScore(top.cat)).toFixed(3)} → ${f1(top.lii)}</div>
      <h4 style="margin-top:16px">Where this configuration's lock-in comes from</h4>
      ${Object.entries(byCat).sort((p, q2) => q2[1] - p[1]).map(([c, v]) => `<div class="stat"><span>${esc(c)}</span><b>${f1(100 * v / totMass)}%</b></div><div style="height:6px;border-radius:3px;background:var(--bar);width:${100 * v / totMass}%;margin:-8px 0 8px"></div>`).join("")}
      </div></div>`;
  }
  analyze();

  // ------------------------------------------------------------ explore
  const tbody = $("#cfgtable tbody");
  const REPO = D.repos || {};
  const ghLink = c => { const r = REPO[c.repo]; return r ? `https://github.com/${c.repo}/tree/${r.sha}${c.path === "." ? "" : "/" + c.path}` : `https://github.com/${c.repo}`; };
  function renderTable() {
    const qv = $("#q").value.trim().toLowerCase(), pv = $("#fprov").value, gv = $("#fgroup").value, sv = $("#fsort").value;
    let list = CFG.map((c, i) => ({ c, i })).filter(({ c }) => (!pv || c.provider === pv) && (!gv || c.group === gv) &&
      (!qv || (c.repo + "/" + c.path).toLowerCase().includes(qv) || c.resources.some(r => r[0].includes(qv))));
    if (sv === "desc") list.sort((a, b) => b.c.lii - a.c.lii); else if (sv === "asc") list.sort((a, b) => a.c.lii - b.c.lii); else list.sort((a, b) => (a.c.repo + a.c.path).localeCompare(b.c.repo + b.c.path));
    $("#count").textContent = `${list.length} of ${CFG.length}`;
    tbody.innerHTML = list.map(({ c, i }) => `<tr data-i="${i}"><td class="mono nowrap">${c.id}</td><td class="pathcell">${esc(c.repo)}<small>${esc(c.path)}</small></td>
      <td><span class="dot" style="background:${PROV_COL[c.provider]}"></span>${c.provider}</td><td><span class="pill">${esc(c.group.replace("-centric", ""))}</span></td>
      <td class="num">${c.resources.length}</td><td class="num"><b>${f1(c.lii)}</b><span class="liibar" style="width:${c.lii * .5}px"></span></td></tr>`).join("");
  }
  tbody.addEventListener("click", e => { const tr = e.target.closest("tr"); if (!tr) return; $$("tr.sel", tbody).forEach(r => r.classList.remove("sel")); tr.classList.add("sel"); detail(CFG[+tr.dataset.i]); });
  function detail(c) {
    const r = REPO[c.repo] || {};
    $("#detail").innerHTML = `<div class="kicker">${c.id} · ${c.provider} · ${esc(c.group)}</div><h4 style="word-break:break-all">${esc(c.repo)}<br><span class="muted mono">${esc(c.path)}</span></h4>
      <p><a href="${ghLink(c)}" target="_blank" rel="noopener">Open the source on GitHub</a> <span class="muted small">(commit ${esc((r.sha || "").slice(0, 7))}, ${esc(r.license || "")} licence)</span></p>
      <div class="tablewrap" style="max-height:340px"><table><thead><tr><th>Resource type</th><th>Category</th><th class="num">Score</th></tr></thead><tbody>
      ${c.resources.map(x => `<tr><td class="mono">${esc(x[0])}</td><td>${esc(x[1])}</td><td class="num">${f1(x[2])}</td></tr>`).join("")}</tbody></table></div>
      <div class="formula" style="margin-top:12px;white-space:normal">LII = (${c.resources.map(x => f1(x[2])).join(" + ")}) / ${c.resources.length} = <b>${f1(c.lii)}</b></div>
      <p class="small muted" style="margin-top:8px">Higher than ${f1(pctBelow(BASE, c.lii))}% of all configurations.</p>`;
  }
  ["#q", "#fprov", "#fgroup", "#fsort"].forEach(s => $(s).addEventListener("input", renderTable));
  renderTable();

  // ------------------------------------------------------------ results
  $$(".subtabs button").forEach(b => b.addEventListener("click", () => renderRQ(b.dataset.rq)));
  function renderRQ(rq) {
    $$(".subtabs button").forEach(b => b.setAttribute("aria-selected", b.dataset.rq === rq));
    const body = $("#rqbody");
    const vals = filt => CFG.map((c, i) => ({ c, v: BASE[i] })).filter(({ c }) => filt(c)).map(({ c, v }) => ({ v, t: `${c.id} · ${esc(c.repo)}<br>${esc(c.path)}<br>LII ${f1(v)}` }));
    if (rq === "rq1") {
      const P = ["AWS", "Azure", "GCP"], g = P.map(p => ({ label: p, color: PROV_COL[p], values: vals(c => c.provider === p) }));
      const v = p => g[P.indexOf(p)].values.map(o => o.v);
      const t1 = mannWhitney(v("AWS"), v("Azure")), t2 = mannWhitney(v("Azure"), v("GCP"));
      const awsNoSP = CFG.map((c, i) => [c, BASE[i]]).filter(([c]) => c.provider === "AWS" && !c.repo.includes("serverless-patterns")).map(([, x]) => x);
      const sp = CFG.filter(c => c.repo.includes("serverless-patterns")).length;
      body.innerHTML = `<div class="two wide-left"><div class="chart">${boxPlot(g, { label: "LII by provider" })}<p class="small muted" style="margin:6px 4px 0">Each dot is one configuration (hover for details). Box = middle 50%; thick line = median.</p></div>
      <div class="card explain"><h4>RQ1: How is lock-in distributed across providers?</h4>
      <div class="stat">${P.map(p => `<span>${p} median (n = ${v(p).length})</span><b>${f1(median(v(p)))}</b>`).join("")}<span>All configurations, mean</span><b>${f1(mean(BASE))}</b><span>Configurations above 40</span><b>${f1(100 * BASE.filter(x => x > 40).length / BASE.length)}%</b></div>
      <p>AWS vs Azure: Cliff's δ = ${t1.delta.toFixed(2)}, p = ${fmtP(t1.p)}. Azure vs GCP: δ = ${t2.delta.toFixed(2)}, p = ${fmtP(t2.p)} (no difference).</p>
      <div class="verdict no"><b>Careful:</b> this is not "AWS locks you in more". ${sp} of the AWS configurations come from <span class="mono">serverless-patterns</span> (Lambda, DynamoDB, API Gateway). Without them, the AWS median drops to ${f1(median(awsNoSP))}. The difference reflects what the sampled code builds.</div></div></div>`;
    } else if (rq === "rq2") {
      const cm = catMass(), top = cm.slice(0, 12), glueRes = cm.filter(d => GLUE.includes(d.cat)).reduce((a, d) => a + d.res, 0), gm = cm.filter(d => GLUE.includes(d.cat)).reduce((a, d) => a + d.mass, 0);
      body.innerHTML = `<div class="two wide-left"><div class="chart">${pairedBars(top)}${legend([["var(--bar)", "Share of total lock-in"], ["var(--bar2)", "Share of resources"]])}</div>
      <div class="card explain"><h4>RQ2: Which categories drive lock-in?</h4>
      <p>Lock-in mass of a category = the sum of its resources' scores across all ${CFG.length} configurations. Blue longer than grey means each resource in that category scores high.</p>
      <div class="stat"><span>#1 category</span><b>${esc(cm[0].cat)}</b><span>Its share of lock-in</span><b>${f1(100 * cm[0].mass)}%</b><span>Glue share of resources</span><b>${f1(100 * glueRes)}%</b><span>Glue share of lock-in</span><b>${f1(100 * gm)}%</b></div>
      <div class="verdict"><b>Conclusion:</b> lock-in is spread through the scaffolding. Identity, networking, governance, secrets and monitoring carry more than half of it, and IAM is the largest single source. Every role and policy is written in the provider's own permission language.</div></div></div>`;
    } else if (rq === "rq3") {
      const g = GROUPS.map((n, i) => ({ label: n, color: ["var(--gcp)", "var(--muted)", "var(--aws)"][i], values: vals(c => c.group === n) }));
      const t = mannWhitney(g[0].values.map(o => o.v), g[2].values.map(o => o.v));
      body.innerHTML = `<div class="two wide-left"><div class="chart">${boxPlot(g, { label: "LII by architecture" })}</div>
      <div class="card explain"><h4>RQ3: Does the index separate architectures?</h4>
      <div class="stat">${g.map(x => `<span>${esc(x.label)} median</span><b>${f1(median(x.values.map(o => o.v)))}</b>`).join("")}</div>
      <p>Mann–Whitney test, Kubernetes-centric vs Managed-PaaS: U = ${t.U.toFixed(1)}, z = ${t.z.toFixed(2)}, p = ${fmtP(t.p)}. Cliff's δ = ${t.delta.toFixed(2)}: a Kubernetes configuration scores lower about ${Math.round(50 * (1 - t.delta))}% of the time.</p>
      <div class="verdict"><b>Conclusion:</b> Kubernetes-centric designs are much less locked-in, but not lock-in free. The cluster still sits on provider networking, IAM and node pools. This is a consistency check, not proof against real migrations.</div></div></div>`;
    } else if (rq === "rq4") {
      const r4 = D.rq4;
      body.innerHTML = `<div class="two wide-left"><div class="chart">${histogram([{ name: "Configuration ranking", color: "var(--bar)", values: r4.rhos }, { name: "Category ranking", color: "var(--aws)", values: r4.cat_rhos }], { mark: r4.rho_p05 })}${legend([["var(--bar)", "Configuration ranking"], ["var(--aws)", "Category ranking"]])}</div>
      <div class="card explain"><h4>RQ4: Do results depend on our exact rubric?</h4>
      <p>We re-scored everything 1,000 times with random weights (Dirichlet around the defaults) and every category score shifted by up to ±0.15, then compared each new ranking with the original.</p>
      <div class="stat"><span>Config ranking, median ρ</span><b>${r4.rho_median.toFixed(2)}</b><span>Config ranking, 5th percentile</span><b>${r4.rho_p05.toFixed(2)}</b><span>Category ranking, median ρ</span><b>${r4.cat_rho_median.toFixed(2)}</b><span>K8s lower than PaaS in</span><b>${f1(100 * r4.k8s_lower_share)}% of trials</b></div>
      <div class="verdict"><b>Conclusion:</b> rankings barely move, so the conclusions don't depend on our exact numbers. <button class="link" data-goto2="whatif">Try changing the rubric yourself →</button></div></div></div>`;
      $("[data-goto2]", body).addEventListener("click", () => show("whatif"));
    } else {
      const c10 = p => Math.round(egressCost(10000, EG[p][0], EG[p][1]));
      body.innerHTML = `<div class="two wide-left"><div class="chart">${egressChart()}${legend([["var(--aws)", "AWS"], ["var(--azure)", "Azure"], ["var(--gcp)", "GCP"]])}</div>
      <div class="card explain"><h4>What does it cost to move data out?</h4>
      <p>One-time internet egress at list prices, without exit waivers.</p>
      <div class="stat"><span>10 TB from AWS</span><b>$${c10("AWS").toLocaleString()}</b><span>10 TB from Azure</span><b>$${c10("Azure").toLocaleString()}</b><span>10 TB from Google Cloud</span><b>$${c10("GCP").toLocaleString()}</b></div>
      <div class="formula">AWS: (10,000 − 100 free) × $0.09 = $891</div>
      <div class="verdict" style="margin-top:12px"><b>Conclusion:</b> small next to the cost of rewriting proprietary code, so egress gets the lowest weight (0.15). Provider exit waivers and the EU Data Act reduce this money cost, but not the technical lock-in our index measures.</div></div></div>`;
    }
    bindTips(body);
  }
  renderRQ("rq1");

  // ------------------------------------------------------------ what-if
  const NAMES = ["A · API proprietariness", "D · Data/state lock", "E · Equivalence gap", "X · Egress exposure"];
  let W = W0.slice(), CATS = CATS0;
  $("#sliders").innerHTML = NAMES.map((n, i) => `<div class="slider"><label for="w${i}"><span>${n}</span><b id="wv${i}"></b></label><input id="w${i}" type="range" min="0" max="1" step="0.01" value="${W0[i]}"></div>`).join("");
  const norm = w => { const s = w.reduce((a, b) => a + b, 0) || 1; return w.map(v => v / s); };
  function readSliders() { W = norm(NAMES.map((_, i) => +$("#w" + i).value)); }
  function setSliders(w) { w.forEach((v, i) => $("#w" + i).value = v.toFixed(2)); }
  NAMES.forEach((_, i) => $("#w" + i).addEventListener("input", () => { readSliders(); CATS = CATS === CATS0 ? CATS0 : CATS; whatif(); }));
  $("#reset").addEventListener("click", () => { setSliders(W0); W = W0.slice(); CATS = CATS0; whatif(); });
  function gamma(k) { // Marsaglia–Tsang
    if (k < 1) return gamma(k + 1) * Math.pow(Math.random(), 1 / k);
    const d = k - 1 / 3, c = 1 / Math.sqrt(9 * d);
    for (;;) { let x, v; do { const u1 = Math.random(), u2 = Math.random(); x = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2); v = 1 + c * x; } while (v <= 0); v = v * v * v; const u = Math.random(); if (u < 1 - .0331 * x ** 4 || Math.log(u) < .5 * x * x + d * (1 - v + Math.log(v))) return d * v; }
  }
  $("#randomize").addEventListener("click", () => {
    W = norm(W0.map(w => gamma(4 * w))); setSliders(W);
    CATS = Object.fromEntries(Object.entries(CATS0).map(([k, v]) => [k, v.map(s => Math.min(1, Math.max(0, s + (Math.random() * .3 - .15))))]));
    whatif();
  });
  function whatif() {
    W.forEach((v, i) => $("#wv" + i).textContent = v.toFixed(2));
    const sc = scoreAll(W, CATS), rho = spearman(BASE, sc);
    const gv = n => CFG.map((c, i) => [c, sc[i]]).filter(([c]) => c.group === n).map(([, v]) => v);
    const mk = median(gv("K8s-centric")), mp = median(gv("Managed-PaaS-centric"));
    const cm = catMass(W, CATS), gm = cm.filter(d => GLUE.includes(d.cat)).reduce((a, d) => a + d.mass, 0);
    const g = GROUPS.map((n, i) => ({ label: n, color: ["var(--gcp)", "var(--muted)", "var(--aws)"][i], values: CFG.map((c, j) => ({ c, v: sc[j] })).filter(({ c }) => c.group === n).map(({ c, v }) => ({ v, t: `${c.id} · LII ${f1(v)}` })) }));
    const changed = CATS !== CATS0;
    $("#whatifout").innerHTML = `<div class="chart">${boxPlot(g, { label: "LII by architecture under this rubric", xmax: 100 })}</div>
      <div class="card" style="margin-top:14px"><div class="stat">
      <span>Similarity to the original ranking (Spearman ρ)</span><b>${rho.toFixed(3)}</b>
      <span>K8s-centric median → Managed-PaaS median</span><b>${f1(mk)} → ${f1(mp)}</b>
      <span>Top lock-in category</span><b>${esc(cm[0].cat)} (${f1(100 * cm[0].mass)}%)</b>
      <span>Glue share of lock-in</span><b>${f1(100 * gm)}%</b></div>
      <div class="verdict ${mk < mp ? "" : "no"}">${mk < mp ? "✓ Kubernetes-centric designs are still less locked-in than managed-PaaS designs." : "✗ Under this rubric, the RQ3 conclusion no longer holds."}${changed ? " (Category scores were also randomly perturbed.)" : ""}</div></div>`;
    bindTips($("#whatifout"));
  }
  whatif();
})();
