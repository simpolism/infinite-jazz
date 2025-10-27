# Repository Guidelines

## Project Structure & Module Organization
- `realtime_jazz.py` is now a thin CLI wrapper; `app.py` builds the runtime and `runtime.RealtimeJazzGenerator` drives playback.
- `generator.py`, `prompts.py` (`PromptBuilder`), and `tracker_parser.py` handle prompt templating, batched LLM calls, and tracker parsing; keep quartet-specific tweaks there.
- `midi_converter.py` and `audio_output.py` translate tracker steps into MIDI events and route them to FluidSynth, hardware, or virtual ports.
- `config.py` exposes the immutable `RuntimeConfig`; use `dataclasses.replace` to tweak tempo, swing, or bar length near the wiring layer instead of mutating globals.
- Generated tracker/MIDI artifacts land in `output/`; do not version-control this directory.

## Build, Test, and Development Commands
- `. .venv/bin/activate` activates the pinned interpreter; install deps with `pip install -r requirements.txt`.
- `.venv/bin/python realtime_jazz.py --llm-backend openai -n 2` exercises the Groq default (`openai/gpt-oss-120b` at `https://api.groq.com/openai/v1`).
- `.venv/bin/python realtime_jazz.py --list-ports` inspects MIDI destinations before choosing `--backend hardware`.
- `.venv/bin/python txt_to_midi.py path/to/tracker.txt --out output/demo.mid` converts archived tracker text into a playable MIDI file.

## Coding Style & Naming Conventions
- Use 4-space indentation, descriptive snake_case identifiers, and keep modules single-responsibility (generation, parsing, playback).
- Preserve existing docstrings and type hints; new public functions should include succinct docstrings explaining musical assumptions.
- Maintain tracker constants (`BASS`, `DRUMS`, `PIANO`, `SAX`) and bar counts defined in `config.py` to stay compatible with live playback.
- Keep `PromptBuilder.style_palette` curated; rotating styles are a cheap lever for variety while remaining easy to override in experiments.
- Adjust continuity with the CLI flag `--context-steps` (default 32); higher values feed more tracker lines back into the prompt, while 0 starts each section clean.
- Use `--prompt` to append collaborator notes (e.g., "bouncy, upbeat") without editing base prompts.
- Exported tracker `.txt` files begin with `# key: value` metadata so you can recover tempo/config; `tracker_parser` strips these automatically.

## Testing Guidelines
- There is no automated suite; validate changes by running `.venv/bin/python realtime_jazz.py --save-output --output-dir output/dev` and confirming tracker/MIDI continuity.
- When modifying parsing or conversion logic, use `-n 2 --tempo 140` to stress timing, and inspect generated `.mid` files in a DAW or MIDI monitor.
- Update or add sample tracker snippets in `output/` (ignored by git) to document edge cases you validated.

## Commit & Pull Request Guidelines
- Follow the repo’s short, imperative commits (e.g., “Add note holding”, “Fix and stabilize”); mention the touched subsystem (`generator`, `midi_converter`) when relevant.
- Ensure PRs describe the musical effect, include reproduction steps, and attach short audio/MIDI evidence when behavior changes.
- Link tracking issues and call out configuration updates (e.g., new env vars like `GROQ_API_KEY`) in the PR description.

## Security & Configuration Tips
- Never commit API keys; load providers by exporting `GROQ_API_KEY` or pointing to a secrets manager before running the app.
- Keep `jazz.sh` private or redact tokens before sharing; regenerate keys if the script is exposed.
