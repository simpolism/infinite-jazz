#!/usr/bin/env python3
"""
Nuclear option: Send note-off for EVERY possible MIDI note on EVERY channel.
Use when panic.py doesn't work.
"""

import sys
import mido


def kill_all_notes(port_index=0):
    """Send note-off for every note (0-127) on every channel (0-15)"""

    output_ports = mido.get_output_names()

    if not output_ports:
        print("ERROR: No MIDI output ports found!")
        sys.exit(1)

    selected_port = output_ports[port_index]
    print(f"Opening: {selected_port}")
    print("Sending note-off for ALL notes on ALL channels...")

    port = mido.open_output(selected_port)

    # Every channel
    for channel in range(16):
        print(f"  Channel {channel}...", end='', flush=True)

        # Every possible MIDI note
        for note in range(128):
            port.send(mido.Message('note_off', note=note, velocity=0, channel=channel))

        # Also send control change messages
        port.send(mido.Message('control_change', control=123, value=0, channel=channel))  # All notes off
        port.send(mido.Message('control_change', control=120, value=0, channel=channel))  # All sound off
        port.send(mido.Message('control_change', control=64, value=0, channel=channel))   # Sustain off

        print(" done")

    port.close()
    print("\n✓ Sent note-off for all 128 notes on all 16 channels!")


if __name__ == '__main__':
    port_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    kill_all_notes(port_idx)
