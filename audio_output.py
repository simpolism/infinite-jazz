"""
Audio output handling
Supports FluidSynth (software) and hardware MIDI output
Designed for easy backend swapping
"""

import mido
import time
import threading
from abc import ABC, abstractmethod
from typing import List, Optional
from queue import Queue, Empty


class AudioBackend(ABC):
    """Abstract base class for audio output backends"""

    @abstractmethod
    def send_message(self, message: mido.Message):
        """Send a MIDI message"""
        pass

    @abstractmethod
    def close(self):
        """Clean up resources"""
        pass


class FluidSynthBackend(AudioBackend):
    """
    FluidSynth software synthesizer backend
    Spawns a FluidSynth process and connects via MIDI
    """

    def __init__(self, soundfont_path: Optional[str] = None):
        """
        Initialize FluidSynth backend
        Args:
            soundfont_path: Path to .sf2 soundfont file
                          If None, searches for system soundfont
        """
        import subprocess
        import shutil
        from pathlib import Path

        # Check if fluidsynth is installed
        if not shutil.which('fluidsynth'):
            raise RuntimeError(
                "FluidSynth not found in PATH.\n"
                "Install it:\n"
                "  Ubuntu/Debian: sudo apt-get install fluidsynth\n"
                "  macOS: brew install fluid-synth\n"
                "  Windows: Download from https://www.fluidsynth.org/"
            )

        # Find soundfont
        if soundfont_path is None:
            # Common soundfont locations
            search_paths = [
                '/usr/share/sounds/sf2/FluidR3_GM.sf2',
                '/usr/share/sounds/sf2/default.sf2',
                '/usr/share/soundfonts/default.sf2',
                '/usr/share/soundfonts/FluidR3_GM.sf2',
                '/usr/share/soundfonts/GeneralUser.sf2',  # Arch/Manjaro
                '/opt/homebrew/share/sound/default.sf2',  # macOS homebrew
            ]

            for path in search_paths:
                if Path(path).exists():
                    soundfont_path = path
                    break

            if soundfont_path is None:
                raise RuntimeError(
                    "No soundfont found. Install one:\n"
                    "  Ubuntu/Debian: sudo apt-get install fluid-soundfont-gm\n"
                    "  macOS: brew install fluid-synth (includes soundfont)\n"
                    "Or specify path with soundfont_path parameter"
                )

        print(f"Using soundfont: {soundfont_path}")

        # Start FluidSynth process in server mode
        # -a alsa: Use ALSA audio driver
        # -m alsa_seq: Use ALSA sequencer for MIDI
        # -g 1.0: Gain/volume
        # -z 256: Buffer size (larger = less choppy but more latency)
        # -c 2: Audio buffers count
        # -r 48000: Sample rate
        try:
            self.process = subprocess.Popen(
                [
                    'fluidsynth',
                    '-a', 'alsa',
                    '-m', 'alsa_seq',
                    '-g', '1.0',
                    '-z', '256',
                    '-c', '4',
                    '-r', '48000',
                    soundfont_path
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            # Give it a moment to start
            import time
            time.sleep(0.5)

            # Check if it's still running
            if self.process.poll() is not None:
                stderr = self.process.stderr.read()
                raise RuntimeError(f"FluidSynth failed to start: {stderr}")

        except FileNotFoundError:
            raise RuntimeError("FluidSynth executable not found")
        except Exception as e:
            raise RuntimeError(f"Failed to start FluidSynth: {e}")

        # Find the FluidSynth MIDI port
        time.sleep(0.5)  # Wait for port to appear

        available_ports = mido.get_output_names()
        fluidsynth_port = None

        for port_name in available_ports:
            if 'fluid' in port_name.lower() or 'synthesizer' in port_name.lower():
                fluidsynth_port = port_name
                break

        if not fluidsynth_port:
            self.process.terminate()
            raise RuntimeError(
                f"Could not find FluidSynth MIDI port.\n"
                f"Available ports: {available_ports}\n"
                f"FluidSynth may not have started correctly."
            )

        # Connect to FluidSynth port
        try:
            self.port = mido.open_output(fluidsynth_port)
            print(f"FluidSynth backend initialized: {fluidsynth_port}")
        except Exception as e:
            self.process.terminate()
            raise RuntimeError(f"Failed to open FluidSynth port: {e}")

    def send_message(self, message: mido.Message):
        """Send MIDI message to FluidSynth"""
        self.port.send(message)

    def close(self):
        """Close FluidSynth port and terminate process"""
        if hasattr(self, 'port'):
            self.port.close()
        if hasattr(self, 'process'):
            self.process.terminate()
            self.process.wait(timeout=2)


class HardwareMIDIBackend(AudioBackend):
    """
    Hardware MIDI output backend
    For connecting to external synths like Yamaha TG-33
    """

    def __init__(self, port_name: Optional[str] = None):
        """
        Initialize hardware MIDI backend
        Args:
            port_name: Name of MIDI output port
                      If None, uses first available port
        """
        available_ports = mido.get_output_names()

        if not available_ports:
            raise RuntimeError("No MIDI output ports found")

        if port_name is None:
            # Use first available port
            port_name = available_ports[0]
            print(f"No port specified, using: {port_name}")
        elif port_name not in available_ports:
            raise ValueError(
                f"Port '{port_name}' not found. Available ports: {available_ports}"
            )

        self.port = mido.open_output(port_name)
        print(f"Hardware MIDI backend initialized: {port_name}")

    def send_message(self, message: mido.Message):
        """Send MIDI message to hardware"""
        self.port.send(message)

    def close(self):
        """Close MIDI port"""
        if hasattr(self, 'port'):
            self.port.close()


class VirtualMIDIBackend(AudioBackend):
    """
    Virtual MIDI port backend
    Useful for connecting to DAWs or other software
    """

    def __init__(self, port_name: str = "Infinite Jazz"):
        """
        Initialize virtual MIDI port
        Args:
            port_name: Name for the virtual port
        """
        try:
            self.port = mido.open_output(port_name, virtual=True)
            print(f"Virtual MIDI port created: {port_name}")
        except Exception as e:
            raise RuntimeError(f"Failed to create virtual MIDI port: {e}")

    def send_message(self, message: mido.Message):
        """Send MIDI message to virtual port"""
        self.port.send(message)

    def close(self):
        """Close virtual port"""
        if hasattr(self, 'port'):
            self.port.close()


class RealtimePlayer:
    """
    Real-time MIDI player with buffering
    Plays MIDI messages with precise timing
    """

    def __init__(self, backend: AudioBackend):
        """
        Initialize realtime player
        Args:
            backend: AudioBackend instance
        """
        self.backend = backend
        self.message_queue = Queue()
        self.is_playing = False
        self.player_thread = None

    def schedule_messages(self, messages: List[tuple]):
        """
        Schedule MIDI messages for playback
        Args:
            messages: List of (time_in_seconds, mido.Message) tuples
        """
        for msg in messages:
            self.message_queue.put(msg)

    def play(self):
        """Start playback in separate thread"""
        if self.is_playing:
            print("Already playing")
            return

        self.is_playing = True
        self.player_thread = threading.Thread(target=self._playback_loop)
        self.player_thread.start()

    def _playback_loop(self):
        """Main playback loop (runs in separate thread)"""
        start_time = time.time()

        while self.is_playing:
            try:
                # Get next message with timeout
                scheduled_time, message = self.message_queue.get(timeout=0.1)

                # Wait until scheduled time
                current_time = time.time() - start_time
                wait_time = scheduled_time - current_time

                if wait_time > 0:
                    time.sleep(wait_time)

                # Send message
                self.backend.send_message(message)

            except Empty:
                # No more messages, stop playing
                self.is_playing = False
                break

    def stop(self):
        """Stop playback"""
        self.is_playing = False
        if self.player_thread:
            self.player_thread.join()

        # Clear remaining messages
        while not self.message_queue.empty():
            try:
                self.message_queue.get_nowait()
            except Empty:
                break

    def close(self):
        """Clean up resources"""
        self.stop()
        self.backend.close()


def play_midi_file(midi_file: mido.MidiFile, backend: AudioBackend):
    """
    Play a MIDI file using specified backend
    Args:
        midi_file: mido.MidiFile object
        backend: AudioBackend instance
    """
    import time

    print(f"Playing MIDI file with {len(midi_file.tracks)} tracks...")

    # Give FluidSynth a moment to warm up before playing
    # This prevents the first notes from being cut off
    time.sleep(1.0)  # Increased to 1 second for better stability

    try:
        # Send all MIDI messages with proper timing
        for message in midi_file.play():
            backend.send_message(message)

        # Wait for audio buffers to finish playing
        # This is important for FluidSynth - MIDI messages are sent but audio still needs to play
        print("Waiting for audio to finish...")
        time.sleep(4.0)  # Give buffers time to drain and reverb to fade out completely

    except KeyboardInterrupt:
        print("\nPlayback interrupted")
    finally:
        backend.close()
        print("Done!")


def list_midi_ports():
    """List available MIDI ports"""
    print("Available MIDI output ports:")
    for port in mido.get_output_names():
        print(f"  - {port}")
