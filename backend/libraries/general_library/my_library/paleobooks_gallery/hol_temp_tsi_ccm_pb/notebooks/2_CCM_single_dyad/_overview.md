# CCM: from a single run to a parameter sweep

:::{figure} ../../figures/Fig2__workflow_diag/stepwise_CCM_workflow_lag.png
Schematic of the CCM pipeline (Fig. 2): embedding each time series into vectors,
building a library, finding nearest neighbors to predict the other variable, and
repeating across library sizes and alignments to test for convergence.
:::

This section walks through Convergent Cross-Mapping at increasing scope:

1. **[A single CCM calculation](1_run__CCMlocally.ipynb)**, using the Erb22–Wu18 dyad:
   for one (E, τ, lag) configuration, estimate CCM skill (ρ) as a function of library
   size, for both the real relationship and its phase-randomized surrogates.
2. **[Library size–ρ trajectories across lags](2_plot__DataGroup_libsize_update.ipynb)**,
   using the GISP2/Alley00–Vieira11 dyad, for that same (E, τ) configuration (Fig. S3),
   used to check convergent behavior and visualize performance for various lags
   relative to surrogate testing envelopes.
3. **[Final ρ at the optimal lag, across a spread of (E, τ) configurations](3_plot__DataGroup_lag.ipynb)**
   (Fig. S4), used to identify the optimal lag configuration used for reporting CCM
   performance in the multi-dyad results grids.
