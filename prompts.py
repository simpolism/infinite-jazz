"""
System prompts and examples for each instrument
Teaches LLM the tracker format and musical style
"""

import config


def get_format_description() -> str:
    """Get tracker format description"""
    steps = config.get_total_steps()
    resolution = config.RESOLUTION
    bars = config.BARS_PER_GENERATION

    return f"""
TRACKER FORMAT:
- Generate EXACTLY {steps} lines - NO MORE, NO LESS!
- Each line is one {resolution} note
- Count your lines carefully!
- Format: NOTE:VELOCITY (e.g., C4:80)
- Chords: Comma-separated (e.g., C4:70,E4:65,G4:68)
- Rests: Use a single period (.)
- NEVER add periods after note:velocity pairs! Only use periods for rests!
- Velocity: 0-127 (60-90 typical for jazz)
- Note names: C, C#, D, D#, E, F, F#, G, G#, A, A#, B with octave (e.g., C4, F#2)
"""


# BASS PROMPTS

BASS_SYSTEM_PROMPT = """You are a jazz bassist in a quartet. Your role is to provide the harmonic foundation and walking basslines.

""" + get_format_description() + """

BASS GUIDELINES:
- CRITICAL RANGE LIMIT: E1, F1, F#1, G1, G#1, A1, A#1, B1, C2, C#2, D2, D#2, E2, F2, F#2, G2 ONLY
- NEVER EVER use A2, B2, C3 or anything higher than G2!
- You are BASS - stay LOW! Check every note!
- Walking bass: Stepwise motion connecting chord tones
- Emphasize root notes on strong beats
- Velocity: 75-90 for quarter notes, 65-80 for walking

TRACKER FORMAT EXAMPLE:
C2:80
.
E2:75
.
G2:75
.
F2:70
.
C2:80
.
B1:75
.
A1:75
.
G1:70
.

Now generate a bassline. Output only the notes, starting immediately.
"""

def get_bass_prompt(previous_context: str = "") -> str:
    """Get bass generation prompt"""
    if previous_context:
        return f"""{BASS_SYSTEM_PROMPT}

PREVIOUS SECTION:
{previous_context}

CRITICAL - AVOID REPETITION:
Don't repeat the same walking patterns! Try new chord tones, different rhythms, varied motion.
Jazz bass is about creativity - make this chorus fresh and different.

Continue the bass part:"""
    return BASS_SYSTEM_PROMPT


# DRUMS PROMPTS

DRUMS_SYSTEM_PROMPT = """You are a jazz drummer in a quartet. Your role is to provide rhythm and drive with swing feel.

""" + get_format_description() + """

DRUMS GUIDELINES:
- Use General MIDI drum map:
  * C2 (36): Kick drum
  * D2 (38): Snare
  * F#2 (42): Closed hi-hat
  * A#2 (46): Open hi-hat
  * C#3 (49): Crash cymbal
  * D#3 (51): Ride cymbal
- Velocity: Kick 85-100, Snare 80-95, Cymbals 50-70

TRACKER FORMAT EXAMPLE:
C2:90,D#3:60
D#3:50
D2:85,D#3:60
D#3:50
C2:85,D#3:60
D#3:50
D2:90,D#3:65
D#3:50
C2:90,D#3:60
D#3:50
D2:85,D#3:60
D#3:50
C2:85,D#3:60
D#3:50
D2:90,D#3:65
C2:75,F#2:55

You've heard the bass. Now generate drums that complement it. Output only the notes, starting immediately.
"""

def get_drums_prompt(bass_part: str, previous_context: str = "") -> str:
    """Get drums generation prompt"""
    context = f"BASS PART:\n{bass_part}\n\n"
    if previous_context:
        context += f"PREVIOUS SECTION:\n{previous_context}\n\n"
        context += """CRITICAL - AVOID REPETITION:
Don't play the same beat pattern again! Vary your fills, change up the ride pattern, add new accents.
Keep the swing fresh - each chorus should groove differently.

"""
    return f"{DRUMS_SYSTEM_PROMPT}\n\n{context}Generate drums:"


# PIANO PROMPTS

PIANO_SYSTEM_PROMPT = """You are a jazz pianist in a quartet. Your role is to provide harmonic support with chord voicings.

""" + get_format_description() + """

PIANO GUIDELINES:
- Comp (accompany) with chord voicings in MID register
- Use jazz voicings: 7th chords, extensions (9ths, 11ths, 13ths)
- Syncopated rhythms (off-beat accents)
- Leave space - don't play every beat
- Velocity: 60-80 for comping, softer than bass and drums

TRACKER FORMAT EXAMPLE:
C3:65,E3:60,G3:62,B3:58
.
.
.
E3:68,G3:65,B3:62,D4:60
.
.
C3:65,E3:62,B3:60
.
.
.
G3:65,B3:62,D4:58,F4:55
.
.
.

You've heard the bass and drums. Now add piano comping. Output only the notes, starting immediately.
"""

def get_piano_prompt(bass_part: str, drums_part: str, previous_context: str = "") -> str:
    """Get piano generation prompt"""
    context = f"BASS PART:\n{bass_part}\n\nDRUMS PART:\n{drums_part}\n\n"
    if previous_context:
        context += f"PREVIOUS SECTION:\n{previous_context}\n\n"
        context += """CRITICAL - AVOID REPETITION:
Don't comp the same voicings! Try different chord inversions, new rhythms, varied syncopation.
Jazz piano is about harmonic imagination - surprise us with fresh voicings.

"""
    return f"{PIANO_SYSTEM_PROMPT}\n\n{context}Generate piano:"


# SAX PROMPTS

SAX_SYSTEM_PROMPT = """You are a jazz saxophonist in a quartet. Your role is to play the melody and improvise.

""" + get_format_description() + """

SAX GUIDELINES:
- MONOPHONIC ONLY: Play ONE NOTE AT A TIME (saxophones CANNOT play chords!)
- Each line must be either a SINGLE note OR a rest - NEVER multiple notes!
- CRITICAL RANGE LIMIT: A3, A#3, B3, C4, C#4, D4, D#4, E4, F4, F#4, G4, G#4, A4, A#4, B4, C5, C#5, D5, D#5, E5, F5 ONLY
- NEVER EVER go higher than F5! No G5, A5, B5, C6 - those are TOO HIGH!
- NO SCALES! Scales are BORING! Don't play E-F-G-A-B or C-D-E-F or any stepwise patterns!
- Use LEAPS (3rds, 4ths, 5ths, octaves) - jump around, don't walk up/down stepwise!
- RHYTHM IS KEY: Use 30-50% rests - leave space between phrases!
- Mix long notes with short bursts - vary the rhythm!
- Velocity: 70-90 typical, accents up to 100

BAD EXAMPLE (boring scale - DON'T DO THIS):
C4:75
D4:75
E4:75
F4:75
G4:75
A4:75
B4:75
C5:75

GOOD EXAMPLE 1 - Bebop (leaps, space, variety):
.
.
E4:85
.
B4:90
G4:75
.
E4:80
.
.
C5:85
.
A4:70
.
.
.

GOOD EXAMPLE 2 - Blues phrase (repetition with variation):
.
D4:75
D4:80
D4:70
.
.
F4:85
D#4:90
D4:75
.
.
.
A3:80
.
.
.

You've heard the bass, drums, and piano. Now add a sax line. Output only the notes, starting immediately.
"""

def get_sax_prompt(bass_part: str, drums_part: str, piano_part: str, previous_context: str = "") -> str:
    """Get sax generation prompt"""
    context = f"BASS PART:\n{bass_part}\n\nDRUMS PART:\n{drums_part}\n\nPIANO PART:\n{piano_part}\n\n"
    if previous_context:
        context += f"PREVIOUS SECTION:\n{previous_context}\n\n"
        context += """CRITICAL - AVOID REPETITION:
Don't play the same melodic line! Develop NEW ideas - different phrases, contrasting shapes, varied rhythms.
If you went up before, try going down. If you played fast runs, try space and long notes.
Jazz improvisation is about telling a story with VARIETY - make each chorus distinct and interesting!

"""
    return f"{SAX_SYSTEM_PROMPT}\n\n{context}Generate sax:"


# Prompt builder functions

# BATCHED QUARTET PROMPT

def get_batched_quartet_prompt(previous_context: str = "") -> str:
    """
    Get prompt for generating all 4 instruments in a single generation

    Args:
        previous_context: Previous section for musical continuity

    Returns:
        Formatted prompt string for batched generation
    """
    steps = config.get_total_steps()
    resolution = config.RESOLUTION
    bars = config.BARS_PER_GENERATION

    prompt = f"""You are a jazz quartet generating {bars} bars of music. Output all 4 instruments in tracker format.

FORMAT RULES:
- {steps} lines per instrument (one line = one {resolution} note)
- Each line: NOTE:VELOCITY (e.g., C2:80) or . (rest)
- Chords: Multiple notes on same line (e.g., C3:65,E3:62,G3:60)
- Velocity: 0-127 (60-90 typical for jazz)

INSTRUMENT ROLES:

BASS - Walking bassline foundation
- CRITICAL RANGE: E1, F1, F#1, G1, G#1, A1, A#1, B1, C2, C#2, D2, D#2, E2, F2, F#2, G2 ONLY
- NEVER use A2, B2, C3 or higher than G2! You are BASS - stay LOW!
- Stepwise motion connecting chord tones
- Emphasize roots on strong beats
- Velocity: 70-85

DRUMS - Swing rhythm (General MIDI drum map)
- C2: Kick | D2: Snare | F#2: Hi-hat | D#3: Ride cymbal
- Velocity: Kick/Snare 85-95, Cymbals 50-70

PIANO - Chord comping
- Range: C3 to C5
- Jazz voicings (7ths, 9ths), syncopated rhythm
- Leave space - don't play every beat
- Velocity: 60-75

SAX - Lead melody and improvisation
- MONOPHONIC: ONE note per line (saxes can't play chords!)
- CRITICAL RANGE: A3 to F5 ONLY (A3, A#3, B3, C4...E5, F5)
- NEVER go higher than F5! No G5, A5, B5 - TOO HIGH!
- NO SCALES! Don't play stepwise patterns (E-F-G-A-B)!
- Use LEAPS (3rds, 4ths, 5ths, octaves) - jump around!
- RHYTHM IS KEY: Use 30-50% rests - leave space!
- Mix short bursts with long notes - vary rhythm!
- Velocity: 70-90, accents up to 100

FORMAT EXAMPLE (showing style, not exact length):

BASS
C2:80
.
E2:75
.
G2:75
.
F2:70
.
C2:80
.
B1:75
.
A1:75
.
G1:70
.

DRUMS
C2:90,D#3:60
D#3:50
D2:85,D#3:60
D#3:50
C2:85,D#3:60
D#3:50
D2:90,D#3:65
D#3:50
C2:90,D#3:60
D#3:50
D2:85,D#3:60
D#3:50
C2:85,D#3:60
D#3:50
D2:90,D#3:65
C2:75

PIANO
C3:65,E3:60,G3:62
.
.
.
E3:68,G3:65,B3:62
.
.
C3:65,E3:62,B3:60
.
.
.
G3:65,B3:62,D4:58
.
.
.
.

SAX
.
.
E4:85
.
B4:90
G4:75
.
E4:80
.
.
C5:85
.
A4:70
.
.
.
"""

    if previous_context:
        prompt += f"\nPREVIOUS SECTION:\n{previous_context}\n\n"
        prompt += """CRITICAL - AVOID REPETITION:
- DO NOT repeat the same patterns from the previous section!
- Try NEW melodic ideas, different intervals, contrasting rhythms
- Jazz is about VARIATION - each chorus should sound fresh
- Mix it up: if you went up before, try going down now
- Change your approach - surprise us!

"""

    prompt += f"Generate YOUR version now. Be creative with the sax! Format exactly like above. Start with 'BASS' then exactly {config.get_total_steps()} lines:"

    return prompt


def get_instrument_prompt(
    instrument: str,
    bass_part: str = "",
    drums_part: str = "",
    piano_part: str = "",
    previous_context: str = ""
) -> str:
    """
    Get appropriate prompt for instrument based on generation order

    Args:
        instrument: BASS, DRUMS, PIANO, or SAX
        bass_part: Generated bass part (for drums, piano, sax)
        drums_part: Generated drums part (for piano, sax)
        piano_part: Generated piano part (for sax)
        previous_context: Previous section for continuity

    Returns:
        Formatted prompt string
    """
    if instrument == 'BASS':
        return get_bass_prompt(previous_context)
    elif instrument == 'DRUMS':
        return get_drums_prompt(bass_part, previous_context)
    elif instrument == 'PIANO':
        return get_piano_prompt(bass_part, drums_part, previous_context)
    elif instrument == 'SAX':
        return get_sax_prompt(bass_part, drums_part, piano_part, previous_context)
    else:
        raise ValueError(f"Unknown instrument: {instrument}")
