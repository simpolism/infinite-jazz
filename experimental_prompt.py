"""Prompt builders for Infinite Jazz batched quartet generation - Improved version."""

from dataclasses import dataclass
from typing import List
import random

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
    "1 C2:90,D#3:60",
    "2 .",
    "3 .",
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


# Rotating prompts to vary the generative approach
EXPLORATION_MODES = [
    "CONVERSATION MODE: Each instrument should respond to or comment on what another just played, like a musical dialogue.",
    "TENSION MODE: Build harmonic or rhythmic tension gradually, then release it unexpectedly.",
    "SPACE MODE: Use silence strategically. At least one instrument should leave significant gaps.",
    "POLYRHYTHM MODE: Layer different rhythmic patterns - some instruments on-beat, others syncopated or in different groupings.",
    "COLOR MODE: Focus on unusual note combinations and extended harmonies. Explore outside notes that still resolve.",
    "MOMENTUM MODE: Create forward motion through walking bass, driving rhythm, or ascending melodic lines.",
    "FRAGMENT MODE: Trade short musical phrases between instruments, breaking up longer lines.",
    "TEXTURE MODE: Contrast sparse and dense moments. Some instruments drop out while others become busier.",
]

DYNAMIC_CONSTRAINTS = [
    "One instrument must play a repeated figure with slight variations each time.",
    "Include at least one moment where all instruments hit the same beat, then scatter.",
    "The sax should leave a dramatic pause of at least 4 steps somewhere.",
    "Piano plays only sparse, angular chords - no more than 3 notes per bar.",
    "Bass ventures into the upper register at least once.",
    "Drums accent unexpected beats while keeping time subtly.",
    "Create a call-and-response between any two instruments.",
    "All instruments should crescendo or decrescendo together at some point.",
]


@dataclass
class PromptBuilder:
    """Build prompts for quartet generation with stylistic guidance."""

    config: RuntimeConfig
    style: str = "exploratory"
    generation_count: int = 0

    def build_quartet_prompt(self, previous_context: str = "") -> str:
        """Construct the prompt for generating all instruments in one pass."""
        steps = self.config.total_steps
        bars = self.config.bars_per_generation
        tempo = self.config.tempo
        
        # Track generations to rotate approaches
        self.generation_count += 1
        
        # Select varying elements
        exploration = EXPLORATION_MODES[self.generation_count % len(EXPLORATION_MODES)]
        constraint = random.choice(DYNAMIC_CONSTRAINTS)

        prompt = [
            f"You are an {self.style} jazz quartet generating {bars} bars of music.",
            "Create music that feels like jazz but isn't afraid to surprise.",
            f"Tempo feel: {tempo} BPM on a 16th-note grid.",
            "",
            "FORMAT RULES:",
            f"- {steps} numbered lines per instrument (one line = one 16th-note step)",
            '- Each line: NUMBER NOTE:VELOCITY (e.g., "1 C2:80"), NUMBER . (rest), or NUMBER ^ (tie)',
            '- Chords: NUMBER NOTE:VELOCITY,NOTE:VELOCITY (e.g., "1 C3:65,E3:62,G3:60")',
            "- Velocity range: 0-127 (but vary dynamics for expression)",
            "",
            "INSTRUMENTS & POSSIBILITIES:",
            "BASS – Walking lines, pedal points, melodic runs, or sparse roots. Range: E1-G3",
            "DRUMS – Swing, straight, broken, or implied time. Create texture with velocity.",
            "PIANO – Comping, clusters, single notes, countermelodies, or silence. Range: A0-C7",
            "SAX – The horn can wail, whisper, stab, float, or fragment. Range: Bb2-F#5",
            "",
            "APPROACH FOR THIS SECTION:",
            exploration,
            "",
            f"SPECIFIC CHALLENGE: {constraint}",
        ]

        prompt.append("")
        prompt.extend(EXAMPLE_SNIPPET)

        prompt.extend([
            "",
            "NOTE: The example shows format only. Create completely different musical content.",
            "",
            "MUSICAL PRINCIPLES:",
            "- Jazz is about interaction and surprise within a flowing conversation",
            "- Each chorus should feel related but never identical to what came before",
            "- Embrace both the expected and unexpected - swing and anti-swing",
            "- Let patterns emerge and dissolve naturally",
            "- If something worked before, transform it rather than repeat it",
        ])

        if previous_context:
            # Analyze context length to provide different instructions
            context_lines = previous_context.strip().split('\n')
            if len(context_lines) > 100:  # More than ~1.5 sections
                context_instruction = "Reference ideas from EARLIER in the context, not just the last section. Transform and develop motifs."
            else:
                context_instruction = "Acknowledge what just happened but take it somewhere new."
            
            prompt.extend([
                "",
                "PREVIOUS CONTEXT (for continuity, not copying):",
                previous_context,
                "",
                f"CONTEXT GUIDANCE: {context_instruction}",
                "Avoid repeating rhythmic patterns verbatim. If a phrase appears familiar, twist it.",
            ])
        else:
            prompt.extend([
                "",
                "This is the opening - establish a mood but leave room to develop.",
            ])

        prompt.extend([
            "",
            f"Generate the new section now with exactly {steps} lines per instrument.",
            "Start with 'BASS' as the first line.",
            "",
            "Remember: Make jazz that breathes, evolves, and occasionally surprises itself.",
        ])

        return "\n".join(prompt)