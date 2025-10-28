# Infinite Jazz (Browser Edition)

A minimal, client-only interface for streaming jazz quartet generations from OpenAI-compatible chat completion endpoints. The web app captures tracker output in real time, keeps audio playback running in the browser, and lets you download the final performance as a MIDI file.

## Quick start

1. Serve the `web/` folder with any static file host:
   ```bash
   cd web
   python -m http.server 8080
   ```

2. Open `http://localhost:8080` in a modern browser (Chrome, Edge, Safari, or Firefox). No backend services or build steps are required.

3. Provide your API key, base URL, and model name for an OpenAI-format endpoint (for example, `https://api.openai.com/v1` with `gpt-4o-mini`). Add optional musical direction, then press **Start Generating**.

The app requests a streaming chat completion, parses tracker updates as they arrive, and schedules playback immediately so the performance never pauses while the model finishes.

## Features

- 🔑 **Zero-install client** – ship the `web/` directory to any static host.
- 🎛️ **Configurable sessions** – tweak tempo, swing, and bar count before you call the model.
- 🎧 **Continuous playback** – Web Audio voices mirror the tracker feed instrument by instrument.
- 💾 **Exports** – copy the tracker text or download the rendered MIDI file once the chorus finishes.

## Using the interface

1. **API settings** – supply an API key and base URL for an OpenAI-compatible `/v1/chat/completions` endpoint. Keys stay in the browser; they are never stored or sent anywhere else.
2. **Model selection** – enter the model ID exactly as your provider expects (e.g., `gpt-4o-mini`, `groq/llama-3.1-70b-versatile`).
3. **Player direction** – optionally add steering text that is appended to the core quartet prompt.
4. **Transport controls** – hit **Start Generating** to begin streaming. Use **Stop Playback** to silence voices or to abort an in-flight request.
5. **Exports** – once the model finishes, use **Download MIDI** for a `.mid` file or **Copy Tracker Text** to place the tracker transcript on your clipboard.

> **Tip:** Leave the API key blank to test the interface with mocked responses (open the DevTools console and emit manual tracker steps). Real playback requires a successful streaming response.

## Code structure

All logic lives in the `web/` directory:

- `index.html` – layout and markup for the single-page app.
- `styles.css` – lightweight styling and responsive grid.
- `app.js` – UI glue code, state management, and export handlers.
- `js/config.js` – shared musical defaults (tempo, swing, channels).
- `js/promptBuilder.js` – browser port of the quartet prompt scaffold.
- `js/generator.js` – fetches streaming completions and feeds tracker lines to the parser and UI.
- `js/trackerParser.js` – tracker parsing utilities and incremental stream parser.
- `js/playback.js` – Web Audio playback engine for bass, drums, piano, and sax voices.
- `js/midi.js` – minimal MIDI writer for exporting combined performances.

The browser orchestrates every stage: build the prompt, request streamed completions, parse tracker steps, schedule playback, and assemble a downloadable MIDI file—no Python runtime or server process needed.

## Deployment

Any static hosting solution works:

- GitHub Pages, Netlify, Vercel static exports
- S3 + CloudFront
- A simple Nginx/Apache directory listing

Make sure HTTPS is enabled if your endpoint requires secure origins for fetch requests.

## Limitations & future improvements

- The Web Audio instruments are intentionally simple (oscillators + filtered noise). Swap in Web MIDI or higher-fidelity synthesis if you have a hardware or software rig available.
- Drum articulation is derived from MIDI pitches in the tracker format. If your model outputs unconventional mappings, adjust `DRUM_FREQUENCIES` in `js/playback.js`.
- The app expects clean tracker headers and line numbering. The incremental parser skips malformed lines; consider reinforcing format examples in the prompt if your model drifts.
- Streaming error handling surfaces the raw API response. Wrap the fetch call or add retries if your provider needs them.

## License

This browser refresh keeps the project MIT licensed—see `LICENSE` for the full text.
