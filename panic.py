#!/usr/bin/env python3
"""
MIDI Panic - Send All Notes Off to all channels.
Use this to stop stuck notes on hardware.

Usage:
  python panic.py              # All notes off on default port
  python panic.py -p 0         # All notes off on port 0
  python panic.py -d "TG-33"   # All notes off on specific device
"""

import argparse
import sys
import mido


def midi_panic(port_name=None, port_index=None):
    """Send All Notes Off and All Sound Off on all channels"""

    output_ports = mido.get_output_names()

    if not output_ports:
        print("ERROR: No MIDI output ports found!")
        sys.exit(1)

    # Select port
    if port_name:
        if port_name not in output_ports:
            print(f"ERROR: Port '{port_name}' not found!")
            print(f"Available ports: {output_ports}")
            sys.exit(1)
        selected_port = port_name
    elif port_index is not None:
        if port_index < 0 or port_index >= len(output_ports):
            print(f"ERROR: Port index {port_index} out of range (0-{len(output_ports)-1})")
            sys.exit(1)
        selected_port = output_ports[port_index]
    else:
        selected_port = output_ports[0]

    print(f"Sending MIDI Panic to: {selected_port}")

    try:
        port = mido.open_output(selected_port)

        # Send on all 16 MIDI channels
        for channel in range(16):
            # All Notes Off (CC 123)
            port.send(mido.Message('control_change', control=123, value=0, channel=channel))

            # All Sound Off (CC 120)
            port.send(mido.Message('control_change', control=120, value=0, channel=channel))

            # Reset All Controllers (CC 121)
            port.send(mido.Message('control_change', control=121, value=0, channel=channel))

        port.close()
        print("✓ MIDI Panic sent successfully!")
        print("  - All Notes Off (CC 123)")
        print("  - All Sound Off (CC 120)")
        print("  - Reset All Controllers (CC 121)")
        print("  - Sent on all 16 channels")

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Send MIDI Panic (All Notes Off) to hardware',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument('-d', '--device', help='MIDI device name')
    parser.add_argument('-p', '--port', type=int, help='MIDI port index')

    args = parser.parse_args()

    midi_panic(args.device, args.port)


if __name__ == '__main__':
    main()
