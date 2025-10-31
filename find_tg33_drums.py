#!/usr/bin/env python3
"""
Find the correct MIDI note numbers for TG-33 drums.
Tests notes around the standard GM drum range.
"""

import argparse
import time
import sys
import mido


def find_drum_notes(port_index=0, channel=9):
    """Play a range of MIDI notes on drum channel to identify sounds"""

    output_ports = mido.get_output_names()
    if not output_ports:
        print("ERROR: No MIDI ports found!")
        sys.exit(1)

    port_name = output_ports[port_index]
    print(f"Opening: {port_name}")
    print(f"Testing on channel {channel} (1-indexed: Ch{channel+1})")
    print(f"{'='*60}\n")

    port = mido.open_output(port_name)

    # Test range around typical drum notes
    # GM drums are usually in the range 35-81
    print("Playing notes 35-55 to find hi-hats...")
    print("Listen for closed and open hi-hat sounds.\n")

    results = []

    for note in range(35, 56):
        print(f"Note {note:3d} ", end='', flush=True)

        # Play note
        port.send(mido.Message('note_on', note=note, velocity=100, channel=channel))
        time.sleep(0.3)
        port.send(mido.Message('note_off', note=note, velocity=0, channel=channel))
        time.sleep(0.4)

        # Ask what it was
        response = input("What sound? (k=kick, s=snare, ch=closed hat, oh=open hat, t=tom, c=cymbal, ?=other, ENTER=skip): ").strip().lower()

        if response:
            results.append((note, response))
            print(f"  → Recorded: Note {note} = {response}")

    # All notes off
    port.send(mido.Message('control_change', control=123, value=0, channel=channel))
    port.close()

    # Print summary
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")

    drum_map = {}
    for note, sound in results:
        if sound == 'k':
            drum_map.setdefault('KICK', []).append(note)
        elif sound == 's':
            drum_map.setdefault('SNARE', []).append(note)
        elif sound == 'ch':
            drum_map.setdefault('CLOSED_HH', []).append(note)
        elif sound == 'oh':
            drum_map.setdefault('OPEN_HH', []).append(note)
        elif sound == 't':
            drum_map.setdefault('TOM', []).append(note)
        elif sound == 'c':
            drum_map.setdefault('CYMBAL', []).append(note)

    print("\nFound drum sounds:")
    for drum_name, notes in sorted(drum_map.items()):
        print(f"  {drum_name:12s}: {notes}")

    print(f"\n{'='*60}")
    print("Config update:")
    print(f"{'='*60}")
    print("Update config.py _default_gm_drums() with:")
    print()
    if 'KICK' in drum_map:
        print(f"    'KICK': {drum_map['KICK'][0]},")
    if 'SNARE' in drum_map:
        print(f"    'SNARE': {drum_map['SNARE'][0]},")
    if 'CLOSED_HH' in drum_map:
        print(f"    'CLOSED_HH': {drum_map['CLOSED_HH'][0]},")
    if 'OPEN_HH' in drum_map:
        print(f"    'OPEN_HH': {drum_map['OPEN_HH'][0]},")
    print()


def quick_test_notes(port_index=0, channel=9, notes=None):
    """Quick test of specific notes"""
    if notes is None:
        # Common hi-hat alternatives in various drum machines
        notes = [42, 44, 46]  # GM: closed HH, pedal HH, open HH

    output_ports = mido.get_output_names()
    port_name = output_ports[port_index]
    print(f"Opening: {port_name}\n")

    port = mido.open_output(port_name)

    print("Testing potential hi-hat notes:")
    for note in notes:
        print(f"\nNote {note}:")
        port.send(mido.Message('note_on', note=note, velocity=100, channel=channel))
        time.sleep(0.3)
        port.send(mido.Message('note_off', note=note, velocity=0, channel=channel))
        time.sleep(0.3)

        response = input("  What sound? ").strip()
        if response:
            print(f"  → {response}")

    port.send(mido.Message('control_change', control=123, value=0, channel=channel))
    port.close()


def main():
    parser = argparse.ArgumentParser(
        description='Find TG-33 drum note mappings',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument('-p', '--port', type=int, default=0, help='MIDI port index')
    parser.add_argument('-c', '--channel', type=int, default=9, help='MIDI channel (0-15)')
    parser.add_argument('--quick', action='store_true', help='Quick test of common hi-hat notes')
    parser.add_argument('--notes', type=str, help='Comma-separated notes to test (e.g., "42,44,46")')

    args = parser.parse_args()

    try:
        if args.quick:
            notes = [int(n.strip()) for n in args.notes.split(',')] if args.notes else None
            quick_test_notes(args.port, args.channel, notes)
        else:
            find_drum_notes(args.port, args.channel)
    except KeyboardInterrupt:
        print("\n\nInterrupted")
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
