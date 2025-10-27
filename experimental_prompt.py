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
            "CRITICAL: You are generating TRACKER FORMAT DATA for a MIDI sequencer, not prose.",
            "This is a structured data format that will be parsed by software.",
            "",
            f"Generate exactly {steps} lines for each of 4 instruments ({bars} bars at {tempo} BPM).",
            "",
            "STRICT FORMAT REQUIREMENTS (violations will cause parsing errors):",
            f"1. Each instrument section starts with its name alone on a line: BASS, DRUMS, PIANO, SAX",
            f"2. Each instrument MUST have exactly {steps} numbered lines (1 through {steps})",
            "3. Each numbered line MUST follow ONE of these exact patterns:",
            "   - Rest: NUMBER .",
            "   - Single note: NUMBER NOTE:VELOCITY",
            "   - Chord: NUMBER NOTE:VEL,NOTE:VEL,NOTE:VEL",  
            "   - Tie: NUMBER ^",
            "4. NO other text, NO comments, NO variations to this format",
            "",
            "VALID NOTES (ONLY these are allowed):",
            "C, C#, D, D#, E, F, F#, G, G#, A, A#, B",
            "With octave numbers: C1, C#1, D1... up to C7",
            "",
            "INSTRUMENT RANGES (stay within these or parsing fails):",
            "BASS: E1 to G3",
            "DRUMS: C1 to B4 (percussion mapping)",
            "PIANO: A0 to C7", 
            "SAX: Bb2 to F#5",
            "",
            "VELOCITY: Must be integer 0-127",
            "",
            "MUSICAL APPROACH FOR THIS SECTION:",
            exploration,
            "",
            f"SPECIFIC CHALLENGE: {constraint}",
        ]

        prompt.append("")
        prompt.append("EXACT FORMAT EXAMPLE (your notes/rhythms must differ):")
        prompt.extend(EXAMPLE_SNIPPET[1:])  # Skip "FORMAT EXAMPLE:" line since we have our own

        prompt.extend([
            "",
            "REMEMBER:",
            f"- Output EXACTLY {steps} numbered lines per instrument",
            "- Use ONLY the note names listed above with octave numbers",
            "- NO prose, NO descriptions, ONLY the tracker format",
            "- Think musically but output ONLY valid tracker data",
        ])

        if previous_context:
            # Analyze context length to provide different instructions
            context_lines = previous_context.strip().split('\n')
            if len(context_lines) > 100:  # More than ~1.5 sections
                context_instruction = "Reference motifs from EARLIER sections, not just the last one."
            else:
                context_instruction = "Develop from what came before without copying."
            
            prompt.extend([
                "",
                "PREVIOUS CONTEXT (for musical continuity):",
                previous_context,
                "",
                f"CONTEXT NOTE: {context_instruction}",
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