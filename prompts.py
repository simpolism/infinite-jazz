"""Prompt builders for Infinite Jazz batched quartet generation."""

import random
from dataclasses import dataclass, field
from itertools import cycle
from typing import Iterable, List

from config import RuntimeConfig


def _default_examples() -> List[List[str]]:
    return [
        [
            "FORMAT EXAMPLE A (Walking swing):",
            "BASS",
            "1 C2:80",
            "2 .",
            "3 E2:75",
            "4 .",
            "5 G2:78",
            "6 .",
            "7 F2:74",
            "8 .",
            "9 Bb1:76",
            "10 .",
            "11 A1:72",
            "12 .",
            "13 D2:79",
            "14 .",
            "15 G1:70",
            "16 .",
            "",
            "DRUMS",
            "1 C2:90,D#3:60",
            "2 .",
            "3 D#3:55",
            "4 .",
            "5 F#2:52",
            "6 .",
            "7 D#3:62",
            "8 .",
            "9 C2:88",
            "10 .",
            "11 D#3:58",
            "12 .",
            "13 F#2:50",
            "14 .",
            "15 D#3:60",
            "16 C2:76",
            "",
            "PIANO",
            "1 C3:65,E3:60,G3:62",
            "2 .",
            "3 .",
            "4 .",
            "5 F3:70,A3:64,C4:60",
            "6 .",
            "7 .",
            "8 Bb2:60,E3:63,A3:59",
            "9 .",
            "10 D3:68,F3:62,C4:60",
            "11 .",
            "12 .",
            "13 G3:66,B3:61,D4:57",
            "14 .",
            "15 .",
            "16 .",
            "",
            "SAX",
            "1 .",
            "2 .",
            "3 E4:85",
            "4 ^",
            "5 B4:90",
            "6 G4:75",
            "7 .",
            "8 D5:82",
            "9 ^",
            "10 .",
            "11 A4:70",
            "12 .",
            "13 F4:76",
            "14 ^",
            "15 .",
            "16 .",
        ],
        [
            "FORMAT EXAMPLE B (Modal variation):",
            "BASS",
            "1 D2:78",
            "2 .",
            "3 F2:74",
            "4 .",
            "5 G2:80",
            "6 .",
            "7 A2:82",
            "8 .",
            "9 C3:77",
            "10 .",
            "11 Bb2:73",
            "12 .",
            "13 A2:76",
            "14 .",
            "15 G2:75",
            "16 .",
            "",
            "PIANO",
            "1 D3:64,A3:60",
            "2 F3:66,C4:61",
            "3 .",
            "4 .",
            "5 G3:70,D4:65",
            "6 .",
            "7 C4:67,E4:62",
            "8 .",
            "9 Bb3:63,D4:60",
            "10 .",
            "11 .",
            "12 A3:66,C4:62",
            "13 .",
            "14 F3:64,G3:60",
            "15 .",
            "16 .",
            "",
            "SAX",
            "1 D4:78",
            "2 F4:81",
            "3 A4:88",
            "4 ^",
            "5 .",
            "6 C5:86",
            "7 Bb4:79",
            "8 G4:76",
            "9 F4:74",
            "10 .",
            "11 D5:84",
            "12 ^",
            "13 C5:80",
            "14 A4:77",
            "15 .",
            "16 .",
        ],
        [
            "FORMAT EXAMPLE C (Broken-time):",
            "BASS",
            "1 G1:76",
            "2 .",
            "3 .",
            "4 D2:82",
            "5 .",
            "6 F#1:74",
            "7 .",
            "8 .",
            "9 C2:80",
            "10 .",
            "11 Eb2:78",
            "12 .",
            "13 .",
            "14 F2:77",
            "15 .",
            "16 Db2:73",
            "",
            "DRUMS",
            "1 C2:88",
            "2 .",
            "3 .",
            "4 F#2:54",
            "5 D#3:63",
            "6 .",
            "7 C2:85",
            "8 .",
            "9 .",
            "10 D#3:58",
            "11 F#2:50",
            "12 .",
            "13 C2:87",
            "14 .",
            "15 D#3:62",
            "16 F#2:52",
            "",
            "PIANO",
            "1 .",
            "2 Bb2:60,E3:63,G3:59",
            "3 .",
            "4 .",
            "5 D3:66,F3:61,A3:64",
            "6 .",
            "7 .",
            "8 G2:58,B3:60,D4:63",
            "9 .",
            "10 .",
            "11 Eb3:65,G3:62,C4:66",
            "12 .",
            "13 .",
            "14 F3:68,A3:64,C4:61",
            "15 .",
            "16 .",
            "",
            "SAX",
            "1 .",
            "2 G4:84",
            "3 Bb4:86",
            "4 .",
            "5 F5:90",
            "6 .",
            "7 E5:88",
            "8 C5:80",
            "9 .",
            "10 A4:76",
            "11 ^",
            "12 .",
            "13 D5:89",
            "14 C#5:87",
            "15 .",
            "16 G4:78",
        ],
    ]


@dataclass
class PromptBuilder:
    """Build prompts for quartet generation with rotating stylistic guidance."""

    config: RuntimeConfig
    primary_style: str = "modern swing"
    style_palette: Iterable[str] = (
        "modern swing",
        "modal post-bop exploration",
        "uptempo bebop chase",
        "late-night ballad phrasing",
    )
    examples_per_prompt: int = 2
    example_catalog: List[List[str]] = field(default_factory=_default_examples)
    _style_cycle: cycle = field(init=False, repr=False)

    def __post_init__(self):
        palette: List[str] = list(self.style_palette) or [self.primary_style]
        if self.primary_style not in palette:
            palette.insert(0, self.primary_style)
        self._style_cycle = cycle(palette)

    def _active_style(self) -> str:
        return next(self._style_cycle)

    def build_quartet_prompt(self, previous_context: str = "") -> str:
        """Construct the prompt for generating all instruments in one pass."""
        steps = self.config.total_steps
        bars = self.config.bars_per_generation
        style = self._active_style()

        prompt = [
            f"You are a {style} jazz quartet generating {bars} bars of music.",
            "Output all 4 instruments in tracker format exactly as specified.",
            "",
            "FORMAT RULES:",
            f"- {steps} numbered lines per instrument (one line = one 16th-note step)",
            '- Each line: NUMBER NOTE:VELOCITY (e.g., "1 C2:80"), NUMBER . (rest), or NUMBER ^ (tie)',
            '- Chords: NUMBER NOTE:VELOCITY,NOTE:VELOCITY (e.g., "1 C3:65,E3:62,G3:60")',
            "- Velocity range: 0-127 (60-90 typical for jazz)",
            "",
            "INSTRUMENT ROLES:",
            "BASS – Walking foundation (E1–G2). Outline harmony but feel free to slip in approach tones.",
            "DRUMS – Swing pulse using GM mapping (kick/snare/cymbals) yet break the ride pattern when inspiration hits.",
            "PIANO – Mid-range comping (C3–C5) with open voicings; leave pockets of silence or punchy stabs at will.",
            "SAX – Monophonic lead (A3–F5). Think in gestures rather than patterns—rests, flurries, and ties are all welcome.",
            "SAX: Vary your rhythmic motifs; if you play a figure twice, twist or displace it on the next pass.",
            "SAX: Approach this chorus like a fearless improviser—chase tension, embrace wide intervals, and resolve phrases in surprising ways while keeping the tracker format clean.",
        ]

        selected_examples = random.sample(
            self.example_catalog,
            k=min(self.examples_per_prompt, len(self.example_catalog))
        )

        for example in selected_examples:
            prompt.append("")
            prompt.extend(example)

        prompt.extend([
            "",
            "EXAMPLE USAGE NOTE: These illustrations are for format only—your rhythms and note choices must differ significantly from them.",
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

        prompt.extend([
            "",
            f"Generate the new section now with exactly {steps} lines per instrument.",
            "Start the output with the literal header 'BASS' on the first line.",
        ])

        return "\n".join(prompt)
