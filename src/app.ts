import { JazzGenerator } from './generator.js';
import { PlaybackEngine } from './playback.js';
import { MidiExporter } from './midi.js';
import { TrackerParser } from './trackerParser.js';
import { cloneConfig, DEFAULT_CONFIG } from './config.js';
import type { InstrumentName, RuntimeConfig } from './types.js';

const CONTEXT_STEPS = 32;
const TRACKER_INSTRUMENTS: InstrumentName[] = ['BASS', 'DRUMS', 'PIANO', 'SAX'];

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
const trackerOutput = requireElement<HTMLElement>(
  document.getElementById('tracker-output'),
  'Tracker output element missing.'
);
const startButton = requireElement<HTMLButtonElement>(
  document.getElementById('start-button'),
  'Start button missing.'
);
const stopButton = requireElement<HTMLButtonElement>(
  document.getElementById('stop-button'),
  'Stop button missing.'
);
const downloadButton = requireElement<HTMLButtonElement>(
  document.getElementById('download-midi'),
  'Download button missing.'
);
const copyButton = requireElement<HTMLButtonElement>(
  document.getElementById('copy-tracker'),
  'Copy button missing.'
);

let isRunning = false;
let generator = new JazzGenerator(DEFAULT_CONFIG);
let playback = new PlaybackEngine(DEFAULT_CONFIG);
let midiExporter = new MidiExporter(DEFAULT_CONFIG);
let displayedCounts: Record<InstrumentName, number> | null = null;
let latestTrackerText = '';
let latestConfig: RuntimeConfig = cloneConfig();
let pendingDownloadUrl: string | null = null;
let contextHistory = emptyInstrumentBuckets();
let contextTrimmed = {
  BASS: false,
  DRUMS: false,
  PIANO: false,
  SAX: false,
} as Record<InstrumentName, boolean>;

function setStatus(message: string, isError = false) {
  statusEl.textContent = message;
  statusEl.dataset.status = isError ? 'error' : 'info';
  statusEl.style.color = isError ? '#ff9a9a' : '';
}

function resetUI() {
  trackerOutput.textContent = '';
  displayedCounts = {
    BASS: 0,
    DRUMS: 0,
    PIANO: 0,
    SAX: 0,
  };
  latestTrackerText = '';
  resetContextHistory();
  if (pendingDownloadUrl) {
    URL.revokeObjectURL(pendingDownloadUrl);
    pendingDownloadUrl = null;
  }
  downloadButton.disabled = true;
  copyButton.disabled = true;
}

function appendTrackerLine(instrument: InstrumentName, line: string): number {
  if (!trackerOutput || !displayedCounts) return 0;
  const currentIndex = displayedCounts[instrument];
  const totalDisplayed =
    displayedCounts.BASS + displayedCounts.DRUMS + displayedCounts.PIANO + displayedCounts.SAX;
  const needsSeparator = totalDisplayed > 0 && instrumentOrderReset(line, currentIndex);
  if (currentIndex === 0 || needsSeparator) {
    trackerOutput.textContent += `${totalDisplayed > 0 ? '\n' : ''}${instrument}\n`;
  }
  trackerOutput.textContent += `${line}\n`;
  displayedCounts[instrument] = currentIndex + 1;
  trackerOutput.scrollTop = trackerOutput.scrollHeight;
  return currentIndex;
}

async function handleSubmit(event: SubmitEvent) {
  event.preventDefault();
  if (isRunning) return;

  const formData = new FormData(form);
  const apiKey = formData.get('apiKey')?.toString();
  const baseUrl = formData.get('baseUrl')?.toString() ?? '';
  const model = formData.get('model')?.toString() ?? '';
  const prompt = formData.get('prompt')?.toString() ?? '';
  const bars = Number.parseInt(formData.get('bars')?.toString() ?? '', 10) || DEFAULT_CONFIG.barsPerGeneration;
  const tempo = Number.parseInt(formData.get('tempo')?.toString() ?? '', 10) || DEFAULT_CONFIG.tempo;
  const swingEnabled = formData.get('swing') !== null;

  resetUI();
  setStatus('Preparing session…');

  isRunning = true;
  startButton.disabled = true;
  stopButton.disabled = false;

  latestConfig = cloneConfig({
    tempo,
    barsPerGeneration: bars,
    swingEnabled,
  });

  await playback.prepare(latestConfig);
  midiExporter.setConfig(latestConfig);

  try {
    await runContinuousGeneration({
      apiKey,
      baseUrl,
      model,
      prompt,
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
  }
}

function handleStop() {
  if (!isRunning) {
    playback.stopAll();
    setStatus('Playback stopped.');
    return;
  }
  generator.abort();
  playback.stopAll();
  setStatus('Session aborted by user.');
  isRunning = false;
  startButton.disabled = false;
  stopButton.disabled = true;
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

function instrumentOrderReset(line: string, currentIndex: number): boolean {
  if (currentIndex !== 0) {
    return /^\s*1[.\s]/.test(line);
  }
  return false;
}

function resetContextHistory(): void {
  contextHistory = emptyInstrumentBuckets();
  contextTrimmed = {
    BASS: false,
    DRUMS: false,
    PIANO: false,
    SAX: false,
  };
}

function emptyInstrumentBuckets(): Record<InstrumentName, string[]> {
  return {
    BASS: [],
    DRUMS: [],
    PIANO: [],
    SAX: [],
  };
}

function extractInstrumentSections(trackerText: string): Record<InstrumentName, string[]> {
  const sections = emptyInstrumentBuckets();
  let current: InstrumentName | null = null;
  for (const rawLine of trackerText.split(/\r?\n/)) {
    const trimmed = rawLine.trim();
    if (!trimmed) {
      continue;
    }
    if ((TRACKER_INSTRUMENTS as string[]).includes(trimmed)) {
      current = trimmed as InstrumentName;
      continue;
    }
    if (!current) {
      continue;
    }
    sections[current].push(trimmed);
  }
  return sections;
}

function stripLineNumber(line: string): string {
  return line.replace(/^\s*\d+\.?\s+/, '').trim();
}

function updateContextHistory(trackerText: string): void {
  const sections = extractInstrumentSections(trackerText);
  for (const instrument of TRACKER_INSTRUMENTS) {
    const existing = contextHistory[instrument];
    const additions = sections[instrument].map((entry) => stripLineNumber(entry));
    const combined = existing.concat(additions);
    const trimmed = combined.length > CONTEXT_STEPS;
    contextHistory[instrument] = trimmed ? combined.slice(-CONTEXT_STEPS) : combined;
    contextTrimmed[instrument] = trimmed;
  }
}

function buildPreviousContext(): string {
  const parts: string[] = [];
  for (const instrument of TRACKER_INSTRUMENTS) {
    const lines = contextHistory[instrument];
    if (!lines.length) continue;
    const prefix = contextTrimmed[instrument] ? '...' : '';
    parts.push(`${instrument} (recent):\n${prefix}${lines.join('\n')}`);
  }
  return parts.join('\n\n');
}

async function runContinuousGeneration(options: {
  apiKey?: string;
  baseUrl: string;
  model: string;
  prompt: string;
  bars: number;
  tempo: number;
  swingEnabled: boolean;
  swingRatio: number;
}): Promise<void> {
  while (isRunning) {
    const session = generator.streamSession({
      apiKey: options.apiKey,
      baseUrl: options.baseUrl,
      model: options.model,
      extraPrompt: options.prompt,
      previousContext: buildPreviousContext(),
      barsPerGeneration: options.bars,
      tempo: options.tempo,
      swingEnabled: options.swingEnabled,
      swingRatio: options.swingRatio,
      onTrackerLine: ({ instrument, stepIndex, step, line }) => {
        const globalIndex = appendTrackerLine(instrument, line);
        const playbackIndex = displayedCounts ? globalIndex : stepIndex;
        playback.enqueueStep(instrument, playbackIndex, step);
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
    updateContextHistory(result.trackerText);
    downloadButton.disabled = latestTrackerText.length === 0;
    copyButton.disabled = latestTrackerText.length === 0;
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
downloadButton.addEventListener('click', handleDownload);
copyButton.addEventListener('click', handleCopy);

setStatus('Idle – configure the session and start streaming.');
resetUI();
