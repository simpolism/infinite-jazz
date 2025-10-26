#!/usr/bin/env python3
"""
Test the raw OpenAI API directly to rule out our code
"""

import argparse
import os


def test_raw_api(model: str, base_url: str, api_key: str):
    """Test raw OpenAI API"""
    try:
        from openai import OpenAI
    except ImportError:
        print("Error: openai package not installed")
        print("Install with: pip install openai")
        return

    client = OpenAI(api_key=api_key, base_url=base_url)

    tests = [
        {
            'name': 'Simple user message',
            'messages': [
                {'role': 'user', 'content': 'Say hello'}
            ]
        },
        {
            'name': 'System + user',
            'messages': [
                {'role': 'system', 'content': 'You are a helpful assistant.'},
                {'role': 'user', 'content': 'Say hello'}
            ]
        },
        {
            'name': 'Generate numbers',
            'messages': [
                {'role': 'user', 'content': 'Write the numbers 1 through 5, one per line.'}
            ]
        },
        {
            'name': 'Music format (no system)',
            'messages': [
                {'role': 'user', 'content': 'Generate 5 musical notes in format NOTE:VELOCITY like C4:80, one per line.'}
            ],
            'max_tokens': 500  # Reasoning models need more tokens
        },
        {
            'name': 'Music format (with system)',
            'messages': [
                {'role': 'system', 'content': 'You generate music in NOTE:VELOCITY format. Example: C4:80'},
                {'role': 'user', 'content': 'Generate 5 bass notes from E1 to G2:'}
            ],
            'max_tokens': 500  # Reasoning models need more tokens
        }
    ]

    print(f"\nTesting model: {model}")
    print(f"Endpoint: {base_url}")
    print(f"{'='*60}\n")

    for i, test in enumerate(tests, 1):
        print(f"Test {i}: {test['name']}")
        print(f"{'-'*60}")

        try:
            response = client.chat.completions.create(
                model=model,
                messages=test['messages'],
                max_tokens=test.get('max_tokens', 100),
                temperature=0.7,
                reasoning_effort='low'  # For reasoning models, save tokens for output
            )

            content = response.choices[0].message.content
            if content and content.strip():
                print(f"✓ SUCCESS ({len(content)} chars)")
                print(f"Output: {content[:200]}")
            else:
                print(f"✗ EMPTY OUTPUT")
                print(f"Response: {response}")

        except Exception as e:
            print(f"✗ ERROR: {e}")

        print()


def main():
    parser = argparse.ArgumentParser(description='Test raw OpenAI API')
    parser.add_argument('-m', '--model', required=True, help='Model name')
    parser.add_argument('--base-url', required=True, help='API base URL')
    parser.add_argument('--api-key', help='API key (or set OPENAI_API_KEY env var)')

    args = parser.parse_args()

    api_key = args.api_key or os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("Error: API key required (--api-key or OPENAI_API_KEY env var)")
        return

    test_raw_api(args.model, args.base_url, api_key)


if __name__ == '__main__':
    main()
