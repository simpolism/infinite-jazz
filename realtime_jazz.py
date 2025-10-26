#!/usr/bin/env python3
"""
Real-time jazz quartet generator
Generates and plays jazz continuously using local LLM
"""

import argparse
import sys
import time
import threading
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
        output_dir: str = "output"
    ):
        """
        Initialize real-time jazz generator

        Args:
            llm: LLMInterface instance
            audio_backend: AudioBackend instance
            save_output: Save generated sections to files
            output_dir: Directory for saved output
        """
        self.llm = llm
        self.audio_backend = audio_backend
        self.save_output = save_output
        self.output_dir = Path(output_dir)

        if self.save_output:
            self.output_dir.mkdir(exist_ok=True)

        self.generator = ContinuousGenerator(llm)  # Uses default buffer_size=2, generates async
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
            Actual duration of the section (in seconds)
        """
        # Create MIDI file for this section
        midi_file = self.midi_converter.create_midi_file(tracks)

        # Extract messages with timing
        current_time = start_time
        msg_count = 0
        for message in midi_file.play():
            self.midi_queue.put((current_time, message))
            current_time += message.time
            msg_count += 1

        print(f"  Added {msg_count} MIDI messages to queue (duration: {current_time - start_time:.2f}s)")

        # Return actual duration
        return current_time - start_time

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

        try:
            # Pre-fill buffer
            print("Pre-generating initial sections...\n")
            buffer_size = self.generator.buffer_size
            self.generator.prefill_buffer()

            # Pre-load all buffered sections into queue BEFORE starting playback
            print(f"Pre-loading {buffer_size} buffered sections into playback queue...")
            section_num = 0
            current_time = 0.0  # Track absolute playback time

            # Pull ONLY the initial buffered sections (don't loop forever)
            for _ in range(buffer_size):
                print(f"\n--- Section {section_num + 1} ---")
                tracks = self.generator.get_next_section()

                # Save section
                self.all_sections.append(tracks)
                if self.save_output:
                    output_file = self.output_dir / f"section_{section_num:04d}.txt"
                    save_generated_section(tracks, str(output_file))

                # Add MIDI messages to queue and get actual duration
                print(f"Queueing section {section_num + 1} for playback...")
                actual_duration = self._add_section_to_queue(tracks, current_time)

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
                tracks = self.generator.get_next_section()

                # Save section
                self.all_sections.append(tracks)
                if self.save_output:
                    output_file = self.output_dir / f"section_{section_num:04d}.txt"
                    save_generated_section(tracks, str(output_file))

                # Add MIDI messages to queue and get actual duration
                print(f"Queueing section {section_num + 1} for playback...")
                actual_duration = self._add_section_to_queue(tracks, current_time)

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

    def _calculate_section_duration(self) -> float:
        """Calculate duration of one section in seconds"""
        beats_per_bar = config.TIME_SIGNATURE[0]
        bars = config.BARS_PER_GENERATION
        total_beats = beats_per_bar * bars

        # Duration = beats / (beats per second)
        duration = total_beats / (config.TEMPO / 60.0)
        return duration

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

            # Save
            output_file = self.output_dir / "complete.mid"
            midi_file.save(str(output_file))
            print(f"✓ Saved complete MIDI: {output_file}")

            # Also save complete tracker text
            txt_file = self.output_dir / "complete.txt"
            save_generated_section(combined_tracks, str(txt_file))

        print("Done!")


def main():
    parser = argparse.ArgumentParser(
        description='Real-time jazz quartet generator using local LLM',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use Ollama (easiest - auto-downloads model)
  python realtime_jazz.py -m qwen2.5:3b

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
        help='Ollama model name (e.g., qwen2.5:3b, phi3:mini) or path to GGUF file (default: qwen2.5:3b)'
    )
    parser.add_argument(
        '--llm-backend',
        choices=['auto', 'ollama', 'llama-cpp'],
        default='auto',
        help='LLM backend to use (default: auto-detect)'
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
        output_dir=args.output_dir
    )

    generator.run(num_sections=args.num_sections)


if __name__ == '__main__':
    main()
