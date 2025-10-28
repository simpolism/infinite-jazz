import { JazzGenerator } from './js/generator.js';
import { PlaybackEngine } from './js/playback.js';
import { MidiExporter } from './js/midi.js';
import { TrackerParser } from './js/trackerParser.js';
import { cloneConfig, DEFAULT_CONFIG } from './js/config.js';

const form = document.getElementById('session-form');
const statusEl = document.getElementById('status');
const trackerOutput = document.getElementById('tracker-output');
const startButton = document.getElementById('start-button');
const stopButton = document.getElementById('stop-button');
const downloadButton = document.getElementById('download-midi');
const copyButton = document.getElementById('copy-tracker');

let isRunning = false;
let generator = new JazzGenerator(DEFAULT_CONFIG);
let playback = new PlaybackEngine(DEFAULT_CONFIG);
let midiExporter = new MidiExporter(DEFAULT_CONFIG);
let displayedCounts = null;
let latestTrackerText = '';
let previousTrackerContext = '';
let latestConfig = cloneConfig();
let pendingDownloadUrl = null;

function setStatus(message, isError = false) {
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

function appendTrackerLine(instrument, line) {
  if (displayedCounts[instrument] === 0) {
    trackerOutput.textContent += `${displayedCounts.BASS + displayedCounts.DRUMS + displayedCounts.PIANO + displayedCounts.SAX > 0 ? '\n' : ''}${instrument}\n`;
  }
  trackerOutput.textContent += `${line}\n`;
  displayedCounts[instrument] += 1;
  trackerOutput.scrollTop = trackerOutput.scrollHeight;
}

async function handleSubmit(event) {
  event.preventDefault();
  if (isRunning) return;

  const formData = new FormData(form);
  const apiKey = formData.get('apiKey');
  const baseUrl = formData.get('baseUrl');
  const model = formData.get('model');
  const prompt = formData.get('prompt') || '';
  const bars = Number.parseInt(formData.get('bars'), 10) || DEFAULT_CONFIG.barsPerGeneration;
  const tempo = Number.parseInt(formData.get('tempo'), 10) || DEFAULT_CONFIG.tempo;
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
    downloadButton.disabled = !latestTrackerText;
    copyButton.disabled = !latestTrackerText;
    setStatus('Ready – playback finished.');
  } catch (error) {
    console.error(error);
    setStatus(error.message || 'Generation failed.', true);
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
