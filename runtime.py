"""Runtime components for Infinite Jazz real-time generation."""

from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import time

from llm_interface import LLMInterface
from generator import ContinuousGenerator, save_generated_section, concatenate_sections
from prompts import PromptBuilder
from midi_converter import MIDIConverter
from config import RuntimeConfig
from tracker_parser import InstrumentTrack
from audio_output import RealtimePlayer


class RealtimeJazzGenerator:
    """
    Coordinate LLM generation, MIDI conversion, and playback for the live loop.
    """

    def __init__(
        self,
        llm: LLMInterface,
        audio_backend,
        runtime_config: RuntimeConfig,
        save_output: bool = False,
        output_dir: str = "output",
        verbose: bool = False,
        context_steps: int = 32,
        extra_prompt: str = "",
        prompt_style: str = "default",
        seed: Optional[int] = None,
        prompt_builder_factory=None,
        tracker_format: str = "block",
        chart=None,
    ):
        self.llm = llm
        self.audio_backend = audio_backend
        self.config = runtime_config
        self.save_output = save_output
        self.output_dir = Path(output_dir)
        self.verbose = verbose
        self.player = RealtimePlayer(audio_backend)
        self.context_steps = context_steps
        self.extra_prompt = extra_prompt
        self.prompt_style = prompt_style
        self.seed = seed
        self.tracker_format = tracker_format

        self.run_timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        if self.save_output:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            print(f"Saving outputs to {self.output_dir}")

        prompt_builder_factory = prompt_builder_factory or PromptBuilder

        self.generator = ContinuousGenerator(
            llm,
            runtime_config,
            verbose=verbose,
            context_steps=context_steps,
            extra_prompt=extra_prompt,
            seed=seed,
            prompt_builder_factory=prompt_builder_factory,
            tracker_format=tracker_format,
            chart=chart,
        )
        self.prefill_delay = 0.5
        self.midi_converter = MIDIConverter(runtime_config)

        self.is_running = False
        self.all_sections = []
        self.section_count = 0

    def _schedule_section(
        self,
        tracks: Dict[str, InstrumentTrack],
        start_time: float
    ) -> Tuple[float, int]:
        messages = self.midi_converter.create_realtime_messages(tracks)
        scheduled: List[Tuple[float, object]] = [
            (start_time + relative_time, message)
            for relative_time, message in messages
        ]
        if scheduled:
            self.player.schedule_messages(scheduled)
            if not self.player.is_playing:
                self.player.play()

        num_steps = len(next(iter(tracks.values())).steps) if tracks else 0
        actual_duration = self._calculate_section_duration_from_steps(num_steps)
        return actual_duration, len(messages)

    def _calculate_section_duration_from_steps(self, num_steps: int) -> float:
        beats_per_second = self.config.tempo / 60.0
        steps_per_beat = 4
        time_per_step = 1.0 / (beats_per_second * steps_per_beat)
        return num_steps * time_per_step

    def run(self, num_sections: Optional[int] = None):
        print(f"\n{'='*60}")
        print("Infinite Jazz - Real-time Quartet Generator")
        print(f"{'='*60}")
        print(f"Tempo: {self.config.tempo} BPM")
        print("Resolution: 16th notes")
        print(f"Bars per section: {self.config.bars_per_generation}")
        print(f"{'='*60}\n")

        if num_sections is not None and num_sections <= 0:
            print("No sections requested; exiting.")
            return

        try:
            print("Pre-generating initial sections...\n")
            buffer_size = self.generator.buffer_size
            initial_prefill = buffer_size if num_sections is None else min(buffer_size, num_sections)
            self.generator.prefill_buffer(count=initial_prefill)
            if self.prefill_delay > 0:
                time.sleep(self.prefill_delay)

            print(f"\n{'='*60}")
            print("Starting playback... (Press Ctrl+C to stop)")
            print(f"{'='*60}\n")

            self.is_running = True
            section_num = 0
            queued_time = 0.0
            playback_start_time = None

            time.sleep(0.5)
            playback_start_time = time.time()

            while self.is_running:
                if num_sections is not None and section_num >= num_sections:
                    break

                wall_clock_elapsed = time.time() - playback_start_time
                ahead_by = queued_time - wall_clock_elapsed
                max_ahead = self.generator.buffer_size * self._calculate_section_duration_from_steps(
                    self.config.total_steps
                )

                if ahead_by >= max_ahead:
                    if self.verbose:
                        print(f"Queued {ahead_by:.1f}s ahead (max {max_ahead:.1f}s), waiting...")
                    time.sleep(0.5)
                    continue

                while len(self.generator.buffer) == 0:
                    if self.verbose:
                        print("Buffer empty, waiting for generation...")
                    time.sleep(0.1)

                print(f"\n--- Section {section_num + 1} ---")
                should_continue = num_sections is None or (section_num + 1) < num_sections
                tracks = self.generator.get_next_section(continue_buffering=should_continue)
                self.all_sections.append(tracks)

                print(f"Queueing section {section_num + 1} for playback...")
                actual_duration, msg_count = self._schedule_section(tracks, queued_time)
                if self.verbose:
                    print(f"  Added {msg_count} MIDI messages (duration {actual_duration:.2f}s)")
                else:
                    print(f"  Section duration {actual_duration:.2f}s")

                queued_time += actual_duration
                section_num += 1

            print("\nFinishing playback...")
            self.player.wait_until_done()
            self.player.stop()
        except KeyboardInterrupt:
            print("\n\nStopping...")
        finally:
            self.cleanup()

    def cleanup(self):
        self.is_running = False

        self.player.stop()

        if self.save_output and self.all_sections:
            print(f"\nSaving complete MIDI file ({len(self.all_sections)} sections)...")
            combined_tracks = concatenate_sections(self.all_sections)

            # Create a separate converter for MIDI file export (no drum translation or transposition for GM compatibility)
            file_converter = MIDIConverter(self.midi_converter.config, translate_drums=False, transpose_octaves=0)
            midi_file = file_converter.create_midi_file(combined_tracks)

            midi_file_path = self.output_dir / f"complete_{self.run_timestamp}.mid"
            midi_file.save(str(midi_file_path))
            print(f"✓ Saved complete MIDI: {midi_file_path}")

            txt_file_path = self.output_dir / f"complete_{self.run_timestamp}.txt"
            save_generated_section(
                combined_tracks,
                str(txt_file_path),
                metadata=self._build_metadata()
            )

        self.player.close()
        print("Done!")

    def _build_metadata(self) -> Dict[str, str]:
        meta = {
            "tempo": str(self.config.tempo),
            "note_mode": self.config.note_mode,
            "swing_enabled": str(self.config.swing_enabled),
            "swing_ratio": str(self.config.swing_ratio),
            "bars_per_generation": str(self.config.bars_per_generation),
            "time_signature": f"{self.config.time_signature[0]}/{self.config.time_signature[1]}",
            "context_steps": str(self.context_steps),
        }
        if self.extra_prompt:
            meta["prompt"] = self.extra_prompt
        if self.prompt_style:
            meta["prompt_style"] = self.prompt_style
        return meta
