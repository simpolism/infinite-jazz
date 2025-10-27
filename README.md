# Infinite Jazz – Realtime Quartet Generator

Infinite Jazz stitches together large-language-model composition, tracker parsing, MIDI conversion, and live playback to improvise an endless jazz quartet. Each cycle generates two bars for bass, drums, piano, and sax in a single batched LLM call, buffers the result, and streams it out with tight timing.

> ⚡ **For real-time responsiveness, use Groq (OpenAI-compatible API).** Ollama remains available for local experimentation but does not guarantee the throughput needed for low-latency playback.

---

## Quickstart

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

Optional software synth:

```bash
# Debian / Ubuntu
sudo apt-get install fluidsynth

# macOS
brew install fluid-synth
```

### 2. Pick an inference backend

**Groq (recommended)**
```bash
export GROQ_API_KEY="your_api_key"
python realtime_jazz.py \
  --llm-backend openai \
  --model llama-3.1-70b-versatile \
  --base-url https://api.groq.com/openai/v1 \
  -n 4
```

**Ollama (local)**
```bash
curl -fsSL https://ollama.com/install.sh | sh   # one-time install
ollama serve                                   # separate terminal
python realtime_jazz.py -m qwen2.5:3b -n 4
```

### 3. Useful flags

- `--tempo 140` – override BPM for generation + playback
- `--save-output --output-dir output/` – persist tracker text and combined MIDI
- `--backend {fluidsynth|hardware|virtual}` – route MIDI to software, hardware, or a DAW
- `--list-ports` – inspect available MIDI outputs before selecting `--backend hardware`

Stop playback with `Ctrl+C`; the app drains the buffer and exits cleanly.

---

## Architecture Overview

1. **Prompting** – `prompts.py` builds a single quartet prompt describing formatting and stylistic guidance.
2. **Generation** – `generator.GenerationPipeline` calls the LLM, parses the response into structured tracks, and keeps a short history for continuity.
3. **Buffering** – `generator.ContinuousGenerator` maintains a queue of upcoming sections so playback never waits on inference.
4. **Conversion** – `midi_converter.MIDIConverter` converts tracker steps to MIDI events on a fixed 16th-note grid with optional swing.
5. **Playback** – `RealtimeJazzGenerator` schedules events and streams them through audio backends (FluidSynth, hardware MIDI, or a virtual port).

The whole loop runs continuously: while one section plays, the system composes the next ones in the background.

---

## Tracker Format (LLM ↔ Pipeline)

```
BASS
C2:80
.
E2:75
.

DRUMS
C2:90,D#3:60
.

PIANO
C3:65,E3:60,G3:62
.

SAX
E4:78
.
```

- Four instrument headers (`BASS`, `DRUMS`, `PIANO`, `SAX`)
- 16th-note resolution, `RuntimeConfig.total_steps` lines per instrument (32 by default)
- Notes: `NOTE:VELOCITY` (e.g., `C4:80`)
- Chords: comma separated (piano voicings)
- Rests: `.`
- Ties: `^` to continue the previous note
- Velocity range: 0–127 (typical swing accents around 70–95)

---

## Configuration Highlights (`config.py`)

```python
from dataclasses import replace
from config import DEFAULT_CONFIG

cfg = DEFAULT_CONFIG                 # Immutable defaults
cfg = replace(cfg, tempo=140)        # Override BPM
cfg.total_steps                      # Derived 16th-note steps per section
```

`RuntimeConfig` also exposes channel and pitch-range maps plus swing parameters. Thread a config instance through constructors instead of mutating globals.

---

## Command Reference

```bash
# Use Groq with a different model
python realtime_jazz.py --llm-backend openai \
  --model gemma-9b-it \
  --base-url https://api.groq.com/openai/v1 \
  --api-key $GROQ_API_KEY

# Save every generated section plus a stitched MIDI file
python realtime_jazz.py --save-output --output-dir recordings/

# Drive a DAW via a virtual MIDI port
python realtime_jazz.py --backend virtual

# Send MIDI to hardware (after checking ports)
python realtime_jazz.py --list-ports
python realtime_jazz.py --backend hardware --port "Yamaha TG-33"
```

---

## Repository Layout

```
infinite_jazz/
├── realtime_jazz.py   # CLI entrypoint & orchestration
├── generator.py       # Batched LLM pipeline & buffering
├── prompts.py         # Quartet prompt template
├── tracker_parser.py  # Tracker text → structured tracks
├── midi_converter.py  # Tracker → MIDI (file + realtime)
├── audio_output.py    # FluidSynth / hardware / virtual backends
├── llm_interface.py   # Ollama + OpenAI-compatible API adapters
├── config.py          # Musical & timing configuration
├── txt_to_midi.py     # Convert archived tracker text to MIDI
└── requirements.txt
```

---

## Tuning & Extensibility

- **Prompt tweaks** – edit `prompts.py` to push the quartet toward different eras, ranges, or rhythmic feels.
- **Generation parameters** – adjust `max_tokens`, `temperature`, or `top_p` in `generator.py` to balance creativity and format adherence.
- **Playback backends** – implement the `AudioBackend` interface in `audio_output.py` to add new destinations (e.g., WebMIDI, OSC).
- **Persistence / streaming** – extend `RealtimeJazzGenerator` to stream tracker text or MIDI to external consumers.

---

## Troubleshooting

- **Playback stutters** – Groq model may be too slow; choose a faster variant or increase `ContinuousGenerator.buffer_size`.
- **No sound** – ensure FluidSynth is installed (or switch to `--backend hardware/virtual`).
- **Ollama outputs empty sections** – smaller local models sometimes struggle with strict formatting; Groq/OpenAI models are more reliable.

---

## License

MIT
