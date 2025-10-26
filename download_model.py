#!/usr/bin/env python3
"""
Helper script to download GGUF models for JazzAI (Advanced - llama-cpp-python)

NOTE: This is only needed if you want to use llama-cpp-python instead of Ollama.
For most users, Ollama is easier - it auto-downloads models when you use them.

Usage:
  python download_model.py qwen-3b-q5
  python realtime_jazz.py -m models/qwen2.5-3b-instruct-q5_k_m.gguf --llm-backend llama-cpp
"""

import sys
import argparse
from pathlib import Path


MODELS = {
    'qwen-3b-q5': {
        'name': 'Qwen 2.5 3B (Q5_K_M)',
        'repo': 'Qwen/Qwen2.5-3B-Instruct-GGUF',
        'file': 'qwen2.5-3b-instruct-q5_k_m.gguf',
        'size': '~2.3GB',
        'description': 'Recommended: Best quality, ~100 TPS on 4070 Ti Super'
    },
    'qwen-3b-q4': {
        'name': 'Qwen 2.5 3B (Q4_K_M)',
        'repo': 'Qwen/Qwen2.5-3B-Instruct-GGUF',
        'file': 'qwen2.5-3b-instruct-q4_k_m.gguf',
        'size': '~1.9GB',
        'description': 'Faster: ~120 TPS, slightly lower quality'
    },
    'phi3-mini-q5': {
        'name': 'Phi-3 Mini (Q5_K_M)',
        'repo': 'microsoft/Phi-3-mini-4k-instruct-gguf',
        'file': 'Phi-3-mini-4k-instruct-q4.gguf',
        'size': '~2.2GB',
        'description': 'Alternative: Good instruction following'
    }
}


def download_model(model_key: str, output_dir: str = 'models'):
    """Download a model using huggingface-hub"""
    if model_key not in MODELS:
        print(f"Error: Unknown model '{model_key}'")
        print(f"Available models: {', '.join(MODELS.keys())}")
        sys.exit(1)

    model_info = MODELS[model_key]

    print(f"\nDownloading: {model_info['name']}")
    print(f"Size: {model_info['size']}")
    print(f"Repository: {model_info['repo']}")
    print(f"File: {model_info['file']}\n")

    # Check if huggingface-hub is installed
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("Error: huggingface-hub not installed")
        print("Install with: pip install huggingface-hub")
        sys.exit(1)

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # Check if file already exists
    output_file = output_path / model_info['file']
    if output_file.exists():
        print(f"Model already exists: {output_file}")
        response = input("Download anyway? (y/n): ")
        if response.lower() != 'y':
            print("Skipping download")
            return str(output_file)

    # Download
    print("Downloading... (this may take a few minutes)\n")
    try:
        downloaded_path = hf_hub_download(
            repo_id=model_info['repo'],
            filename=model_info['file'],
            local_dir=str(output_path),
            local_dir_use_symlinks=False
        )
        print(f"\n✓ Download complete: {downloaded_path}")
        return downloaded_path

    except Exception as e:
        print(f"\nError downloading model: {e}")
        sys.exit(1)


def list_models():
    """List available models"""
    print("\nAvailable models:\n")
    for key, info in MODELS.items():
        print(f"  {key}")
        print(f"    Name: {info['name']}")
        print(f"    Size: {info['size']}")
        print(f"    {info['description']}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Download models for JazzAI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download recommended model
  python download_model.py qwen-3b-q5

  # List available models
  python download_model.py --list

  # Download to custom directory
  python download_model.py qwen-3b-q5 --output-dir my_models
        """
    )

    parser.add_argument(
        'model',
        nargs='?',
        help='Model to download (use --list to see options)'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List available models'
    )
    parser.add_argument(
        '--output-dir',
        default='models',
        help='Output directory (default: models/)'
    )

    args = parser.parse_args()

    if args.list:
        list_models()
        return

    if not args.model:
        print("Error: Please specify a model to download")
        print("Use --list to see available models")
        sys.exit(1)

    download_model(args.model, args.output_dir)

    print("\n" + "="*60)
    print("Setup complete!")
    print("="*60)
    print("\nNext steps:")
    print("  1. Test playback: python test_playback.py")
    print("  2. Test generation: python test_generation.py")
    print("  3. Run JazzAI: python realtime_jazz.py")
    print("\n")


if __name__ == '__main__':
    main()
