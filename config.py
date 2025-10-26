"""
Configuration for JazzAI real-time jazz quartet generator
"""

# Timing configuration
TEMPO = 120  # BPM
RESOLUTION = '8th'  # '8th' or '16th' note resolution

# Note duration mode
NOTE_MODE = 'trigger'  # 'trigger' or 'sustain'

# MIDI configuration
TICKS_PER_BEAT = 480  # Standard MIDI resolution

# Instrument MIDI channels (General MIDI)
CHANNELS = {
    'BASS': 0,
    'DRUMS': 9,  # Channel 10 in 1-indexed (GM drum channel)
    'PIANO': 1,
    'SAX': 2,
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
    """Calculate MIDI ticks per tracker step based on resolution"""
    beats_per_bar = TIME_SIGNATURE[0]

    if RESOLUTION == '8th':
        steps_per_beat = 2
    elif RESOLUTION == '16th':
        steps_per_beat = 4
    else:
        raise ValueError(f"Unknown resolution: {RESOLUTION}")

    # Ticks per step = ticks per beat / steps per beat
    return TICKS_PER_BEAT // steps_per_beat


def get_steps_per_bar():
    """Get number of tracker steps per bar"""
    if RESOLUTION == '8th':
        return TIME_SIGNATURE[0] * 2  # 8 steps for 4/4
    elif RESOLUTION == '16th':
        return TIME_SIGNATURE[0] * 4  # 16 steps for 4/4
    else:
        raise ValueError(f"Unknown resolution: {RESOLUTION}")


def get_total_steps():
    """Get total number of tracker steps for configured bars"""
    return get_steps_per_bar() * BARS_PER_GENERATION
