"""Prompt builders for Infinite Jazz batched quartet generation."""

from dataclasses import dataclass
from typing import List

from config import RuntimeConfig


EXAMPLE_SNIPPET: List[str] = [
    "FORMAT EXAMPLE:",
    "BASS",
    "1 C2:80",
    "2 .",
    "3 E2:75",
    "4 .",
    "",
    "DRUMS",
    "1 C2:90,F#2:60",
    "2 F#2:55",
    "3 D2:75,F#2:58",
    "4 F#2:52",
    "",
    "PIANO",
    "1 C3:65,E3:60,G3:62",
    "2 .",
    "3 .",
    "4 F3:70,A3:64,C4:60",
    "",
    "SAX",
    "1 E4:85",
    "2 .",
    "3 B4:90",
    "4 ^",
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
            "INSTRUMENT ROLES (treated as tendencies, not rules):",
            "BASS – Walking foundation (E1–G2). Outline harmony but feel free to slip in approach tones.",
            "",
            "DRUMS – Swing pulse with standard jazz kit. Use these EXACT note names:",
            "  • C2 = KICK (Bass Drum 1)",
            "  • D2 = SNARE (Acoustic Snare)",
            "  • F#2 = CLOSED HI-HAT",
            "  • Bb2 = OPEN HI-HAT",
            "  • Eb3 = RIDE CYMBAL",
            "DRUMS: Build swing patterns with ride/hi-hat on beats, kick on 1 & 3, snare on 2 & 4.",
            "DRUMS: Layer multiple drums per step for realism (e.g., '1 C2:90,F#2:60' = kick + closed hat).",
            "DRUMS: Break the pattern when inspiration hits—add fills, ghost notes, or drop-outs.",
            "",
            "PIANO – Mid-range comping (C3–C5) with open voicings; leave pockets of silence or punchy stabs at will.",
            "SAX – Monophonic lead (A3–F5). Think in gestures rather than patterns—rests, flurries, and ties are all welcome.",
            "SAX: Vary your rhythmic motifs; if you play a figure twice, twist or displace it on the next pass.",
            "SAX: Approach this chorus like a fearless improviser—chase tension, embrace wide intervals, and resolve phrases in surprising ways while keeping the tracker format clean.",
        ]

        prompt.append("")
        prompt.extend(EXAMPLE_SNIPPET)

        prompt.extend([
            "",
            "EXAMPLE USAGE NOTE: This illustration is for format only—your rhythms and note choices must differ significantly from it.",
            "",
            "GUIDELINES:",
            "- Let each chorus mutate; avoid recycling the previous cadence.",
            "- Rests and unexpected accents are encouraged—rhythmic surprises keep the quartet alive.",
            "- Stay in range and obey the tracker format, everything else is yours to reinvent.",
        ])

        if previous_context:
            prompt.extend([
                "",
                "PREVIOUS SECTION:",
                previous_context,
                "",
                "CRITICAL: Do not copy the previous section verbatim. Vary rhythm, contour, and voicings.",
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
