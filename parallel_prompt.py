"""Parallel prefill prompt builder for Infinite Jazz.

Each instrument gets its own LLM call with assistant turn prefill.
The model doesn't compose a quartet — it inhabits one player.
"""

from dataclasses import dataclass

from config import RuntimeConfig


INSTRUMENT_PROFILES = {
    'BASS': {
        'identity': 'You are the bass player in a jazz quartet.',
        'range': 'E1 to G2',
        'character': (
            'You anchor the harmony. Walk lines, lock with the drums, outline the changes. '
            'Not every beat needs a note — space is part of the groove. '
            'Roots, fifths, chromatic approaches. Let the rhythm breathe.'
        ),
        'format_notes': '',
    },
    'DRUMS': {
        'identity': 'You are the drummer in a jazz quartet.',
        'range': 'C2=kick, D2=snare, F#2=closed-hat, Bb2=open-hat, Eb3=ride',
        'character': (
            'You keep time and shape the feel. The ride cymbal is your voice — '
            'kick and snare are punctuation, not a beat machine. '
            'Swing. Use dynamics. Ghost notes, accents, space. '
            'Listen to the bass — lock in, push, pull.'
        ),
        'format_notes': (
            'Use multiple notes for layering (e.g., C2:90,F#2:60 for kick + hat).\n'
            'Available drums: C2=kick, D2=snare, F#2=closed-hat, Bb2=open-hat, Eb3=ride'
        ),
    },
    'PIANO': {
        'identity': 'You are the piano player in a jazz quartet.',
        'range': 'C3 to C5',
        'character': (
            'You comp for the soloist. Leave space — you do not need to fill every beat. '
            'Rhythmic variety in your voicings. Drop notes from chords. '
            'Stabs, shells, the occasional run. React to what the sax is doing.'
        ),
        'format_notes': (
            'Use chords: NOTE:VEL,NOTE:VEL,NOTE:VEL (e.g., C3:65,E3:60,G3:62).\n'
            'Shell voicings (2-3 notes) are more idiomatic than full chords.'
        ),
    },
    'SAX': {
        'identity': 'You are the saxophone player in a jazz quartet.',
        'range': 'A3 to F5',
        'character': (
            'You carry the melody and improvise. Breathe — real phrases have shape. '
            'Use motifs and develop them. Silence is as important as notes. '
            'React to the rhythm section. Surprise yourself.'
        ),
        'format_notes': '',
    },
}


@dataclass
class ParallelPromptBuilder:
    """Build per-instrument prompts for parallel prefill generation."""

    config: RuntimeConfig

    def build_instrument_system_prompt(self, instrument: str) -> str:
        """System prompt for a single instrument's LLM call."""
        profile = INSTRUMENT_PROFILES[instrument]
        steps = self.config.total_steps
        tempo = self.config.tempo
        bars = self.config.bars_per_generation

        lines = [
            profile['identity'],
            '',
            profile['character'],
            '',
            f'You are improvising {bars} bars at {tempo} BPM on a 16th-note grid.',
            '',
            'OUTPUT FORMAT:',
            f'Write exactly {steps} numbered lines, one per 16th-note step.',
            'Each line: NUMBER NOTE:VELOCITY (e.g., "1 C2:80"), NUMBER . (rest), or NUMBER ^ (tie).',
            f'Range: {profile["range"]}. Velocity: 0-127 (60-90 typical).',
            '',
            'CONTINUITY:',
            'You may see your own recent playing (numbered lines) before the new section.',
            f'Continue numbering from where you left off and write exactly {steps} new lines.',
            'Build on what you were playing — develop your ideas, not repeat them.',
            '',
            'HARMONY:',
            'The user prompt may include chord changes mapped to step ranges.',
            'Example: "Steps 1-4: Cm7 (C,Eb,G,Bb)" means steps 1-4 are over C minor 7.',
            'Target these chord tones — roots, thirds, fifths, sevenths, chromatic approaches.',
        ]

        if profile['format_notes']:
            lines.extend(['', profile['format_notes']])

        lines.extend([
            '',
            'Output ONLY the numbered lines. No explanations, no headers.',
        ])

        return '\n'.join(lines)

    def build_context_prompt(self, previous_context: str = '', extra_prompt: str = '',
                             chord_context: str = '') -> str:
        """User prompt shared across all 4 instrument calls."""
        lines = []

        if previous_context:
            lines.extend([
                'Here is what the quartet just played:',
                '',
                previous_context,
                '',
                'Continue from here. React to what you heard — continue it, contrast it, or take it somewhere new.',
            ])
        else:
            lines.append('This is the first section. Set the tone.')

        if chord_context:
            lines.extend(['', 'CHANGES FOR THIS SECTION:', chord_context])

        if extra_prompt:
            lines.extend(['', 'Direction:', extra_prompt])

        lines.extend(['', 'Play your part now.'])

        return '\n'.join(lines)

    def build_quartet_prompt(self, previous_context: str = '', extra_prompt: str = '') -> str:
        """Not used in parallel path. Raises if called."""
        raise NotImplementedError(
            'ParallelPromptBuilder generates per-instrument prompts, not quartet prompts. '
            'Use build_instrument_system_prompt() and build_context_prompt() instead.'
        )


MINIMAL_RANGES = {
    'BASS': 'E1-G2',
    'DRUMS': 'C2=kick D2=snare F#2=hat Bb2=open-hat Eb3=ride',
    'PIANO': 'C3-C5, chords: NOTE:VEL,NOTE:VEL',
    'SAX': 'A3-F5',
}


@dataclass
class MinimalParallelPromptBuilder:
    """Stripped-down parallel prompt. Format only, no character guidance."""

    config: RuntimeConfig

    def build_instrument_system_prompt(self, instrument: str) -> str:
        steps = self.config.total_steps
        return (
            f'{instrument}. Jazz quartet. {steps} numbered lines, 16th-note grid.\n'
            f'One step per line. Range: {MINIMAL_RANGES[instrument]}. Velocity 0-127.\n'
            f'Example:\n'
            f'1 C3:75\n'
            f'2 .\n'
            f'3 E3:70\n'
            f'4 ^'
        )

    def build_context_prompt(self, previous_context: str = '', extra_prompt: str = '',
                             chord_context: str = '') -> str:
        parts = []
        if previous_context:
            parts.append(previous_context)
        if chord_context:
            parts.append(chord_context)
        if extra_prompt:
            parts.append(extra_prompt)
        parts.append('Go.')
        return '\n\n'.join(parts)

    def build_quartet_prompt(self, previous_context: str = '', extra_prompt: str = '') -> str:
        raise NotImplementedError
