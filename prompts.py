"""Prompt builders for Infinite Jazz batched quartet generation."""

from config import RuntimeConfig


def get_batched_quartet_prompt(runtime_config: RuntimeConfig, previous_context: str = "") -> str:
    """
    Build the system prompt for generating all instruments in one pass.

    Args:
        runtime_config: Immutable runtime configuration.
        previous_context: Optional tracker text from the prior section.

    Returns:
        Formatted prompt string for batched generation.
    """
    steps = runtime_config.total_steps
    bars = runtime_config.bars_per_generation

    prompt = f"""You are a jazz quartet generating {bars} bars of music. Output all 4 instruments in tracker format.

FORMAT RULES:
- {steps} numbered lines per instrument (one line = one 16th-note step)
- Each line: NUMBER NOTE:VELOCITY (e.g., "1 C2:80"), NUMBER . (rest), or NUMBER ^ (hold previous note)
- Chords: Multiple notes on same line (e.g., "1 C3:65,E3:62,G3:60")
- Ties: Use ^ to hold previous note longer (e.g., "1 C2:80" then "2 ^" holds C2 across both steps)
- Velocity: 0-127 (60-90 typical for jazz)

INSTRUMENT ROLES:

BASS - Walking bassline foundation
- Recommended range: E1 to G2 (keep it low for bass sound)
- Stepwise motion connecting chord tones
- Emphasize roots on strong beats
- Velocity: 70-85

DRUMS - Swing rhythm (General MIDI drum map)
- C2: Kick | D2: Snare | F#2: Hi-hat | D#3: Ride cymbal
- Swing feel: Don't play every 16th note! Use rests (.)
- Ride/hi-hat on swing 8ths (every other 16th note or less)
- Velocity: Kick/Snare 85-95, Cymbals 50-70

PIANO - Chord comping
- Recommended range: C3 to C5 (mid-range for comping)
- Jazz voicings (7ths, 9ths), syncopated rhythm
- Leave space - don't play every beat
- Velocity: 60-75

SAX - Lead melody and improvisation
- MONOPHONIC: ONE note per line (saxes can't play chords!)
- Recommended range: A3 to F5 (typical tenor sax range)
- Create interesting melodies with varied intervals and rhythms
- Use space - include rests between phrases
- Use ^ (tie) to hold longer melodic notes
- Velocity: 70-90, accents up to 100

FORMAT EXAMPLE:

BASS
1 C2:80
2 .
3 E2:75
4 .
5 G2:75
6 .
7 F2:70
8 .
9 C2:80
10 .
11 B1:75
12 .
13 A1:75
14 .
15 G1:70
16 .
17 C2:80
18 .
19 E2:75
20 .
21 G2:70
22 .
23 F2:75
24 .
25 E2:80
26 .
27 D2:75
28 .
29 C2:80
30 .
31 B1:75
32 .

DRUMS
1 C2:90,D#3:60
2 .
3 D#3:55
4 .
5 D2:85,F#2:50
6 .
7 D#3:60
8 .
9 C2:85
10 .
11 D#3:55
12 .
13 D2:90,F#2:50
14 .
15 D#3:60
16 C2:75
17 C2:90,D#3:60
18 .
19 D#3:55
20 .
21 D2:85,F#2:50
22 .
23 D#3:60
24 .
25 C2:85
26 .
27 D#3:55
28 .
29 D2:90,F#2:50
30 C2:75,F#2:45
31 D#3:60
32 .

PIANO
1 C3:65,E3:60,G3:62
2 .
3 .
4 .
5 E3:68,G3:65,B3:62
6 .
7 .
8 C3:65,E3:62,B3:60
9 .
10 .
11 .
12 G3:65,B3:62,D4:58
13 .
14 .
15 .
16 .
17 C3:65,E3:60,G3:62
18 .
19 .
20 .
21 F3:68,A3:65,C4:62
22 .
23 .
24 D3:65,F3:62,A3:60
25 .
26 .
27 .
28 G3:65,B3:62,D4:58
29 .
30 .
31 .
32 .

SAX
1 .
2 .
3 E4:85
4 ^
5 B4:90
6 G4:75
7 .
8 E4:80
9 ^
10 .
11 C5:85
12 ^
13 A4:70
14 .
15 .
16 .
17 D5:85
18 ^
19 ^
20 B4:80
21 .
22 G4:75
23 D4:70
24 ^
25 .
26 E4:85
27 .
28 C5:90
29 ^
30 ^
31 A4:75
32 .
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

    prompt += (
        "Generate the new section now. Output ONLY tracker lines exactly as specified "
        f"above with {steps} lines per instrument:"
    )

    return prompt
