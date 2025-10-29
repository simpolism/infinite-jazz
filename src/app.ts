import { JazzGenerator } from './generator.js';
import { PlaybackEngine } from './playback.js';
import { MidiExporter } from './midi.js';
import { TrackerParser } from './trackerParser.js';
import { cloneConfig, DEFAULT_CONFIG } from './config.js';
import type { InstrumentName, RuntimeConfig } from './types.js';

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
let previousTrackerContext = '';
let latestConfig: RuntimeConfig = cloneConfig();
let pendingDownloadUrl: string | null = null;

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
  if (pendingDownloadUrl) {
    URL.revokeObjectURL(pendingDownloadUrl);
    pendingDownloadUrl = null;
  }
  downloadButton.disabled = true;
  copyButton.disabled = true;
}

function appendTrackerLine(instrument: InstrumentName, line: string) {
  if (!trackerOutput || !displayedCounts) return;
  const totalDisplayed =
    displayedCounts.BASS + displayedCounts.DRUMS + displayedCounts.PIANO + displayedCounts.SAX;
  if (displayedCounts[instrument] === 0) {
    trackerOutput.textContent += `${totalDisplayed > 0 ? '\n' : ''}${instrument}\n`;
  }
  trackerOutput.textContent += `${line}\n`;
  displayedCounts[instrument] += 1;
  trackerOutput.scrollTop = trackerOutput.scrollHeight;
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

  playback.prepare(latestConfig);
  midiExporter.setConfig(latestConfig);

  try {
    const result = await generator.streamSession({
      apiKey,
      baseUrl,
      model,
      extraPrompt: prompt,
      previousContext: previousTrackerContext,
      barsPerGeneration: bars,
      tempo,
      swingEnabled,
      swingRatio: latestConfig.swingRatio,
      onTrackerLine: ({ instrument, stepIndex, step, line }) => {
        appendTrackerLine(instrument, line);
        playback.enqueueStep(instrument, stepIndex, step);
      },
      onStatus: (message) => setStatus(message),
    });

    if (result?.aborted) {
      setStatus('Generation aborted.');
      return;
    }

    latestTrackerText = result.trackerText;
    previousTrackerContext = result.trackerText;
    downloadButton.disabled = latestTrackerText.length === 0;
    copyButton.disabled = latestTrackerText.length === 0;
    setStatus('Ready – playback finished.');
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

form.addEventListener('submit', handleSubmit);
stopButton.addEventListener('click', handleStop);
downloadButton.addEventListener('click', handleDownload);
copyButton.addEventListener('click', handleCopy);

setStatus('Idle – configure the session and start streaming.');
resetUI();
