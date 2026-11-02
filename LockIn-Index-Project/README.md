# Lock-In Index: measuring cloud vendor lock-in from Terraform code

Project behind the paper **"Quantifying Vendor Lock-In in Multi-Cloud Infrastructure: A Static-Analysis
Lock-In Index and an Empirical Study of 677 Terraform Configurations"**
by Deepak Soni (590012874), Navneet Pant (590011569) and Mohd Toshif (590018042).

Everything used to reach the paper's conclusions is in this folder: the raw input data, every script,
all intermediate results, the figures, an interactive demo, a step-by-step notebook and the paper itself.

---

## What the project does

We built a **static analyzer** that reads Terraform (infrastructure-as-code) files and gives each
configuration a **Lock-In Index (LII) from 0 to 100**: how tightly it is tied to one cloud provider.

```
 data/terraform_sources  ──►  src/lii.py  ──►  results/  ──►  src/figs.py  ──►  figures/
 (raw .tf code, 23 repos)     analyzer         scores,        charts            Figs. 2–6
                              + statistics     tables         
                                         └──►  src/summarize.py ──► demo/  (interactive)
                                         └──►  src/verify_against_paper.py ──► 36/36 checks
```

For every root configuration, `src/lii.py`:

1. **Extracts** each `resource "TYPE" "NAME"` block (following local modules).
2. **Identifies the provider** from the prefix (`aws_`, `azurerm_`, `google_` …).
3. **Classifies** the resource into one of 21 service categories using ordered pattern rules.
4. **Scores** it with the rubric: `LII(r) = 0.35·A + 0.25·D + 0.25·E + 0.15·X`
   (A = API proprietariness, D = data/state lock, E = equivalence gap, X = egress exposure).
5. **Averages** the resource scores: `LII(C) = 100 × mean LII(r)`.

It then answers the four research questions (provider comparison, category contribution, Mann–Whitney
test between architectures, and 1,000-trial Monte Carlo sensitivity analysis).

This is a rule-based model, not machine learning: there is no public dataset of real migration costs to
train on, so the rubric is transparent expert scoring, and RQ4 tests how much the results depend on it.

---

## Quick start (macOS / Linux)

```bash
cd LockIn-Index-Project
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
bash run_all.sh                 # about 2 minutes
open demo/index.html            # macOS; or double-click the file
```

`run_all.sh` rebuilds every result from the raw code and ends by printing **36/36 checks passed**, a
comparison of every number quoted in the paper with the freshly computed value (saved in
`results/verification.txt`). The random seed is fixed (42), so results are identical on every run.

On Windows, run the four commands inside `run_all.sh` one by one in a terminal.

**Notebook (optional):** `pip install -r requirements-notebook.txt`, then open `notebook/walkthrough.ipynb`
in VS Code or Jupyter. A pre-run copy is in `notebook/walkthrough.html` (opens in any browser).

---

## Folder map

| Path | What it is |
|---|---|
| `data/terraform_sources/` | **Raw input:** the original `.tf` files of all 677 configurations and the local modules they use, with each repository's licence |
| `data/repositories.csv` | All 28 source repositories: URL, exact commit SHA, licence, configurations included, exclusion reason |
| `src/lii.py` | **The analyzer:** extraction, classification, rubric scoring, RQ1–RQ4 statistics |
| `src/figs.py` | Draws Figs. 2–6 and computes the extra statistics (glue share, egress costs) |
| `src/summarize.py` | Writes the summary tables and the demo's data file |
| `src/verify_against_paper.py` | Checks 36 numbers in the paper against the results |
| `src/clone_corpus.sh` | Optional: re-downloads the original repositories at the exact commits |
| `run_all.sh` | Runs the whole pipeline |
| `results/results.json` | All computed results |
| `results/tables/resources.csv` | One row per resource (8,908): type, provider, category, A/D/E/X, score |
| `results/tables/configurations.csv` | One row per configuration (677): provider, group, size, LII |
| `results/tables/*.csv` | Rubric, category, provider, group, sensitivity and egress tables |
| `results/run_log.txt`, `results/verification.txt` | Console output of the last run and the 36-check report |
| `figures/` | Figures 2–6 (PDF for the paper, PNG for slides) |
| `demo/index.html` | **Interactive demo** (works offline, no installation) |
| `notebook/` | Step-by-step walkthrough from one raw file to every conclusion |
| `paper/` | Overleaf source (`main.tex`, `refs.bib`, `figs/`) and the compiled PDF |
| `docs/` | Study guide, reference verification list with links, project notes |

---

## How each conclusion was reached

| Paper result | Produced by | Evidence file | In the demo |
|---|---|---|---|
| Dataset: 677 configs, 8,908 resources, 844 types, 23 repos | `lii.py` | `results/tables/configurations.csv`, `resources.csv` | Overview, Explore |
| Table I (rubric) | `lii.py` | `results/tables/rubric.csv` | Analyze (A/D/E/X columns) |
| RQ1, Table II, Fig. 2: AWS higher, but a sampling effect | `lii.py`, `figs.py` | `provider_summary.csv`, `fig_provider` | Results › RQ1 |
| RQ2, Fig. 3: IAM 21.1% of lock-in; glue 52.7% | `lii.py`, `figs.py` | `category_summary.csv`, `fig_categories` | Results › RQ2 |
| RQ3, Table III, Fig. 4: K8s 25.2 vs PaaS 41.9, δ = −0.84 | `lii.py` (Mann–Whitney) | `architecture_groups.csv`, `fig_groups` | Results › RQ3 |
| RQ4, Fig. 5: median ρ = 0.91 over 1,000 trials | `lii.py` (Monte Carlo) | `sensitivity_trials.csv`, `fig_sensitivity` | Results › RQ4, What-if |
| Section VI, Fig. 6: exit egress cost | `figs.py` | `egress_exit_cost.csv`, `fig_egress` | Results › Exit cost |

---

## Demo walkthrough (5 minutes)

1. **Overview:** the pipeline and the three headline findings.
2. **Analyze Terraform:** load the *Serverless app* sample → LII 50.0, with every resource's A/D/E/X scores
   and the formula worked out. Switch to the *Kubernetes cluster* sample → 18.0. You can also upload any
   `.tf` file.
3. **Explore dataset:** search or filter the 677 configurations; click one to see its score calculation and
   open its source on GitHub at the exact commit used.
4. **Results:** each research question computed live from the data, with the statistics and conclusion.
5. **What-if rubric:** move the weight sliders or press *Random rubric*. Every score is recalculated, and
   the Kubernetes-vs-PaaS conclusion still holds, which shows RQ4 interactively.

The demo applies exactly the same rules as `lii.py`. All 8,908 classifications were checked to match, and the
statistics shown match the paper.

---

## Reproducibility notes

- **Same input every time:** `data/terraform_sources` contains every file the analysis reads. To prove where it
  came from, `bash src/clone_corpus.sh corpus && bash run_all.sh corpus` re-downloads the original
  repositories at the recorded commits and gives the same results.
- **Deterministic:** the sensitivity analysis uses seed 42; scores are rounded to 9 decimals so tied
  configurations tie exactly on every Python version.
- **Requirements:** Python 3.9+ and matplotlib. The demo needs only a web browser.

## Limitations

The rubric scores are expert judgments, not measurements, and the index has not yet been validated against real
migration effort. Parsing uses regular expressions (registry modules, `count` and `for_each` are not
evaluated). The corpus is public examples and modules, not production systems. See Section VII-C of the paper.

## AI assistance

An AI assistant (Claude, Anthropic) helped write the analysis code, the demo and the manuscript text, as
disclosed in the paper's acknowledgment. All results are produced by the code in this folder and can be
re-run with `run_all.sh`.

## Licence of third-party data

The Terraform code in `data/terraform_sources` belongs to its original authors and stays under its original
open-source licence (Apache-2.0, MPL-2.0, MIT or MIT-0); see the `LICENSE` file in each repository folder and
`data/repositories.csv`.
