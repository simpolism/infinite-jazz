#!/usr/bin/env python3
"""
Convert tracker text files to MIDI
Usage: python txt_to_midi.py input.txt [output.mid]
       python txt_to_midi.py section_*.txt -o complete.mid  # Concatenate multiple files
"""

import argparse
import sys
from pathlib import Path

from tracker_parser import parse_tracker
from midi_converter import MIDIConverter
from generator import concatenate_sections
import config


def convert_txt_to_midi(input_files: list, output_file: str = None, tempo: int = None):
    """
    Convert tracker text file(s) to MIDI

    Args:
        input_files: List of paths to .txt tracker files (will be concatenated)
        output_file: Path to output .mid file (optional, defaults to first_input.mid)
        tempo: Optional tempo override
    """
    if not input_files:
        print("Error: No input files specified")
        sys.exit(1)

    # Default output file based on first input
    if output_file is None:
        if len(input_files) == 1:
            output_file = Path(input_files[0]).with_suffix('.mid')
        else:
            output_file = "combined.mid"

    # Read and parse all input files
    all_sections = []
    for input_file in input_files:
        input_path = Path(input_file)

        if not input_path.exists():
            print(f"Error: File not found: {input_file}")
            sys.exit(1)

        # Read tracker text
        print(f"Reading {input_file}...")
        with open(input_file, 'r') as f:
            tracker_text = f.read()

        # Parse tracker format
        try:
            tracks = parse_tracker(tracker_text)
            all_sections.append(tracks)
        except Exception as e:
            print(f"Error parsing {input_file}: {e}")
            sys.exit(1)

    # Concatenate all sections if multiple files
    if len(all_sections) > 1:
        print(f"Concatenating {len(all_sections)} sections...")
        combined_tracks = concatenate_sections(all_sections)
    else:
        combined_tracks = all_sections[0]

    # Convert to MIDI
    print("Converting to MIDI...")
    midi_tempo = tempo if tempo else config.TEMPO
    converter = MIDIConverter(tempo=midi_tempo)
    midi_file = converter.create_midi_file(combined_tracks)

    # Save
    print(f"Saving to {output_file}...")
    midi_file.save(str(output_file))

    print(f"✓ Successfully converted to MIDI!")
    print(f"  Sections: {len(all_sections)}")
    print(f"  Tempo: {midi_tempo} BPM")
    print(f"  Tracks: {len(combined_tracks)}")
    print(f"  Output: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Convert tracker text files to MIDI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert single file
  python txt_to_midi.py section_0001.txt

  # Specify output name
  python txt_to_midi.py section_0001.txt -o my_jazz.mid

  # Concatenate multiple sections into one MIDI
  python txt_to_midi.py output/section_*.txt -o complete.mid

  # Override tempo
  python txt_to_midi.py section_0001.txt --tempo 100
        """
    )

    parser.add_argument(
        'input',
        nargs='+',
        help='Input tracker text file(s) (.txt) - multiple files will be concatenated'
    )
    parser.add_argument(
        '-o', '--output',
        help='Output MIDI file (.mid) - defaults to input filename with .mid extension'
    )
    parser.add_argument(
        '--tempo',
        type=int,
        help=f'Tempo in BPM (default: {config.TEMPO})'
    )

    args = parser.parse_args()

    convert_txt_to_midi(args.input, args.output, args.tempo)


if __name__ == '__main__':
    main()
