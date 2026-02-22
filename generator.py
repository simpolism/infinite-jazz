"""Generation pipeline for real-time jazz quartet."""

from typing import Dict, Optional, Callable
import re
import time

from llm_interface import LLMInterface
from prompts import PromptBuilder
from tracker_parser import parse_tracker, parse_interleaved, InstrumentTrack, TrackerStep, TrackerParser
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
        extra_prompt: str = "",
        prompt_builder_factory: Callable[[RuntimeConfig], PromptBuilder] = PromptBuilder,
        seed: Optional[int] = None,
        max_retries: int = 3,
        tracker_format: str = "block",
    ):
        """
        Initialize generation pipeline

        Args:
            llm: LLMInterface instance
            runtime_config: Immutable runtime configuration.
            verbose: Print generation details
            context_steps: Number of tracker steps per instrument to feed as context.
            tracker_format: "block" (instruments sequentially) or "interleaved" (beat-by-beat)
        """
        self.llm = llm
        self.history = []  # Track previous sections for continuity
        self.verbose = verbose
        self.config = runtime_config
        self.prompt_builder = prompt_builder_factory(runtime_config)
        self.extra_prompt = extra_prompt.strip()
        self.context_steps = max(0, context_steps)
        steps_per_section = self.config.total_steps or 1
        self.history_limit = max(3, (self.context_steps // steps_per_section) + 2)
        self.max_retries = max(1, max_retries)
        self.seed = seed
        self.tracker_format = tracker_format

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

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                if self.tracker_format == "parallel":
                    tracks, raw_text = self._generate_parallel(previous_context)
                elif self.tracker_format == "interleaved":
                    tracks, raw_text = self._generate_interleaved(previous_context)
                else:
                    generated_text = self._generate_batched(previous_context)
                    full_tracker = self._assemble_tracker(generated_text)
                    tracks = parse_tracker(full_tracker)
                    raw_text = generated_text

                expected_steps = self.config.total_steps
                invalid_instruments = []
                for instrument in self.GENERATION_ORDER:
                    track = tracks.get(instrument)
                    if not track or len(track.steps) != expected_steps:
                        invalid_instruments.append(instrument)

                if invalid_instruments:
                    raise ValueError(
                        f"Incomplete tracker data for: {', '.join(invalid_instruments)}"
                        f" (got {', '.join(f'{i}={len(tracks[i].steps) if i in tracks else 0}' for i in invalid_instruments)},"
                        f" expected {expected_steps} each)"
                    )

                # Update history
                self.history.append(raw_text)
                if len(self.history) > self.history_limit:
                    self.history.pop(0)

                return tracks
            except Exception as exc:
                last_error = exc
                print(f"Generation attempt {attempt} failed: {exc}")
                time.sleep(0.5)

        raise RuntimeError(f"Failed to generate a valid section after {self.max_retries} attempts") from last_error

    def _generate_interleaved(self, previous_context: str = ""):
        """
        Generate all instruments in interleaved (beat-by-beat) format.

        Returns:
            Tuple of (parsed tracks dict, raw output text for history)
        """
        if self.verbose:
            print("[INTERLEAVED GENERATION]")

        prompt = self.prompt_builder.build_quartet_prompt(previous_context, self.extra_prompt)

        gen_config = {
            'max_tokens': 4096,
            'temperature': 1.05,
            'top_p': 0.99,
            'repeat_penalty': 1.0,
        }
        if self.seed is not None:
            gen_config['seed'] = self.seed

        result = self.llm.generate(prompt, **gen_config)
        raw_output = result.text

        if self.verbose:
            print(
                f"\nLLM stats: backend={result.backend}, tokens={result.tokens}, "
                f"latency={result.latency:.2f}s, finish_reason={result.finish_reason}"
            )
            print(f"\nRaw output length: {len(raw_output)} chars")

        tracks = parse_interleaved(raw_output)
        return tracks, raw_output

    def _generate_parallel(self, previous_context: str = ""):
        """
        Generate all instruments via 4 parallel API calls with assistant prefill.

        Each instrument gets its own call where the model inhabits that player.
        Returns:
            Tuple of (parsed tracks dict, raw text dict for history)
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        if self.verbose:
            print("[PARALLEL GENERATION]")

        steps = self.config.total_steps

        context_prompt = self.prompt_builder.build_context_prompt(
            previous_context, self.extra_prompt
        )

        # Build per-instrument prefill from own history (numbered lines)
        instrument_prefills = {}
        instrument_history_counts = {}
        for instrument in self.GENERATION_ORDER:
            own_lines = []
            for section in self.history:
                if isinstance(section, dict) and instrument in section and section[instrument]:
                    own_lines.extend(section[instrument].split('\n'))
            if own_lines:
                own_lines = own_lines[-self.context_steps:]
                numbered = [f"{i} {line}" for i, line in enumerate(own_lines, 1)]
                instrument_prefills[instrument] = (
                    f"{instrument}\n" + '\n'.join(numbered) + '\n'
                )
                instrument_history_counts[instrument] = len(own_lines)
            else:
                instrument_prefills[instrument] = f"{instrument}\n"
                instrument_history_counts[instrument] = 0

        def generate_instrument(instrument: str):
            system_prompt = self.prompt_builder.build_instrument_system_prompt(instrument)
            prefill = instrument_prefills[instrument]
            history_count = instrument_history_counts[instrument]

            # Stop after generating total_steps new lines
            # Model continues numbering from history, so stop at history + steps + 1
            stop_line = history_count + steps + 1
            inst_stop_seqs = [f"\n{stop_line} ", f"\n{stop_line}."]

            # Scale token budget: ~10 tokens per line, with headroom
            max_toks = max(1024, (history_count + steps) * 12)

            gen_config = {
                'max_tokens': max_toks,
                'temperature': 1.05,
                'top_p': 0.99,
                'repeat_penalty': 1.0,
                'system_message': system_prompt,
                'assistant_prefill': prefill,
                'stop': inst_stop_seqs,
            }
            if self.seed is not None:
                gen_config['seed'] = self.seed

            result = self.llm.generate(context_prompt, **gen_config)

            if self.verbose:
                print(
                    f"  [{instrument}] {result.tokens} tokens, "
                    f"{result.latency:.2f}s, finish={result.finish_reason}"
                )

            return instrument, result.text

        tracks = {}
        raw_texts = {}

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(generate_instrument, inst): inst
                for inst in self.GENERATION_ORDER
            }

            for future in as_completed(futures):
                instrument = futures[future]
                try:
                    inst, raw_text = future.result()
                    cleaned = self._clean_output(raw_text, inst)
                    # Take only the last total_steps lines — strips echoed prefill
                    # regardless of whether the provider echoes it or not
                    cleaned_lines = [l for l in cleaned.split('\n') if l.strip()]
                    if len(cleaned_lines) > steps:
                        cleaned = '\n'.join(cleaned_lines[-steps:])
                    validated = self._validate_output(cleaned, inst)
                    raw_texts[inst] = validated

                    lines = validated.split('\n')
                    track = TrackerParser.parse_track(inst, lines)
                    tracks[inst] = track
                except Exception as exc:
                    print(f"  {instrument} generation failed: {exc}")

        # Fill missing instruments with rests
        for instrument in self.GENERATION_ORDER:
            if instrument not in tracks:
                print(f"  Filling {instrument} with rests")
                rest_steps = [
                    TrackerStep(notes=[], is_rest=True, is_tie=False)
                    for _ in range(steps)
                ]
                tracks[instrument] = InstrumentTrack(
                    instrument=instrument, steps=rest_steps
                )
                raw_texts[instrument] = '\n'.join(['.'] * steps)

        return tracks, raw_texts

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

        # Build batched prompt with extra_prompt integrated
        prompt = self.prompt_builder.build_quartet_prompt(previous_context, self.extra_prompt)

        # Generate with higher token limit (need to fit all 4 instruments)
        # Reasoning models need MUCH more tokens (they use tokens for internal reasoning)
        gen_config = {
            'max_tokens': 4096,  # Leave headroom for longer sections and richer phrasing
            'temperature': 1.05,
            'top_p': 0.99,
            'repeat_penalty': 1.0,
        }
        if self.seed is not None:
            gen_config['seed'] = self.seed

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

        if self.tracker_format == "interleaved":
            # For interleaved, history entries are raw text strings
            # Just return the tail of the most recent section
            recent = self.history[-1]
            if isinstance(recent, str):
                lines = recent.strip().split('\n')
                # Keep roughly the last N beats (4 lines per beat)
                beats_to_keep = max(1, self.context_steps // 4)
                lines_to_keep = beats_to_keep * 5  # 4 instrument lines + 1 beat marker per beat
                if len(lines) > lines_to_keep:
                    return "...\n" + '\n'.join(lines[-lines_to_keep:])
                return '\n'.join(lines)

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
        extra_prompt: str = "",
        seed: Optional[int] = None,
        prompt_builder_factory: Callable[[RuntimeConfig], PromptBuilder] = PromptBuilder,
        tracker_format: str = "block",
    ):
        """
        Initialize continuous generator

        Args:
            llm: LLMInterface instance
            runtime_config: Immutable runtime configuration.
            buffer_size: Number of sections to buffer ahead
            verbose: Print generation details
            tracker_format: "block" or "interleaved"
        """
        import threading

        self.config = runtime_config
        self.pipeline = GenerationPipeline(
            llm,
            runtime_config,
            verbose=verbose,
            context_steps=context_steps,
            extra_prompt=extra_prompt,
            seed=seed,
            prompt_builder_factory=prompt_builder_factory,
            tracker_format=tracker_format,
        )
        self.buffer_size = buffer_size
        self.buffer = []
        self.generation_lock = threading.Lock()
        self.generation_thread = None
        self.last_generation_error = None
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
            if self.last_generation_error:
                raise RuntimeError("Background generation failed") from self.last_generation_error

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
            try:
                new_section = self.pipeline.generate_section(context)
                with self.generation_lock:
                    self.buffer.append(new_section)
                self.last_generation_error = None
            except Exception as exc:
                self.last_generation_error = exc
                if self.verbose:
                    print(f"Background generation error: {exc}")

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


def save_generated_section(
    tracks: Dict[str, InstrumentTrack],
    filepath: str,
    metadata: Optional[Dict[str, str]] = None
):
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

    header_lines = []
    if metadata:
        for key, value in metadata.items():
            header_lines.append(f"# {key}: {value}")

    parts = []
    if header_lines:
        parts.append('\n'.join(header_lines))
    parts.append('\n\n'.join(sections))
    output = '\n\n'.join(parts)

    with open(filepath, 'w') as f:
        f.write(output)

    print(f"Saved to {filepath}")
