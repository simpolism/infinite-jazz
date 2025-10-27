# Infinite Jazz – Realtime Quartet Generator

Infinite Jazz stitches together large-language-model composition, tracker parsing, MIDI conversion, and live playback to improvise an endless jazz quartet. Each cycle generates two bars for bass, drums, piano, and sax in a single batched LLM call, buffers the result, and streams it out with tight timing.

> ⚡ **For real-time responsiveness, use Groq (OpenAI-compatible API).** Ollama remains available for local experimentation but does not guarantee the throughput needed for low-latency playback.

---

## Example Output



https://github.com/user-attachments/assets/e2c88863-a5c6-492a-8606-d2ed5f727e6b


*AI-generated jazz quartet improvisation*

---

## Quickstart

### 1. Set up the environment

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Optional software synth (FluidSynth provides the default software backend):

```bash
# Debian / Ubuntu
sudo apt-get install fluidsynth

# macOS (Homebrew)
brew install fluid-synth
```

### 2. Choose an inference backend

**Groq (recommended)**
```bash
export GROQ_API_KEY="your_api_key"
.venv/bin/python realtime_jazz.py \
  --llm-backend openai \
  -n 4
```
When no model or base URL is supplied, the CLI targets Groq's `openai/gpt-oss-120b` via `https://api.groq.com/openai/v1`.

**Ollama (local)**
```bash
curl -fsSL https://ollama.com/install.sh | sh   # one-time install
ollama serve                                   # separate terminal
.venv/bin/python realtime_jazz.py -m qwen2.5:3b -n 4
```

### 3. Useful flags

- `--tempo 140` – override BPM for generation + playback
- `--save-output --output-dir output/` – persist tracker text and combined MIDI
- `--backend {fluidsynth|hardware|virtual}` – route MIDI to software, hardware, or a DAW
- `--list-ports` – inspect available MIDI outputs before selecting `--backend hardware`

Stop playback with `Ctrl+C`; the app drains the buffer and exits cleanly.

---

## Everyday Workflow

```bash
# 1. Activate the repo's virtualenv (keeps dependencies pinned)
. .venv/bin/activate

# 2. Run the realtime generator with Groq (default model + endpoint)
python realtime_jazz.py --llm-backend openai --save-output --context-steps 128

# 3. Inspect saved tracker/MIDI artifacts (ignored by git)
ls output/
```

- Append collaborator notes with `--prompt "atmospheric, sparse"` without touching base prompts.
- Flip to the exploratory template via `--prompt-style experimental`.
- Increase continuity with `--context-steps 128` (32 is the default); use `0` for clean-room sections.
- Use `--seed 42` (or any integer) to make the LLM generation deterministic for A/B comparisons.
- `--tempo`, `--swing`, or other `RuntimeConfig` tweaks should be applied by cloning `DEFAULT_CONFIG` via `dataclasses.replace` rather than mutating globals.

---

## Architecture Overview

1. **Prompting** – `prompts.PromptBuilder` emits quartet prompts tailored by runtime config and style.
2. **Generation** – `generator.GenerationPipeline` calls the LLM, parses the response into structured tracks, and keeps a short history for continuity.
3. **Buffering** – `generator.ContinuousGenerator` maintains a queue of upcoming sections so playback never waits on inference.
4. **Conversion** – `midi_converter.MIDIConverter` converts tracker steps to MIDI events on a fixed 16th-note grid with optional swing.
5. **Playback** – `audio_output.RealtimePlayer` schedules events and streams them through FluidSynth, hardware MIDI, or a virtual port.
6. **Runtime** – `runtime.RealtimeJazzGenerator` glues generation, conversion, buffering, and playback together.
7. **Application layer** – `app.InfiniteJazzApp` prepares dependencies; `realtime_jazz.py` is a thin CLI wrapper around the app.

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

- Need a tempo tweak for one run? Use `replace(DEFAULT_CONFIG, tempo=140)` at the wiring layer (`app.py`, tests, or scripts) rather than changing `config.py`.
- Generated tracker and MIDI artifacts live in `output/` (ignored by git) so you can archive or audition takes without polluting commits.

---

## Tuning Creativity

- Generation temperature/top-p defaults are 1.05 / 0.99 with `max_tokens` ≈ 4500 to comfortably handle 32-step sections (and longer, if you increase bar count). Drop temperature/top-p for tighter adherence, or bump them for wilder phrases.
- Inject custom instructions by subclassing `PromptBuilder` or swapping it in `GenerationPipeline` (e.g., derivative of `PromptBuilder` that emphasises polyrhythms or Latin grooves).
- Still want more surprise? Feed a short corpus of tracker snippets into `previous_context` to prime different harmonic territory before realtime playback.
- Control how much history the model references with `--context-steps` (default 32). Higher values increase continuity; lower values encourage fresh jumps.
- Add custom vibe text with `--prompt "bouncy, upbeat"` (or any phrase) to inject extra guidance on top of the base prompt.
- Switch prompts with `--prompt-style experimental` for the exploratory/chaotic preset (default is tighter swing).
- Saved tracker `.txt` files start with comment metadata (lines prefixed with `#`) so you can recover tempo/config later; parsers ignore these automatically.

---

## Command Reference

```bash
# Use Groq with a different model/base URL
.venv/bin/python realtime_jazz.py --llm-backend openai \
  --model gemma-9b-it \
  --base-url https://api.groq.com/openai/v1 \
  --api-key $GROQ_API_KEY

# Save every generated section plus a stitched MIDI file
.venv/bin/python realtime_jazz.py --save-output --output-dir recordings/

# Drive a DAW via a virtual MIDI port
.venv/bin/python realtime_jazz.py --backend virtual

# Send MIDI to hardware (after checking ports)
.venv/bin/python realtime_jazz.py --list-ports
.venv/bin/python realtime_jazz.py --backend hardware --port "Yamaha TG-33"
```

---

## Repository Layout

```
infinite_jazz/
├── realtime_jazz.py        # CLI entrypoint (arg parsing + app.run)
├── app.py                  # Dependency wiring (LLM/audio/runtime)
├── runtime.py              # Realtime coordinator (generation → playback)
├── generator.py            # Batched LLM pipeline & buffering
├── prompts.py              # Default prompt templates
├── experimental_prompt.py  # Alternate "experimental" template
├── tracker_parser.py       # Tracker text → structured tracks
├── midi_converter.py       # Tracker → MIDI (files + realtime messages)
├── audio_output.py         # FluidSynth / hardware / virtual backends
├── llm_interface.py        # Ollama + OpenAI-compatible API adapters
├── midi_to_mp3.py          # Offline MIDI rendering helper
├── txt_to_midi.py          # Convert archived tracker text to MIDI
├── config.py               # Immutable RuntimeConfig + defaults
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
- **Weird out-of-range notes** – parser now skips them with a warning instead of aborting; check prompts/style if it happens often.
- **Offline MIDI drifts vs realtime** – `midi_converter` now mirrors realtime swing timing; regenerate the section if you have older exports.

---

## License

MIT
