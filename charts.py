"""Chord charts for jazz forms.

Each chart is a list of (chord_symbol, chord_tones) per beat.
The generator tracks form position and slices the relevant beats
for each section, injecting them as inline annotations.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional


# Chord tones as pitch classes (no octave — instrument determines register)
CHORD_TONES = {
    'BbM7': 'Bb,D,F,A',
    'Gm7': 'G,Bb,D,F',
    'Cm7': 'C,Eb,G,Bb',
    'F7': 'F,A,C,Eb',
    'Bb7': 'Bb,D,F,Ab',
    'EbM7': 'Eb,G,Bb,D',
    'Ebm7': 'Eb,Gb,Bb,Db',
    'Dm7': 'D,F,A,C',
    'G7': 'G,B,D,F',
    'D7': 'D,F#,A,C',
    'C7': 'C,E,G,Bb',
}


def _beats(chord: str, n: int = 2) -> list:
    """Repeat a chord for n beats."""
    return [chord] * n


def _bar(c1: str, c2: str) -> list:
    """Two chords splitting a bar (2 beats each)."""
    return _beats(c1) + _beats(c2)


# 32-bar AABA rhythm changes in Bb — 128 beats total
_A1 = (
    _bar('BbM7', 'Gm7') + _bar('Cm7', 'F7')       # bars 1-2
    + _bar('BbM7', 'Gm7') + _bar('Cm7', 'F7')      # bars 3-4
    + _bar('BbM7', 'Bb7') + _bar('EbM7', 'Ebm7')   # bars 5-6
    + _bar('Dm7', 'G7') + _bar('Cm7', 'F7')         # bars 7-8
)

_B = (
    _beats('D7', 8)                                   # bars 9-10
    + _beats('G7', 8)                                  # bars 11-12
    + _beats('C7', 8)                                  # bars 13-14
    + _beats('F7', 8)                                  # bars 15-16
)

_A2 = (
    _bar('BbM7', 'Gm7') + _bar('Cm7', 'F7')        # bars 25-26
    + _bar('BbM7', 'Gm7') + _bar('Cm7', 'F7')      # bars 27-28
    + _bar('BbM7', 'Bb7') + _bar('EbM7', 'Ebm7')   # bars 29-30
    + _bar('Cm7', 'F7') + _beats('BbM7', 4)         # bars 31-32
)

RHYTHM_CHANGES_Bb = _A1 + _A1 + _B + _A2  # AABA = 128 beats


@dataclass
class ChordChart:
    """A chord chart with per-beat chord symbols."""

    name: str
    beats: List[str]  # chord symbol per beat

    @property
    def total_beats(self) -> int:
        return len(self.beats)

    @property
    def total_bars(self) -> int:
        return self.total_beats // 4

    def get_section_chords(self, form_position_bars: int, num_bars: int) -> List[Tuple[str, str]]:
        """Get (chord_symbol, chord_tones) for a section.

        Args:
            form_position_bars: Current position in the form (in bars, 0-indexed)
            num_bars: Number of bars in this section

        Returns:
            List of (chord_symbol, tones_string) per beat
        """
        start_beat = (form_position_bars * 4) % self.total_beats
        num_beats = num_bars * 4
        result = []
        for i in range(num_beats):
            chord = self.beats[(start_beat + i) % self.total_beats]
            tones = CHORD_TONES.get(chord, chord)
            result.append((chord, tones))
        return result

    def format_beat_annotation(self, chord: str, tones: str) -> str:
        """Format a single beat's chord annotation as a comment line."""
        return f"# {chord}: {tones}"


# Pre-built charts
CHARTS = {
    'rhythm-changes': ChordChart(name='Rhythm Changes in Bb', beats=RHYTHM_CHANGES_Bb),
}
