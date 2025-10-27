"""
Configuration for Infinite Jazz real-time quartet generator
"""

from tracker_parser import TrackerParser

# Timing configuration
TEMPO = 120  # BPM
# Tracker uses fixed 16th-note resolution
RESOLUTION = '16th'
# Fixed 16th-note resolution for tracker steps

# Note duration mode
NOTE_MODE = 'trigger'  # 'trigger' or 'sustain'

# Swing rhythm configuration
SWING_ENABLED = True  # Enable swing feel for off-beats
SWING_RATIO = 0.67  # 0.67 = 2:1 swing (typical jazz), 0.5 = straight (no swing), 0.75 = heavy swing

# MIDI configuration
TICKS_PER_BEAT = 480  # Standard MIDI resolution

# Instrument MIDI channels (General MIDI)
CHANNELS = {
    'BASS': 0,
    'DRUMS': 9,  # Channel 10 in 1-indexed (GM drum channel)
    'PIANO': 1,
    'SAX': 2,
}

# Instrument pitch ranges expressed as MIDI note numbers (inclusive)
# Used for validation and retry logic
PITCH_RANGES = {
    'BASS': (TrackerParser.note_to_midi('E1'), TrackerParser.note_to_midi('G2')),
    'PIANO': (TrackerParser.note_to_midi('C3'), TrackerParser.note_to_midi('C5')),
    'SAX': (TrackerParser.note_to_midi('A3'), TrackerParser.note_to_midi('F5')),
}

# General MIDI Level 1 Drum Map (note numbers)
GM_DRUMS = {
    'KICK': 36,      # C2
    'SNARE': 38,     # D2
    'CLOSED_HH': 42, # F#2
    'OPEN_HH': 46,   # A#2
    'TOM_LOW': 45,   # A2
    'TOM_MID': 48,   # C3
    'TOM_HIGH': 50,  # D3
    'CRASH': 49,     # C#3
    'RIDE': 51,      # D#3
}

# Generation configuration
BARS_PER_GENERATION = 2  # Generate 2 bars at a time
TIME_SIGNATURE = (4, 4)  # 4/4 time


def get_ticks_per_step():
    """MIDI ticks per tracker step (fixed to 16th-note resolution)"""
    steps_per_beat = 4  # 16th notes
    return TICKS_PER_BEAT // steps_per_beat


def get_steps_per_bar():
    """Number of tracker steps per bar (fixed 16th-note grid)"""
    return TIME_SIGNATURE[0] * 4  # 16th notes in 4/4


def get_total_steps():
    """Get total number of tracker steps for configured bars"""
    return get_steps_per_bar() * BARS_PER_GENERATION
