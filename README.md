# JazzAI - Real-time Jazz Quartet Generator

AI-powered real-time jazz quartet using local LLMs and MIDI output.

## Architecture

**Hardware:**
- Target: Nvidia 4070 Ti Super 16GB
- Goal: 100+ TPS with 3B model (Phi-3, Qwen 2.5, or Llama 3.2)
- Output: MIDI → FluidSynth (software) or Yamaha TG-33 (hardware)

**Approach:**
- Single LLM, 4 sequential passes per generation cycle
- Generate 2 bars at a time per instrument
- Call-and-response: Each instrument sees previous instruments' output
- Buffer ahead while current bars play

**Instruments:**
- Bass (MIDI channel 0)
- Drums (MIDI channel 9, General MIDI Level 1)
- Piano (MIDI channel 1)
- Sax (MIDI channel 2)

**LLM Backend:**
- Primary: **Ollama** (easiest setup, great performance)
- Alternative: llama-cpp-python (manual model management)

## Tracker Format

Ultra-minimal text format for music notation:

```
BASS
C2:80
.
E2:75
.

DRUMS
C1:90,F#1:60
F#1:50

PIANO
C3:65,E3:60,G3:62
.

SAX
E4:70
G4:75
```

**Format Rules:**
- Section headers: `BASS`, `DRUMS`, `PIANO`, `SAX`
- One line per time step (8th or 16th note resolution)
- Note format: `NOTE:VELOCITY` (e.g., `C4:80`)
- Chords: Comma-separated notes (e.g., `C4:70,E4:65,G4:68`)
- Rests: `.` or blank line
- Velocity range: 0-127

**General MIDI Level 1 Drums:**
- C2 (36): Kick
- D2 (38): Snare
- F#2 (42): Closed Hi-Hat
- A#2 (46): Open Hi-Hat
- A2 (45): Low Tom
- C3 (48): Mid Tom
- D3 (50): High Tom
- C#3 (49): Crash
- D#3 (51): Ride

## Quick Start

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Install Ollama
# Linux:
curl -fsSL https://ollama.com/install.sh | sh
# macOS:
brew install ollama
# Windows: Download from https://ollama.com/download

# 3. Start Ollama server (in separate terminal)
ollama serve

# 4. Install FluidSynth (for audio output)
# Ubuntu/Debian:
sudo apt-get install fluidsynth
# macOS:
brew install fluid-synth
# Windows: Download from https://www.fluidsynth.org/

# 5. Run JazzAI! (auto-downloads model on first run)
python realtime_jazz.py -m qwen2.5:3b -n 4
```

See [SETUP.md](SETUP.md) for detailed instructions.

## Usage

### Real-time Generation

```bash
# Basic usage with qwen2.5:3b (recommended)
python realtime_jazz.py -m qwen2.5:3b -n 4

# Try different model
python realtime_jazz.py -m phi3:mini -n 4

# Save generated sections
python realtime_jazz.py -m qwen2.5:3b --save-output

# Change tempo
python realtime_jazz.py -m qwen2.5:3b --tempo 140

# Use 16th note resolution
python realtime_jazz.py -m qwen2.5:3b --resolution 16th

# List available models
python realtime_jazz.py --list-models

# Hardware MIDI output (e.g., Yamaha TG-33)
python realtime_jazz.py -m qwen2.5:3b --backend hardware --port "Your MIDI Device"
```

### Test Without LLM

```bash
# Test tracker → MIDI conversion
python test_playback.py

# Test generation pipeline with mock data
python test_generation.py

# Export to MIDI file
python test_playback.py -o output.mid
```

### Configuration

Edit `config.py` to customize:

```python
TEMPO = 120              # BPM
RESOLUTION = '8th'       # '8th' or '16th' notes
NOTE_MODE = 'trigger'    # 'trigger' or 'sustain'
BARS_PER_GENERATION = 2  # Bars per LLM generation
```

## Project Structure

```
jazzai/
├── config.py              # Configuration settings
├── tracker_parser.py      # Parse tracker format to structured data
├── midi_converter.py      # Convert tracker to MIDI
├── audio_output.py        # Audio backends (FluidSynth, hardware, virtual)
├── llm_interface.py       # LLM integration (TODO)
├── generator.py           # Generation pipeline (TODO)
├── test_playback.py       # Test script
├── examples/
│   └── test_pattern.txt   # Example tracker pattern
└── requirements.txt       # Python dependencies
```

## Components

### tracker_parser.py
Parses text tracker format into structured Python objects.

**Key functions:**
- `parse_tracker(text)`: Parse complete tracker file
- `TrackerParser.note_to_midi(note)`: Convert note names to MIDI numbers

### midi_converter.py
Converts parsed tracker data to MIDI.

**Key classes:**
- `MIDIConverter`: Main converter class
- `create_midi_file()`: Generate mido.MidiFile
- `create_realtime_messages()`: Generate timed MIDI messages for playback

**Features:**
- Configurable resolution (8th/16th notes)
- Trigger or sustain mode
- Proper MIDI timing with ticks

### audio_output.py
Audio output backends with unified interface.

**Backends:**
- `FluidSynthBackend`: Software synthesis
- `HardwareMIDIBackend`: External MIDI hardware (e.g., Yamaha TG-33)
- `VirtualMIDIBackend`: Virtual MIDI port for DAWs

**Key classes:**
- `RealtimePlayer`: Buffer and play MIDI messages with precise timing
- `play_midi_file()`: Simple MIDI file playback

## Design Decisions

### Configurable Resolution
Resolution is configurable between 8th and 16th notes. All timing calculations are centralized in `config.py`:
- `get_ticks_per_step()`: MIDI ticks per tracker step
- `get_steps_per_bar()`: Tracker steps per bar
- Change `RESOLUTION` in config.py or use `--resolution` flag

### Note Duration Modes

**Trigger mode** (current default):
- Each note plays for exactly one time step
- Simple and predictable
- Good for LLM to learn

**Sustain mode** (future):
- Notes hold until next event
- More expressive
- Requires careful LLM prompting
- Set `NOTE_MODE = 'sustain'` in config.py

### Backend Abstraction
All audio backends implement `AudioBackend` interface:
- Easy to swap between FluidSynth, hardware, or virtual MIDI
- Add new backends by implementing `send_message()` and `close()`
- Future: Add latency compensation, MIDI clock sync

## Customization

1. **Prompts** (prompts.py)
   - Edit instrument-specific prompts
   - Change musical style and guidelines
   - Add examples in tracker format

2. **Generation Config** (llm_interface.py)
   - Adjust temperature, top_p for each instrument
   - Tune creativity vs consistency
   - Modify stop sequences

3. **Music Config** (config.py)
   - Change tempo, time signature
   - Adjust bars per generation
   - Switch resolution (8th/16th notes)

4. **LLM Backend**
   - Try different models (qwen2.5:3b, phi3:mini, llama3.2:3b)
   - Use llama-cpp-python for manual model management
   - Adjust context window size

## Performance Targets

- **Inference**: 100+ TPS with 3B model
- **Latency**: Generate 2 bars before current playback ends
- **Timing**: Sub-millisecond MIDI timing accuracy

## License

MIT
