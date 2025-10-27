"""
LLM interface for music generation.
Supports Ollama for local inference and OpenAI-compatible APIs (e.g., Groq).
"""

from typing import Optional, Dict, Any
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


class OpenAIBackend:
    """OpenAI-compatible API backend - for OpenAI, Groq, etc."""

    def __init__(
        self,
        model_name: str,
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
    ) -> str:
        """Generate text from prompt"""
        start_time = time.time()

        # Split prompt into system and user messages for better instruction following
        system_msg, user_msg = self._split_prompt(prompt)

        # Note: OpenAI API doesn't support top_k or repeat_penalty
        # We'll use what's available
        messages = [
            {'role': 'system', 'content': system_msg},
            {'role': 'user', 'content': user_msg}
        ]

        completion_kwargs = {
            'model': self.model_name,
            'messages': messages,
            'max_tokens': max_tokens,
            'temperature': temperature,
            'top_p': top_p,
        }

        # For reasoning models, use low reasoning effort to save tokens for output
        if 'reasoning_effort' not in kwargs:
            completion_kwargs['reasoning_effort'] = 'low'
        else:
            completion_kwargs['reasoning_effort'] = kwargs['reasoning_effort']

        if stop:
            completion_kwargs['stop'] = stop

        response = self.client.chat.completions.create(**completion_kwargs)

        gen_time = time.time() - start_time
        text = response.choices[0].message.content

        # Handle reasoning models (like gpt-oss) that may have reasoning field
        if not text and hasattr(response.choices[0].message, 'reasoning'):
            reasoning = response.choices[0].message.reasoning
            if reasoning:
                print(f"⚠️  Note: This appears to be a reasoning model. Content was empty but reasoning field had {len(reasoning)} chars.")
                print(f"Reasoning preview: {reasoning[:100]}...")

        # Get token counts from usage
        tokens_generated = response.usage.completion_tokens
        tps = tokens_generated / gen_time if gen_time > 0 else 0

        # Check if we hit token limit
        if response.choices[0].finish_reason == 'length':
            print(f"⚠️  WARNING: Hit token limit! Increase max_tokens (current: {max_tokens})")

        print(f"Generated {tokens_generated} tokens in {gen_time:.2f}s ({tps:.1f} tokens/sec)")

        return text or ""

    def _split_prompt(self, prompt: str) -> tuple[str, str]:
        """
        Split prompt into system and user messages for better instruction following.

        Strategy:
        - System message: Instructions, format rules, examples
        - User message: The actual generation request
        """
        # Look for common split points in our prompts
        split_markers = [
            "\nGenerate YOUR version now.",
            "\nContinue the bass part:",
            "\nGenerate drums:",
            "\nGenerate piano:",
            "\nGenerate sax:",
            "Output only the notes, starting immediately."
        ]

        for marker in split_markers:
            if marker in prompt:
                parts = prompt.split(marker, 1)
                system_msg = parts[0].strip()
                user_msg = marker.strip() + (parts[1] if len(parts) > 1 else "")

                # Add explicit start trigger to user message
                if "Generate YOUR version now" in marker:
                    import config
                    steps = config.get_total_steps()
                    user_msg += f"\n\nStart your output with 'BASS' on the first line, then provide exactly {steps} numbered lines per instrument:"
                elif "Output only the notes" in marker:
                    import config
                    steps = config.get_total_steps()
                    user_msg += f"\n\nBegin outputting {steps} numbered lines now:"

                return system_msg, user_msg

        # Fallback: if no marker found, split at "You are" / "Generate" boundary
        # Put all instructions in system, minimal user message
        if "You are a jazz" in prompt:
            # Everything up to the last newline is system
            lines = prompt.split('\n')
            # Find the last substantial instruction line
            for i in range(len(lines) - 1, -1, -1):
                if lines[i].strip() and not lines[i].strip().startswith('Generate'):
                    system_msg = '\n'.join(lines[:i+1])
                    user_msg = '\n'.join(lines[i+1:]).strip() or "Generate the music now in the specified format:"
                    return system_msg, user_msg

        # Last resort: entire prompt as system, simple user message
        return prompt, "Generate the output in the exact format specified above. Start immediately with the first line of output:"


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
                   For OpenAI-compatible APIs: model name (e.g., "gpt-4.1-mini", "llama-3.1-70b-versatile")
            backend: "auto", "ollama", or "openai"
            **kwargs: Backend-specific options
                      For OpenAI: api_key, base_url
        """
        self.backend_name = backend
        self.backend = None

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
            self.backend = OpenAIBackend(model_name=model, **kwargs)
            self.backend_name = "openai"

        else:
            raise ValueError(f"Unknown backend: {backend}")

    def generate(self, prompt: str, **kwargs) -> str:
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
