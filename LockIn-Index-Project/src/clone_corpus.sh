#!/usr/bin/env bash
# Optional: re-download the 28 original GitHub repositories at the exact commits we analysed.
# The bundled data/terraform_sources already contains every file the analysis reads,
# so this is only needed to prove the data came from these public repositories.
# Usage:  bash src/clone_corpus.sh corpus     then:  bash run_all.sh corpus
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${1:-corpus}"; mkdir -p "$OUT"
tail -n +2 data/repositories.csv | while IFS=, read -r repo url sha lic n status; do
  dir="$OUT/$(echo "$repo" | sed 's#/#_#')"
  if [ ! -d "$dir" ]; then
    echo "cloning $repo @ ${sha:0:7}"
    git clone -q --filter=blob:limit=200k "$url" "$dir"
    git -C "$dir" checkout -q "$sha"
  fi
done
echo "Corpus ready in $OUT"
