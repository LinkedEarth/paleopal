# Data preparation & exploration

## Contents

1. [Standardize Time Axes](1_setup__standardize_time_axes.ipynb)
2. [Detrending & High-Pass Filtering (Figure S5)](2_setup__detrend_highpass_1kyr.ipynb)
3. [Raw Data & Power Spectra (Figures 1 & S5)](3_plot__Fig1_real_ts_psd_unified.ipynb)

Before any analysis, the four source records (two temperature reconstructions, two
TSI reconstructions) are put on a common decadal time axis. Figure 1 summarizes these
raw series and their spectral content. Linear detrending and 1-kyr high-pass
filtering were added afterward as sensitivity checks, to test whether slow background
trends affect the CCM results; the extended comparison across every supplemental
record and treatment is Fig. S5.

## Source datasets

### Total Solar Irradiance

- **WU18** — [@Wu:2018aa]
- **VIEIRA11** — [@vieira2011]


### Temperature

Main manuscript:

- **ERB22** — [@erb2022]
- **ALLEY00 (GISP2)** — [@Alley:2000aa]. GISP2 ice core temperature reconstruction: https://www.ncei.noaa.gov/pub/data/paleo/icecore/greenland/summit/gisp2/isotopes/gisp2_temp_alley2000-noaa.txt

Supplementary Greenland records:

- **Döring22 (GISP2)** — [@Doring:2022aa]
- **Martin24 (GISP2, NEEM, NGRIP)** — [@Martin:2024aa]. Underlying dataset: https://arcticdata.io/catalog/view/doi:10.18739/A2KP7TT2N
- **Seierstad14 (GISP2, NGRIP δ¹⁸O)** — [@Seierstad:2014aa]
- **Tian22 (transient GCM GMST)** — [@Tian:2022aa]. Simulation output: https://doi.org/10.5281/zenodo.6269566
