"""Prompt builders for Infinite Jazz batched quartet generation."""

from dataclasses import dataclass
from typing import List

from config import RuntimeConfig


MINIMAL_FORMAT_EXAMPLE: List[str] = [
    "FORMAT EXAMPLE (just syntax, not a musical suggestion):",
    "BASS",
    "1 C2:80     ← note + velocity",
    "2 .         ← rest",
    "3 ^         ← tie (continue previous note)",
    "",
    "DRUMS",
    "1 C2:90,F#2:60   ← multiple notes = layering (kick + hat)",
    "2 D2:85",
    "",
    "PIANO",
    "1 C3:70,E3:65,G3:68   ← chord (3 notes together)",
    "",
    "SAX",
    "1 G4:75",
]


@dataclass
class PromptBuilder:
    """Build prompts for quartet generation with stylistic guidance."""

    config: RuntimeConfig

    def build_quartet_prompt(self, previous_context: str = "", extra_prompt: str = "") -> str:
        """Construct the prompt for generating all instruments in one pass.

        Args:
            previous_context: Previous section for musical continuity
            extra_prompt: Additional instructions to guide the generation
        """
        steps = self.config.total_steps
        bars = self.config.bars_per_generation
        tempo = self.config.tempo

        prompt = [
            f"You are a jazz quartet generating {bars} bars of music.",
            "Output all 4 instruments in tracker format exactly as specified.",
            f"Approximate tempo: {tempo} BPM on a 16th-note grid.",
            "",
            "FORMAT RULES:",
            f"- {steps} numbered lines per instrument (one line = one 16th-note step)",
            '- Each line: NUMBER NOTE:VELOCITY (e.g., "1 C2:80"), NUMBER . (rest), or NUMBER ^ (tie)',
            '- Chords: NUMBER NOTE:VELOCITY,NOTE:VELOCITY (e.g., "1 C3:65,E3:62,G3:60")',
            "- Velocity range: 0-127 (60-90 typical for jazz)",
            "",
            "DRUMS AVAILABLE NOTES (use these exact note names for drums):",
            "  C2=kick, D2=snare, F#2=closed-hat, Bb2=open-hat, Eb3=ride",
            "",
            "CREATIVE FREEDOM:",
            "You are a jazz quartet improvising together. Make your own musical choices.",
            "Play what sounds good to you. Break patterns. Surprise yourself.",
            "Use space, dynamics, and rhythm however you want.",
        ]

        prompt.append("")
        prompt.extend(MINIMAL_FORMAT_EXAMPLE)

        if previous_context:
            prompt.extend([
                "",
                "PREVIOUS SECTION:",
                previous_context,
                "",
                "Respond to what came before however you want - continue it, contrast it, or go somewhere completely new.",
            ])

        if extra_prompt:
            prompt.extend([
                "",
                "PLAYER DIRECTION:",
                extra_prompt,
            ])

        prompt.extend([
            "",
            "OUTPUT REQUIREMENTS:",
            "1. First line must be: BASS",
            f"2. Follow with exactly {steps} numbered lines for bass",
            "3. Then: DRUMS (blank line before is OK)",
            f"4. Follow with exactly {steps} numbered lines for drums",
            "5. Then: PIANO",
            f"6. Follow with exactly {steps} numbered lines for piano",
            "7. Then: SAX",
            f"8. Follow with exactly {steps} numbered lines for sax",
            "",
            "Generate the tracker data now:",
        ])

        return "\n".join(prompt)
