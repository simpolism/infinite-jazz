"""
LLM interface for music generation
Primary: Ollama (easy install, great performance)
Alternative: llama-cpp-python (if you prefer manual setup)
"""

from typing import Optional, Dict, Any
from pathlib import Path
import time


class OllamaBackend:
    """Ollama backend - easiest and recommended"""

    def __init__(
        self,
        model_name: str,
        base_url: str = "http://localhost:11434",
        **kwargs
    ):
        """
        Initialize Ollama backend

        Args:
            model_name: Ollama model name (e.g., "qwen2.5:3b", "phi3:mini")
            base_url: Ollama server URL
        """
        try:
            import ollama
        except ImportError:
            raise ImportError(
                "ollama not installed. Install with:\n"
                "  pip install ollama\n"
                "Then install Ollama itself:\n"
                "  Linux: curl -fsSL https://ollama.com/install.sh | sh\n"
                "  macOS: brew install ollama\n"
                "  Windows: https://ollama.com/download\n"
            )

        self.client = ollama.Client(host=base_url)
        self.model_name = model_name

        # Check if model exists, pull if not
        print(f"Checking for model: {model_name}")
        try:
            # Try to get model info
            self.client.show(model_name)
            print(f"✓ Model found: {model_name}")
        except:
            print(f"Model not found locally. Pulling {model_name}...")
            print("This may take a few minutes on first run...")
            self.client.pull(model_name)
            print(f"✓ Model pulled: {model_name}")

    def generate(
        self,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.8,
        top_p: float = 0.95,
        top_k: int = 40,
        repeat_penalty: float = 1.1,
        stop: Optional[list] = None,
        **kwargs
    ) -> str:
        """Generate text from prompt"""
        start_time = time.time()

        # Ollama options
        options = {
            'temperature': temperature,
            'top_p': top_p,
            'top_k': top_k,
            'repeat_penalty': repeat_penalty,
            'num_predict': max_tokens,
        }

        if stop:
            options['stop'] = stop

        response = self.client.generate(
            model=self.model_name,
            prompt=prompt,
            options=options,
            stream=False
        )

        gen_time = time.time() - start_time
        text = response['response']

        # Calculate approximate TPS
        # Ollama doesn't always provide token counts, so estimate
        tokens_generated = response.get('eval_count', len(text.split()) * 1.3)
        tps = tokens_generated / gen_time if gen_time > 0 else 0

        print(f"Generated ~{int(tokens_generated)} tokens in {gen_time:.2f}s ({tps:.1f} tokens/sec)")

        return text


class LlamaCppBackend:
    """llama-cpp-python backend - alternative if you have it installed"""

    def __init__(
        self,
        model_path: str,
        n_ctx: int = 2048,
        n_gpu_layers: int = -1,
        n_threads: Optional[int] = None,
        verbose: bool = False
    ):
        """Initialize llama-cpp-python backend"""
        try:
            from llama_cpp import Llama
        except ImportError:
            raise ImportError(
                "llama-cpp-python not installed. Install with:\n"
                "  pip install llama-cpp-python\n"
                "For GPU support (CUDA):\n"
                "  CMAKE_ARGS=\"-DGGML_CUDA=on\" pip install llama-cpp-python\n"
                "\nOr use Ollama instead (much easier):\n"
                "  pip install ollama"
            )

        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        print(f"Loading model: {self.model_path}")
        print(f"  Context size: {n_ctx}")
        print(f"  GPU layers: {n_gpu_layers} ({'all' if n_gpu_layers == -1 else n_gpu_layers})")

        start_time = time.time()

        self.llm = Llama(
            model_path=str(self.model_path),
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            n_threads=n_threads,
            verbose=verbose
        )

        load_time = time.time() - start_time
        print(f"Model loaded in {load_time:.2f}s")

    def generate(
        self,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.8,
        top_p: float = 0.95,
        top_k: int = 40,
        repeat_penalty: float = 1.1,
        stop: Optional[list] = None,
        **kwargs
    ) -> str:
        """Generate text from prompt"""
        start_time = time.time()

        output = self.llm(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            repeat_penalty=repeat_penalty,
            stop=stop or [],
            echo=False
        )

        gen_time = time.time() - start_time
        text = output['choices'][0]['text']
        tokens_generated = output['usage']['completion_tokens']
        tps = tokens_generated / gen_time if gen_time > 0 else 0

        print(f"Generated {tokens_generated} tokens in {gen_time:.2f}s ({tps:.1f} tokens/sec)")

        return text


class LLMInterface:
    """
    Unified LLM interface for music generation
    Auto-detects and uses the best available backend
    """

    def __init__(
        self,
        model: str,
        backend: str = "auto",
        **kwargs
    ):
        """
        Initialize LLM interface

        Args:
            model: Model identifier
                   For Ollama: model name (e.g., "qwen2.5:3b", "phi3:mini")
                   For llama.cpp: path to GGUF file
            backend: "auto", "ollama", or "llama-cpp"
            **kwargs: Backend-specific options
        """
        self.backend_name = backend
        self.backend = None

        # Auto-detect backend
        if backend == "auto":
            # Check if model looks like a file path
            if Path(model).exists() or model.endswith('.gguf'):
                backend = "llama-cpp"
            else:
                backend = "ollama"

        # Initialize backend
        if backend == "ollama":
            print(f"Using Ollama backend")
            self.backend = OllamaBackend(model_name=model, **kwargs)
            self.backend_name = "ollama"

        elif backend == "llama-cpp":
            print(f"Using llama-cpp-python backend")
            self.backend = LlamaCppBackend(model_path=model, **kwargs)
            self.backend_name = "llama-cpp"

        else:
            raise ValueError(f"Unknown backend: {backend}")

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text from prompt"""
        return self.backend.generate(prompt, **kwargs)


class GenerationConfig:
    """Configuration for music generation"""

    # Default generation parameters
    BASS_CONFIG = {
        'max_tokens': 256,
        'temperature': 0.7,
        'top_p': 0.9,
        'repeat_penalty': 1.15,
        'stop': ['\n\nDRUMS', '\n\nPIANO', '\n\nSAX', '\n\n']
    }

    DRUMS_CONFIG = {
        'max_tokens': 256,
        'temperature': 0.8,
        'top_p': 0.9,
        'repeat_penalty': 1.1,
        'stop': ['\n\nPIANO', '\n\nSAX', '\n\nBASS', '\n\n']
    }

    PIANO_CONFIG = {
        'max_tokens': 256,
        'temperature': 0.75,
        'top_p': 0.92,
        'repeat_penalty': 1.12,
        'stop': ['\n\nSAX', '\n\nBASS', '\n\nDRUMS', '\n\n']
    }

    SAX_CONFIG = {
        'max_tokens': 256,
        'temperature': 0.85,
        'top_p': 0.95,
        'repeat_penalty': 1.1,
        'stop': ['\n\nBASS', '\n\nDRUMS', '\n\nPIANO', '\n\n']
    }

    @classmethod
    def get_config(cls, instrument: str) -> Dict[str, Any]:
        """Get generation config for instrument"""
        configs = {
            'BASS': cls.BASS_CONFIG,
            'DRUMS': cls.DRUMS_CONFIG,
            'PIANO': cls.PIANO_CONFIG,
            'SAX': cls.SAX_CONFIG
        }
        return configs.get(instrument, cls.BASS_CONFIG).copy()


# Recommended models for Ollama
RECOMMENDED_MODELS = {
    'qwen2.5:3b': {
        'name': 'Qwen 2.5 3B',
        'size': '~2GB',
        'description': 'Recommended: Best quality, fast'
    },
    'phi3:mini': {
        'name': 'Phi-3 Mini',
        'size': '~2.3GB',
        'description': 'Alternative: Good instruction following'
    },
    'llama3.2:3b': {
        'name': 'Llama 3.2 3B',
        'size': '~2GB',
        'description': 'Alternative: Good general model'
    }
}


def list_ollama_models():
    """List available Ollama models"""
    try:
        import ollama
        client = ollama.Client()
        models = client.list()

        print("\nInstalled Ollama models:")
        for model in models.get('models', []):
            print(f"  - {model['name']}")

        if not models.get('models'):
            print("  (none installed)")
            print("\nRecommended models:")
            for name, info in RECOMMENDED_MODELS.items():
                print(f"  {name}: {info['description']}")
            print("\nPull with: ollama pull <model>")

    except ImportError:
        print("Ollama not installed. Install with: pip install ollama")
    except Exception as e:
        print(f"Error listing models: {e}")


def find_model(model_dir: str = "models") -> Optional[Path]:
    """
    Find a GGUF model in the models directory
    Returns the first .gguf file found
    """
    model_path = Path(model_dir)
    if not model_path.exists():
        return None

    gguf_files = list(model_path.glob("*.gguf"))
    if gguf_files:
        return gguf_files[0]

    return None
