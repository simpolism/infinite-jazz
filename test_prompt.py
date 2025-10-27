#!/usr/bin/env python3
"""
Test prompt against LLM to inspect instruction following
Shows raw output and validates format compliance
"""

import argparse
import sys
from pathlib import Path

from llm_interface import LLMInterface, list_ollama_models
from prompts import get_batched_quartet_prompt, get_instrument_prompt
import config


def test_batched_prompt(llm: LLMInterface, previous_context: str = "", verbose: bool = False, debug: bool = False):
    """Test batched quartet generation prompt"""

    print(f"\n{'='*60}")
    print("TESTING BATCHED QUARTET PROMPT")
    print(f"{'='*60}\n")

    # Get the prompt
    prompt = get_batched_quartet_prompt(previous_context)

    if verbose:
        print("FULL PROMPT:")
        print(f"{'-'*60}")
        print(prompt)
        print(f"{'-'*60}\n")

    # Show how prompt is split for OpenAI backend
    if debug and hasattr(llm.backend, '_split_prompt'):
        system_msg, user_msg = llm.backend._split_prompt(prompt)
        print("DEBUG - MESSAGE SPLIT:")
        print(f"{'-'*60}")
        print(f"SYSTEM MESSAGE ({len(system_msg)} chars):")
        print(system_msg[:500] + "..." if len(system_msg) > 500 else system_msg)
        print(f"\n{'-'*60}")
        print(f"USER MESSAGE ({len(user_msg)} chars):")
        print(user_msg)
        print(f"{'-'*60}\n")

    print("Sending to LLM...")

    # Generation config (same as used in generator.py)
    # High max_tokens for reasoning models (like gpt-oss-20b)
    gen_config = {
        'max_tokens': 3000,
        'temperature': 0.8,
        'top_p': 0.92,
        'repeat_penalty': 1.1,
    }

    # Generate
    raw_output = llm.generate(prompt, **gen_config)

    print(f"\n{'='*60}")
    print("RAW LLM OUTPUT")
    print(f"{'='*60}\n")
    if raw_output:
        print(raw_output)
    else:
        print("⚠️  EMPTY OUTPUT!")
        print("This usually means:")
        print("  1. Model doesn't understand the prompt format")
        print("  2. Model needs system/user message split")
        print("  3. Model needs explicit output trigger (e.g., 'Output:')")
        print("  4. Max tokens is being hit immediately (check model logs)")
    print(f"\n{'='*60}")

    # Analyze output
    analyze_output(raw_output, mode='batched')


def test_instrument_prompt(llm: LLMInterface, instrument: str, verbose: bool = False, debug: bool = False):
    """Test single instrument generation prompt"""

    print(f"\n{'='*60}")
    print(f"TESTING {instrument} PROMPT")
    print(f"{'='*60}\n")

    # Get the prompt
    prompt = get_instrument_prompt(instrument)

    if verbose:
        print("FULL PROMPT:")
        print(f"{'-'*60}")
        print(prompt)
        print(f"{'-'*60}\n")

    # Show how prompt is split for OpenAI backend
    if debug and hasattr(llm.backend, '_split_prompt'):
        system_msg, user_msg = llm.backend._split_prompt(prompt)
        print("DEBUG - MESSAGE SPLIT:")
        print(f"{'-'*60}")
        print(f"SYSTEM MESSAGE ({len(system_msg)} chars):")
        print(system_msg[:500] + "..." if len(system_msg) > 500 else system_msg)
        print(f"\n{'-'*60}")
        print(f"USER MESSAGE ({len(user_msg)} chars):")
        print(user_msg)
        print(f"{'-'*60}\n")

    print("Sending to LLM...")

    # Generation config (from llm_interface.py)
    # High max_tokens for reasoning models (like gpt-oss-20b)
    gen_config = {
        'max_tokens': 1000,
        'temperature': 0.8,
        'top_p': 0.92,
        'repeat_penalty': 1.1,
    }

    # Generate
    raw_output = llm.generate(prompt, **gen_config)

    print(f"\n{'='*60}")
    print("RAW LLM OUTPUT")
    print(f"{'='*60}\n")
    if raw_output:
        print(raw_output)
    else:
        print("⚠️  EMPTY OUTPUT!")
        print("This usually means:")
        print("  1. Model doesn't understand the prompt format")
        print("  2. Model needs system/user message split")
        print("  3. Model needs explicit output trigger (e.g., 'Output:')")
        print("  4. Max tokens is being hit immediately (check model logs)")
    print(f"\n{'='*60}")

    # Analyze output
    analyze_output(raw_output, mode='single', instrument=instrument)


def analyze_output(raw_output: str, mode: str = 'batched', instrument: str = None):
    """Analyze the output for common issues"""

    print(f"\n{'='*60}")
    print("ANALYSIS")
    print(f"{'='*60}\n")

    issues = []

    # Check output length
    print(f"Output length: {len(raw_output)} characters")
    print(f"Line count: {len(raw_output.split(chr(10)))}")

    # Expected lines per instrument
    expected_lines = config.get_total_steps()

    if mode == 'batched':
        # Check for instrument headers
        instruments = ['BASS', 'DRUMS', 'PIANO', 'SAX']
        for inst in instruments:
            if inst in raw_output:
                print(f"✓ Found {inst} section")
            else:
                print(f"✗ Missing {inst} section")
                issues.append(f"Missing {inst} section")

        # Try to extract each section
        import re
        for inst in instruments:
            pattern = rf'^{inst}\s*$'
            matches = list(re.finditer(pattern, raw_output, re.MULTILINE))
            if matches:
                # Find section content
                start = matches[0].end()
                # Find next instrument or end
                inst_idx = instruments.index(inst)
                if inst_idx < len(instruments) - 1:
                    next_inst = instruments[inst_idx + 1]
                    next_pattern = rf'^{next_inst}\s*$'
                    next_matches = list(re.finditer(next_pattern, raw_output, re.MULTILINE))
                    end = next_matches[0].start() if next_matches else len(raw_output)
                else:
                    end = len(raw_output)

                section = raw_output[start:end].strip()
                section_lines = [l for l in section.split('\n') if l.strip()]

                print(f"\n{inst}:")
                print(f"  Lines: {len(section_lines)} (expected {expected_lines})")

                if len(section_lines) != expected_lines:
                    issues.append(f"{inst} has {len(section_lines)} lines, expected {expected_lines}")

                # Check format
                check_format(section_lines, inst, issues)

    elif mode == 'single':
        lines = [l.strip() for l in raw_output.split('\n') if l.strip()]

        # Remove instrument header if present
        if lines and lines[0].upper() in ['BASS', 'DRUMS', 'PIANO', 'SAX']:
            lines = lines[1:]

        print(f"\nLines: {len(lines)} (expected {expected_lines})")

        if len(lines) != expected_lines:
            issues.append(f"Got {len(lines)} lines, expected {expected_lines}")

        check_format(lines, instrument, issues)

    # Summary
    print(f"\n{'='*60}")
    if issues:
        print(f"FOUND {len(issues)} ISSUES:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
    else:
        print("✓ No obvious formatting issues detected!")
    print(f"{'='*60}\n")


def check_format(lines: list, instrument: str, issues: list):
    """Check line format for common issues"""
    import re

    rest_count = 0
    note_count = 0
    invalid_count = 0

    for i, line in enumerate(lines, 1):
        # Strip line numbers if present (format: "1 C2:80" or "1. C2:80" -> "C2:80")
        line = re.sub(r'^\d+\.?\s+', '', line)

        if line == '.':
            rest_count += 1
        elif ':' in line:
            note_count += 1

            # Check for valid note format
            # Allow NOTE:VELOCITY or NOTE:VELOCITY,NOTE:VELOCITY etc
            pattern = r'^[A-G][#b]?-?\d+:\d+[^,]*(?:,[A-G][#b]?-?\d+:\d+[^,]*)*$'
            if not re.match(pattern, line.rstrip('.,;')):
                issues.append(f"Line {i} invalid format: '{line}'")
                invalid_count += 1

            # Check for trailing periods (common mistake)
            if line.endswith('.') and line != '.':
                issues.append(f"Line {i} has trailing period: '{line}'")

            # Check for SAX chords
            if instrument == 'SAX' and ',' in line:
                issues.append(f"Line {i} SAX playing chord (should be monophonic): '{line}'")
        else:
            invalid_count += 1
            issues.append(f"Line {i} unrecognized format: '{line}'")

    print(f"  Rests: {rest_count}")
    print(f"  Notes: {note_count}")
    if invalid_count > 0:
        print(f"  Invalid: {invalid_count}")


def main():
    parser = argparse.ArgumentParser(
        description='Test LLM prompt for instruction following',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test batched quartet generation
  python test_prompt.py -m qwen2.5:3b --mode batched

  # Test single instrument (sequential mode)
  python test_prompt.py -m qwen2.5:3b --mode single --instrument BASS

  # Use Groq for testing
  python test_prompt.py --llm-backend openai -m llama-3.1-70b-versatile \\
    --base-url https://api.groq.com/openai/v1 --mode batched

  # Show full prompt before generation
  python test_prompt.py -m qwen2.5:3b --mode batched --verbose
        """
    )

    parser.add_argument(
        '-m', '--model',
        default='qwen2.5:3b',
        help='Model identifier (default: qwen2.5:3b)'
    )
    parser.add_argument(
        '--llm-backend',
        choices=['auto', 'ollama', 'llama-cpp', 'openai'],
        default='auto',
        help='LLM backend to use (default: auto-detect)'
    )
    parser.add_argument(
        '--api-key',
        help='API key for OpenAI-compatible backend'
    )
    parser.add_argument(
        '--base-url',
        help='Base URL for OpenAI-compatible API'
    )
    parser.add_argument(
        '--mode',
        choices=['batched', 'single'],
        default='batched',
        help='Test mode: batched (all instruments) or single instrument (default: batched)'
    )
    parser.add_argument(
        '--instrument',
        choices=['BASS', 'DRUMS', 'PIANO', 'SAX'],
        help='Instrument to test (required for single mode)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show full prompt before generation'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Show how prompt is split into system/user messages (OpenAI backend only)'
    )
    parser.add_argument(
        '--list-models',
        action='store_true',
        help='List available Ollama models and exit'
    )

    args = parser.parse_args()

    # List models and exit
    if args.list_models:
        list_ollama_models()
        return

    # Validate arguments
    if args.mode == 'single' and not args.instrument:
        print("Error: --instrument required for single mode")
        sys.exit(1)

    # Initialize LLM
    print(f"\n{'='*60}")
    print("Initializing LLM...")
    print(f"{'='*60}\n")

    try:
        # Prepare kwargs based on backend
        llm_kwargs = {}
        if args.llm_backend == 'llama-cpp':
            llm_kwargs = {
                'n_ctx': 2048,
                'n_gpu_layers': -1,
                'verbose': False
            }
        elif args.llm_backend == 'openai':
            if args.api_key:
                llm_kwargs['api_key'] = args.api_key
            if args.base_url:
                llm_kwargs['base_url'] = args.base_url

        llm = LLMInterface(
            model=args.model,
            backend=args.llm_backend,
            **llm_kwargs
        )
    except Exception as e:
        print(f"Error loading model: {e}")
        sys.exit(1)

    # Run test
    if args.mode == 'batched':
        test_batched_prompt(llm, verbose=args.verbose, debug=args.debug)
    else:
        test_instrument_prompt(llm, args.instrument, verbose=args.verbose, debug=args.debug)


if __name__ == '__main__':
    main()
