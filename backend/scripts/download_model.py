#!/usr/bin/env python3
"""
Download embedding model to local cache directory.
This script can be run on the host machine to pre-download models for Docker.
"""
import os
import sys
from pathlib import Path

def download_model_using_huggingface_hub():
    """Download model using huggingface_hub (lighter weight, no PyTorch needed)."""
    try:
        from huggingface_hub import snapshot_download
        
        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        cache_dir = Path(__file__).parent.parent / "models_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Downloading {model_name} to {cache_dir}...")
        print("This may take a few minutes...")
        
        snapshot_download(
            repo_id=model_name,
            cache_dir=str(cache_dir),
            local_dir=str(cache_dir / "all-MiniLM-L6-v2"),
            local_dir_use_symlinks=False
        )
        
        print(f"✅ Model downloaded successfully to {cache_dir}")
        return True
        
    except ImportError:
        print("❌ huggingface_hub not installed. Install with: pip install huggingface_hub")
        return False
    except Exception as e:
        print(f"❌ Error downloading model: {e}")
        return False

def download_model_using_sentence_transformers():
    """Download model using sentence-transformers (requires PyTorch)."""
    try:
        from sentence_transformers import SentenceTransformer
        
        model_name = "all-MiniLM-L6-v2"
        cache_dir = Path(__file__).parent.parent / "models_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Downloading {model_name} to {cache_dir}...")
        print("This may take a few minutes...")
        
        # Load model which will download it
        model = SentenceTransformer(model_name, cache_folder=str(cache_dir))
        
        print(f"✅ Model downloaded successfully to {cache_dir}")
        print(f"Model loaded: {model}")
        return True
        
    except ImportError as e:
        print(f"❌ sentence-transformers not installed: {e}")
        print("Install with: pip install sentence-transformers")
        return False
    except Exception as e:
        print(f"❌ Error downloading model: {e}")
        return False

def main():
    """Try different methods to download the model."""
    print("=" * 60)
    print("PaleoPal Model Downloader")
    print("=" * 60)
    print()
    
    # Try huggingface_hub first (lighter weight)
    print("Method 1: Using huggingface_hub (recommended)...")
    if download_model_using_huggingface_hub():
        return
    
    print()
    print("Method 2: Using sentence-transformers...")
    if download_model_using_sentence_transformers():
        return
    
    print()
    print("=" * 60)
    print("❌ Failed to download model using both methods.")
    print()
    print("Alternative: Copy from existing HuggingFace cache:")
    print("  cp -r ~/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2 backend/models_cache/")
    print()
    print("Or install dependencies:")
    print("  pip install huggingface_hub")
    print("  # OR")
    print("  pip install sentence-transformers")
    print("=" * 60)
    sys.exit(1)

if __name__ == "__main__":
    main()

