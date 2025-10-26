# JazzAI - 30 Second Quickstart

## 1. Install Dependencies

```bash
pip install -r requirements.txt
```

## 2. Install Ollama

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**macOS:**
```bash
brew install ollama
```

**Windows:** https://ollama.com/download

## 3. Start Ollama

In a separate terminal:
```bash
ollama serve
```

## 4. Install FluidSynth (for audio)

**Ubuntu/Debian:**
```bash
sudo apt-get install fluidsynth
```

**macOS:**
```bash
brew install fluid-synth
```

**Windows:** https://github.com/FluidSynth/fluidsynth/releases

## 5. Run!

```bash
python realtime_jazz.py -m qwen2.5:3b -n 4
```

The first run downloads the model (~2GB). Then it generates 4 sections of jazz!

---

**Having trouble?** See [SETUP.md](SETUP.md) for detailed instructions and troubleshooting.

**Want to customize?** See [README.md](README.md) for full documentation.
