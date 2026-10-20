# Paper build notes

This directory contains an arXiv-style LaTeX manuscript based on the frozen
experiment in `../experiments/`.

## Files

- `main.tex` — manuscript
- `refs.bib` — bibliography
- `figures/` — Figures 1–5 (PDF, plus the system screenshot PNG)

## Compile

From this directory:

```bash
pdflatex main
bibtex main
pdflatex main
pdflatex main
```

or:

```bash
latexmk -pdf main.tex
```

The manuscript uses only standard LaTeX packages: `geometry`, `fontenc`,
`lmodern`, `amsmath`, `amssymb`, `graphicx`, `booktabs`, `caption`, `float`,
`natbib`, `url`, `microtype`, and `hyperref`. If your TeX distribution is
minimal, install `natbib`, `booktabs`, `caption`, `microtype`, and `lmodern`.

The manuscript was authored without a local TeX installation in this
environment, so please run one compile pass and fix any local package or font
issue before uploading. The LaTeX structure, labels, citations, and figure
paths have been checked; all cited keys exist and all figure files are present.

## Before submitting to arXiv

1. **Author metadata.** `main.tex` currently uses the GitHub handle
   `Huiihao` with no affiliation. Replace it with your preferred name,
   affiliation, and email. arXiv requires at least one author.
2. **Categories.** Suggested primary category: `cs.MA` (Multiagent Systems).
   Suggested cross-list: `q-fin.TR` (Trading and Market Microstructure).
   `cs.CE` or `q-fin.CP` are also plausible.
3. **Title/abstract.** The title emphasizes the empirical finding:
   *Learning to Diverge, Imitating to Coordinate*. The abstract reports the
   main effect sizes and the post-hoc caveat for the revised observer.
4. **Data/code statement.** The repository and frozen snapshot SHA-256 are in
   the manuscript:
   `3c9cf0ff864b68e6886c1f3181f67e6e93dbacef8102007c34fedc768c9f86fe`.
5. **Licensing.** The code is MIT. Three.js (vendored) is MIT. Market data is
   public Yahoo/yfinance data; check the vendor's terms before redistributing
   the snapshot beyond the repository if your institution requires it.

## Reproducing the numbers and figures

From the repository root:

```bash
pip install -r experiments/requirements.txt
python experiments/run_experiment.py     # 64 runs, ~40-60 s
python experiments/analyze_results.py    # tables, figures, results.json
python -m unittest discover -s tests -v  # 21 tests
```

The experiment runner uses only the frozen
`experiments/data/market_snapshot_5m_5d.json`; it does not access the network.
The analysis script writes figures to `experiments/figures/` and copies them to
`paper/figures/`.

## Reading the results

The full report, including the v1/v2 observer audit, is in
`../experiments/REPORT.md`. The key caveat is that the v2 flow-risk observer
score was designed after observing the v1 failure on the same 64 runs; it is a
hypothesis for independent validation, not a pre-registered early-warning
system. The paper says this explicitly in the abstract, results, and
limitations.
