"""LLM interface for music generation."""

from dataclasses import dataclass
from typing import Optional, Dict, Any
import time

from config import RuntimeConfig


@dataclass
class GenerationResult:
    """Structured result for an LLM generation call."""

    text: str
    tokens: int
    latency: float
    backend: str
    finish_reason: Optional[str] = None
    prompt_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


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
    ) -> GenerationResult:
        """Generate text from prompt."""
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
        text = response.get('response', "")

        tokens_generated = response.get('eval_count')
        if tokens_generated is None:
            tokens_generated = int(len(text.split()) * 1.3)

        tps = tokens_generated / gen_time if gen_time > 0 else 0

        print(f"[ollama] Generated ~{int(tokens_generated)} tokens in {gen_time:.2f}s ({tps:.1f} tokens/sec)")

        return GenerationResult(
            text=text,
            tokens=int(tokens_generated),
            latency=gen_time,
            backend="ollama",
            finish_reason=response.get('done_reason'),
            total_tokens=response.get('eval_count'),
        )


class OpenAIBackend:
    """OpenAI-compatible API backend - for OpenAI, Groq, etc."""

    def __init__(
        self,
        model_name: str,
        runtime_config: RuntimeConfig,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize OpenAI-compatible backend

        Args:
            model_name: Model identifier (e.g., "gpt-3.5-turbo", "llama-3.1-70b-versatile")
            api_key: API key (defaults to OPENAI_API_KEY env var)
            base_url: Custom base URL (e.g., "https://api.groq.com/openai/v1")
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai not installed. Install with:\n"
                "  pip install openai\n"
            )

        self.model_name = model_name
        self.runtime_config = runtime_config

        # Initialize client with custom base_url if provided
        client_kwargs = {}
        if api_key:
            client_kwargs['api_key'] = api_key
        if base_url:
            client_kwargs['base_url'] = base_url

        self.client = OpenAI(**client_kwargs)

        # Store base_url for display
        self.base_url = base_url or "https://api.openai.com/v1"

        print(f"✓ OpenAI-compatible API initialized")
        print(f"  Endpoint: {self.base_url}")
        print(f"  Model: {model_name}")

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
    ) -> GenerationResult:
        """Generate text from prompt."""
        start_time = time.time()

        system_message = kwargs.pop('system_message', None)
        messages = []
        if system_message:
            messages.append({'role': 'system', 'content': system_message})
        messages.append({'role': 'user', 'content': prompt})

        completion_kwargs = {
            'model': self.model_name,
            'messages': messages,
            'max_tokens': max_tokens,
            'temperature': temperature,
            'top_p': top_p,
        }

        if 'reasoning_effort' not in kwargs:
            completion_kwargs['reasoning_effort'] = 'low'
        else:
            completion_kwargs['reasoning_effort'] = kwargs['reasoning_effort']

        if stop:
            completion_kwargs['stop'] = stop

        try:
            response = self.client.chat.completions.create(**completion_kwargs)
        except Exception as exc:
            raise RuntimeError(
                "OpenAI-compatible backend request failed. "
                "Check connectivity, API key, model availability, and base URL."
            ) from exc

        gen_time = time.time() - start_time
        choice = response.choices[0]
        text = choice.message.content or ""

        if not text and hasattr(choice.message, 'reasoning'):
            reasoning = choice.message.reasoning
            if reasoning:
                print(
                    f"⚠️  Reasoning content returned without completion text "
                    f"({len(reasoning)} chars). Preview: {reasoning[:100]}..."
                )

        tokens_generated = response.usage.completion_tokens
        prompt_tokens = response.usage.prompt_tokens
        total_tokens = response.usage.total_tokens
        tps = tokens_generated / gen_time if gen_time > 0 else 0

        if choice.finish_reason == 'length':
            print(f"⚠️  WARNING: Hit token limit! Increase max_tokens (current: {max_tokens})")

        print(
            f"[openai] Generated {tokens_generated} tokens "
            f"(prompt {prompt_tokens}, total {total_tokens}) in {gen_time:.2f}s "
            f"({tps:.1f} tokens/sec)"
        )

        return GenerationResult(
            text=text,
            tokens=tokens_generated,
            latency=gen_time,
            backend="openai",
            finish_reason=choice.finish_reason,
            prompt_tokens=prompt_tokens,
            total_tokens=total_tokens,
        )


class LLMInterface:
    """
    Unified LLM interface for music generation
    Auto-detects and uses the best available backend
    """

    def __init__(
        self,
        model: str,
        runtime_config: RuntimeConfig,
        backend: str = "auto",
        **kwargs
    ):
        """
        Initialize LLM interface

        Args:
            model: Model identifier
                   For Ollama: model name (e.g., "qwen2.5:3b", "phi3:mini")
                   For OpenAI-compatible APIs: model name (e.g., "gpt-4.1-mini", "llama-3.1-70b-versatile")
            runtime_config: Immutable runtime configuration shared across the app.
            backend: "auto", "ollama", or "openai"
            **kwargs: Backend-specific options
                      For OpenAI: api_key, base_url
        """
        self.backend_name = backend
        self.backend = None
        self.runtime_config = runtime_config

        # Auto-detect backend
        if backend == "auto":
            backend = "ollama"

        # Initialize backend
        if backend == "ollama":
            print(f"Using Ollama backend")
            self.backend = OllamaBackend(model_name=model, **kwargs)
            self.backend_name = "ollama"

        elif backend == "openai":
            print(f"Using OpenAI-compatible API backend")
            self.backend = OpenAIBackend(model_name=model, runtime_config=runtime_config, **kwargs)
            self.backend_name = "openai"

        else:
            raise ValueError(f"Unknown backend: {backend}")

    def generate(self, prompt: str, **kwargs) -> GenerationResult:
        """Generate text from prompt"""
        return self.backend.generate(prompt, **kwargs)


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
