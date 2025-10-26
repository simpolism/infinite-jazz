#!/usr/bin/env python3
"""
Real-time jazz quartet generator
Generates and plays jazz continuously using local LLM
"""

import argparse
import sys
import time
import threading
from datetime import datetime
from pathlib import Path
from queue import Queue, Empty
from typing import Optional

from llm_interface import LLMInterface, list_ollama_models
from generator import ContinuousGenerator, save_generated_section, concatenate_sections
from midi_converter import MIDIConverter
from audio_output import (
    FluidSynthBackend,
    HardwareMIDIBackend,
    VirtualMIDIBackend,
    list_midi_ports
)
import config


class RealtimeJazzGenerator:
    """
    Main application for real-time jazz generation
    Coordinates LLM generation, MIDI conversion, and playback
    """

    def __init__(
        self,
        llm: LLMInterface,
        audio_backend,
        save_output: bool = False,
        output_dir: str = "output",
        batched: bool = True,
        verbose: bool = False
    ):
        """
        Initialize real-time jazz generator

        Args:
            llm: LLMInterface instance
            audio_backend: AudioBackend instance
            save_output: Save generated sections to files
            output_dir: Directory for saved output
            batched: Use batched generation (all instruments at once)
            verbose: Print generation details
        """
        self.llm = llm
        self.audio_backend = audio_backend
        self.save_output = save_output
        self.output_dir = Path(output_dir)
        self.verbose = verbose

        self.run_timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        if self.save_output:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            print(f"Saving outputs to {self.output_dir}")

        self.generator = ContinuousGenerator(llm, batched=batched, verbose=verbose)  # Uses default buffer_size
        self.midi_converter = MIDIConverter(tempo=config.TEMPO)

        self.section_count = 0
        self.is_running = False
        self.all_sections = []  # Accumulate all sections for final MIDI export

        # FIFO queue for MIDI messages
        self.midi_queue = Queue()
        self.playback_thread = None

    def _playback_worker(self):
        """
        Playback worker thread - continuously pulls MIDI messages from queue and plays them
        """
        import mido

        start_time = time.time()
        msg_count = 0

        while self.is_running:
            try:
                # Get next message from queue (blocking with timeout)
                item = self.midi_queue.get(timeout=0.1)

                # Check for sentinel (end signal)
                if item is None:
                    print(f"Playback finished ({msg_count} messages played)")
                    break

                scheduled_time, message = item

                # Wait until scheduled time
                current_time = time.time() - start_time
                wait_time = scheduled_time - current_time

                if wait_time > 0:
                    time.sleep(wait_time)

                # Send message
                self.audio_backend.send_message(message)
                msg_count += 1

            except Empty:
                # No messages in queue, continue waiting
                continue

    def _add_section_to_queue(self, tracks, start_time):
        """
        Convert section to MIDI messages and add to playback queue

        Args:
            tracks: Dict of instrument tracks
            start_time: Absolute start time for this section (in seconds)

        Returns:
            Tuple containing actual duration (seconds) and message count
        """
        # Use the faster create_realtime_messages method instead of creating a full MIDI file
        messages = self.midi_converter.create_realtime_messages(tracks)

        # Add messages to queue with adjusted timing
        for relative_time, message in messages:
            self.midi_queue.put((start_time + relative_time, message))

        # Calculate actual duration based on number of steps, not last message
        # (last message might not represent true duration if last step is a rest)
        num_steps = len(next(iter(tracks.values())).steps) if tracks else 0
        actual_duration = self._calculate_section_duration_from_steps(num_steps)

        return actual_duration, len(messages)

    def _calculate_section_duration_from_steps(self, num_steps: int) -> float:
        """Calculate duration in seconds for a given number of steps"""
        beats_per_second = config.TEMPO / 60.0
        if config.RESOLUTION == '8th':
            steps_per_beat = 2
        else:  # 16th
            steps_per_beat = 4

        time_per_step = 1.0 / (beats_per_second * steps_per_beat)
        return num_steps * time_per_step

    def run(self, num_sections: Optional[int] = None):
        """
        Run the real-time jazz generator

        Args:
            num_sections: Number of sections to generate (None = infinite)
        """
        print(f"\n{'='*60}")
        print(f"JazzAI - Real-time Jazz Quartet Generator")
        print(f"{'='*60}")
        print(f"Tempo: {config.TEMPO} BPM")
        print(f"Resolution: {config.RESOLUTION} notes")
        print(f"Bars per section: {config.BARS_PER_GENERATION}")
        print(f"{'='*60}\n")

        if num_sections is not None and num_sections <= 0:
            print("No sections requested; exiting.")
            return

        try:
            # Pre-fill buffer
            print("Pre-generating initial sections...\n")
            buffer_size = self.generator.buffer_size
            if num_sections is None:
                initial_prefill = buffer_size
            else:
                initial_prefill = min(buffer_size, num_sections)

            prefilled = self.generator.prefill_buffer(count=initial_prefill) or 0

            # Pre-load all buffered sections into queue BEFORE starting playback
            print(f"Pre-loading {prefilled} buffered sections into playback queue...")
            section_num = 0
            current_time = 0.0  # Track absolute playback time

            # Pull ONLY the initial buffered sections (don't loop forever)
            # Don't start background generation yet - wait until playback starts
            for _ in range(prefilled):
                print(f"\n--- Section {section_num + 1} ---")
                # Don't refill buffer during initial load - we already prefilled it
                tracks = self.generator.get_next_section(continue_buffering=False)

                # Track section for final export
                self.all_sections.append(tracks)

                # Add MIDI messages to queue and get actual duration
                print(f"Queueing section {section_num + 1} for playback...")
                actual_duration, msg_count = self._add_section_to_queue(tracks, current_time)
                if self.verbose:
                    print(f"  Added {msg_count} MIDI messages (duration {actual_duration:.2f}s)")
                else:
                    print(f"  Section duration {actual_duration:.2f}s")

                # Advance time for next section (use actual MIDI duration)
                current_time += actual_duration
                section_num += 1

            print(f"\n{'='*60}")
            print("Starting playback... (Press Ctrl+C to stop)")
            print(f"{'='*60}\n")

            self.is_running = True

            # Give FluidSynth a moment to be ready
            time.sleep(0.5)

            # Start playback thread
            self.playback_thread = threading.Thread(target=self._playback_worker)
            self.playback_thread.daemon = True
            self.playback_thread.start()

            # Continue generating and queueing sections while playing
            while self.is_running:
                # Check if we've reached the limit
                if num_sections is not None and section_num >= num_sections:
                    break

                # Get next section (this will block until generation is ready)
                print(f"\n--- Section {section_num + 1} ---")
                should_continue = (
                    num_sections is None or (section_num + 1) < num_sections
                )
                tracks = self.generator.get_next_section(continue_buffering=should_continue)

                # Track section for final export
                self.all_sections.append(tracks)

                # Add MIDI messages to queue and get actual duration
                print(f"Queueing section {section_num + 1} for playback...")
                actual_duration, msg_count = self._add_section_to_queue(tracks, current_time)
                if self.verbose:
                    print(f"  Added {msg_count} MIDI messages (duration {actual_duration:.2f}s)")
                else:
                    print(f"  Section duration {actual_duration:.2f}s")

                # Advance time for next section (use actual MIDI duration)
                current_time += actual_duration
                section_num += 1

            # Signal end of playback
            print("\nFinishing playback...")
            self.midi_queue.put(None)  # Sentinel

            # Wait for playback to finish
            if self.playback_thread:
                self.playback_thread.join(timeout=10.0)

        except KeyboardInterrupt:
            print("\n\nStopping...")
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        self.is_running = False

        # Stop playback thread
        if self.playback_thread and self.playback_thread.is_alive():
            self.midi_queue.put(None)  # Send sentinel
            self.playback_thread.join(timeout=2.0)

        self.audio_backend.close()

        # Save complete MIDI file if we have sections
        if self.save_output and self.all_sections:
            print(f"\nSaving complete MIDI file ({len(self.all_sections)} sections)...")

            # Concatenate all sections
            combined_tracks = concatenate_sections(self.all_sections)

            # Convert to MIDI
            midi_file = self.midi_converter.create_midi_file(combined_tracks)

            # Save with timestamped filenames
            midi_file_path = self.output_dir / f"complete_{self.run_timestamp}.mid"
            midi_file.save(str(midi_file_path))
            print(f"✓ Saved complete MIDI: {midi_file_path}")

            txt_file_path = self.output_dir / f"complete_{self.run_timestamp}.txt"
            save_generated_section(combined_tracks, str(txt_file_path))

        print("Done!")


def main():
    parser = argparse.ArgumentParser(
        description='Real-time jazz quartet generator using local LLM',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use Ollama (easiest - auto-downloads model)
  python realtime_jazz.py -m qwen2.5:3b

  # Use Groq for fast inference
  python realtime_jazz.py --llm-backend openai -m llama-3.1-70b-versatile \\
    --base-url https://api.groq.com/openai/v1 --api-key YOUR_GROQ_API_KEY

  # Use OpenAI
  python realtime_jazz.py --llm-backend openai -m gpt-3.5-turbo

  # Generate only 4 sections to test
  python realtime_jazz.py -m qwen2.5:3b -n 4

  # Use hardware MIDI output
  python realtime_jazz.py -m qwen2.5:3b --backend hardware --port "Your MIDI Port"

  # Save generated sections to files
  python realtime_jazz.py -m qwen2.5:3b --save-output
        """
    )

    parser.add_argument(
        '-m', '--model',
        default='qwen2.5:3b',
        help='Model identifier: Ollama model name (e.g., qwen2.5:3b), GGUF file path, or OpenAI model name (e.g., gpt-3.5-turbo, llama-3.1-70b-versatile) (default: qwen2.5:3b)'
    )
    parser.add_argument(
        '--llm-backend',
        choices=['auto', 'ollama', 'llama-cpp', 'openai'],
        default='auto',
        help='LLM backend to use (default: auto-detect)'
    )
    parser.add_argument(
        '--api-key',
        help='API key for OpenAI-compatible backend (defaults to OPENAI_API_KEY env var)'
    )
    parser.add_argument(
        '--base-url',
        help='Base URL for OpenAI-compatible API (e.g., https://api.groq.com/openai/v1)'
    )
    parser.add_argument(
        '--list-models',
        action='store_true',
        help='List available Ollama models and exit'
    )
    parser.add_argument(
        '--backend',
        choices=['fluidsynth', 'hardware', 'virtual'],
        default='fluidsynth',
        help='Audio backend (default: fluidsynth)'
    )
    parser.add_argument(
        '--port',
        help='MIDI port name (for hardware backend)'
    )
    parser.add_argument(
        '--list-ports',
        action='store_true',
        help='List available MIDI ports and exit'
    )
    parser.add_argument(
        '-n', '--num-sections',
        type=int,
        help='Number of sections to generate (default: infinite)'
    )
    parser.add_argument(
        '--save-output',
        action='store_true',
        help='Save generated sections to files'
    )
    parser.add_argument(
        '--output-dir',
        default='output',
        help='Directory for saved output (default: output/)'
    )
    parser.add_argument(
        '--tempo',
        type=int,
        help=f'Tempo in BPM (default: {config.TEMPO})'
    )
    parser.add_argument(
        '--resolution',
        choices=['8th', '16th'],
        help=f'Note resolution (default: {config.RESOLUTION})'
    )
    parser.add_argument(
        '--gpu-layers',
        type=int,
        default=-1,
        help='GPU layers to offload (-1 = all, default: -1)'
    )
    parser.add_argument(
        '--ctx-size',
        type=int,
        default=2048,
        help='Context window size (default: 2048)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging for debugging'
    )
    parser.add_argument(
        '--sequential',
        action='store_true',
        help='Use sequential generation (bass→drums→piano→sax) instead of batched (default: batched)'
    )

    args = parser.parse_args()

    # List models and exit
    if args.list_models:
        list_ollama_models()
        return

    # List ports and exit
    if args.list_ports:
        list_midi_ports()
        return

    # Override config
    if args.tempo:
        config.TEMPO = args.tempo
    if args.resolution:
        config.RESOLUTION = args.resolution

    # Initialize LLM
    print(f"\n{'='*60}")
    print("Initializing LLM...")
    print(f"{'='*60}\n")

    try:
        # Prepare kwargs based on backend
        llm_kwargs = {}
        if args.llm_backend == 'llama-cpp':
            llm_kwargs = {
                'n_ctx': args.ctx_size,
                'n_gpu_layers': args.gpu_layers,
                'verbose': False
            }
        elif args.llm_backend == 'openai':
            if args.api_key:
                llm_kwargs['api_key'] = args.api_key
            if args.base_url:
                llm_kwargs['base_url'] = args.base_url

        llm = LLMInterface(
            model=args.model,
            backend=args.llm_backend,
            **llm_kwargs
        )
    except Exception as e:
        print(f"Error loading model: {e}")
        print("\nTroubleshooting:")
        print("  - For Ollama: Make sure Ollama is installed and running")
        print("    Install: curl -fsSL https://ollama.com/install.sh | sh")
        print("    Start: ollama serve")
        print("  - For llama-cpp: Make sure model file exists")
        print("  - For OpenAI/Groq: Make sure API key is set and base-url is correct")
        print("    Set OPENAI_API_KEY env var or use --api-key")
        print("  - Use --list-models to see available Ollama models")
        sys.exit(1)

    # Initialize audio backend
    print(f"\n{'='*60}")
    print("Initializing audio backend...")
    print(f"{'='*60}\n")

    try:
        if args.backend == 'fluidsynth':
            backend = FluidSynthBackend()
        elif args.backend == 'hardware':
            backend = HardwareMIDIBackend(port_name=args.port)
        elif args.backend == 'virtual':
            backend = VirtualMIDIBackend()
    except Exception as e:
        print(f"Error initializing audio backend: {e}")
        print("\nTry one of these options:")
        print("  1. Install FluidSynth (for software synthesis)")
        print("  2. Use --list-ports to see available MIDI ports")
        print("  3. Use --backend virtual to create a virtual MIDI port")
        sys.exit(1)

    # Run generator
    generator = RealtimeJazzGenerator(
        llm=llm,
        audio_backend=backend,
        save_output=args.save_output,
        output_dir=args.output_dir,
        batched=not args.sequential,  # Default to batched unless --sequential is passed
        verbose=args.verbose
    )

    generator.run(num_sections=args.num_sections)


if __name__ == '__main__':
    main()
