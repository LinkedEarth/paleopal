# A Causal Examination of the Solar Influence on Holocene Climate

Jordan P. Landers, Julien Emile-Geay, Alexander K. James, Stephan B. Munch,
Deborah Khider, Edouard Bard

## Overview

Variations in Total Solar Irradiance (TSI) have long been hypothesized to influence
global mean surface temperature (GMST) on multidecadal-to-millennial timescales, but
empirical evidence has remained elusive. This paleobook explores the link between
solar variability and climate over the pre-industrial Holocene using **Convergent
Cross-Mapping (CCM)** (Sugihara et al., 2012), a nonlinear causal-inference framework, applied to four
temperature–TSI dyads spanning two temperature reconstructions (a global mean
reconstruction, ERB22, and a central-Greenland record, ALLEY00) and two TSI
reconstructions (VIEIRA11, WU18).

## Key Findings

- TSI shows a discernible causal influence on temperature in ~80% of the (E, τ)
  parameter configurations tested.
- The influence is weaker but more consistently significant for the global mean
  (ERB22); stronger but less consistently significant for the single high-latitude
  site (ALLEY00/GISP2).
- Solar forcing appears to have been a minor — but detectable — driver of
  pre-industrial Holocene climate fluctuations, distinct from and much smaller than
  anthropogenic forcing over the industrial era.
- This empirical signal may serve as a benchmark for evaluating whether climate
  models correctly capture such subtle, non-linear solar–climate dynamics.

## How to Navigate This Book

Read in order for the full narrative, or jump to a specific figure using the table
below.

1. **Data Preparation & Exploration** — standardizing, detrending, and characterizing
   the four source records
2. **Embedding & Methodology** — choosing CCM's embedding parameters (E, τ)
3. **CCM: From Single Run to Parameter Sweep** — the causal-inference pipeline for
   one dyad, in increasing scope
4. **Results from Multiple Dyads** — pulling together CCM results across all four dyads
5. **Supplementary Analyses** — CCM vs. simple correlation, and other supporting work
6. **Utilities** — CCM configuration notebooks used throughout the pipeline (not
   narrative, but rerun as needed)

## Figure-to-Notebook Mapping

| Figure                                                                                       | Notebook |
|----------------------------------------------------------------------------------------------|---|
| Fig. 1 (data & power spectra)                                                                | [Raw Data & Power Spectra (Figures 1 & S5)](notebooks/0_Datasets/3_plot__Fig1_real_ts_psd_unified.ipynb) |
| Fig. 2 ([CCM workflow schematic](figures/Fig2__workflow_diag/stepwise_CCM_workflow_lag.pdf)) | not code-generated |
| Fig. 3 (main result grid)                                                                    | [Main Result Grid (Figure 3)](notebooks/3_CCM_multi_dyad/1_plot__DataGroup_grid_untreated_2x2__final_result_grid.ipynb) |
| Fig. S1 (choosing E, τ)                                                                      | [Choosing E and τ (Figure S1)](notebooks/1_Embedding/1_plot__FigS1_embedding.ipynb) |
| Fig. S2 (simplex self-prediction)                                                            | [Simplex Self-Prediction (Figure S2)](notebooks/1_Embedding/2_plot__FigS2_simplex.ipynb) |
| Fig. S3 (library size–ρ trajectories)                                                        | [Library Size–ρ Trajectories Across Lags (Figure S3)](notebooks/2_CCM_single_dyad/2_plot__DataGroup_libsize_update.ipynb) |
| Fig. S4 (final ρ vs. lag)                                                                    | [Final ρ Across (E, τ) Configurations (Figure S4)](notebooks/2_CCM_single_dyad/3_plot__DataGroup_lag.ipynb) |
| Fig. S5 (raw/detrended/high-pass comparison)                                                 | [Detrending & High-Pass Filtering (Figure S5)](notebooks/0_Datasets/2_setup__detrend_highpass_1kyr.ipynb) |
| Fig. S6 (full result overview)                                                               | [Full Result Overview (Figures S6, S7, S9)](notebooks/3_CCM_multi_dyad/2_plot__DataGroup_grid__final_result_grid.ipynb) |
| Fig. S7 (lag choice)                                                                         | [Full Result Overview (Figures S6, S7, S9)](notebooks/3_CCM_multi_dyad/2_plot__DataGroup_grid__final_result_grid.ipynb) |
| Fig. S8 (simple correlation, all dyads)                                                      | [Simple Correlation, All Dyads (Figure S8)](notebooks/4_Extras/2_plot__corr_lag_tau_resultsgrid.ipynb) |
| Fig. S9 (CCM skill at optimal lag)                                                           | [Full Result Overview (Figures S6, S7, S9)](notebooks/3_CCM_multi_dyad/2_plot__DataGroup_grid__final_result_grid.ipynb) |
| Fig. S10 (CCM − simple-correlation difference)                                               | computed as Fig. S9 minus Fig. S8; no dedicated notebook yet |

## Data & Reproducibility

Source datasets (all publicly available, as cited in the paper):

- **Temperature**: GISP2/ALLEY00 (Alley, 2000), ERB22 (Erb et al., 2022)
- **TSI**: VIEIRA11 (Vieira et al., 2011), WU18 (Wu et al., 2018)

CCM outputs are archived on [Figshare](https://doi.org/10.6084/m9.figshare.c.8150612)
(Landers et al., 2026). Data used throughout the notebooks lives in
`hol_temp_tsi_ccm/` (not a Python package — a data directory).

Analysis parameters (dataset specifications, CCM sweep settings, plot colors) are
centralized in [`proj_config.yaml`](proj_config.yaml), loaded directly by the
notebooks. Modify it to adjust the parameter sweep or add new datasets.

## Getting Started

```bash
conda env create -f environment.yml
conda activate holoccm
python -m ipykernel install --user --name=holoccm
jupyter lab
```

This installs [Cedarkit](https://github.com/jordanplanders/cedar_util) (CCM/EDM data
structures and workflow tooling) and a pinned fork of
[pyEDM](https://github.com/jordanplanders/pyEDM), both required by the notebooks.

To build this book locally:

```bash
pip install mystmd
brew install imagemagick webp
myst build --html
```

## Dependencies

See [`environment.yml`](environment.yml). Core packages: `pyleoclim`, `pyEDM`,
`cedarkit`, `xarray`, `pandas`, `numpy`, `matplotlib`, `polars`.

## Citation

This work is in press at *Geophysical Research Letters*:

Landers, J.P., Emile-Geay, J., James, A.K., Munch, S.B., Khider, D., & Bard, E. (2026).
A causal examination of the solar influence on Holocene climate. *Geophysical Research
Letters*, 53, e2025GL121120. https://doi.org/10.1029/2025GL121120

The CCM analysis library, Cedarkit, is archived on
[Zenodo](https://doi.org/10.5281/zenodo.19992883) and
[GitHub](https://github.com/jordanplanders/cedar_util).

## Acknowledgements

J.P.L., D.K., and J.E.-G. acknowledge support from the US National Science
Foundation (Award RISE-2126510). A.K.J. was supported by the University of Southern
California.
