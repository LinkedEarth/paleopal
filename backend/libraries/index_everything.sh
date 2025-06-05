# Index Sparql Queries
python sparql_library/index_queries.py --queries-dir sparql_library/queries

# Index Ontology Library
python ontology_library/index_ontology.py --data-file ontology_library/ontology/indexing_data.json

# Index Notebooks
python notebook_library/index_notebooks.py --keep-invalid --no-synth-imports notebook_library/my_notebooks

# Index ReadtheDocs documentation for Pyleoclim and PyliPD
python readthedocs_library/index_docs.py readthedocs_library/my_docs_simple
python readthedocs_library/index_symbols.py readthedocs_library/my_docs_simple
python readthedocs_library/index_code.py readthedocs_library/my_docs_simple

# Index Literature (Extracted Methods)
python literature_library/index_methods.py --json-dir literature_library/my_documents/extracted_methods
