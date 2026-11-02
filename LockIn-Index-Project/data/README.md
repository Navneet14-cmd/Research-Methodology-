# Input data

`terraform_sources/` holds the original Terraform (`.tf`) files of every configuration we analysed, plus the
local modules they use. Folder names are `<owner>_<repository>`, and paths inside match the original repositories.

`repositories.csv` lists all 28 repositories we collected: GitHub URL, the exact commit we used, licence,
how many configurations were included, and why a repository was excluded (if it was).

All source repositories are open source (Apache-2.0, MPL-2.0, MIT or MIT-0). Each repository's `LICENSE`
file is kept next to its code; the code remains under that licence.

To re-download the originals at the same commits instead: `bash src/clone_corpus.sh corpus`, then `bash run_all.sh corpus`.
