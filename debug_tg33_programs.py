#!/usr/bin/env python3
"""
Debug TG-33 program number mapping.
Sends program changes and waits for you to report what the TG-33 displays.

Usage:
  python debug_tg33_programs.py -p 0           # Use port 0
  python debug_tg33_programs.py -d "TG-33"     # Use specific device
"""

import argparse
import sys
import time
import mido


def test_program_numbers(port_name=None, port_index=None, channel=0):
    """
    Send a series of program changes and let user verify on hardware

    Args:
        port_name: MIDI port name
        port_index: MIDI port index
        channel: MIDI channel to test (0-indexed)
    """
    # List available ports
    output_ports = mido.get_output_names()
    print(f"\n{'='*60}")
    print(f"Available MIDI output ports:")
    print(f"{'='*60}")
    for idx, port in enumerate(output_ports):
        print(f"  [{idx}] {port}")
    print(f"{'='*60}\n")

    if not output_ports:
        print("ERROR: No MIDI output ports found!")
        sys.exit(1)

    # Select port
    if port_name:
        if port_name not in output_ports:
            print(f"ERROR: Port '{port_name}' not found!")
            sys.exit(1)
        selected_port = port_name
    elif port_index is not None:
        if port_index < 0 or port_index >= len(output_ports):
            print(f"ERROR: Port index {port_index} out of range")
            sys.exit(1)
        selected_port = output_ports[port_index]
    else:
        selected_port = output_ports[0]

    print(f"Opening port: {selected_port}")
    port = mido.open_output(selected_port)
    print(f"✓ Connected\n")

    print(f"Testing on MIDI channel {channel} (1-indexed: Ch{channel+1})")
    print(f"{'='*60}\n")

    # Test a range of program numbers
    test_programs = [0, 1, 10, 20, 30, 40, 50, 60, 63, 64, 65, 70, 80, 90, 100, 110, 120, 127]

    print("This script will send MIDI program change messages.")
    print("After each one, check what the TG-33 displays.\n")
    print(f"Format: MIDI_Program -> [play test note] -> You report TG-33 display\n")

    results = []

    for midi_program in test_programs:
        print(f"\n{'─'*60}")
        print(f"Sending MIDI Program Change: {midi_program}")
        print(f"{'─'*60}")

        # Send program change
        port.send(mido.Message('program_change', program=midi_program, channel=channel))
        time.sleep(0.2)

        # Play a test note so user can hear the sound
        print("Playing test note (C4)...")
        port.send(mido.Message('note_on', note=60, velocity=100, channel=channel))
        time.sleep(0.5)
        port.send(mido.Message('note_off', note=60, velocity=0, channel=channel))
        time.sleep(0.2)

        # Ask user what TG-33 displays
        response = input(f"What does TG-33 display? (bank+number, or press Enter to skip): ").strip()

        if response:
            results.append((midi_program, response))
            print(f"  Recorded: MIDI {midi_program} → TG-33 shows '{response}'")

    # All notes off
    port.send(mido.Message('control_change', control=123, value=0, channel=channel))
    port.close()

    # Print summary
    print(f"\n\n{'='*60}")
    print("RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"{'MIDI Program':<15} {'TG-33 Display':<20}")
    print(f"{'─'*15} {'─'*20}")
    for midi_prog, tg33_display in results:
        print(f"{midi_prog:<15} {tg33_display:<20}")

    print(f"\n{'='*60}")
    print("Analysis:")
    print(f"{'='*60}")

    if len(results) >= 2:
        # Try to detect pattern
        print("\nLooking for patterns...")

        # Check if it's a simple offset
        try:
            first_midi, first_tg = results[0]
            if first_tg.isdigit():
                offset = int(first_tg) - first_midi
                print(f"Possible offset: TG-33 = MIDI + {offset}")
        except:
            pass

        # Check for bank system
        print("\nIf TG-33 uses banks (A1-H8 format):")
        print("  Banks A-H = 8 banks")
        print("  Each bank has 8 presets (1-8)")
        print("  Total = 64 presets")
        print("  Bank A = presets 1-8")
        print("  Bank B = presets 9-16")
        print("  etc.")

    print(f"\n{'='*60}\n")


def quick_test(port_name=None, port_index=None, channel=0):
    """Quick test of specific program numbers"""
    output_ports = mido.get_output_names()

    if port_index is not None:
        selected_port = output_ports[port_index]
    elif port_name:
        selected_port = port_name
    else:
        selected_port = output_ports[0]

    print(f"Opening: {selected_port}\n")
    port = mido.open_output(selected_port)

    # Test the three programs you want
    print("Testing your desired programs on TG-33:")
    print(f"Channel {channel} (1-indexed: Ch{channel+1})\n")

    tests = [
        ("Current PIANO config", 40),
        ("Current BASS config", 64),
        ("Current SAX config", 63),
    ]

    for label, midi_prog in tests:
        print(f"\n{label}: MIDI program {midi_prog}")
        port.send(mido.Message('program_change', program=midi_prog, channel=channel))
        time.sleep(0.2)

        print("  Playing test note...")
        port.send(mido.Message('note_on', note=60, velocity=100, channel=channel))
        time.sleep(0.5)
        port.send(mido.Message('note_off', note=60, velocity=0, channel=channel))
        time.sleep(0.2)

        response = input(f"  TG-33 shows: ").strip()
        print(f"  → Recorded: {response}")

    port.send(mido.Message('control_change', control=123, value=0, channel=channel))
    port.close()


def main():
    parser = argparse.ArgumentParser(
        description='Debug TG-33 program number mapping',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test a range of program numbers interactively
  python debug_tg33_programs.py -p 0

  # Quick test of current config values
  python debug_tg33_programs.py -p 0 --quick

  # Test on specific channel
  python debug_tg33_programs.py -p 0 --channel 1
        """
    )

    parser.add_argument('-d', '--device', help='MIDI device name')
    parser.add_argument('-p', '--port', type=int, help='MIDI port index')
    parser.add_argument('-c', '--channel', type=int, default=0,
                       help='MIDI channel to test (0-15, default: 0)')
    parser.add_argument('--quick', action='store_true',
                       help='Quick test of current config values only')

    args = parser.parse_args()

    try:
        if args.quick:
            quick_test(args.device, args.port, args.channel)
        else:
            test_program_numbers(args.device, args.port, args.channel)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
