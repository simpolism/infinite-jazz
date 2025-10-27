"""
Parser for minimal tracker format
Converts text tracker format to structured representation
"""

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class Note:
    """Represents a single note with pitch and velocity"""
    pitch: int  # MIDI note number (0-127) or pitch name (e.g., "C4")
    velocity: int  # MIDI velocity (0-127)


@dataclass
class TrackerStep:
    """Represents one time step in the tracker"""
    notes: List[Note]  # Empty list = rest
    is_rest: bool


@dataclass
class InstrumentTrack:
    """Represents a complete track for one instrument"""
    instrument: str
    steps: List[TrackerStep]


class TrackerParser:
    """Parses minimal tracker format into structured data"""

    # Note name to MIDI number mapping
    # Includes enharmonic equivalents (Cb=B, Fb=E, E#=F, B#=C)
    NOTE_MAP = {
        'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3,
        'E': 4, 'Fb': 4, 'E#': 5, 'F': 5, 'F#': 6, 'Gb': 6,
        'G': 7, 'G#': 8, 'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10,
        'B': 11, 'Cb': 11, 'B#': 0
    }

    @staticmethod
    def note_to_midi(note_name: str) -> int:
        """
        Convert note name to MIDI number
        Examples: C4 -> 60, A#3 -> 58, Gb5 -> 78, Cb4 -> 59 (B3)
        """
        match = re.match(r'^([A-G][#b]?)(-?\d+)$', note_name)
        if not match:
            raise ValueError(f"Invalid note name: {note_name}")

        note, octave = match.groups()
        octave = int(octave)

        # Handle enharmonic equivalents that cross octave boundaries
        # Cb needs to go down an octave (Cb4 = B3)
        # B# needs to go up an octave (B#3 = C4)
        if note == 'Cb':
            octave -= 1
        elif note == 'B#':
            octave += 1

        # MIDI note number = (octave + 1) * 12 + note_offset
        # Middle C (C4) = 60
        midi_num = (octave + 1) * 12 + TrackerParser.NOTE_MAP[note]

        if not 0 <= midi_num <= 127:
            raise ValueError(f"Note {note_name} out of MIDI range (0-127): {midi_num}")

        return midi_num

    @staticmethod
    def parse_note_entry(entry: str) -> List[Note]:
        """
        Parse a single note entry (can be chord)
        Examples:
          "C4:80" -> [Note(60, 80)]
          "C4:70,E4:65,G4:68" -> [Note(60, 70), Note(64, 65), Note(67, 68)]
          "C4:70,E4:65," -> [Note(60, 70), Note(64, 65)] (trailing comma ignored)
          "C4:70." -> [Note(60, 70)] (trailing period ignored)
          "." -> [] (rest)
        """
        entry = entry.strip()

        # Clean up common LLM mistakes: trailing commas, periods
        entry = entry.rstrip('.,;')
        entry = entry.strip()

        if entry == '.' or entry == '':
            return []

        notes = []
        for note_str in entry.split(','):
            note_str = note_str.strip()

            # Skip empty strings (from trailing commas)
            if not note_str:
                continue

            if ':' not in note_str:
                raise ValueError(f"Invalid note format (expected NOTE:VELOCITY): {note_str}")

            pitch_str, velocity_str = note_str.split(':', 1)

            # Clean velocity string (might have trailing junk)
            velocity_str = velocity_str.strip()
            # Extract just the digits
            velocity_digits = ''.join(c for c in velocity_str if c.isdigit())

            if not velocity_digits:
                raise ValueError(f"No valid velocity found in: {velocity_str}")

            # Convert pitch name to MIDI number
            pitch = TrackerParser.note_to_midi(pitch_str.strip())
            velocity = int(velocity_digits)

            # Clamp velocity to valid MIDI range (0-127) instead of failing
            if velocity < 0:
                print(f"  Warning: Velocity {velocity} too low, clamping to 0")
                velocity = 0
            elif velocity > 127:
                print(f"  Warning: Velocity {velocity} too high, clamping to 127")
                velocity = 127

            notes.append(Note(pitch=pitch, velocity=velocity))

        return notes

    @staticmethod
    def parse_track(instrument: str, lines: List[str]) -> InstrumentTrack:
        """
        Parse a single instrument track
        Args:
            instrument: Instrument name (BASS, DRUMS, PIANO, SAX)
            lines: List of tracker lines (one per step)
        """
        steps = []

        for line_num, line in enumerate(lines, 1):
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Strip line number if present (format: "1 C2:80" or "1. C2:80")
            # Match optional number (with optional period) followed by whitespace
            line = re.sub(r'^\d+\.?\s+', '', line)

            try:
                notes = TrackerParser.parse_note_entry(line)
                is_rest = len(notes) == 0
                steps.append(TrackerStep(notes=notes, is_rest=is_rest))
            except ValueError as e:
                raise ValueError(f"Error in {instrument} track, line {line_num}: {e}")

        return InstrumentTrack(instrument=instrument, steps=steps)

    @staticmethod
    def parse(tracker_text: str) -> Dict[str, InstrumentTrack]:
        """
        Parse complete tracker format text
        Returns dict mapping instrument name to InstrumentTrack

        Expected format:
        BASS
        1 C2:80
        2 .
        3 E2:75
        ...

        DRUMS
        1 C1:90,F#1:60
        ...

        Note: Line numbers are optional and will be automatically stripped if present.
        """
        lines = tracker_text.strip().split('\n')
        tracks = {}
        current_instrument = None
        current_lines = []

        for line in lines:
            line = line.strip()

            # Check if this is a section header
            if line in ['BASS', 'DRUMS', 'PIANO', 'SAX']:
                # Save previous instrument if exists
                if current_instrument and current_lines:
                    tracks[current_instrument] = TrackerParser.parse_track(
                        current_instrument, current_lines
                    )

                # Start new instrument
                current_instrument = line
                current_lines = []
            elif line:  # Non-empty line, not a header
                if current_instrument is None:
                    raise ValueError(f"Found note data before instrument header: {line}")
                current_lines.append(line)

        # Don't forget the last instrument
        if current_instrument and current_lines:
            tracks[current_instrument] = TrackerParser.parse_track(
                current_instrument, current_lines
            )

        return tracks


# Convenience function
def parse_tracker(tracker_text: str) -> Dict[str, InstrumentTrack]:
    """Parse tracker format text. Returns dict of instrument -> InstrumentTrack"""
    return TrackerParser.parse(tracker_text)
