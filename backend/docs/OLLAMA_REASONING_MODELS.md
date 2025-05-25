# Ollama Reasoning Models Support

PaleoPal now properly supports Ollama reasoning models like `deepseek-r1` that include `<think></think>` tags in their output and may not always return clean JSON.

## 🎯 Problem Solved

Reasoning models like `deepseek-r1` often return responses like:
```
<think>
Let me think about this SPARQL query...
The user wants to find coral data...
</think>

{
    "query": "SELECT ?archive ?temp WHERE { ... }",
    "description": "Finds coral archives with temperature data"
}
```

This breaks JSON parsing and causes errors in the SPARQL generation pipeline.

## ✅ Solution Implemented

### 1. **Automatic Reasoning Model Detection**
The system automatically detects reasoning models based on configurable patterns:
- `deepseek-r1` (all variants)
- `marco-o1`
- `qwen2.5-coder`
- `thinking-model`

### 2. **Response Cleaning**
- Automatically removes `<think>`, `<thinking>`, and `<thought>` tags
- Cleans up extra whitespace
- Preserves the actual response content

### 3. **Smart JSON Extraction**
Multiple fallback methods to extract JSON:
- Code block detection (```json)
- Brace matching for nested objects
- Line-by-line parsing
- Pattern matching for simple JSON

### 4. **Optimized Parameters**
For reasoning models, the system uses:
- Lower temperature (0.1) for more consistent JSON
- Adjusted top_p and repeat_penalty
- Clear instructions for JSON-only output

## 🔧 Configuration

### Environment Variables
```bash
# Comma-separated list of reasoning model names
OLLAMA_REASONING_MODELS=deepseek-r1,marco-o1,qwen2.5-coder,thinking-model

# JSON generation parameters for reasoning models
OLLAMA_JSON_TEMPERATURE=0.1
OLLAMA_JSON_TOP_P=0.9
OLLAMA_JSON_REPEAT_PENALTY=1.1
```

### Programmatic Configuration
```python
from services.llm_providers import OllamaProvider

# Initialize with automatic reasoning detection
provider = OllamaProvider(model_name="deepseek-r1")

# Check if it's detected as a reasoning model
if provider.is_reasoning_model:
    print("Reasoning model detected - will clean responses")
```

## 🧪 Testing

Test the reasoning model handling:
```bash
cd backend
python test_ollama_reasoning.py
```

This will:
1. Test response cleaning functions
2. Test basic JSON generation
3. Test complex SPARQL generation
4. Verify JSON parsing works correctly

## 📋 Example Usage

### Before (Broken)
```python
# This would fail with deepseek-r1
response = provider.generate_response([
    {"role": "user", "content": "Generate SPARQL query as JSON"}
])
# Response: "<think>...</think>\n{\"query\": \"...\"}"
json.loads(response)  # ❌ JSONDecodeError
```

### After (Fixed)
```python
# This now works correctly
response = provider.generate_response([
    {"role": "user", "content": "Generate SPARQL query as JSON"}
])
# Response: "{\"query\": \"...\"}"  (cleaned automatically)
json.loads(response)  # ✅ Success
```

## 🎮 Interactive Testing

You can test individual components:

```python
from services.llm_providers import clean_reasoning_response, extract_json_from_response

# Test cleaning
dirty_response = "<think>reasoning...</think>\n{\"key\": \"value\"}"
clean_response = clean_reasoning_response(dirty_response)
print(clean_response)  # {"key": "value"}

# Test JSON extraction
mixed_response = "Here's the result:\n{\"query\": \"SELECT...\"}\nHope this helps!"
json_only = extract_json_from_response(mixed_response)
print(json_only)  # {"query": "SELECT..."}
```

## 🔄 Model Support

### Currently Supported Reasoning Models
- **DeepSeek R1**: `deepseek-r1`, `deepseek-r1:1.5b`, `deepseek-r1:7b`, etc.
- **Marco O1**: `marco-o1`
- **Qwen Coder**: `qwen2.5-coder:32b-instruct`
- **Generic**: Any model with `thinking-model` in the name

### Adding New Reasoning Models
1. Update the configuration:
   ```bash
   OLLAMA_REASONING_MODELS=deepseek-r1,marco-o1,your-new-model
   ```

2. Or modify `backend/config.py`:
   ```python
   OLLAMA_REASONING_MODELS = [
       "deepseek-r1", "marco-o1", "your-new-model"
   ]
   ```

## 🐛 Troubleshooting

### Common Issues

1. **Model not detected as reasoning model**
   - Check if model name is in `OLLAMA_REASONING_MODELS`
   - Model names are matched using substring matching

2. **JSON still not parsing**
   - Run the test script to see what's happening
   - Check the raw response in logs
   - The fallback methods should handle most cases

3. **Performance issues**
   - Reasoning models are slower due to their thinking process
   - Adjust temperature settings if needed
   - Consider using non-reasoning models for simple tasks

### Debug Mode
Enable detailed logging to see the cleaning process:
```python
import logging
logging.getLogger('services.llm_providers').setLevel(logging.DEBUG)
```

## 🚀 Performance Tips

1. **Use reasoning models only when needed** - They're slower but more accurate
2. **Adjust temperature** - Lower values (0.1) give more consistent JSON
3. **Be specific in prompts** - Ask explicitly for JSON-only responses
4. **Use system messages** - Set clear expectations about output format

## 📊 Compatibility

| Model | Reasoning Tags | JSON Support | Status |
|-------|---------------|--------------|---------|
| deepseek-r1 | ✅ | ✅ | Fully supported |
| marco-o1 | ✅ | ✅ | Fully supported |
| qwen2.5-coder | ✅ | ✅ | Fully supported |
| llama2 | ❌ | ✅ | Standard support |
| codellama | ❌ | ✅ | Standard support | 