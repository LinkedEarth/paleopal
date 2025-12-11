### Install and run Qdrant locally

In most cases, this will already been down in the first step (docker compose):

- Recommended (matches defaults used by the indexers):
```bash
docker run -p 6333:6333 -p 6334:6334 -v qdrant-data:/qdrant/storage --name paleopal-qdrant qdrant/qdrant:v1.7.0
```
- If you use the provided docker-compose, Qdrant is exposed on host port 6333. In that case set QDRANT_PORT=6333 when running indexers on your host.

### Python environment

This is only for filling up the Quadrant. You do not need to be within this environment when running PaleoPAL later. 

```bash
cd /Users/varun/git/paleopal
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### Required environment variables
Set these in your shell before indexing (or in your `.env` if you prefer). Values shown match the simple `docker run` above:
```bash
export QDRANT_HOST=localhost
export QDRANT_PORT=6335
# Optional: only if your Qdrant requires auth
# export QDRANT_API_KEY=...

# Optional: change embedding model used by sentence-transformers
# Note: qdrant_config.py reads EMBED_MODEL (not EMBED_MODEL_NAME)
# export EMBED_MODEL=all-MiniLM-L6-v2
```

### Prepare notebooks to index
- Create the folder and add any `.ipynb` you want indexed:
```bash
mkdir -p /Users/varun/git/paleopal/backend/libraries/notebook_library/my_notebooks
# Copy or save your notebooks into that folder
```

### Verify Qdrant connectivity (optional but recommended)
```bash
cd /Users/varun/git/paleopal/backend/libraries
python qdrant_config.py --status
# You should see "qdrant_server": "connected"
```

### Run the indexers
- From the libraries directory:
```bash
cd /Users/varun/git/paleopal/backend/libraries
bash index_everything.sh
```
This will:
- Index SPARQL queries
- Index ontology entities
- Index notebook snippets/workflows from `notebook_library/my_notebooks`
- Index ReadTheDocs docs/symbols/code
- Index extracted literature methods

If you only want notebooks:
```bash
cd /Users/varun/git/paleopal/backend/libraries
python notebook_library/index_notebooks.py --keep-invalid --no-synth-imports notebook_library/my_notebooks
```

### Check collections and counts (optional)
```bash
cd /Users/varun/git/paleopal/backend/libraries
python qdrant_config.py --libraries
python qdrant_config.py --health
```

Notes:
- If using docker-compose, either:
  - Set `export QDRANT_PORT=6333` on host before indexing, or
  - Run indexing inside a container that can reach `qdrant:6333`.
- The first run will download the embedding model; allow a few minutes.

- I confirmed the env keys from `qdrant_config.py`: QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY (optional), and EMBED_MODEL (optional).
- Per your requirement, indexing expects the `notebook_library/my_notebooks` folder to exist with your notebooks.
