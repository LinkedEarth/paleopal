[![DOI](https://zenodo.org/badge/635936257.svg)](https://doi.org/10.5281/zenodo.17575008)

# C-iTRACE (and friends) PaleoBook

This PaleoBook looks at how to slice, dice, navigate, visualize and investigate paleoceanographic questions at the interface between models and observations using the multi-proxy, spatially resolved model output from [coarse iTRACE (C-iTRACE) runs](https://sites.google.com/colorado.edu/citrace). 

## Motivation

Paleo-model output offers a spatially resolved look at how proxy distributions may have evolved over time--a welcome gift in a field perpetually saddled with navigating sparse data problems. Working with model output comes with a few unique challenges, in addition to some intriguing opportunities. 

C-iTRACE is a deglacial simulation performed using a low resolution (3 degrees) configuration of the isotope enabled version of the Parallel Ocean Program version 2 (POP2) with 60 vertical layers and active biogeochemistry. The isotope suite includes a growing set of geotracers such as $\delta^{13}$C, $\Delta^{14}$C, $\varepsilon$Nd, $\delta^{18}$O. 

The simulation spans 20ka to present at decadal resolution and is forced with momentum, heat, freshwater fluxes and sea ice fractions from existing fully-coupled TraCE-21 ka simulation and reconstructed atmospheric CO$_2$ and $\Delta^{14}$C. The C-iTRACE simulation is part of an effort to test code prior to adding the tracer suite to the full resolution ocean component of the Community Earth System Model (CESM) and reasonably reproduces the physical circulation of TraCE-21ka when strong restoring is applied at the surface boundary. Tracers were spun up separately on timescales relevant to their residence times.

## Authors

[Jordan Landers](@jordanplanders)

### Contributors

<a href="https://github.com/LinkedEarth/LMR_CMIP_paleobook/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=LinkedEarth/LMR_CMIP_paleobook" />
</a>

## Structure

This PaleoBook is made up of two sections: Lifehacks, and Science Bits

## Funding
This work was supported by NSF Award ICER 2126510

### Lifehacks

This section covers nuts and bolts about how to assess and work with model grids that aren't indexed on latitude and longitude, access cloud available data, process it, and produce some of visualizations most commonly used to look at ocean variables.

### Science Bits

This section applies the technical skills from the Lifehacks section to explore questions surrounding the evolution of global ocean circulation and tracer distribution since the Last Glacial Maximum. 

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

1. Clone the `https://github.com/jordanplanders/LMR_CMIP_paleobook` repository:

   ```bash
    git clone https://github.com/LinkedEarth/citrace_paleobook
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
