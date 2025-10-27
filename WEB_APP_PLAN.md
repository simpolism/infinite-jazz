# Infinite Jazz Web App Plan

## 1. Service Architecture
- Wrap `InfiniteJazzApp` inside an async web server (FastAPI or Starlette).
- Maintain one generator instance per user session; use an async task to run `RealtimeJazzGenerator`.
- Expose REST endpoints for start/stop, tempo changes, and style/LLM selection.

## 2. Streaming Pipeline
- Replace the current audio backend with a `WebSocketPlayer` that serialises `mido.Message` events (timestamp + payload) into JSON.
- Buffer a small lead time (1–2 sections) before sending to smooth jitter.
- Encode tracker sections alongside MIDI events so the client can render patterns.

## 3. Client Delivery
- Use WebSockets for realtime delivery; fall back to Server-Sent Events for simpler deployments.
- Define a compact event schema, e.g. `{ "t": 1.245, "type": "note_on", "instrument": "SAX", "note": 64, "velocity": 82 }`.
- Store recent events in Redis or in-memory so late subscribers can catch up. Optional chunking for persistence.

## 4. Browser Playback
- Prefer the Web MIDI API to route events to local synths when available.
- Provide a WebAudio fallback via Tone.js or WebAudioFont; map instruments to appropriate patches.
- Implement a scheduler that converts relative timestamps into `AudioContext` callbacks with drift correction.

## 5. Controls & UX
- Add UI toggles for tempo, groove presets, backend model, and buffer length.
- Visualise tracker grids per instrument using the streamed tracker text.
- Offer download buttons for the latest tracker/MIDI bundle once a session ends.

## 6. Operational Concerns
- Keep server-side API keys (Groq/Ollama) hidden; clients request sessions with opaque IDs.
- Require users to supply **their own** Groq API key at session start; store only in-memory for the lifetime of that session.
- Rate-limit session creation and provide idle timeouts to reclaim generators.
- Instrument latency metrics (queue depth, skip counts) to monitor realtime health.

## 7. Next Steps
- Prototype the `WebSocketPlayer` by adapting `audio_output.RealtimePlayer` to push JSON instead of calling `send_message`.
- Stand up a FastAPI server with a proof-of-concept websocket endpoint streaming canned MIDI before wiring in the generator.
- Iterate on the browser scheduler using recorded event dumps to validate timing accuracy before connecting live generation.
