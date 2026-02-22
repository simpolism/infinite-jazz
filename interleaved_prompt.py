"""Interleaved prompt builder for Infinite Jazz.

Generates format where instruments are written beat-by-beat rather than
in sequential blocks. This creates information asymmetry in the attention
structure: each instrument can react to the others with a 1-beat delay,
mimicking the delayed response of real improvisation.
"""

from dataclasses import dataclass

from config import RuntimeConfig


@dataclass
class InterleavedPromptBuilder:
    """Build prompts for beat-by-beat interleaved quartet generation."""

    config: RuntimeConfig

    def build_quartet_prompt(self, previous_context: str = "", extra_prompt: str = "") -> str:
        steps = self.config.total_steps
        bars = self.config.bars_per_generation
        tempo = self.config.tempo
        beats = bars * self.config.time_signature[0]

        prompt = [
            f"You are a jazz quartet improvising {bars} bars of music together.",
            f"Tempo: {tempo} BPM, 16th-note grid, {self.config.time_signature[0]}/{self.config.time_signature[1]} time.",
            "",
            "You will write the music BEAT BY BEAT, with all 4 instruments on each beat.",
            "This lets each instrument HEAR and REACT to what the others just played.",
            "",
            "FORMAT: Each beat has 4 lines, one per instrument.",
            "Each line has the instrument name, a colon, then 4 space-separated steps (the 4 sixteenth notes of that beat).",
            "",
            "STEP NOTATION:",
            "  Note: NOTE:VELOCITY (e.g. C2:80, F#4:70)",
            "  Chord: NOTE:VEL,NOTE:VEL (e.g. C3:65,E3:60,G3:62)",
            "  Rest: .",
            "  Tie: ^",
            "",
            "INSTRUMENT RANGES:",
            "  BASS: E1-G2 (low register, roots and fifths)",
            "  DRUMS: C2=kick, D2=snare, F#2=closed-hat, Bb2=open-hat, Eb3=ride",
            "  PIANO: C3-C5 (chords and voicings)",
            "  SAX: A3-F5 (melody and improvisation)",
            "Velocity range: 0-127 (60-90 typical for jazz)",
            "",
            "EXAMPLE (2 beats shown):",
            "[BEAT 1]",
            "BASS: C2:80 . . .",
            "DRUMS: C2:90,F#2:60 F#2:60 F#2:60 D2:80",
            "PIANO: C3:70,E3:65,G3:68 . . .",
            "SAX: G4:75 . . .",
            "",
            "[BEAT 2]",
            "BASS: E2:75 . . .",
            "DRUMS: F#2:60 . D2:85,F#2:60 F#2:60",
            "PIANO: . . . C3:65,Bb3:60",
            "SAX: . A4:80 . G4:72",
            "",
            "LISTEN TO EACH OTHER. React to what just happened on the previous beat.",
            "Leave space. Not every instrument needs to play every beat.",
            "Surprise each other. This is a conversation, not a script.",
        ]

        if previous_context:
            prompt.extend([
                "",
                "WHAT JUST HAPPENED (previous section):",
                previous_context,
                "",
                "Continue the conversation from here.",
            ])

        if extra_prompt:
            prompt.extend([
                "",
                "DIRECTION:",
                extra_prompt,
            ])

        prompt.extend([
            "",
            f"Generate exactly {beats} beats. Each beat has exactly 4 instrument lines (BASS, DRUMS, PIANO, SAX), each with exactly 4 steps.",
            "Output ONLY the tracker data, no explanations.",
            "",
            "Begin:",
        ])

        return "\n".join(prompt)
