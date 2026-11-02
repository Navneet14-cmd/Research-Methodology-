# Lock-In Index dataset

Dataset behind the paper "Quantifying Vendor Lock-In in Multi-Cloud Infrastructure: A Static-Analysis
Lock-In Index and an Empirical Study of 677 Terraform Configurations"
(D. Soni, N. Pant, M. Toshif).

- 677 Terraform root configurations, 8,908 resource declarations, 844 resource types
- 23 public GitHub repositories (AWS, Azure, Google Cloud), cloned Oct. 29, 2026 at the commits in tables/repositories.csv

## Contents
tables/repositories.csv        repos, URLs, commit SHAs, licences, include/exclude reason
tables/configurations.csv      one row per configuration (ID, repo, path, provider, group, size, LII, per-category counts)
tables/resources.csv           one row per resource declaration (type, provider, category, A/D/E/X, resource LII)
tables/rubric.csv              scoring rubric (paper Table I) and weights
tables/category_summary.csv    Fig. 3 data
tables/provider_summary.csv    Table II / Fig. 2 data
tables/architecture_groups.csv Table III / Fig. 4 data
tables/sensitivity_trials.csv  1,000 Monte Carlo trials (Fig. 5)
tables/egress_exit_cost.csv    Fig. 6 data (USD, list prices, no waivers)
terraform_sources/<owner_repo>/...  original .tf files of analysed configurations + local modules, with each repo's LICENSE
code/lii.py                    analysis (run: python3 code/lii.py <corpus_dir> out)
code/figs.py                   figures (run: python3 code/figs.py out/results.json figs)
code/export_dataset.py         builds this dataset

## Notes
- config paths in the CSVs are relative to the repository root.
- Dimensions: A = API proprietariness, D = data/state lock, E = equivalence gap, X = egress exposure.
  Resource LII = 100 * (0.35A + 0.25D + 0.25E + 0.15X). Configuration LII = mean resource LII.
- Source code in terraform_sources/ remains under its original licence (Apache-2.0, MPL-2.0, MIT or MIT-0).
