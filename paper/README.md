# Paper build notes

This directory contains an arXiv-style LaTeX manuscript based on the frozen
multi-window experiments in `../experiments/`.

## Files

- `main.tex` — manuscript
- `refs.bib` — bibliography
- `figures/` — nine figures (PDF, plus the system screenshot PNG)

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
All nine figures exist as both PDF and PNG in `figures/`; the manuscript uses
the PDFs except for the system screenshot.

## Before submitting to arXiv

1. **Author metadata.** `main.tex` currently uses the GitHub handle
   `Huiihao` with no affiliation. Replace it with your preferred name,
   affiliation, and email. arXiv requires at least one author.
2. **Categories.** Suggested primary category: `cs.MA` (Multiagent Systems).
   Suggested cross-list: `q-fin.TR` (Trading and Market Microstructure).
   `cs.CE` or `q-fin.CP` are also plausible.
3. **Title/abstract.** The title is
   *Learning to Diverge, Imitating to Coordinate: A Multi-Window Replication and
   Observer Audit of an Agent-Based Market*. The abstract reports both the
   robust behavioural results and the failed performance/observer replications;
   this is deliberate. Do not shorten it into a single-window performance claim.
4. **Data/code statement.** The repository and frozen snapshot SHA-256 are in
   the manuscript:
   `3c9cf0ff864b68e6886c1f3181f67e6e93dbacef8102007c34fedc768c9f86fe`.
   The six held-out snapshots have per-window SHA-256 values in their metadata.
5. **Licensing.** The code is MIT. Three.js (vendored) is MIT. Market data is
   public Yahoo/yfinance data; check the vendor's terms before redistributing
   the snapshots beyond the repository if your institution requires it.

## Reproducing the numbers and figures

From the repository root:

```bash
pip install -r experiments/requirements.txt

# Discovery window: 4 conditions x 16 seeds x 300 ticks
python experiments/run_experiment.py --design base --ticks 300 \
  --seeds 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16 \
  --out experiments/results

# Six held-out windows: 4 conditions x 8 seeds x 300 ticks each
for d in experiments/data/windows/w*; do
  name=$(basename "$d")
  python experiments/run_experiment.py --design base --ticks 300 \
    --seeds 1,2,3,4,5,6,7,8 \
    --snapshot "$d/market_snapshot_5m_5d.json" \
    --metadata "$d/snapshot_metadata.json" \
    --out "experiments/results_windows/$name"
done

# Learning x imitation phase sweep: 4 x 4 x 8 x 250 ticks
python experiments/run_experiment.py --design sweep --ticks 250 \
  --seeds 1,2,3,4,5,6,7,8 \
  --learning-scales 0,0.5,1,2 --imitation-scales 0,0.5,1,2 \
  --out experiments/results_sweep

# Analysis and figures
python experiments/analyze_results.py
python experiments/analyze_extensions.py
python experiments/analyze_strategy.py
python experiments/analyze_observer_targets.py
python -m unittest discover -s tests -v
```

The experiments use only the frozen snapshots; they do not access the network.
The analysis scripts write figures to `experiments/figures/` and copy them to
`paper/figures/`.

## Reading the results

The full report is in `../experiments/REPORT.md`. The paper is a multi-window
replication and observer audit, not a single-window alpha claim. The discovery
window shows learning improving returns/drawdowns and imitation coordinating;
the six held-out windows show that only the behavioural effects replicate.
Learning robustly increases diversity and signal-genome divergence; imitation
robustly increases order-flow coordination; the full-minus-static return and
drawdown advantages do not replicate. The v2 flow-risk *level* is a
coordination-persistence signal, not a validated drawdown warning: it predicts
future synchrony/imbalance in and out of sample, but its discovery-window
drawdown correlation reverses out of sample. The target-specific follow-up shows
that the observers are different sensors (between-window volatility, trust
structure, coordination, placebo); the flow *change* 20 ticks earlier has a
modest event-level AUC of .61 (five of six windows) but no run-level signal. The
paper says this explicitly in the abstract, results, observer audit, discussion,
and limitations.
