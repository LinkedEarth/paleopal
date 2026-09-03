# Embedding & methodology

## Contents

1. [Choosing E and τ (Figure S1)](1_plot__FigS1_embedding.ipynb)
2. [Simplex Self-Prediction (Figure S2)](2_plot__FigS2_simplex.ipynb)

CCM requires each time series to be represented as a set of embedding vectors —
snippets of recent history described by two parameters: E (embedding dimension, the number of data points), and
τ (time steps between points). This section illustrates how E and τ shape the
resulting snippet (Fig. S1), and shows why no single "optimal" configuration emerged
from simplex self-prediction (Fig. S2) — motivating the parameter-sweep approach used
throughout the rest of this book.

:::{figure} ../../figures/FigS1__embedding/FigS1__embedding.png
Embedding vectors for the GISP2 (Alley, 2000) temperature record across a grid of
embedding dimension (E, columns) and time steps between points (τ, rows) values
(Fig. S1): the target observation (blue) and the earlier points spaced τ steps
apart selected for its embedding vector (red), with horizontal bars showing each
configuration's temporal coverage.
:::