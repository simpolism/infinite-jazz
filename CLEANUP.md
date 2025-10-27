# Infinite Jazz – Cleanup Roadmap

Outstanding refactors and polish tasks, ordered by impact.

1. **Introduce a runtime config object**
   - Replace mutable globals in `config.py` with an immutable dataclass (e.g., `RuntimeConfig`).
   - Pass the config explicitly into `RealtimeJazzGenerator`, `ContinuousGenerator`, `MIDIConverter`, and `get_batched_quartet_prompt` so CLI overrides stay scoped and future tests can inject variants.

2. **Consolidate playback scheduling**
   - Reuse or replace `audio_output.RealtimePlayer` rather than keeping a parallel queue/thread loop inside `RealtimeJazzGenerator`.
   - Extract a `PlaybackController` to own queue creation, worker lifecycle, and shutdown, leaving the app class to orchestrate high-level flow.

3. **Split orchestration into an application layer**
   - Move argument parsing into a thin CLI wrapper and create an `App` (or `InfiniteJazzService`) that wires together config, LLM interface, generator, and playback.
   - This enables both CLI and future GUI/API entrypoints to reuse the same lifecycle management.

4. **Refine the LLM adapter**
   - Separate backend selection/logging from prompt splitting and retries; expose a minimal interface for generation plus structured telemetry (latency, token counts).
   - Consider surfacing backend-specific errors with actionable messages before they bubble into the main loop.

5. **Add automated regression coverage**
   - Introduce smoke tests that mock `LLMInterface.generate` to feed deterministic tracker text and verify buffering, MIDI conversion, and save/export flows.
   - Add a static prompt-format validator to guard against regressions when editing `prompts.py`.

6. **Encapsulate prompt templates**
   - Convert the global string builder into a small `PromptBuilder` class that can swap styles (e.g., bebop, modal) and respond to future config flags without touching module-level state.

7. **Documentation follow-ups**
   - Rename the repository folder/package to `infinite_jazz` for consistency with the new branding.
   - Expand README setup notes for hardware MIDI users (driver expectations, ALSA/JACK tips) and clarify performance requirements for Groq tiers.
