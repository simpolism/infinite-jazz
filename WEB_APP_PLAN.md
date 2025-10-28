# Infinite Jazz Browser Refresh – Implementation Notes

## Overview
The legacy Python runtime has been replaced with a static web bundle that streams OpenAI-compatible chat completions directly from the browser. The app keeps playback responsive with Web Audio, mirrors the tracker text on screen, and assembles downloadable MIDI files when a chorus finishes.

## Key Modules
- **`web/app.js`** – handles UI state, orchestrates the generator, updates the tracker view, and exposes copy/download helpers.
- **`web/js/generator.js`** – posts streaming chat completion requests and emits tracker steps as they arrive.
- **`web/js/trackerParser.js`** – provides both incremental parsing for live playback and full parsing for MIDI export.
- **`web/js/playback.js`** – Web Audio implementation that schedules oscillators/noise bursts for each instrument while respecting swing offsets.
- **`web/js/midi.js`** – minimal Standard MIDI File encoder supporting swing timing, per-instrument tracks, and drum accents.
- **`web/js/config.js`** – shared configuration surface (tempo, swing ratio, channel/program maps) used by every subsystem.

## Session Flow
1. Collect API credentials, base URL, tempo, swing, bar count, and optional player direction from the UI.
2. Build the quartet prompt in the browser and request a streaming chat completion.
3. Feed streamed deltas into the incremental tracker parser; render each new line and queue it into the playback engine.
4. When streaming completes, parse the accumulated tracker text into structured tracks and export a MIDI blob on demand.

## Extensibility Ideas
- Swap Web Audio voices for Web MIDI output to target hardware synths on capable browsers.
- Add persistence by storing the latest tracker/MIDI blobs in IndexedDB for offline replay.
- Layer in analytics/error reporting hooks for long-running sessions.
- Expand the UI with a library of preset prompts or saved grooves to speed up creative iteration.
