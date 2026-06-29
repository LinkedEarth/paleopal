# Code for Reproducing Cropper et al. (under review)

## Python Notebooks
### gen_ec_data.ipynb
* constructs the variability metrics relevant to the emergent constraints
* uses the timeseries data available in 'data/ts.csv' and the ecs values from 'data/ecs.csv'

### pp2k-ppe-pda.ipynb
* draws heavily from Feng Zhu's pseudoPAGES2k project: https://github.com/fzhu2e/paper-pseudoPAGES2k
uses the following data files to vary SNR:
* ppwn_SNR10_rta.nc
* ppwn_SNR2_rta.nc
* ppwn_SNR1_rta.nc
* ppwn_SNR0.5_rta.nc
* ppwn_SNR0.25_rta.nc

### main.ipynb
* contains the codes required to reproduce the main figures in the manuscript
* uses volcanic forcing data, 'crowley_2000.txt' (Crowley et al., 2000), 'crowley_2008.txt' (Crowley et al., 2008), 'gao_2008.txt' (Gao et al., 2008), and 'evolv2k.nc' (Toohey & Sigl, 2017).
* uses emergent constraint data, 'ec_data.csv'
* uses the following data files to generate Figure 1: 'data_fig1a_cmip5.csv', 'data_fig1a_cmip6.csv', 'data_fig1b_cmip5.csv', 'data_fig1b_cmip6.csv'

### supplement.ipynb
* generates the figures for the supplemental materials
* uses volcanic forcing data, 'crowley_2000.txt' (Crowley et al., 2000), 'crowley_2008.txt' (Crowley et al., 2008), 'gao_2008.txt' (Gao et al., 2008), and 'evolv2k.nc' (Toohey & Sigl, 2017).
* uses emergent constraint data, 'ec_data.csv'
