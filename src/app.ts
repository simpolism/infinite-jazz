import { JazzGenerator } from './generator.js';
import { PlaybackEngine, type PlaybackBackendName } from './playback.js';
import { MidiExporter } from './midi.js';
import { TrackerParser } from './trackerParser.js';
import { cloneConfig, DEFAULT_CONFIG } from './config.js';
import { TrackerContext } from './contextManager.js';
import { PromptBuilder } from './promptBuilder.js';
import { loadSettings, saveSettings, type StoredSettings } from './settings.js';
import type { RuntimeConfig } from './types.js';

const CONTEXT_STEPS = 32;

function requireElement<T extends Element>(value: Element | null, message: string): T {
  if (!value) {
    throw new Error(message);
  }
  return value as T;
}

const form = requireElement<HTMLFormElement>(
  document.getElementById('session-form'),
  'Unable to find session form.'
);
const statusEl = requireElement<HTMLElement>(document.getElementById('status'), 'Status element missing.');
const startButton = requireElement<HTMLButtonElement>(
  document.getElementById('start-button'),
  'Start button missing.'
);
const stopButton = requireElement<HTMLButtonElement>(
  document.getElementById('stop-button'),
  'Stop button missing.'
);
const playbackToggleButton = requireElement<HTMLButtonElement>(
  document.getElementById('toggle-playback'),
  'Playback toggle button missing.'
);
const downloadButton = requireElement<HTMLButtonElement>(
  document.getElementById('download-midi'),
  'Download button missing.'
);
const copyButton = requireElement<HTMLButtonElement>(
  document.getElementById('copy-tracker'),
  'Copy button missing.'
);
const promptEditor = requireElement<HTMLTextAreaElement>(
  document.getElementById('prompt-editor'),
  'Prompt editor missing.'
);
const promptSelect = requireElement<HTMLSelectElement>(
  document.getElementById('prompt-select'),
  'Prompt preset selector missing.'
);
const promptLoadButton = requireElement<HTMLButtonElement>(
  document.getElementById('prompt-load'),
  'Prompt load button missing.'
);
const promptSaveButton = requireElement<HTMLButtonElement>(
  document.getElementById('prompt-save'),
  'Prompt save button missing.'
);
const promptDeleteButton = requireElement<HTMLButtonElement>(
  document.getElementById('prompt-delete'),
  'Prompt delete button missing.'
);

const DEFAULT_PROMPT_ID = '__auto__';
const PROMPT_LIBRARY_KEY = 'infinite_jazz_prompt_library_v1';

interface PromptPreset {
  id: string;
  name: string;
  text: string;
}

let isRunning = false;
let generator = new JazzGenerator(DEFAULT_CONFIG);
let playback = new PlaybackEngine(DEFAULT_CONFIG);
let activePlaybackBackend: PlaybackBackendName = playback.getActiveBackend();
let isSwitchingPlayback = false;
let midiExporter = new MidiExporter(DEFAULT_CONFIG);
let latestTrackerText = '';
let latestConfig: RuntimeConfig = cloneConfig();
let pendingDownloadUrl: string | null = null;
const trackerContext = new TrackerContext(CONTEXT_STEPS);
let promptLibrary: PromptPreset[] = [];
let currentDefaultPrompt = '';

function setStatus(message: string, isError = false) {
  statusEl.textContent = message;
  statusEl.dataset.status = isError ? 'error' : 'info';
  statusEl.style.color = isError ? '#ff9a9a' : '';
}

function refreshPlaybackToggleControl(): void {
  const label =
    activePlaybackBackend === 'soundfont'
      ? 'Switch to External MIDI'
      : 'Switch to Soundfont';
  playbackToggleButton.textContent = label;
  playbackToggleButton.disabled = isRunning || isSwitchingPlayback;
  playbackToggleButton.dataset.mode = activePlaybackBackend;
}

function resetSessionState(): void {
  latestTrackerText = '';
  if (pendingDownloadUrl) {
    URL.revokeObjectURL(pendingDownloadUrl);
    pendingDownloadUrl = null;
  }
  downloadButton.disabled = true;
  copyButton.disabled = true;
}

function resetUI(): void {
  trackerContext.reset();
  resetSessionState();
}

function getRuntimeFormValues(): { tempo: number; bars: number; swingEnabled: boolean } {
  const barsField = form.elements.namedItem('bars') as HTMLInputElement | null;
  const tempoField = form.elements.namedItem('tempo') as HTMLInputElement | null;
  const swingField = form.elements.namedItem('swing') as HTMLInputElement | null;
  const bars = Number.parseInt(barsField?.value ?? '', 10) || DEFAULT_CONFIG.barsPerGeneration;
  const tempo = Number.parseInt(tempoField?.value ?? '', 10) || DEFAULT_CONFIG.tempo;
  const swingEnabled = Boolean(swingField?.checked ?? DEFAULT_CONFIG.swingEnabled);
  return { tempo, bars, swingEnabled };
}

function defaultPromptLabel(values: { tempo: number; bars: number; swingEnabled: boolean }): string {
  const swingLabel = values.swingEnabled ? 'swing' : 'straight';
  return `Current config – ${values.bars} bars @ ${values.tempo} BPM (${swingLabel})`;
}

function loadPromptLibraryFromStorage(): PromptPreset[] {
  try {
    const raw = window.localStorage.getItem(PROMPT_LIBRARY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as PromptPreset[];
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((preset) => typeof preset?.id === 'string' && typeof preset?.name === 'string' && typeof preset?.text === 'string')
      .map((preset) => ({ id: preset.id, name: preset.name, text: preset.text }));
  } catch (error) {
    console.warn('Failed to load prompt presets', error);
    return [];
  }
}

function savePromptLibraryToStorage(): void {
  try {
    window.localStorage.setItem(PROMPT_LIBRARY_KEY, JSON.stringify(promptLibrary));
  } catch (error) {
    console.warn('Failed to store prompt presets', error);
  }
}

function populatePromptSelect(selectedId?: string): void {
  const values = getRuntimeFormValues();
  const defaultLabel = defaultPromptLabel(values);
  promptSelect.innerHTML = '';

  const defaultOption = document.createElement('option');
  defaultOption.value = DEFAULT_PROMPT_ID;
  defaultOption.textContent = defaultLabel;
  promptSelect.append(defaultOption);

  for (const preset of promptLibrary) {
    const option = document.createElement('option');
    option.value = preset.id;
    option.textContent = preset.name;
    promptSelect.append(option);
  }

  const desired = selectedId ?? promptSelect.value ?? DEFAULT_PROMPT_ID;
  const valid =
    desired === DEFAULT_PROMPT_ID || promptLibrary.some((preset) => preset.id === desired);
  promptSelect.value = valid ? desired : DEFAULT_PROMPT_ID;
}

function refreshDefaultPrompt(): void {
  const { tempo, bars, swingEnabled } = getRuntimeFormValues();
  const config = cloneConfig({
    tempo,
    barsPerGeneration: bars,
    swingEnabled,
  });
  const builder = new PromptBuilder(config);
  currentDefaultPrompt = builder.buildQuartetPrompt({
    previousContext: '',
    extraPrompt: '',
  });
  const currentSelection = promptSelect.value;
  populatePromptSelect(currentSelection);
  if (promptSelect.value === DEFAULT_PROMPT_ID && !isRunning) {
    promptEditor.value = currentDefaultPrompt;
  }
}

function createPresetId(): string {
  return `preset-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

function handlePromptLoad(): void {
  const selection = promptSelect.value;
  if (selection === DEFAULT_PROMPT_ID) {
    promptEditor.value = currentDefaultPrompt;
    setStatus('Loaded current configuration prompt.');
    return;
  }
  const preset = promptLibrary.find((item) => item.id === selection);
  if (!preset) {
    setStatus('Selected prompt preset was not found.', true);
    return;
  }
  promptEditor.value = preset.text;
  setStatus(`Loaded prompt "${preset.name}".`);
  persistSettings();
}

function handlePromptSave(): void {
  const rawName = window.prompt('Save prompt as (name)', promptSelect.value === DEFAULT_PROMPT_ID ? '' : promptSelect.selectedOptions[0]?.text ?? '');
  if (!rawName) return;
  const name = rawName.trim();
  if (!name) return;
  const existing = promptLibrary.find((preset) => preset.name.toLowerCase() === name.toLowerCase());
  if (existing) {
    existing.text = promptEditor.value;
    savePromptLibraryToStorage();
    populatePromptSelect(existing.id);
    promptSelect.value = existing.id;
    setStatus(`Updated prompt "${existing.name}".`);
  } else {
    const preset: PromptPreset = {
      id: createPresetId(),
      name,
      text: promptEditor.value,
    };
    promptLibrary.push(preset);
    savePromptLibraryToStorage();
    populatePromptSelect(preset.id);
    promptSelect.value = preset.id;
    setStatus(`Saved new prompt "${preset.name}".`);
  }
  persistSettings();
}

function handlePromptDelete(): void {
  const selection = promptSelect.value;
  if (selection === DEFAULT_PROMPT_ID) {
    setStatus('Cannot delete the auto-generated prompt.', true);
    return;
  }
  const presetIndex = promptLibrary.findIndex((preset) => preset.id === selection);
  if (presetIndex === -1) {
    setStatus('Selected prompt preset was not found.', true);
    return;
  }
  const preset = promptLibrary[presetIndex];
  const confirmed = window.confirm(`Delete saved prompt "${preset.name}"?`);
  if (!confirmed) return;
  promptLibrary.splice(presetIndex, 1);
  savePromptLibraryToStorage();
  populatePromptSelect(DEFAULT_PROMPT_ID);
  promptSelect.value = DEFAULT_PROMPT_ID;
  promptEditor.value = currentDefaultPrompt;
  setStatus(`Deleted prompt "${preset.name}".`);
  persistSettings();
}

async function handleSubmit(event: SubmitEvent) {
  event.preventDefault();
  if (isRunning) return;

  const formData = new FormData(form);
  persistSettings();
  const apiKey = formData.get('apiKey')?.toString();
  const baseUrl = formData.get('baseUrl')?.toString() ?? '';
  const model = formData.get('model')?.toString() ?? '';
  const bars = Number.parseInt(formData.get('bars')?.toString() ?? '', 10) || DEFAULT_CONFIG.barsPerGeneration;
  const tempo = Number.parseInt(formData.get('tempo')?.toString() ?? '', 10) || DEFAULT_CONFIG.tempo;
  const swingEnabled = formData.get('swing') !== null;
  const promptOverride = promptEditor.value;

  resetUI();
  setStatus('Preparing session…');

  isRunning = true;
  startButton.disabled = true;
  stopButton.disabled = false;
  refreshPlaybackToggleControl();

  latestConfig = cloneConfig({
    tempo,
    barsPerGeneration: bars,
    swingEnabled,
  });
  refreshDefaultPrompt();

  try {
    activePlaybackBackend = await playback.prepare(latestConfig);
  } catch (error) {
    const err = error as Error;
    console.error(err);
    setStatus(err.message || 'Unable to initialize playback.', true);
    isRunning = false;
    startButton.disabled = false;
    stopButton.disabled = true;
    refreshPlaybackToggleControl();
    return;
  }

  refreshPlaybackToggleControl();
  midiExporter.setConfig(latestConfig);

  try {
    await runContinuousGeneration({
      apiKey,
      baseUrl,
      model,
      promptOverride,
      bars,
      tempo,
      swingEnabled,
      swingRatio: latestConfig.swingRatio,
    });
  } catch (error) {
    const err = error as Error;
    console.error(err);
    setStatus(err.message || 'Generation failed.', true);
  } finally {
    isRunning = false;
    startButton.disabled = false;
    stopButton.disabled = true;
    refreshPlaybackToggleControl();
  }
}

function handleStop() {
  if (!isRunning) {
    playback.stopAll();
    setStatus('Playback stopped.');
    downloadButton.disabled = latestTrackerText.length === 0;
    copyButton.disabled = latestTrackerText.length === 0;
    refreshPlaybackToggleControl();
    return;
  }
  generator.abort();
  playback.stopAll();
  setStatus('Session aborted by user.');
  isRunning = false;
  trackerContext.reset();
  downloadButton.disabled = latestTrackerText.length === 0;
  copyButton.disabled = latestTrackerText.length === 0;
  startButton.disabled = false;
  stopButton.disabled = true;
  refreshPlaybackToggleControl();
}

async function handleCopy() {
  if (!latestTrackerText) return;
  try {
    await navigator.clipboard.writeText(latestTrackerText);
    setStatus('Tracker data copied to clipboard.');
  } catch (error) {
    console.error(error);
    setStatus('Unable to copy tracker to clipboard.', true);
  }
}

function handleDownload() {
  if (!latestTrackerText) return;
  try {
    const tracks = TrackerParser.parse(latestTrackerText);
    const blob = midiExporter.createFile(tracks);
    if (pendingDownloadUrl) {
      URL.revokeObjectURL(pendingDownloadUrl);
    }
    pendingDownloadUrl = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = pendingDownloadUrl;
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    anchor.download = `infinite-jazz-${timestamp}.mid`;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    setStatus('MIDI file downloaded.');
  } catch (error) {
    console.error(error);
    setStatus('Unable to build MIDI file.', true);
  }
}

async function handlePlaybackToggle(): Promise<void> {
  if (isRunning || isSwitchingPlayback) return;
  const target: PlaybackBackendName = activePlaybackBackend === 'soundfont' ? 'midi' : 'soundfont';
  isSwitchingPlayback = true;
  refreshPlaybackToggleControl();
  try {
    const nextBackend = await playback.useBackend(latestConfig, target);
    activePlaybackBackend = nextBackend;
    if (nextBackend === target) {
      const message =
        nextBackend === 'midi'
          ? 'External MIDI playback enabled.'
          : 'Soundfont playback enabled.';
      setStatus(message);
    } else if (target === 'midi') {
      setStatus('External MIDI output unavailable – continuing with built-in soundfont.', true);
    } else {
      setStatus('Switched back to soundfont playback.');
    }
  } catch (error) {
    const err = error as Error;
    console.error(err);
    setStatus(err.message || 'Unable to change playback backend.', true);
  } finally {
    isSwitchingPlayback = false;
    refreshPlaybackToggleControl();
  }
}

function applyStoredSettings(): void {
  const storedSettings = loadSettings();
  const apiKeyField = form.elements.namedItem('apiKey') as HTMLInputElement | null;
  const baseUrlField = form.elements.namedItem('baseUrl') as HTMLInputElement | null;
  const modelField = form.elements.namedItem('model') as HTMLInputElement | null;
  const barsField = form.elements.namedItem('bars') as HTMLInputElement | null;
  const tempoField = form.elements.namedItem('tempo') as HTMLInputElement | null;
  const swingField = form.elements.namedItem('swing') as HTMLInputElement | null;

  if (apiKeyField && storedSettings.apiKey) apiKeyField.value = storedSettings.apiKey;
  if (baseUrlField && storedSettings.baseUrl) baseUrlField.value = storedSettings.baseUrl;
  if (modelField && storedSettings.model) modelField.value = storedSettings.model;
  if (barsField && typeof storedSettings.bars === 'number') barsField.value = String(storedSettings.bars);
  if (tempoField && typeof storedSettings.tempo === 'number') tempoField.value = String(storedSettings.tempo);
  if (swingField && typeof storedSettings.swing === 'boolean') swingField.checked = storedSettings.swing;

  refreshDefaultPrompt();

  if (typeof storedSettings.prompt === 'string' && storedSettings.prompt.length > 0) {
    promptEditor.value = storedSettings.prompt;
  } else {
    promptEditor.value = currentDefaultPrompt;
  }
  populatePromptSelect(promptSelect.value);
}

function extractSettings(formData: FormData): StoredSettings {
  const next: StoredSettings = {
    apiKey: formData.get('apiKey')?.toString() ?? '',
    baseUrl: formData.get('baseUrl')?.toString() ?? '',
    model: formData.get('model')?.toString() ?? '',
    bars: Number.parseInt(formData.get('bars')?.toString() ?? '', 10),
    tempo: Number.parseInt(formData.get('tempo')?.toString() ?? '', 10),
    swing: formData.get('swing') !== null,
  };
  if (Number.isNaN(next.bars)) {
    delete next.bars;
  }
  if (Number.isNaN(next.tempo)) {
    delete next.tempo;
  }
  if (!next.apiKey) delete next.apiKey;
  if (!next.baseUrl) delete next.baseUrl;
  if (!next.model) delete next.model;
  const promptTextRaw = promptEditor.value;
  const promptText = promptTextRaw.trim();
  if (promptText) {
    next.prompt = promptTextRaw;
  } else {
    delete next.prompt;
  }
  return next;
}

function persistSettings(): void {
  const formData = new FormData(form);
  const settings = extractSettings(formData);
  saveSettings(settings);
}

function handleFormChange(): void {
  persistSettings();
  refreshDefaultPrompt();
}

async function runContinuousGeneration(options: {
  apiKey?: string;
  baseUrl: string;
  model: string;
  promptOverride: string;
  bars: number;
  tempo: number;
  swingEnabled: boolean;
  swingRatio: number;
}): Promise<void> {
  let sectionIndex = 0;
  while (isRunning) {
    setStatus(`Generating section ${sectionIndex + 1}…`);
    const session = generator.streamSession({
      apiKey: options.apiKey,
      baseUrl: options.baseUrl,
      model: options.model,
      promptOverride: options.promptOverride,
      previousContext: trackerContext.buildPromptChunk(),
      barsPerGeneration: options.bars,
      tempo: options.tempo,
      swingEnabled: options.swingEnabled,
      swingRatio: options.swingRatio,
      onTrackerLine: ({ instrument, stepIndex, step }) => {
        playback.enqueueStep(instrument, stepIndex, step);
      },
      onStatus: (message) => setStatus(message),
    });

    let result: Awaited<typeof session>;
    try {
      result = await session;
    } catch (error) {
      if (!isRunning) {
        break;
      }
      throw error;
    }

    if (!isRunning) {
      break;
    }

    if (result?.aborted) {
      setStatus('Generation aborted.');
      break;
    }

    latestTrackerText = result.trackerText;
    trackerContext.incorporate(result.trackerText);
    downloadButton.disabled = latestTrackerText.length === 0;
    copyButton.disabled = latestTrackerText.length === 0;
    sectionIndex += 1;
    setStatus('Section complete – generating next…');
  }

  if (!isRunning) {
    setStatus('Session aborted by user.');
  } else {
    setStatus('Ready – playback finished.');
  }
}

form.addEventListener('submit', handleSubmit);
stopButton.addEventListener('click', handleStop);
playbackToggleButton.addEventListener('click', handlePlaybackToggle);
downloadButton.addEventListener('click', handleDownload);
copyButton.addEventListener('click', handleCopy);
form.addEventListener('change', handleFormChange);
promptLoadButton.addEventListener('click', handlePromptLoad);
promptSaveButton.addEventListener('click', handlePromptSave);
promptDeleteButton.addEventListener('click', handlePromptDelete);
promptEditor.addEventListener('input', () => {
  persistSettings();
});

promptLibrary = loadPromptLibraryFromStorage();
populatePromptSelect(DEFAULT_PROMPT_ID);
applyStoredSettings();
resetUI();
refreshPlaybackToggleControl();
setStatus('Idle – configure the session and start streaming.');
