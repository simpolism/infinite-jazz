#!/usr/bin/env python3
"""
Test script for JazzAI tracker to MIDI pipeline
Demonstrates parsing, conversion, and playback
"""

import sys
import argparse
from pathlib import Path

from tracker_parser import parse_tracker
from midi_converter import tracker_to_midi_file, MIDIConverter
from audio_output import (
    FluidSynthBackend,
    HardwareMIDIBackend,
    VirtualMIDIBackend,
    RealtimePlayer,
    play_midi_file,
    list_midi_ports
)
import config


def main():
    parser = argparse.ArgumentParser(description='Test JazzAI tracker to MIDI pipeline')
    parser.add_argument(
        'tracker_file',
        nargs='?',
        default='examples/test_pattern.txt',
        help='Path to tracker file (default: examples/test_pattern.txt)'
    )
    parser.add_argument(
        '-o', '--output',
        help='Output MIDI file path (if not specified, plays audio directly)'
    )
    parser.add_argument(
        '-b', '--backend',
        choices=['fluidsynth', 'hardware', 'virtual'],
        default='fluidsynth',
        help='Audio backend to use (default: fluidsynth)'
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
        '--resolution',
        choices=['8th', '16th'],
        help='Override resolution from config'
    )
    parser.add_argument(
        '--tempo',
        type=int,
        help='Override tempo from config (BPM)'
    )

    args = parser.parse_args()

    # List ports and exit
    if args.list_ports:
        list_midi_ports()
        return

    # Override config if specified
    if args.resolution:
        config.RESOLUTION = args.resolution
        print(f"Resolution: {config.RESOLUTION} notes")

    tempo = args.tempo or config.TEMPO
    print(f"Tempo: {tempo} BPM")

    # Read tracker file
    tracker_path = Path(args.tracker_file)
    if not tracker_path.exists():
        print(f"Error: Tracker file not found: {tracker_path}")
        sys.exit(1)

    print(f"Reading tracker file: {tracker_path}")
    with open(tracker_path, 'r') as f:
        tracker_text = f.read()

    # Parse tracker
    print("Parsing tracker format...")
    try:
        tracks = parse_tracker(tracker_text)
    except Exception as e:
        print(f"Error parsing tracker: {e}")
        sys.exit(1)

    print(f"Parsed {len(tracks)} instrument tracks:")
    for instrument, track in tracks.items():
        print(f"  {instrument}: {len(track.steps)} steps")

    # Convert to MIDI
    print("Converting to MIDI...")
    midi_file = tracker_to_midi_file(tracks, tempo=tempo)

    # Output to file or play
    if args.output:
        # Save to file
        output_path = Path(args.output)
        print(f"Saving MIDI file: {output_path}")
        midi_file.save(output_path)
        print("Done!")

    else:
        # Play audio
        print(f"Initializing {args.backend} backend...")

        try:
            if args.backend == 'fluidsynth':
                backend = FluidSynthBackend()
            elif args.backend == 'hardware':
                backend = HardwareMIDIBackend(port_name=args.port)
            elif args.backend == 'virtual':
                backend = VirtualMIDIBackend()

            print("\nPlaying... (Press Ctrl+C to stop)")
            play_midi_file(midi_file, backend)

        except Exception as e:
            print(f"Error initializing audio backend: {e}")
            print("\nTry one of these options:")
            print("  1. Install FluidSynth (see error message above)")
            print("  2. Use --list-ports to see available MIDI ports")
            print("  3. Use -o output.mid to save to file instead")
            sys.exit(1)


if __name__ == '__main__':
    main()
