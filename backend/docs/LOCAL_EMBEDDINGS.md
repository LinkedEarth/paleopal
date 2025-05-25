# Local Embeddings for PaleoPal

PaleoPal now supports fast local embedding options that don't require API calls or internet connectivity. This provides better privacy, reduced costs, and faster response times for embedding operations.

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Install all local embedding dependencies
cd backend
pip install -r requirements-local-embeddings.txt

# Or install specific providers
pip install sentence-transformers  # For sentence-transformers
pip install ollama                 # For Ollama embeddings
pip install transformers torch     # For HuggingFace models
```

### 2. Configure Environment

Set your embedding provider in your `.env` file:

```bash
# Use sentence-transformers (recommended for most users)
EMBEDDING_PROVIDER=sentence-transformers

# Or use Ollama (requires Ollama server running)
EMBEDDING_PROVIDER=ollama

# Or use HuggingFace transformers
EMBEDDING_PROVIDER=huggingface
```

### 3. Test Your Setup

```bash
# Check what's available
python scripts/setup_local_embeddings.py --check

# Test a specific provider
python scripts/setup_local_embeddings.py --test sentence-transformers

# Get recommendations
python scripts/setup_local_embeddings.py --recommendations

# Run all tests
python scripts/setup_local_embeddings.py --all
```

## 📊 Available Providers

### 1. Sentence-Transformers (Recommended)
- **Best for**: Most users, fast setup, good quality
- **Pros**: Easy to install, fast, good quality embeddings
- **Cons**: Requires downloading models (~100MB each)
- **Models**:
  - `all-MiniLM-L6-v2` (default) - Fast and lightweight
  - `all-mpnet-base-v2` - Higher quality, slower
  - `allenai-specter` - Optimized for scientific text
  - `paraphrase-multilingual-MiniLM-L12-v2` - Multilingual support

### 2. Ollama Embeddings
- **Best for**: Users already running Ollama
- **Pros**: Integrates with existing Ollama setup
- **Cons**: Requires Ollama server running
- **Models**:
  - `nomic-embed-text` (default) - General purpose
  - `mxbai-embed-large` - High quality embeddings

### 3. HuggingFace Transformers
- **Best for**: Advanced users, custom models
- **Pros**: Access to any HuggingFace model, GPU support
- **Cons**: More complex setup, larger memory usage
- **Models**: Any sentence-transformers compatible model on HuggingFace

## 🎯 Use Case Recommendations

| Use Case | Provider | Model | Why |
|----------|----------|-------|-----|
| **Development/Testing** | sentence-transformers | all-MiniLM-L6-v2 | Fast, lightweight |
| **Production (General)** | sentence-transformers | all-mpnet-base-v2 | Best quality/speed balance |
| **Scientific Text** | sentence-transformers | allenai-specter | Optimized for scientific papers |
| **Multilingual** | sentence-transformers | paraphrase-multilingual-* | Supports multiple languages |
| **Existing Ollama Users** | ollama | nomic-embed-text | Leverages existing setup |
| **Custom Requirements** | huggingface | custom model | Maximum flexibility |

## ⚙️ Configuration Options

### Environment Variables

```bash
# Basic configuration
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Ollama configuration
OLLAMA_BASE_URL=http://localhost:11434

# Advanced: Model-specific settings
SENTENCE_TRANSFORMERS_CACHE_FOLDER=/path/to/cache
HUGGINGFACE_DEVICE=cuda  # or cpu
```

### Programmatic Configuration

```python
from services.local_embeddings import create_local_embeddings

# Create embeddings with specific model
embeddings = create_local_embeddings(
    provider="sentence-transformers",
    model_name="all-mpnet-base-v2"
)

# Test embedding
text = "paleoclimate temperature data"
embedding = embeddings.embed_query(text)
print(f"Embedding dimension: {len(embedding)}")
```

## 🔧 API Endpoints

### Check Available Providers
```bash
curl http://localhost:8000/embeddings/providers
```

### Test a Provider
```bash
curl http://localhost:8000/embeddings/test/sentence-transformers
curl http://localhost:8000/embeddings/test/ollama?model=nomic-embed-text
```

## 📈 Performance Comparison

| Provider | Model | Speed | Quality | Memory | Disk Space |
|----------|-------|-------|---------|--------|------------|
| sentence-transformers | all-MiniLM-L6-v2 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ~100MB | ~90MB |
| sentence-transformers | all-mpnet-base-v2 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ~400MB | ~420MB |
| sentence-transformers | allenai-specter | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ~400MB | ~440MB |
| ollama | nomic-embed-text | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ~300MB | ~270MB |
| huggingface | custom | ⭐⭐ | ⭐⭐⭐⭐⭐ | ~500MB+ | varies |

## 🛠️ Troubleshooting

### Common Issues

1. **Import Error: sentence-transformers not found**
   ```bash
   pip install sentence-transformers
   ```

2. **Ollama connection error**
   ```bash
   # Make sure Ollama is running
   ollama serve
   
   # Pull the embedding model
   ollama pull nomic-embed-text
   ```

3. **CUDA out of memory (HuggingFace)**
   ```python
   # Force CPU usage
   embeddings = create_local_embeddings(
       provider="huggingface",
       device="cpu"
   )
   ```

4. **Model download issues**
   ```bash
   # Set cache directory
   export SENTENCE_TRANSFORMERS_HOME=/path/to/cache
   ```

### Performance Tips

1. **Use GPU for HuggingFace models** (if available):
   ```bash
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
   ```

2. **Cache models locally**:
   ```bash
   export SENTENCE_TRANSFORMERS_HOME=~/.cache/sentence_transformers
   ```

3. **Batch processing** for multiple documents:
   ```python
   # More efficient than individual calls
   embeddings = model.embed_documents(list_of_texts)
   ```

## 🔄 Migration from API-based Embeddings

### From OpenAI
```bash
# Old configuration
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-ada-002

# New configuration (recommended)
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL=all-mpnet-base-v2
```

### Re-initialize Embeddings
After changing providers, you'll need to re-initialize your vector databases:

```bash
# Via API
curl -X POST http://localhost:8000/db/initialize

# Or via CLI
python scripts/setup_local_embeddings.py --test sentence-transformers
```

## 📚 Advanced Usage

### Custom Model Configuration
```python
from services.local_embeddings import SentenceTransformersEmbeddings

# Use a specific model with custom cache
embeddings = SentenceTransformersEmbeddings(
    model_name="sentence-transformers/all-mpnet-base-v2",
    cache_folder="/custom/cache/path"
)
```

### Batch Processing
```python
# Process multiple texts efficiently
texts = ["text1", "text2", "text3"]
embeddings_list = embeddings.embed_documents(texts)
```

### Model Comparison
```python
from services.local_embeddings import get_recommended_model

# Get recommendations for different use cases
fast_model = get_recommended_model("fast")
quality_model = get_recommended_model("quality")
scientific_model = get_recommended_model("scientific")
```

## 🤝 Contributing

To add support for new local embedding providers:

1. Implement the provider class in `services/local_embeddings.py`
2. Add configuration in `config.py`
3. Update the factory function `create_local_embeddings()`
4. Add tests in the setup script
5. Update this documentation

## 📄 License

Local embedding support uses the same license as PaleoPal. Individual embedding models may have their own licenses - please check the model documentation. 