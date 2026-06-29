# Setting up the environment

To setup the environment, run the following commands in the terminal:

```
conda install -n base conda-libmamba-solver
conda config --set solver libmamba
conda env create -f env.yml

conda activate cropper_ecs_env
conda install ipykernel    
python -m ipykernel install --user --name=cropper_ecs_env
```

This will create a conda environment named `cropper_ecs_env` with all the necessary packages installed. The environment can be activated by running `conda activate cropper_ecs_env`.

Note: the commands about `ipykernel` are necessary to make the environment available in Jupyter notebooks.