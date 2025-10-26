# JazzAI Quick Setup Guide

Get JazzAI running in 3 simple steps.

## Prerequisites

- Python 3.8+
- Nvidia GPU with CUDA (for best performance)
- ~5GB free disk space

## Step 1: Install Python Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `mido` and `python-rtmidi` for MIDI
- `ollama` for LLM inference
- `numpy` for numerical operations

## Step 2: Install Ollama

Ollama is the easiest way to run local LLMs.

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**macOS:**
```bash
brew install ollama
```

**Windows:**
Download from https://ollama.com/download

### Start Ollama Server

```bash
ollama serve
```

Keep this running in a separate terminal.

## Step 3: Install FluidSynth (for audio output)

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install fluidsynth fluid-soundfont-gm
```

**macOS:**
```bash
brew install fluid-synth
```

**Windows:**
Download from https://github.com/FluidSynth/fluidsynth/releases

## Done! Run JazzAI

```bash
# This will auto-download qwen2.5:3b on first run
python realtime_jazz.py -m qwen2.5:3b -n 4
```

The first run will download the model (~2GB). Subsequent runs start instantly.

## Test Without LLM First

If you want to test the MIDI pipeline before running the LLM:

```bash
# Test tracker → MIDI conversion (no LLM needed)
python test_playback.py

# Test generation pipeline with mock data (no LLM needed)
python test_generation.py
```

## Recommended Models

**For Nvidia 4070 Ti Super (16GB VRAM):**

1. **qwen2.5:3b** (Recommended)
   - Best quality
   - ~100 TPS
   - Auto-downloads on first use

2. **phi3:mini** (Alternative)
   - Good instruction following
   - ~90 TPS

3. **llama3.2:3b** (Alternative)
   - Good general model
   - ~95 TPS

All models auto-download when you first use them.

## Usage Examples

```bash
# Basic: Generate 4 sections with default model
python realtime_jazz.py -m qwen2.5:3b -n 4

# Different model
python realtime_jazz.py -m phi3:mini -n 4

# Save generated sections to files
python realtime_jazz.py -m qwen2.5:3b --save-output

# Change tempo to 140 BPM
python realtime_jazz.py -m qwen2.5:3b --tempo 140

# Use 16th note resolution
python realtime_jazz.py -m qwen2.5:3b --resolution 16th

# List available models
python realtime_jazz.py --list-models

# Use hardware MIDI (e.g., Yamaha TG-33)
python realtime_jazz.py --list-ports  # See available ports
python realtime_jazz.py -m qwen2.5:3b --backend hardware --port "Your MIDI Device"
```

## Troubleshooting

### "Connection error" when running

Make sure Ollama server is running:
```bash
ollama serve
```

### "Failed to initialize FluidSynth"

Install FluidSynth (see Step 3) or export to MIDI file instead:
```bash
python test_playback.py -o output.mid
```

### Low TPS (tokens per second)

1. Make sure Ollama detected your GPU:
```bash
ollama ps
# Should show GPU usage
```

2. Try a smaller model:
```bash
python realtime_jazz.py -m qwen2.5:1.5b
```

### Model not downloading

Manually pull the model:
```bash
ollama pull qwen2.5:3b
```

## Advanced: Using llama-cpp-python (optional)

If you prefer manual model management with llama-cpp-python:

```bash
# Install llama-cpp-python with CUDA support
CMAKE_ARGS="-DGGML_CUDA=on" pip install llama-cpp-python

# Download a GGUF model to models/ directory
# Then run with file path:
python realtime_jazz.py -m models/qwen2.5-3b-instruct-q5_k_m.gguf --llm-backend llama-cpp
```

But Ollama is much easier!

## Next Steps

- Edit prompts in `prompts.py` to change musical style
- Adjust generation configs in `llm_interface.py`
- Try different tempos and resolutions
- Save output and analyze what works well
