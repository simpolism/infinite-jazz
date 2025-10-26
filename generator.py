"""
Generation pipeline for real-time jazz quartet
Orchestrates sequential LLM generation: bass → drums → piano → sax
"""

from typing import Dict, Optional, Tuple
import re

from llm_interface import LLMInterface, GenerationConfig
from prompts import get_instrument_prompt, get_batched_quartet_prompt
from tracker_parser import parse_tracker, InstrumentTrack, TrackerParser
import config


class GenerationPipeline:
    """
    Generation pipeline for jazz quartet
    Supports both sequential (bass→drums→piano→sax) and batched (all at once) generation
    """

    GENERATION_ORDER = ['BASS', 'DRUMS', 'PIANO', 'SAX']

    def __init__(self, llm: LLMInterface, batched: bool = True, verbose: bool = False):
        """
        Initialize generation pipeline

        Args:
            llm: LLMInterface instance
            batched: If True, generate all instruments in one LLM call (faster, more creative)
                    If False, generate sequentially with call-and-response
            verbose: Print generation details
        """
        self.llm = llm
        self.batched = batched
        self.history = []  # Track previous sections for continuity
        self.verbose = verbose

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
            print(f"Generating new section ({'batched' if self.batched else 'sequential'})...")
            if previous_context:
                print("(Building on previous section)")
            print(f"{'='*60}\n")

        if self.batched:
            generated_text = self._generate_batched(previous_context)
        else:
            generated_text = self._generate_sequential(previous_context)

        # Parse all parts together
        full_tracker = self._assemble_tracker(generated_text)
        tracks = parse_tracker(full_tracker)

        # Update history
        self.history.append(generated_text)
        if len(self.history) > 2:
            self.history.pop(0)  # Keep only last 2 sections

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
        prompt = get_batched_quartet_prompt(previous_context)

        # Generate with higher token limit (need to fit all 4 instruments)
        gen_config = {
            'max_tokens': 1024,  # ~4x more tokens than single instrument
            'temperature': 0.8,
            'top_p': 0.92,
            'repeat_penalty': 1.1,
        }

        raw_output = self.llm.generate(prompt, **gen_config)

        if self.verbose:
            print(f"\nRaw output length: {len(raw_output)} chars")

        # Parse out each instrument section
        generated_text = self._parse_batched_output(raw_output)

        return generated_text

    def _generate_sequential(self, previous_context: str = "") -> Dict[str, str]:
        """
        Generate instruments sequentially (bass→drums→piano→sax)

        Args:
            previous_context: Previous section for musical continuity

        Returns:
            Dict mapping instrument name to generated text
        """
        # Store generated parts for call-and-response
        generated_text = {}

        # Generate each instrument in sequence
        for instrument in self.GENERATION_ORDER:
            if self.verbose:
                print(f"\n[{instrument}]")

            # Build prompt with previously generated parts
            prompt = get_instrument_prompt(
                instrument=instrument,
                bass_part=generated_text.get('BASS', ''),
                drums_part=generated_text.get('DRUMS', ''),
                piano_part=generated_text.get('PIANO', ''),
                previous_context=previous_context
            )

            validated_output = self._generate_instrument_output(
                instrument=instrument,
                prompt=prompt
            )

            # Store for next instrument
            generated_text[instrument] = validated_output
            if self.verbose:
                print(f"\nGenerated {instrument}:")
                print(validated_output[:200] + "..." if len(validated_output) > 200 else validated_output)

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
                generated_text[instrument] = '.' * config.get_total_steps()
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
        """
        # Remove markdown code blocks
        text = re.sub(r'```[\w]*\n?', '', text)

        # Remove section headers (BASS, DRUMS, etc.)
        text = re.sub(r'^(BASS|DRUMS|PIANO|SAX)\s*\n?', '', text, flags=re.MULTILINE)

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
        expected_steps = config.get_total_steps()

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

            # Empty or rest
            if not line or line == '.':
                validated_lines.append('.')
                continue

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
        if line == '.':
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
        """Get previous section for continuity"""
        if not self.history:
            return ""

        # Return the last section
        prev = self.history[-1]
        return self._assemble_tracker(prev)

    def _generate_instrument_output(self, instrument: str, prompt: str) -> str:
        """Generate output for a single instrument with retry strategy"""
        attempts = 3
        base_prompt = prompt

        for attempt in range(1, attempts + 1):
            gen_config = GenerationConfig.get_config(instrument)

            attempt_prompt = base_prompt
            if attempt > 1:
                attempt_prompt += (
                    "\n\nIMPORTANT: Respond with exactly "
                    f"{config.get_total_steps()} lines.\n"
                    "Each line must be either NOTE:VELOCITY (e.g., C2:80) "
                    "or a single period '.' for a rest.\n"
                    "Do not include explanations or leave the response blank."
                )
                if attempt == attempts:
                    gen_config['temperature'] = min(gen_config['temperature'] + 0.1, 1.1)
                    gen_config['repeat_penalty'] = max(gen_config['repeat_penalty'] - 0.05, 1.0)

            raw_output = self.llm.generate(attempt_prompt, **gen_config)
            cleaned_output = self._clean_output(raw_output, instrument)

            if not cleaned_output.strip():
                print(f"  Warning: {instrument} generation attempt {attempt} returned blank output.")
                continue

            validated_output = self._validate_output(cleaned_output, instrument)

            if self._has_meaningful_content(validated_output):
                return validated_output

            print(f"  Warning: {instrument} generation attempt {attempt} produced only rests. Retrying...")

        print(f"  Warning: {instrument} generation failed after {attempts} attempts. Using rests.")
        rest_line = '.'
        return '\n'.join([rest_line] * config.get_total_steps())

    @staticmethod
    def _has_meaningful_content(output: str) -> bool:
        """Check if validated output contains any notes (not just rests)"""
        for line in output.split('\n'):
            stripped = line.strip()
            if stripped and stripped != '.':
                return True
        return False


class ContinuousGenerator:
    """
    Continuous generation with buffering for real-time playback
    Generates ahead while current section plays
    """

    def __init__(self, llm: LLMInterface, buffer_size: int = 2, batched: bool = True, verbose: bool = False):
        """
        Initialize continuous generator

        Args:
            llm: LLMInterface instance
            buffer_size: Number of sections to buffer ahead
            batched: If True, generate all instruments in one LLM call (faster)
            verbose: Print generation details
        """
        import threading

        self.pipeline = GenerationPipeline(llm, batched=batched, verbose=verbose)
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
