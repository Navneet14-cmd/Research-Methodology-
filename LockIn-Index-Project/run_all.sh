#!/usr/bin/env bash
# Rebuilds every result, table and figure of the paper from the raw Terraform code.
# Usage:  bash run_all.sh            (uses the bundled code in data/terraform_sources)
#         bash run_all.sh corpus     (uses a fresh download made by src/clone_corpus.sh)
set -euo pipefail
cd "$(dirname "$0")"
SRC_DIR="${1:-data/terraform_sources}"

echo "== Step 1/4: analysing Terraform code in $SRC_DIR (takes a few minutes: 1,000 sensitivity trials)"
python3 src/lii.py "$SRC_DIR" results | tee results/run_log.txt

echo "== Step 2/4: drawing figures"
python3 src/figs.py results/results.json figures > /dev/null

echo "== Step 3/4: writing summary tables and demo data"
python3 src/summarize.py results demo

echo "== Step 4/4: checking results against the numbers in the paper"
python3 src/verify_against_paper.py results | tee results/verification.txt

echo "Done. Open demo/index.html in a browser to explore the results."
