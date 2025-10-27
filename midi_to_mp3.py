#!/usr/bin/env python3
"""Convert a MIDI file to an MP3 using FluidSynth and FFmpeg with loudness normalization."""

import argparse
import subprocess
from pathlib import Path
import os


def convert_midi_to_mp3(midi_path: Path, soundfont: Path, output_path: Path, tmp_wav: Path) -> None:
    """Run FluidSynth to render MIDI to WAV, then encode to MP3 via FFmpeg."""
    fluidsynth_cmd = [
        "fluidsynth",
        "-ni",
        str(soundfont),
        str(midi_path),
        "-F",
        str(tmp_wav),
        "-r",
        "44100",
    ]

    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(tmp_wav),
        "-af",
        "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-ar",
        "44100",
        "-b:a",
        "192k",
        str(output_path),
    ]

    subprocess.run(fluidsynth_cmd, check=True)
    subprocess.run(ffmpeg_cmd, check=True)

    if tmp_wav.exists():
        try:
            os.remove(tmp_wav)
        except OSError as exc:
            print(f"Warning: could not remove temp WAV {tmp_wav}: {exc}")


def main():
    parser = argparse.ArgumentParser(description="Render MIDI to MP3 with FluidSynth & FFmpeg loudnorm.")
    parser.add_argument("midi", type=Path, help="Path to MIDI file")
    parser.add_argument(
        "--soundfont",
        type=Path,
        default=Path("/usr/share/sounds/sf2/FluidR3_GM.sf2"),
        help="Path to .sf2 soundfont file (default: /usr/share/sounds/sf2/FluidR3_GM.sf2)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for output MP3; defaults to input name with .mp3"
    )
    parser.add_argument(
        "--temp-wav",
        type=Path,
        default=None,
        help="Optional path for temporary WAV (defaults to alongside output)"
    )
    args = parser.parse_args()

    if not args.midi.exists():
        parser.error(f"MIDI file not found: {args.midi}")
    if not args.soundfont.exists():
        parser.error(f"Soundfont not found: {args.soundfont}")

    output = args.output or args.midi.with_suffix(".mp3")
    tmp_wav = args.temp_wav or output.with_suffix(".wav")

    convert_midi_to_mp3(args.midi, args.soundfont, output, tmp_wav)


if __name__ == "__main__":
    main()
