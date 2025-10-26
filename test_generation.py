#!/usr/bin/env python3
"""
Test generation pipeline without LLM
Uses mock generation to validate the pipeline logic
"""

import sys
from pathlib import Path

from tracker_parser import parse_tracker
from midi_converter import MIDIConverter
from generator import GenerationPipeline, save_generated_section
import config


class MockLLM:
    """Mock LLM for testing pipeline"""

    def __init__(self):
        self.generation_count = 0

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate mock output based on instrument"""
        self.generation_count += 1

        # Detect if this is a batched quartet prompt
        if 'quartet' in prompt.lower() and 'all 4 instruments' in prompt.lower():
            return self._generate_batched_quartet()
        # Detect individual instrument from prompt
        elif 'bassist' in prompt.lower():
            return self._generate_bass()
        elif 'drummer' in prompt.lower():
            return self._generate_drums()
        elif 'pianist' in prompt.lower():
            return self._generate_piano()
        elif 'saxophonist' in prompt.lower():
            return self._generate_sax()
        else:
            return self._generate_bass()  # Default

    def _generate_bass(self) -> str:
        """Mock bass generation"""
        return """C2:80
.
C2:75
.
F2:80
.
F2:75
.
C2:80
.
C2:75
.
G2:80
.
G2:75
.
"""

    def _generate_drums(self) -> str:
        """Mock drums generation"""
        return """C2:90,F#2:60
F#2:50
C2:75,F#2:60
F#2:50
C2:90,F#2:60
F#2:50
D2:85,F#2:60
F#2:50
C2:90,F#2:60
F#2:50
C2:75,F#2:60
F#2:50
C2:90,F#2:60
F#2:50
D2:85,F#2:60
F#2:50
"""

    def _generate_piano(self) -> str:
        """Mock piano generation"""
        return """C3:65,E3:60,G3:62
.
.
.
F3:65,A3:60,C4:62
.
.
.
C3:65,E3:60,G3:62
.
.
.
G2:65,B2:60,D3:62
.
.
.
"""

    def _generate_sax(self) -> str:
        """Mock sax generation"""
        return """.
.
E4:70
G4:75
A4:80
G4:70
F4:75
E4:70
D4:65
.
.
C4:70
D4:75
.
B3:80
.
"""

    def _generate_batched_quartet(self) -> str:
        """Mock batched quartet generation (all 4 instruments)"""
        return """BASS
C2:80
.
C2:75
.
F2:80
.
F2:75
.
C2:80
.
C2:75
.
G2:80
.
G2:75
.

DRUMS
C2:90,F#2:60
F#2:50
C2:75,F#2:60
F#2:50
C2:90,F#2:60
F#2:50
D2:85,F#2:60
F#2:50
C2:90,F#2:60
F#2:50
C2:75,F#2:60
F#2:50
C2:90,F#2:60
F#2:50
D2:85,F#2:60
F#2:50

PIANO
C3:65,E3:60,G3:62
.
.
.
F3:65,A3:60,C4:62
.
.
.
C3:65,E3:60,G3:62
.
.
.
G2:65,B2:60,D3:62
.
.
.

SAX
.
.
E4:70
G4:75
A4:80
G4:70
F4:75
E4:70
D4:65
.
.
C4:70
D4:75
.
B3:80
.
"""


def test_pipeline():
    """Test the generation pipeline with mock LLM"""
    print("Testing generation pipeline with mock LLM\n")
    print(f"Configuration:")
    print(f"  Tempo: {config.TEMPO} BPM")
    print(f"  Resolution: {config.RESOLUTION} notes")
    print(f"  Bars per section: {config.BARS_PER_GENERATION}")
    print(f"  Steps per section: {config.get_total_steps()}\n")

    # Create mock LLM
    mock_llm = MockLLM()

    # Create pipeline
    pipeline = GenerationPipeline(mock_llm)

    # Generate a section
    print("Generating section...\n")
    tracks = pipeline.generate_section()

    print("\nGenerated tracks:")
    for instrument, track in tracks.items():
        print(f"  {instrument}: {len(track.steps)} steps")

    # Validate track lengths
    expected_steps = config.get_total_steps()
    all_valid = True
    for instrument, track in tracks.items():
        if len(track.steps) != expected_steps:
            print(f"ERROR: {instrument} has {len(track.steps)} steps, expected {expected_steps}")
            all_valid = False

    if all_valid:
        print("\n✓ All tracks have correct length")
    else:
        print("\n✗ Track length validation failed")
        return False

    # Save to file
    output_file = "test_output_section.txt"
    save_generated_section(tracks, output_file)
    print(f"\nSaved to {output_file}")

    # Test MIDI conversion
    print("\nTesting MIDI conversion...")
    converter = MIDIConverter(tempo=config.TEMPO)
    midi_file = converter.create_midi_file(tracks)
    midi_output = "test_output_section.mid"
    midi_file.save(midi_output)
    print(f"MIDI file saved: {midi_output}")

    # Test realtime messages
    print("\nTesting realtime message generation...")
    messages = converter.create_realtime_messages(tracks)
    print(f"Generated {len(messages)} MIDI messages")

    if messages:
        print(f"First message: {messages[0]}")
        print(f"Last message: {messages[-1]}")

    print("\n" + "="*60)
    print("Pipeline test complete!")
    print("="*60)

    return True


def main():
    try:
        success = test_pipeline()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nError during testing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
