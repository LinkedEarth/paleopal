# Comparing Simulated and Reconstructed Climate Variability over the Past Millennium
[![DOI](https://zenodo.org/badge/614554628.svg)](https://doi.org/10.5281/zenodo.17574947)

This Paleobook covers basic examples of how to access, process and visualize data from the [CMIP6 _past1000_ simulations](https://gmd.copernicus.org/articles/10/4005/2017/) and the [Last Millennium Reanalysis v2.1](https://doi.org/10.5194/cp-15-1251-2019).  

## Motivation

A chief goal of paleoclimatology is to ground-truth models used for prediction using observations on which they have not  been tuned.  Long transient simulations climate those of the PMIP _past1000_ provide a unique opportunity to validate their representation of climate variability against the [wealth of data from the past 2 millennia](https://doi.org/10.1038/sdata.2017.88). This integration poses both technical and scientific challenges.  
Here we look at how to leverage multiple cloud-based data sources to examine a few aspects of climate evolution over the last millennium. In addition to information about how to pull data using `intake` and wrangle it using `Xarray`, these notebooks include tips about how to explore climate variables as time series and as well as spatially resolved snapshots, particularly the response to explosive volcanism (the main climate forcing over this time period). 

## Authors

[Jordan Landers](@jordanplanders), [Julien Emile-Geay](@CommonClimate)

### Contributors

<a href="https://github.com/LinkedEarth/LMR_CMIP_paleobook/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=LinkedEarth/LMR_CMIP_paleobook" />
</a>

## Funding
This work was supported by NSF Award ICER 2126510

## Structure

This Paleobook is made up of two sections: Lifehacks, and Science Bits.

### Lifehacks

This section covers nuts and bolts about how to access cloud available data, process it, and make some stock visualizations.

### Science Bits

This section applies technical skills from the Lifehacks section in a pair of example analyses.

## Running the Notebooks

You can either run the notebook using [Binder](https://mybinder.org/), or on your local machine.

### Running on Binder

The simplest way to interact with a Jupyter Notebook is through
[Binder](https://mybinder.org/), which enables the execution of a
[Jupyter Book](https://jupyterbook.org) in the cloud. The details of how this works are not
important for now. All you need to know is how to launch a PaleoBooks chapter via Binder. Simply navigate your mouse to
the top right corner of the book chapter you are viewing and click
on the rocket ship icon, (see figure below), and be sure to select
“launch Binder”. After a moment you should be presented with a
notebook that you can interact with. I.e. you’ll be able to execute
and even change the example programs. You’ll see that the code cells
have no output at first, until you execute them by pressing
{kbd}`Shift`\+{kbd}`Enter`. Complete details on how to interact with
a live Jupyter notebook are described in [Getting Started with
Jupyter](https://foundations.projectpythia.org/foundations/getting-started-jupyter.html).

### Running on Your Own Machine

If you are interested in running this material locally on your computer, you will need to follow this workflow:

1. Clone the `https://github.com/LinkedEarth/LMR_CMIP_paleobook` repository:

   ```bash
    git clone https://github.com/LinkedEarth/LMR_CMIP_paleobook.git
   ```

1. Create and activate your conda environment from the `environment.yml` file
   ```bash
   conda env create -f environment.yml
   conda activate conda-env-paleobook-dev-py
   ```
1. Move into the `notebooks` directory and start up Jupyterlab
   ```bash
   cd notebooks/
   jupyter lab
   ```
