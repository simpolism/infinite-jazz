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
    """
    General MIDI standard drum note numbers.
    These are what the LLM should generate in tracker files.
    """
    return MappingProxyType({
        'KICK': 36,       # MIDI note 36 - Bass Drum 1 (GM Standard)
        'SNARE': 38,      # MIDI note 38 - Acoustic Snare (GM Standard)
        'CLOSED_HH': 42,  # MIDI note 42 - Closed Hi-Hat (GM Standard)
        'OPEN_HH': 46,    # MIDI note 46 - Open Hi-Hat (GM Standard)
        'TOM_LOW': 45,    # MIDI note 45 - Low Tom (GM Standard)
        'TOM_MID': 48,    # MIDI note 48 - Hi-Mid Tom (GM Standard)
        'TOM_HIGH': 50,   # MIDI note 50 - High Tom (GM Standard)
        'CRASH': 49,      # MIDI note 49 - Crash Cymbal 1 (GM Standard)
        'RIDE': 51,       # MIDI note 51 - Ride Cymbal 1 (GM Standard)
    })


def _default_drum_mapping() -> Mapping[int, int]:
    """
    Map LLM-generated drum notes to TG-33 drum notes.
    Format: {LLM_note: TG33_note}

    This translation allows LLM to generate drums while
    playing back correctly on the TG-33 hardware.
    """
    return MappingProxyType({
        # Kick/Bass Drums (LLM generates C1=24)
        24: 36,  # LLM Kick (C1) -> TG-33 BD 1 (C2)
        35: 36,  # GM Acoustic Bass Drum -> TG-33 BD 1
        36: 36,  # GM Bass Drum 1 -> TG-33 BD 1

        # Snares
        26: 38,  # LLM Snare (D1) -> TG-33 SD 2 (D2)
        38: 38,  # GM Acoustic Snare -> TG-33 SD 2
        40: 38,  # GM Electric Snare -> TG-33 SD 2

        # Hi-Hats
        42: 57,  # GM Closed Hi-Hat -> TG-33 HH closed (A3)
        44: 57,  # GM Pedal Hi-Hat -> TG-33 HH closed (A3)
        46: 59,  # GM Open Hi-Hat -> TG-33 HH open (B3)

        # Toms
        41: 47,  # GM Low Floor Tom -> TG-33 Tom 1 (B2)
        43: 47,  # GM High Floor Tom -> TG-33 Tom 1 (B2)
        45: 47,  # GM Low Tom -> TG-33 Tom 1 (B2)
        47: 48,  # GM Low-Mid Tom -> TG-33 Tom 2 (C3)
        48: 48,  # GM Hi-Mid Tom -> TG-33 Tom 2 (C3)
        50: 50,  # GM High Tom -> TG-33 Tom 3 (D3)

        # Cymbals
        49: 58,  # GM Crash Cymbal 1 -> TG-33 Crash 1 (A#3)
        55: 58,  # GM Splash Cymbal -> TG-33 Crash 1 (A#3)
        57: 58,  # GM Crash Cymbal 2 -> TG-33 Crash 1 (A#3)
        51: 63,  # GM Ride Cymbal 1 -> TG-33 Ride (D#4)
        59: 63,  # GM Ride Cymbal 2 -> TG-33 Ride (D#4)
    })


def _default_programs() -> Mapping[str, int]:
    """General MIDI program numbers for software synths (FluidSynth etc.)."""
    return MappingProxyType({
        'PIANO': 0,    # Acoustic Grand Piano
        'BASS': 33,    # Electric Bass (Finger)
        'SAX': 65,     # Soprano Sax
    })


def _tg33_programs() -> Mapping[str, int]:
    """
    TG-33 program numbers (MUST be 0-63 only!)

    TG-33 only responds to program changes 0-63 in Voice Play Mode.
    Voice calculation: MIDI Program = (Bank-1)*8 + (Preset-1)
    """
    return MappingProxyType({
        'PIANO': 1,   # TG-33 Bank 2.4 (voice 22)
        'BASS': 26,    # TG-33 Bank 4.3 (voice 37)
        'SAX': 43,     # TG-33 Bank 6.4 (voice 54)
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
    drum_mapping: Mapping[int, int] = field(default_factory=_default_drum_mapping)
    programs: Mapping[str, int] = field(default_factory=_default_programs)
    bars_per_generation: int = 2
    time_signature: Tuple[int, int] = (4, 4)
    send_program_changes: bool = True
    translate_drums: bool = False  # Enable for TG-33 hardware
    transpose_octaves: int = 0  # Set to 1 for TG-33 hardware

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
