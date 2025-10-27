"""Generation pipeline for real-time jazz quartet."""

from typing import Dict, Optional
import re

from llm_interface import LLMInterface
from prompts import PromptBuilder
from tracker_parser import parse_tracker, InstrumentTrack
from config import RuntimeConfig


class GenerationPipeline:
    """Generation pipeline for jazz quartet (batched-only generation)"""

    GENERATION_ORDER = ['BASS', 'DRUMS', 'PIANO', 'SAX']

    def __init__(
        self,
        llm: LLMInterface,
        runtime_config: RuntimeConfig,
        verbose: bool = False,
        context_steps: int = 32,
        extra_prompt: str = ""
    ):
        """
        Initialize generation pipeline

        Args:
            llm: LLMInterface instance
            runtime_config: Immutable runtime configuration.
            verbose: Print generation details
            context_steps: Number of tracker steps per instrument to feed as context.
        """
        self.llm = llm
        self.history = []  # Track previous sections for continuity
        self.verbose = verbose
        self.config = runtime_config
        self.prompt_builder = PromptBuilder(runtime_config)
        self.extra_prompt = extra_prompt.strip()
        self.context_steps = max(0, context_steps)
        steps_per_section = self.config.total_steps or 1
        self.history_limit = max(3, (self.context_steps // steps_per_section) + 2)

    def generate_section(self, previous_context: str = "") -> Dict[str, InstrumentTrack]:
        """
        Generate one complete section (2 bars, all 4 instruments)

        Args:
            previous_context: Previous section for musical continuity

        Returns:
            Dict mapping instrument name to InstrumentTrack
        """
        if self.verbose:
            print(f"\n{'='*60}")
            print("Generating new section (batched)...")
            if previous_context:
                print("(Building on previous section)")
            print(f"{'='*60}\n")

        generated_text = self._generate_batched(previous_context)

        # Parse all parts together
        full_tracker = self._assemble_tracker(generated_text)
        tracks = parse_tracker(full_tracker)

        # Update history
        self.history.append(generated_text)
        if len(self.history) > self.history_limit:
            self.history.pop(0)

        return tracks

    def _generate_batched(self, previous_context: str = "") -> Dict[str, str]:
        """
        Generate all instruments in a single LLM call

        Args:
            previous_context: Previous section for musical continuity

        Returns:
            Dict mapping instrument name to generated text
        """
        if self.verbose:
            print("[BATCHED GENERATION]")

        # Build batched prompt
        prompt = self.prompt_builder.build_quartet_prompt(previous_context)
        if self.extra_prompt:
            prompt += "\n\nPLAYER DIRECTION: " + self.extra_prompt

        # Generate with higher token limit (need to fit all 4 instruments)
        # Reasoning models need MUCH more tokens (they use tokens for internal reasoning)
        gen_config = {
            'max_tokens': 3200,  # Leave headroom for richer phrasing
            'temperature': 1.05,
            'top_p': 0.99,
            'repeat_penalty': 1.0,
        }

        result = self.llm.generate(prompt, **gen_config)
        raw_output = result.text

        if self.verbose:
            print(
                f"\nLLM stats: backend={result.backend}, tokens={result.tokens}, "
                f"latency={result.latency:.2f}s, finish_reason={result.finish_reason}"
            )

        if self.verbose:
            print(f"\nRaw output length: {len(raw_output)} chars")

        # Parse out each instrument section
        generated_text = self._parse_batched_output(raw_output)

        return generated_text

    def _parse_batched_output(self, raw_output: str) -> Dict[str, str]:
        """
        Parse batched generation output to extract each instrument's section

        Args:
            raw_output: Raw LLM output containing all instruments

        Returns:
            Dict mapping instrument name to generated text
        """
        generated_text = {}

        # Remove markdown formatting
        cleaned = re.sub(r'\*\*([A-Z]+)\*\*', r'\1', raw_output)
        cleaned = re.sub(r'```[\w]*\n?', '', cleaned)

        # Split by instrument headers
        for i, instrument in enumerate(self.GENERATION_ORDER):
            # Find this instrument's section
            pattern = rf'^{instrument}\s*$'
            matches = list(re.finditer(pattern, cleaned, re.MULTILINE))

            if not matches:
                if self.verbose:
                    print(f"  Warning: Could not find {instrument} section in output")
                generated_text[instrument] = '.' * self.config.total_steps
                continue

            # Get content between this instrument and the next
            start = matches[0].end()

            # Find where this section ends (next instrument header or end of text)
            if i < len(self.GENERATION_ORDER) - 1:
                next_instrument = self.GENERATION_ORDER[i + 1]
                next_pattern = rf'^{next_instrument}\s*$'
                next_matches = list(re.finditer(next_pattern, cleaned, re.MULTILINE))
                end = next_matches[0].start() if next_matches else len(cleaned)
            else:
                end = len(cleaned)

            # Extract and clean the section
            section = cleaned[start:end].strip()
            cleaned_section = self._clean_output(section, instrument)
            validated_section = self._validate_output(cleaned_section, instrument)

            generated_text[instrument] = validated_section

            if self.verbose:
                print(f"\n[{instrument}]")
                print(validated_section[:200] + "..." if len(validated_section) > 200 else validated_section)

        return generated_text

    def _clean_output(self, text: str, instrument: str) -> str:
        """
        Clean up LLM output
        - Remove section headers if present
        - Strip extra whitespace
        - Remove markdown code blocks
        - Remove line numbers
        - Normalize unicode musical symbols
        """
        # Remove markdown code blocks
        text = re.sub(r'```[\w]*\n?', '', text)

        # Remove section headers (BASS, DRUMS, etc.)
        text = re.sub(r'^(BASS|DRUMS|PIANO|SAX)\s*\n?', '', text, flags=re.MULTILINE)

        # Remove line numbers (format: "1 C2:80" or "1. C2:80" -> "C2:80")
        # Handle both "1 " and "1. " formats (LLMs often add periods)
        text = re.sub(r'^\d+\.?\s+', '', text, flags=re.MULTILINE)

        # Normalize unicode musical symbols to ASCII equivalents
        # ♯ (U+266F) -> #
        # ♭ (U+266D) -> b
        text = text.replace('♯', '#').replace('♭', 'b')

        # Remove leading/trailing whitespace
        text = text.strip()

        # Ensure consistent line breaks
        text = re.sub(r'\n\s*\n', '\n', text)

        return text

    def _validate_output(self, text: str, instrument: str) -> str:
        """
        Validate and fix common issues in generated output

        Args:
            text: Cleaned output text
            instrument: Instrument name

        Returns:
            Validated and possibly corrected output
        """
        lines = text.split('\n')
        expected_steps = self.config.total_steps

        # Check line count
        if len(lines) < expected_steps:
            print(f"  Warning: Expected {expected_steps} lines, got {len(lines)}. Padding with rests.")
            while len(lines) < expected_steps:
                lines.append('.')
        elif len(lines) > expected_steps:
            print(f"  Warning: Expected {expected_steps} lines, got {len(lines)}. Truncating.")
            lines = lines[:expected_steps]

        # Validate each line format
        validated_lines = []
        for i, line in enumerate(lines):
            line = line.strip()

            # Empty or rest or tie
            if not line or line == '.' or line == '^':
                validated_lines.append(line)
                continue

            # Strip trailing comments/explanations (LLMs love to explain themselves)
            # Remove anything after: parentheses, #, //, --, etc.
            line = re.split(r'\s+[(\[#]|//|--', line)[0].strip()

            # Validate note format
            try:
                # Check if it matches NOTE:VELOCITY format
                if self._is_valid_line(line):
                    validated_lines.append(line)
                else:
                    print(f"  Warning: Invalid format at line {i+1}: '{line}'. Replacing with rest.")
                    validated_lines.append('.')
            except Exception as e:
                print(f"  Warning: Error validating line {i+1}: {e}. Replacing with rest.")
                validated_lines.append('.')

        return '\n'.join(validated_lines)

    def _is_valid_line(self, line: str) -> bool:
        """Check if line matches valid tracker format"""
        if line == '.' or line == '^':
            return True

        # Clean up common LLM mistakes before validation
        line_clean = line.strip().rstrip('.,;')

        # Check for note:velocity or chord format
        # Allow trailing junk in velocity that will be cleaned by parser
        pattern = r'^[A-G][#b]?-?\d+:\d+[^,]*(?:,[A-G][#b]?-?\d+:\d+[^,]*)*$'
        return bool(re.match(pattern, line_clean))

    def _assemble_tracker(self, generated_text: Dict[str, str]) -> str:
        """
        Assemble full tracker format from generated parts

        Args:
            generated_text: Dict mapping instrument to generated text

        Returns:
            Complete tracker format string
        """
        sections = []
        for instrument in self.GENERATION_ORDER:
            if instrument in generated_text:
                sections.append(f"{instrument}\n{generated_text[instrument]}")

        return '\n\n'.join(sections)

    def get_previous_context(self) -> str:
        """Get previous section for continuity (truncated to last few notes)"""
        if not self.history or self.context_steps <= 0:
            return ""
        aggregated = {instrument: [] for instrument in self.GENERATION_ORDER}

        for section in self.history:
            for instrument in self.GENERATION_ORDER:
                if instrument in section and section[instrument]:
                    aggregated[instrument].extend(section[instrument].split('\n'))

        steps_to_keep = self.context_steps
        sections = []
        for instrument in self.GENERATION_ORDER:
            lines = aggregated[instrument][-steps_to_keep:]
            if lines:
                ellipsis = "..." if len(aggregated[instrument]) > steps_to_keep else ""
                sections.append(f"{instrument} (recent):\n{ellipsis}" + '\n'.join(lines))

        return '\n\n'.join(sections)


class ContinuousGenerator:
    """
    Continuous generation with buffering for real-time playback
    Generates ahead while current section plays
    """

    def __init__(
        self,
        llm: LLMInterface,
        runtime_config: RuntimeConfig,
        buffer_size: int = 4,
        verbose: bool = False,
        context_steps: int = 32,
        extra_prompt: str = ""
    ):
        """
        Initialize continuous generator

        Args:
            llm: LLMInterface instance
            runtime_config: Immutable runtime configuration.
            buffer_size: Number of sections to buffer ahead
            verbose: Print generation details
        """
        import threading

        self.config = runtime_config
        self.pipeline = GenerationPipeline(
            llm,
            runtime_config,
            verbose=verbose,
            context_steps=context_steps,
            extra_prompt=extra_prompt
        )
        self.buffer_size = buffer_size
        self.buffer = []
        self.generation_lock = threading.Lock()
        self.generation_thread = None
        self.verbose = verbose

    def prefill_buffer(self, count: Optional[int] = None):
        """Generate initial buffer of sections"""
        target = self.buffer_size if count is None else max(0, min(count, self.buffer_size))
        if target <= 0:
            return 0

        if self.verbose:
            print(f"Pre-filling buffer with {target} sections...\n")

        for i in range(target):
            context = self.pipeline.get_previous_context()
            section = self.pipeline.generate_section(context)
            self.buffer.append(section)
            if self.verbose:
                print(f"\nBuffered section {i+1}/{target}")

        return target

    def get_next_section(self, continue_buffering: bool = True) -> Dict[str, InstrumentTrack]:
        """
        Get next section from buffer and start generating a new one asynchronously

        Returns:
            Dict mapping instrument to InstrumentTrack
        """
        if not self.buffer:
            # Buffer empty, generate immediately (not ideal)
            print("Warning: Buffer empty! Generating immediately...")
            context = self.pipeline.get_previous_context()
            return self.pipeline.generate_section(context)

        # Pop from buffer
        with self.generation_lock:
            section = self.buffer.pop(0)

        # Start generating new section in background when more sections are needed
        if continue_buffering:
            self._start_background_generation()

        return section

    def _start_background_generation(self):
        """Start generating a new section in the background"""
        import threading

        # Only start if no generation is already happening
        if self.generation_thread is not None and self.generation_thread.is_alive():
            return

        def generate():
            context = self.pipeline.get_previous_context()
            new_section = self.pipeline.generate_section(context)
            with self.generation_lock:
                self.buffer.append(new_section)

        self.generation_thread = threading.Thread(target=generate)
        self.generation_thread.daemon = True
        self.generation_thread.start()

    def has_buffered_sections(self) -> bool:
        """Check if buffer has sections"""
        return len(self.buffer) > 0


def concatenate_sections(sections_list: list) -> Dict[str, InstrumentTrack]:
    """
    Concatenate multiple sections into one long track set

    Args:
        sections_list: List of track dicts (each from generate_section)

    Returns:
        Single track dict with all sections concatenated
    """
    if not sections_list:
        return {}

    # Start with empty tracks for each instrument
    combined = {}

    for instrument in GenerationPipeline.GENERATION_ORDER:
        all_steps = []

        # Concatenate steps from each section
        for section in sections_list:
            if instrument in section:
                all_steps.extend(section[instrument].steps)

        # Create combined track
        if all_steps:
            combined[instrument] = InstrumentTrack(
                instrument=instrument,
                steps=all_steps
            )

    return combined


def save_generated_section(tracks: Dict[str, InstrumentTrack], filepath: str):
    """
    Save generated section to tracker file

    Args:
        tracks: Dict mapping instrument to InstrumentTrack
        filepath: Output file path
    """
    sections = []
    for instrument in GenerationPipeline.GENERATION_ORDER:
        if instrument in tracks:
            track = tracks[instrument]
            lines = []
            for step in track.steps:
                if step.is_rest:
                    lines.append('.')
                else:
                    notes = ','.join([f"{n.pitch}:{n.velocity}" for n in step.notes])
                    lines.append(notes)

            sections.append(f"{instrument}\n" + '\n'.join(lines))

    output = '\n\n'.join(sections)

    with open(filepath, 'w') as f:
        f.write(output)

    print(f"Saved to {filepath}")
