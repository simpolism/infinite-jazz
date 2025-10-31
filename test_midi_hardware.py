#!/usr/bin/env python3
"""
Test MIDI output to hardware devices.
Tests channel assignments, drum channel, and all instruments.

Usage:
  python test_midi_hardware.py                    # List available devices
  python test_midi_hardware.py -d "Your Device"   # Test specific device
  python test_midi_hardware.py -p 0               # Test device at port 0
  python test_midi_hardware.py --drums-only       # Test only drum channel
"""

import argparse
import time
import sys
from typing import Optional, List

import mido

from config import DEFAULT_CONFIG


class MIDIHardwareTester:
    """Test MIDI hardware output"""

    def __init__(self, port_name: Optional[str] = None, port_index: Optional[int] = None):
        """
        Initialize hardware tester

        Args:
            port_name: Name of MIDI output port
            port_index: Index of MIDI output port (alternative to port_name)
        """
        self.port = None
        self.config = DEFAULT_CONFIG

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
            print("Make sure your MIDI hardware is connected.")
            sys.exit(1)

        # Select port
        if port_name:
            if port_name not in output_ports:
                print(f"ERROR: Port '{port_name}' not found!")
                sys.exit(1)
            selected_port = port_name
        elif port_index is not None:
            if port_index < 0 or port_index >= len(output_ports):
                print(f"ERROR: Port index {port_index} out of range (0-{len(output_ports)-1})")
                sys.exit(1)
            selected_port = output_ports[port_index]
        else:
            # Default to first port
            selected_port = output_ports[0]

        print(f"Opening port: {selected_port}")
        self.port = mido.open_output(selected_port)
        print(f"✓ Connected to {selected_port}\n")

    def __del__(self):
        """Clean up MIDI connection"""
        if self.port:
            self.all_notes_off()
            self.port.close()

    def all_notes_off(self):
        """Send all notes off on all channels"""
        print("Sending all notes off...")
        for channel in range(16):
            self.port.send(mido.Message('control_change', control=123, value=0, channel=channel))
        time.sleep(0.1)

    def test_channel(self, channel: int, instrument_name: str, program: Optional[int] = None,
                     test_notes: List[int] = None, note_duration: float = 0.5):
        """
        Test a specific MIDI channel

        Args:
            channel: MIDI channel (0-15, where 9 is drums/channel 10)
            instrument_name: Name for display
            program: GM program number (skip for drums)
            test_notes: List of MIDI note numbers to test
            note_duration: Duration of each note in seconds
        """
        print(f"\n{'─'*60}")
        print(f"Testing {instrument_name} on Channel {channel} (1-indexed: Ch{channel+1})")
        print(f"{'─'*60}")

        # Set program if provided
        if program is not None:
            print(f"  Setting program: {program}")
            self.port.send(mido.Message('program_change', program=program, channel=channel))
            time.sleep(0.1)
        else:
            print(f"  No program change (drums channel)")

        # Test notes
        if test_notes is None:
            test_notes = [60, 64, 67]  # C, E, G (C major chord)

        for note in test_notes:
            note_name = self._note_to_name(note)
            print(f"  Playing note {note} ({note_name})...")

            # Note on
            self.port.send(mido.Message('note_on', note=note, velocity=100, channel=channel))
            time.sleep(note_duration)

            # Note off
            self.port.send(mido.Message('note_off', note=note, velocity=0, channel=channel))
            time.sleep(0.1)

        print(f"  ✓ {instrument_name} test complete")

    def test_drums_channel(self, note_duration: float = 0.3):
        """Test drum channel with common drum sounds"""
        drums_config = self.config.gm_drums
        drums_channel = self.config.channels['DRUMS']

        print(f"\n{'='*60}")
        print(f"DRUM CHANNEL TEST")
        print(f"{'='*60}")
        print(f"Channel: {drums_channel} (1-indexed: Ch{drums_channel+1})")
        print(f"Expected: Channel 9 (1-indexed: Ch10) for General MIDI")
        print(f"{'='*60}")

        # Test each drum sound
        drum_tests = [
            ('KICK', drums_config['KICK']),
            ('SNARE', drums_config['SNARE']),
            ('CLOSED_HH', drums_config['CLOSED_HH']),
            ('OPEN_HH', drums_config['OPEN_HH']),
        ]

        print("\nTesting individual drums:")
        for drum_name, note in drum_tests:
            print(f"  Playing {drum_name} (note {note})...")
            self.port.send(mido.Message('note_on', note=note, velocity=100, channel=drums_channel))
            time.sleep(note_duration)
            self.port.send(mido.Message('note_off', note=note, velocity=0, channel=drums_channel))
            time.sleep(0.1)

        print("\nPlaying basic beat pattern...")
        pattern = [
            ('KICK', 0.0),
            ('CLOSED_HH', 0.0),
            ('SNARE', 0.5),
            ('CLOSED_HH', 0.5),
            ('KICK', 1.0),
            ('CLOSED_HH', 1.0),
            ('SNARE', 1.5),
            ('CLOSED_HH', 1.5),
        ]

        start_time = time.time()
        for drum_name, beat_time in pattern:
            note = drums_config[drum_name]

            # Wait until beat time
            while time.time() - start_time < beat_time:
                time.sleep(0.001)

            self.port.send(mido.Message('note_on', note=note, velocity=100, channel=drums_channel))
            time.sleep(0.05)
            self.port.send(mido.Message('note_off', note=note, velocity=0, channel=drums_channel))

        time.sleep(0.5)
        print("  ✓ Drum test complete")

    def test_all_instruments(self):
        """Test all configured instruments"""
        print(f"\n{'='*60}")
        print(f"TESTING ALL INSTRUMENTS")
        print(f"{'='*60}")

        if self.config.send_program_changes:
            print(f"Using configured programs from config.programs")
        else:
            print(f"Program changes DISABLED - using hardware settings")
        print()

        # Test melodic instruments with configured programs
        instruments = [
            ('BASS', [40, 43, 47]),      # E1, G1, B1
            ('PIANO', [60, 64, 67]),     # C4, E4, G4
            ('SAX', [69, 73, 76]),       # A4, C#5, E5
        ]

        for instrument_name, test_notes in instruments:
            channel = self.config.channels[instrument_name]
            program = self.config.programs.get(instrument_name, 0) if self.config.send_program_changes else None
            self.test_channel(channel, instrument_name, program, test_notes)

        # Test drums
        self.test_drums_channel()

        print(f"\n{'='*60}")
        print(f"ALL TESTS COMPLETE")
        print(f"{'='*60}\n")

    def test_channel_scan(self):
        """Scan all 16 MIDI channels to find where drums respond"""
        print(f"\n{'='*60}")
        print(f"CHANNEL SCAN - Finding drum channel")
        print(f"{'='*60}")
        print("Playing kick drum on each channel...")
        print("Listen for which channel produces drum sound.\n")

        kick_note = self.config.gm_drums['KICK']

        for channel in range(16):
            print(f"  Channel {channel} (1-indexed: Ch{channel+1})...", end='', flush=True)

            # Play kick
            self.port.send(mido.Message('note_on', note=kick_note, velocity=100, channel=channel))
            time.sleep(0.3)
            self.port.send(mido.Message('note_off', note=kick_note, velocity=0, channel=channel))
            time.sleep(0.5)

            if channel == 9:
                print(" ← Expected drum channel (GM standard)")
            else:
                print()

        print(f"\n{'='*60}")
        print("If you heard drums on a different channel than 9,")
        print("update config.py DRUMS channel accordingly.")
        print(f"{'='*60}\n")

    def _note_to_name(self, midi_note: int) -> str:
        """Convert MIDI note number to name"""
        notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        octave = (midi_note // 12) - 1
        note = notes[midi_note % 12]
        return f"{note}{octave}"


def main():
    parser = argparse.ArgumentParser(
        description='Test MIDI hardware output',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List available devices (default behavior if no device specified)
  python test_midi_hardware.py

  # Test specific device by name
  python test_midi_hardware.py -d "USB MIDI Device"

  # Test device by port index
  python test_midi_hardware.py -p 0

  # Test only drums
  python test_midi_hardware.py -p 0 --drums-only

  # Scan all channels to find drum channel
  python test_midi_hardware.py -p 0 --scan-channels
        """
    )

    parser.add_argument(
        '-d', '--device',
        help='MIDI device name'
    )
    parser.add_argument(
        '-p', '--port',
        type=int,
        help='MIDI port index (see list)'
    )
    parser.add_argument(
        '--drums-only',
        action='store_true',
        help='Test only drum channel'
    )
    parser.add_argument(
        '--scan-channels',
        action='store_true',
        help='Scan all 16 channels to find drum channel'
    )

    args = parser.parse_args()

    try:
        # Create tester
        tester = MIDIHardwareTester(port_name=args.device, port_index=args.port)

        # Run appropriate test
        if args.scan_channels:
            tester.test_channel_scan()
        elif args.drums_only:
            tester.test_drums_channel()
        else:
            tester.test_all_instruments()

        print("\nTest session complete!")
        print("Press Ctrl+C to exit if any notes are still playing.\n")

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
