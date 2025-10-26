#!/usr/bin/env python3
"""
Diagnose what prompts work with a given model
Tests progressively more complex prompts to find what works
"""

import argparse
import sys
from llm_interface import LLMInterface


TEST_PROMPTS = [
    {
        'name': 'Simple completion',
        'prompt': 'Hello, how are you?',
        'max_tokens': 50
    },
    {
        'name': 'Simple instruction',
        'prompt': 'Write the numbers 1 through 5, one per line.',
        'max_tokens': 50
    },
    {
        'name': 'Format following',
        'prompt': 'Generate 3 lines in the format NAME:NUMBER. For example:\nAlice:25\nBob:30\nCarol:28\n\nNow generate 3 different ones:',
        'max_tokens': 50
    },
    {
        'name': 'Music notation simple',
        'prompt': 'Generate 5 musical notes in this format: NOTE:VELOCITY\nExample:\nC4:80\nE4:75\nG4:70\n\nNow generate 5 notes:',
        'max_tokens': 100
    },
    {
        'name': 'Music notation with instructions',
        'system': 'You are a music generator. Output notes in NOTE:VELOCITY format (e.g., C4:80). Use . for rests.',
        'user': 'Generate 8 lines of bass notes (range E1 to G2):',
        'max_tokens': 150
    },
    {
        'name': 'Full bass prompt (short)',
        'system': '''You are a jazz bassist. Generate 8 lines in tracker format.

FORMAT:
- Each line: NOTE:VELOCITY (e.g., C2:80) or . (rest)
- Range: E1 to G2 only
- Velocity: 70-85

EXAMPLE:
C2:80
.
E2:75
.
G2:75
.
F2:70
.''',
        'user': 'Generate 8 lines of bass notes now:',
        'max_tokens': 200
    }
]


def test_prompt(llm: LLMInterface, test_case: dict, verbose: bool = False):
    """Test a single prompt"""
    print(f"\n{'='*60}")
    print(f"TEST: {test_case['name']}")
    print(f"{'='*60}")

    if verbose:
        if 'system' in test_case and 'user' in test_case:
            print(f"\nSYSTEM: {test_case['system']}")
            print(f"\nUSER: {test_case['user']}")
        else:
            print(f"\nPROMPT: {test_case['prompt']}")

    gen_config = {
        'max_tokens': test_case.get('max_tokens', 100),
        'temperature': 0.7,
        'top_p': 0.9,
    }

    try:
        # Handle system/user split if provided
        if 'system' in test_case and 'user' in test_case:
            # Temporarily inject these as a combined prompt for the backend to split
            prompt = test_case['system'] + '\n\n' + test_case['user']
        else:
            prompt = test_case['prompt']

        output = llm.generate(prompt, **gen_config)

        if output and output.strip():
            print(f"\n✓ SUCCESS - Got output:")
            print(f"{'-'*60}")
            print(output)
            print(f"{'-'*60}")
            return True
        else:
            print(f"\n✗ FAILED - Empty output")
            return False

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Diagnose model prompting issues',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '-m', '--model',
        required=True,
        help='Model identifier'
    )
    parser.add_argument(
        '--llm-backend',
        choices=['auto', 'ollama', 'llama-cpp', 'openai'],
        default='openai',
        help='LLM backend to use'
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
        '--verbose',
        action='store_true',
        help='Show full prompts'
    )
    parser.add_argument(
        '--test',
        type=int,
        help='Run only specific test number (1-indexed)'
    )

    args = parser.parse_args()

    # Initialize LLM
    print(f"\n{'='*60}")
    print("Initializing LLM...")
    print(f"{'='*60}")

    try:
        llm_kwargs = {}
        if args.llm_backend == 'openai':
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

    # Run tests
    print(f"\n{'='*60}")
    print("Running diagnostic tests...")
    print(f"{'='*60}")

    if args.test:
        # Run specific test
        test_idx = args.test - 1
        if 0 <= test_idx < len(TEST_PROMPTS):
            test_prompt(llm, TEST_PROMPTS[test_idx], verbose=args.verbose)
        else:
            print(f"Error: Test {args.test} out of range (1-{len(TEST_PROMPTS)})")
    else:
        # Run all tests
        results = []
        for i, test_case in enumerate(TEST_PROMPTS, 1):
            success = test_prompt(llm, test_case, verbose=args.verbose)
            results.append((i, test_case['name'], success))

        # Summary
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        for i, name, success in results:
            status = "✓ PASS" if success else "✗ FAIL"
            print(f"{i}. {status} - {name}")

        passed = sum(1 for _, _, s in results if s)
        print(f"\nPassed: {passed}/{len(results)}")

        if passed == 0:
            print("\n⚠️  Model returned empty output for ALL tests!")
            print("Possible issues:")
            print("  1. Model name incorrect")
            print("  2. API endpoint not compatible")
            print("  3. Model requires specific prompt format")
            print("  4. API key/authentication issue")
        elif passed < len(results):
            first_fail = next((i for i, _, s in results if not s), None)
            print(f"\n⚠️  First failure at test {first_fail}")
            print(f"Try: python diagnose_model.py --test {first_fail} --verbose")


if __name__ == '__main__':
    main()
