import { midiToFrequency } from './trackerParser.js';
import { cloneConfig, totalSteps } from './config.js';

const DRUM_FREQUENCIES = {
  36: 60,
  38: 180,
  42: 4000,
  45: 200,
  46: 3500,
  48: 300,
  49: 8000,
  50: 420,
  51: 5000,
};

function velocityToGain(velocity) {
  return Math.max(0.05, Math.min(1, velocity / 127));
}

export class PlaybackEngine {
  constructor(baseConfig) {
    this.config = cloneConfig(baseConfig);
    this.context = null;
    this.destination = null;
    this.startTime = 0;
    this.activeVoices = {};
    this.started = false;
    this.noiseBuffer = null;
    this.resetVoices();
  }

  resetVoices() {
    this.activeVoices = {
      BASS: new Map(),
      PIANO: new Map(),
      SAX: new Map(),
    };
  }

  prepare(config) {
    this.config = cloneConfig(config);
    this.started = false;
    this.resetVoices();
    if (this.context && this.context.state === 'running') {
      this.stopAll();
    }
  }

  ensureContext() {
    if (!this.context) {
      this.context = new (window.AudioContext || window.webkitAudioContext)();
      this.destination = this.context.createGain();
      this.destination.gain.setValueAtTime(0.8, this.context.currentTime);
      this.destination.connect(this.context.destination);
    }
    if (this.context.state === 'suspended') {
      this.context.resume();
    }
    if (!this.started) {
      this.startTime = this.context.currentTime + 0.1;
      this.started = true;
    }
  }

  stopAll() {
    for (const map of Object.values(this.activeVoices)) {
      for (const voice of map.values()) {
        this._releaseVoice(voice, this.context?.currentTime || 0);
      }
      map.clear();
    }
  }

  shutdown() {
    this.stopAll();
    if (this.context) {
      this.context.close();
      this.context = null;
      this.destination = null;
    }
    this.started = false;
  }

  _stepDurationSeconds(stepIndex) {
    const quarter = 60 / this.config.tempo;
    const base = quarter / 4;
    const pairDuration = base * 2;
    const start = this._stepStartSeconds(stepIndex, quarter, base, pairDuration);
    const end = this._stepStartSeconds(stepIndex + 1, quarter, base, pairDuration);
    return Math.max(0.01, end - start);
  }

  _stepStartSeconds(stepIndex, quarter, base, pairDuration) {
    if (stepIndex >= totalSteps(this.config)) {
      return stepIndex * base; // fallback for final boundary
    }
    const pairIndex = Math.floor(stepIndex / 2);
    const pairStart = pairIndex * pairDuration;
    const isOffbeat = stepIndex % 2 === 1;
    if (!this.config.swingEnabled || !isOffbeat) {
      return pairStart;
    }
    return pairStart + pairDuration * this.config.swingRatio;
  }

  enqueueStep(instrument, stepIndex, step) {
    if (instrument === 'DRUMS') {
      return this._enqueueDrums(stepIndex, step);
    }
    if (step.isTie) {
      return; // sustain existing notes
    }
    this.ensureContext();
    const start = this.startTime + this._stepStartSeconds(stepIndex, 60 / this.config.tempo, (60 / this.config.tempo) / 4, (60 / this.config.tempo) / 2);
    this._stopInstrument(instrument, start);
    if (step.isRest) {
      return;
    }
    const duration = this._stepDurationSeconds(stepIndex);
    for (const note of step.notes) {
      this._startVoice(instrument, note, start, duration);
    }
  }

  _stopInstrument(instrument, atTime) {
    const voices = this.activeVoices[instrument];
    if (!voices) return;
    for (const voice of voices.values()) {
      this._releaseVoice(voice, atTime);
    }
    voices.clear();
  }

  _startVoice(instrument, note, startTime, duration) {
    this.ensureContext();
    const pitchKey = `${note.pitch}`;
    const osc = this.context.createOscillator();
    const gain = this.context.createGain();
    gain.gain.setValueAtTime(0, startTime);
    const sustainLevel = velocityToGain(note.velocity) * this._instrumentLevel(instrument);
    gain.gain.linearRampToValueAtTime(sustainLevel, startTime + 0.02);
    gain.gain.setTargetAtTime(0.0001, startTime + duration, 0.08);

    osc.frequency.setValueAtTime(midiToFrequency(note.pitch), startTime);
    osc.type = this._waveformFor(instrument);

    const voice = { osc, gain };
    osc.connect(gain).connect(this.destination);
    osc.start(startTime);
    osc.stop(startTime + duration + 1.2);
    this.activeVoices[instrument].set(pitchKey, voice);
  }

  _releaseVoice(voice, atTime) {
    if (!voice || !voice.gain) return;
    const releaseStart = Math.max(atTime, (this.context?.currentTime ?? 0));
    try {
      voice.gain.gain.cancelScheduledValues(releaseStart);
      voice.gain.gain.setValueAtTime(voice.gain.gain.value, releaseStart);
      voice.gain.gain.exponentialRampToValueAtTime(0.0001, releaseStart + 0.12);
      voice.osc.stop(releaseStart + 0.2);
    } catch (error) {
      console.warn('Failed to release voice', error);
    }
  }

  _waveformFor(instrument) {
    switch (instrument) {
      case 'BASS':
        return 'sawtooth';
      case 'PIANO':
        return 'triangle';
      case 'SAX':
        return 'square';
      default:
        return 'sine';
    }
  }

  _instrumentLevel(instrument) {
    switch (instrument) {
      case 'BASS':
        return 0.4;
      case 'PIANO':
        return 0.3;
      case 'SAX':
        return 0.25;
      default:
        return 0.3;
    }
  }

  _ensureNoiseBuffer() {
    if (this.noiseBuffer || !this.context) return;
    const buffer = this.context.createBuffer(1, this.context.sampleRate * 0.5, this.context.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < data.length; i += 1) {
      data[i] = Math.random() * 2 - 1;
    }
    this.noiseBuffer = buffer;
  }

  _enqueueDrums(stepIndex, step) {
    if (step.isRest || step.isTie) return;
    this.ensureContext();
    this._ensureNoiseBuffer();
    const start = this.startTime + this._stepStartSeconds(stepIndex, 60 / this.config.tempo, (60 / this.config.tempo) / 4, (60 / this.config.tempo) / 2);
    for (const note of step.notes) {
      this._triggerDrum(note.pitch, note.velocity, start);
    }
  }

  _triggerDrum(pitch, velocity, startTime) {
    const src = this.context.createBufferSource();
    src.buffer = this.noiseBuffer;
    const gain = this.context.createGain();
    const level = velocityToGain(velocity) * 0.8;
    gain.gain.setValueAtTime(0, startTime);
    gain.gain.linearRampToValueAtTime(level, startTime + 0.005);
    gain.gain.setTargetAtTime(0.0001, startTime + 0.08, 0.05);

    const filter = this.context.createBiquadFilter();
    filter.type = 'bandpass';
    filter.Q.value = 1;
    filter.frequency.setValueAtTime(DRUM_FREQUENCIES[pitch] || 800, startTime);

    src.connect(filter).connect(gain).connect(this.destination);
    src.start(startTime);
    src.stop(startTime + 0.3);
  }
}
