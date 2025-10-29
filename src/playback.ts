import { midiToFrequency } from './trackerParser.js';
import { cloneConfig, totalSteps } from './config.js';
import type { InstrumentName, RuntimeConfig, TrackerStep } from './types.js';

const DRUM_FREQUENCIES: Record<number, number> = {
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

function velocityToGain(velocity: number): number {
  return Math.max(0.05, Math.min(1, velocity / 127));
}

interface ActiveVoice {
  osc: OscillatorNode;
  gain: GainNode;
}

type VoiceRegistry = Record<Exclude<InstrumentName, 'DRUMS'>, Map<string, ActiveVoice>>;

export class PlaybackEngine {
  private config: RuntimeConfig;
  private context: AudioContext | null;
  private destination: GainNode | null;
  private startTime: number;
  private activeVoices: VoiceRegistry;
  private started: boolean;
  private noiseBuffer: AudioBuffer | null;

  constructor(baseConfig: RuntimeConfig) {
    this.config = cloneConfig(baseConfig);
    this.context = null;
    this.destination = null;
    this.startTime = 0;
    this.activeVoices = this.createVoiceRegistry();
    this.started = false;
    this.noiseBuffer = null;
  }

  prepare(config: RuntimeConfig): void {
    this.config = cloneConfig(config);
    this.started = false;
    this.activeVoices = this.createVoiceRegistry();
    if (this.context && this.context.state === 'running') {
      this.stopAll();
    }
  }

  enqueueStep(instrument: InstrumentName, stepIndex: number, step: TrackerStep): void {
    if (instrument === 'DRUMS') {
      this.enqueueDrums(stepIndex, step);
      return;
    }
    if (step.isTie) {
      return;
    }
    this.ensureContext();
    const context = this.context;
    if (!context) return;
    const start =
      this.startTime +
      this.stepStartSeconds(stepIndex, 60 / this.config.tempo, (60 / this.config.tempo) / 4, (60 / this.config.tempo) / 2);
    this.stopInstrument(instrument, start);
    if (step.isRest) {
      return;
    }
    const duration = this.stepDurationSeconds(stepIndex);
    for (const note of step.notes) {
      this.startVoice(instrument, note.pitch, note.velocity, start, duration);
    }
  }

  stopAll(): void {
    const context = this.context;
    for (const map of Object.values(this.activeVoices)) {
      for (const voice of map.values()) {
        this.releaseVoice(voice, context?.currentTime ?? 0);
      }
      map.clear();
    }
  }

  shutdown(): void {
    this.stopAll();
    if (this.context) {
      void this.context.close();
      this.context = null;
      this.destination = null;
    }
    this.started = false;
  }

  private createVoiceRegistry(): VoiceRegistry {
    return {
      BASS: new Map(),
      PIANO: new Map(),
      SAX: new Map(),
    };
  }

  private ensureContext(): void {
    if (!this.context) {
      const AudioContextCtor =
        window.AudioContext ?? (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!AudioContextCtor) {
        throw new Error('Web Audio is not supported in this browser.');
      }
      this.context = new AudioContextCtor();
      this.destination = this.context.createGain();
      this.destination.gain.setValueAtTime(0.8, this.context.currentTime);
      this.destination.connect(this.context.destination);
    }
    if (this.context.state === 'suspended') {
      void this.context.resume();
    }
    if (!this.started) {
      this.startTime = this.context.currentTime + 0.1;
      this.started = true;
    }
  }

  private stepDurationSeconds(stepIndex: number): number {
    const quarter = 60 / this.config.tempo;
    const base = quarter / 4;
    const pairDuration = base * 2;
    const start = this.stepStartSeconds(stepIndex, quarter, base, pairDuration);
    const end = this.stepStartSeconds(stepIndex + 1, quarter, base, pairDuration);
    return Math.max(0.01, end - start);
  }

  private stepStartSeconds(
    stepIndex: number,
    quarter: number,
    base: number,
    pairDuration: number
  ): number {
    if (stepIndex >= totalSteps(this.config)) {
      return stepIndex * base;
    }
    const pairIndex = Math.floor(stepIndex / 2);
    const pairStart = pairIndex * pairDuration;
    const isOffbeat = stepIndex % 2 === 1;
    if (!this.config.swingEnabled || !isOffbeat) {
      return pairStart;
    }
    return pairStart + pairDuration * this.config.swingRatio;
  }

  private stopInstrument(instrument: InstrumentName, atTime: number): void {
    if (instrument === 'DRUMS') return;
    const voices = this.activeVoices[instrument];
    const context = this.context;
    for (const voice of voices.values()) {
      this.releaseVoice(voice, atTime, context ?? undefined);
    }
    voices.clear();
  }

  private startVoice(
    instrument: InstrumentName,
    pitch: number,
    velocity: number,
    startTime: number,
    duration: number
  ): void {
    if (instrument === 'DRUMS') return;
    this.ensureContext();
    const context = this.context;
    const destination = this.destination;
    if (!context || !destination) return;
    const pitchKey = `${pitch}`;
    const osc = context.createOscillator();
    const gain = context.createGain();
    gain.gain.setValueAtTime(0, startTime);
    const sustainLevel = velocityToGain(velocity) * this.instrumentLevel(instrument);
    gain.gain.linearRampToValueAtTime(sustainLevel, startTime + 0.02);
    gain.gain.setTargetAtTime(0.0001, startTime + duration, 0.08);

    osc.frequency.setValueAtTime(midiToFrequency(pitch), startTime);
    osc.type = this.waveformFor(instrument);

    const voice: ActiveVoice = { osc, gain };
    osc.connect(gain).connect(destination);
    osc.start(startTime);
    osc.stop(startTime + duration + 1.2);
    this.activeVoices[instrument].set(pitchKey, voice);
  }

  private releaseVoice(voice: ActiveVoice, atTime: number, context?: AudioContext): void {
    const audioContext = context ?? this.context;
    if (!voice || !voice.gain || !audioContext) return;
    const releaseStart = Math.max(atTime, audioContext.currentTime);
    try {
      voice.gain.gain.cancelScheduledValues(releaseStart);
      voice.gain.gain.setValueAtTime(voice.gain.gain.value, releaseStart);
      voice.gain.gain.exponentialRampToValueAtTime(0.0001, releaseStart + 0.12);
      voice.osc.stop(releaseStart + 0.2);
    } catch (error) {
      console.warn('Failed to release voice', error);
    }
  }

  private waveformFor(instrument: InstrumentName): OscillatorType {
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

  private instrumentLevel(instrument: InstrumentName): number {
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

  private ensureNoiseBuffer(): void {
    if (this.noiseBuffer || !this.context) return;
    const sampleRate = this.context.sampleRate;
    const buffer = this.context.createBuffer(1, sampleRate * 0.5, sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < data.length; i += 1) {
      data[i] = Math.random() * 2 - 1;
    }
    this.noiseBuffer = buffer;
  }

  private enqueueDrums(stepIndex: number, step: TrackerStep): void {
    if (step.isRest || step.isTie) return;
    this.ensureContext();
    const context = this.context;
    if (!context) return;
    this.ensureNoiseBuffer();
    const start =
      this.startTime +
      this.stepStartSeconds(stepIndex, 60 / this.config.tempo, (60 / this.config.tempo) / 4, (60 / this.config.tempo) / 2);
    for (const note of step.notes) {
      this.triggerDrum(note.pitch, note.velocity, start);
    }
  }

  private triggerDrum(pitch: number, velocity: number, startTime: number): void {
    const context = this.context;
    const destination = this.destination;
    const noise = this.noiseBuffer;
    if (!context || !destination || !noise) return;
    const src = context.createBufferSource();
    src.buffer = noise;
    const gain = context.createGain();
    const level = velocityToGain(velocity) * 0.8;
    gain.gain.setValueAtTime(0, startTime);
    gain.gain.linearRampToValueAtTime(level, startTime + 0.005);
    gain.gain.setTargetAtTime(0.0001, startTime + 0.08, 0.05);

    const filter = context.createBiquadFilter();
    filter.type = 'bandpass';
    filter.Q.value = 1;
    filter.frequency.setValueAtTime(DRUM_FREQUENCIES[pitch] ?? 800, startTime);

    src.connect(filter).connect(gain).connect(destination);
    src.start(startTime);
    src.stop(startTime + 0.3);
  }
}
