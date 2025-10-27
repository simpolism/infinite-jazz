#!/usr/bin/env python3
"""CLI entrypoint for the Infinite Jazz realtime generator."""

import argparse
import sys
from dataclasses import replace
from typing import Optional

from audio_output import list_midi_ports
from app import InfiniteJazzApp, LLMOptions, AudioOptions, RunOptions
from config import DEFAULT_CONFIG
from llm_interface import list_ollama_models


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Real-time jazz quartet generator using local LLM',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use Ollama (easiest - auto-downloads model)
  python realtime_jazz.py -m qwen2.5:3b

  # Quick sanity run (Groq defaults)
  .venv/bin/python realtime_jazz.py --llm-backend openai -n 2

  # Generate only 4 sections with Ollama
  .venv/bin/python realtime_jazz.py -m qwen2.5:3b -n 4

  # Use hardware MIDI output
  .venv/bin/python realtime_jazz.py --backend hardware --port "Your MIDI Port"

  # Save generated sections to files
  .venv/bin/python realtime_jazz.py --save-output
        """
    )

    parser.add_argument(
        '-m', '--model',
        help='Model identifier: Ollama (e.g., qwen2.5:3b) or OpenAI-compatible (e.g., openai/gpt-oss-120b)'
    )
    parser.add_argument(
        '--llm-backend',
        choices=['auto', 'ollama', 'openai'],
        default='auto',
        help='LLM backend to use (default: auto-detect)'
    )
    parser.add_argument(
        '--api-key',
        help='API key for OpenAI-compatible backend (defaults to OPENAI_API_KEY env var)'
    )
    parser.add_argument(
        '--base-url',
        help='Base URL for OpenAI-compatible API (default: https://api.groq.com/openai/v1 when backend=openai)'
    )
    parser.add_argument(
        '--list-models',
        action='store_true',
        help='List available Ollama models and exit'
    )
    parser.add_argument(
        '--backend',
        choices=['fluidsynth', 'hardware', 'virtual'],
        default='fluidsynth',
        help='Audio backend (default: fluidsynth)'
    )
    parser.add_argument(
        '--port',
        help='MIDI port name (for hardware backend)'
    )
    parser.add_argument(
        '--list-ports',
        action='store_true',
        help='List available MIDI ports and exit'
    )
    parser.add_argument(
        '-n', '--num-sections',
        type=int,
        help='Number of sections to generate (default: infinite)'
    )
    parser.add_argument(
        '--save-output',
        action='store_true',
        help='Save generated sections to files'
    )
    parser.add_argument(
        '--output-dir',
        default='output',
        help='Directory for saved output (default: output/)'
    )
    parser.add_argument(
        '--tempo',
        type=int,
        help=f'Tempo in BPM (default: {DEFAULT_CONFIG.tempo})'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging for debugging'
    )
    parser.add_argument(
        '--context-steps',
        type=int,
        default=4,
        help='Number of tracker steps per instrument to include from the previous section (default: 4)'
    )
    return parser


def main(argv: Optional[list[str]] = None):
    parser = build_parser()
    args = parser.parse_args(argv)

    # List models and exit
    if args.list_models:
        list_ollama_models()
        return

    # List ports and exit
    if args.list_ports:
        list_midi_ports()
        return

    runtime_config = DEFAULT_CONFIG if args.tempo is None else replace(DEFAULT_CONFIG, tempo=args.tempo)

    llm_options = LLMOptions(
        backend=args.llm_backend,
        model=args.model,
        api_key=args.api_key,
        base_url=args.base_url,
    )
    audio_options = AudioOptions(
        backend=args.backend,
        port=args.port,
    )
    run_options = RunOptions(
        num_sections=args.num_sections,
        save_output=args.save_output,
        output_dir=args.output_dir,
        verbose=args.verbose,
        context_steps=max(0, args.context_steps),
    )

    app = InfiniteJazzApp(
        runtime_config=runtime_config,
        llm_options=llm_options,
        audio_options=audio_options,
        run_options=run_options,
    )

    try:
        app.run()
    except Exception:
        sys.exit(1)


if __name__ == '__main__':
    main()
