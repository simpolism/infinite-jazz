"""Immutable runtime configuration for Infinite Jazz."""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Tuple

from tracker_parser import TrackerParser


def _default_channels() -> Mapping[str, int]:
    return MappingProxyType({
        'BASS': 0,
        'DRUMS': 9,  # Channel 10 in 1-indexed GM numbering
        'PIANO': 1,
        'SAX': 2,
    })


def _default_pitch_ranges() -> Mapping[str, Tuple[int, int]]:
    return MappingProxyType({
        'BASS': (TrackerParser.note_to_midi('E1'), TrackerParser.note_to_midi('G2')),
        'PIANO': (TrackerParser.note_to_midi('C3'), TrackerParser.note_to_midi('C5')),
        'SAX': (TrackerParser.note_to_midi('A3'), TrackerParser.note_to_midi('F5')),
    })


def _default_gm_drums() -> Mapping[str, int]:
    return MappingProxyType({
        'KICK': 36,       # C2
        'SNARE': 38,      # D2
        'CLOSED_HH': 42,  # F#2
        'OPEN_HH': 46,    # A#2
        'TOM_LOW': 45,    # A2
        'TOM_MID': 48,    # C3
        'TOM_HIGH': 50,   # D3
        'CRASH': 49,      # C#3
        'RIDE': 51,       # D#3
    })


@dataclass(frozen=True)
class RuntimeConfig:
    """Immutable configuration used across the runtime pipeline."""

    tempo: int = 120  # BPM
    resolution: str = '16th'
    note_mode: str = 'trigger'  # 'trigger' or 'sustain'
    swing_enabled: bool = True
    swing_ratio: float = 0.67  # 0.67 = 2:1 swing
    ticks_per_beat: int = 480
    channels: Mapping[str, int] = field(default_factory=_default_channels)
    pitch_ranges: Mapping[str, Tuple[int, int]] = field(default_factory=_default_pitch_ranges)
    gm_drums: Mapping[str, int] = field(default_factory=_default_gm_drums)
    bars_per_generation: int = 2
    time_signature: Tuple[int, int] = (4, 4)

    def __post_init__(self):
        if self.note_mode not in {'trigger', 'sustain'}:
            raise ValueError(f"note_mode must be 'trigger' or 'sustain', got {self.note_mode}")
        if self.bars_per_generation <= 0:
            raise ValueError("bars_per_generation must be positive")
        if self.time_signature[0] <= 0 or self.time_signature[1] <= 0:
            raise ValueError("time_signature must contain positive integers")

    @property
    def steps_per_bar(self) -> int:
        """Number of tracker steps per bar for the fixed 16th-note grid."""
        # 16th-note resolution = 4 steps per beat
        beats_per_bar = self.time_signature[0]
        return beats_per_bar * 4

    @property
    def total_steps(self) -> int:
        """Total tracker steps per generated section."""
        return self.steps_per_bar * self.bars_per_generation

    @property
    def ticks_per_step(self) -> int:
        """MIDI ticks per tracker step (fixed to 16th-note resolution)."""
        return self.ticks_per_beat // 4


# Default immutable configuration used when no overrides are supplied.
DEFAULT_CONFIG = RuntimeConfig()
