"""Application layer that wires configuration, LLM, and playback."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from audio_output import FluidSynthBackend, HardwareMIDIBackend, VirtualMIDIBackend
from config import RuntimeConfig
from llm_interface import LLMInterface
from runtime import RealtimeJazzGenerator


@dataclass(frozen=True)
class LLMOptions:
    backend: str
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AudioOptions:
    backend: str
    port: Optional[str] = None


@dataclass(frozen=True)
class RunOptions:
    num_sections: Optional[int] = None
    save_output: bool = False
    output_dir: str = "output"
    verbose: bool = False
    context_steps: int = 32
    prompt_flavor: Optional[str] = None


class InfiniteJazzApp:
    """Service facade that prepares dependencies and runs the realtime loop."""

    def __init__(
        self,
        runtime_config: RuntimeConfig,
        llm_options: LLMOptions,
        audio_options: AudioOptions,
        run_options: RunOptions,
    ):
        self.runtime_config = runtime_config
        self.llm_options = llm_options
        self.audio_options = audio_options
        self.run_options = run_options

    def _resolve_llm_options(self) -> tuple[str, Dict[str, Any]]:
        backend = self.llm_options.backend or "auto"

        if backend == "openai":
            base_url = self.llm_options.base_url or "https://api.groq.com/openai/v1"
            opts = {
                "base_url": base_url,
                **({"api_key": self.llm_options.api_key} if self.llm_options.api_key else {}),
                **self.llm_options.extra,
            }
        else:
            opts = {**self.llm_options.extra}
            if self.llm_options.api_key:
                opts["api_key"] = self.llm_options.api_key
            if self.llm_options.base_url:
                opts["base_url"] = self.llm_options.base_url

        model = self.llm_options.model or (
            "openai/gpt-oss-120b" if backend == "openai" else "qwen2.5:3b"
        )

        return model, opts

    def _build_llm(self) -> LLMInterface:
        model, opts = self._resolve_llm_options()
        return LLMInterface(
            model=model,
            runtime_config=self.runtime_config,
            backend=self.llm_options.backend,
            **opts,
        )

    def _build_audio_backend(self):
        backend = self.audio_options.backend
        if backend == "fluidsynth":
            return FluidSynthBackend()
        if backend == "hardware":
            return HardwareMIDIBackend(port_name=self.audio_options.port)
        if backend == "virtual":
            return VirtualMIDIBackend()
        raise ValueError(f"Unknown audio backend: {backend}")

    def run(self):
        print(f"\n{'='*60}")
        print("Initializing LLM...")
        print(f"{'='*60}\n")
        llm = None
        audio_backend = None
        try:
            llm = self._build_llm()
        except Exception as exc:
            print(f"Error loading model: {exc}")
            print("\nTroubleshooting:")
            print("  - For Ollama: ensure the daemon is running (`ollama serve`).")
            print("  - For Groq/OpenAI: verify API credentials and base URL.")
            print("  - Use --list-models to see locally available Ollama models.")
            raise

        print(f"\n{'='*60}")
        print("Initializing audio backend...")
        print(f"{'='*60}\n")
        try:
            audio_backend = self._build_audio_backend()
        except Exception as exc:
            print(f"Error initializing audio backend: {exc}")
            print("\nTry one of these options:")
            print("  1. Install FluidSynth (for software synthesis).")
            print("  2. Use --list-ports to inspect hardware targets.")
            print("  3. Switch to --backend virtual to expose a virtual port.")
            raise

        generator = RealtimeJazzGenerator(
            llm=llm,
            audio_backend=audio_backend,
            runtime_config=self.runtime_config,
            save_output=self.run_options.save_output,
            output_dir=self.run_options.output_dir,
            verbose=self.run_options.verbose,
            context_steps=self.run_options.context_steps,
            extra_prompt=self.run_options.prompt_flavor or "",
        )

        generator.run(num_sections=self.run_options.num_sections)
