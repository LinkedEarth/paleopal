# Setting up the environment

To setup the environment, run the following commands in the terminal:

```
conda install -n base conda-libmamba-solver
conda config --set solver libmamba
conda env create -f env.yml

conda activate inso_env
conda install ipykernel    
python -m ipykernel install --user --name=asc_env
```

This will create a conda environment named `inso_env` with all the necessary packages installed. The environment can be activated by running `conda activate inso_env`.

Note 1: the commands about `ipykernel` are necessary to make the environment available in Jupyter notebooks.
Note 2: The first two commands regarding libmamba can likely be skipped (this wasn't tested), they are only there so that the more efficient libmamba environment solver is used.