Cleanup / Refactor Ideas
========================

1. Centralize logging
   - Replace direct `print` usage with the `logging` module (supporting levels, structured output, reuse of `--verbose` flag).
   - Ensure background threads use the same logger to avoid interleaved console output.

2. Extract runtime configuration
   - Gather CLI overrides, tempo/resolution, and backend wiring into a dedicated dataclass or config object.
   - Makes it easier to pass configuration into unit tests and future GUIs while reducing global mutations in `config.py`.

3. Improve generator/test coverage
   - Add an integration test that exercises `RealtimeJazzGenerator` with mocked LLM and audio backend, verifying section counts and queue timing.
   - Provide fixtures for `ContinuousGenerator` so concurrent buffer behaviour is deterministically tested (no thread bleed between tests).

4. Separate concerns in MIDI conversion
   - Split trigger vs. sustain handling into helper methods to clarify control flow.
   - Document/validate step timing with unit tests to catch regressions when adjusting tempo or resolution logic.
