# PaleoPal VSCode Extension (Scaffold)

Commands:
- PaleoPal: New Conversation
- PaleoPal: Ask Agent
- PaleoPal: Insert Result
- PaleoPal: Run Notebook Locally

Settings:
- paleopal.backendUrl (default http://localhost:8000/api)
- paleopal.defaultProvider (openai|anthropic|google|ollama|grok)
- paleopal.defaultModel

Notes:
- This scaffold uses the active editor (markdown) as a proxy for a notebook. In a full implementation, adopt VS Code Notebook API and ipynb editing for richer UX.
- Calls backend stateless endpoints with metadata.stateless=true and metadata.enable_execution=false so code runs locally.
