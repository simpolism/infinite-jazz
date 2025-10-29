import { cloneConfig, totalSteps } from './config.js';
import type { InstrumentName, RuntimeConfig, TrackerStep } from './types.js';
import { createSynthesizer, applyProgramMap, FluidSynthBridge, DRUM_CHANNEL } from './soundfontBridge.js';

type MelodicInstrument = Exclude<InstrumentName, 'DRUMS'>;

type MidiVoiceRegistry = Record<InstrumentName, Set<number>>;

type ScheduledNote = {
  pitch: number;
  timerOn: number;
  timerOff: number;
};

type ScheduledNoteRegistry = Record<MelodicInstrument, Map<string, ScheduledNote>>;

interface PlaybackBackend {
  prepare(config: RuntimeConfig): Promise<boolean> | boolean;
  enqueueStep(instrument: InstrumentName, stepIndex: number, step: TrackerStep): void;
  stopAll(): void;
  shutdown(): void;
}

export type PlaybackBackendName = 'soundfont' | 'midi';

export class PlaybackEngine {
  private midiBackend: WebMidiPlayback;
  private synthBackend: SoundfontPlayback;
  private activeBackend: PlaybackBackend;
  private preferredBackend: PlaybackBackendName;
  private activeBackendName: PlaybackBackendName;

  constructor(baseConfig: RuntimeConfig) {
    this.midiBackend = new WebMidiPlayback(baseConfig);
    this.synthBackend = new SoundfontPlayback(baseConfig);
    this.activeBackend = this.synthBackend;
    this.preferredBackend = 'soundfont';
    this.activeBackendName = 'soundfont';
  }

  async prepare(config: RuntimeConfig): Promise<PlaybackBackendName> {
    this.stopAll();
    const order: PlaybackBackendName[] =
      this.preferredBackend === 'midi' ? ['midi', 'soundfont'] : ['soundfont', 'midi'];
    let lastError: unknown = null;

    for (const backendName of order) {
      const backend = backendName === 'midi' ? this.midiBackend : this.synthBackend;
      try {
        const ready = await backend.prepare(config);
        if (!ready) {
          backend.shutdown();
          continue;
        }
        this.activeBackend = backend;
        this.activeBackendName = backendName;
        this.preferredBackend = backendName;
        if (backendName === 'midi') {
          this.synthBackend.shutdown();
        } else {
          this.midiBackend.shutdown();
        }
        return backendName;
      } catch (error) {
        lastError = error;
        backend.shutdown();
      }
    }

    this.activeBackend = this.synthBackend;
    this.activeBackendName = 'soundfont';

    if (lastError instanceof Error) {
      throw lastError;
    }
    throw new Error('No playback backend available.');
  }

  async useBackend(config: RuntimeConfig, backendName: PlaybackBackendName): Promise<PlaybackBackendName> {
    this.preferredBackend = backendName;
    return this.prepare(config);
  }

  getActiveBackend(): PlaybackBackendName {
    return this.activeBackendName;
  }

  enqueueStep(instrument: InstrumentName, stepIndex: number, step: TrackerStep): void {
    this.activeBackend.enqueueStep(instrument, stepIndex, step);
  }

  stopAll(): void {
    this.midiBackend.stopAll();
    this.synthBackend.stopAll();
  }

  shutdown(): void {
    this.midiBackend.shutdown();
    this.synthBackend.shutdown();
  }
}

class SoundfontPlayback implements PlaybackBackend {
  private config: RuntimeConfig;
  private context: AudioContext | null;
  private synth: FluidSynthBridge | null;
  private started: boolean;
  private startTime: number;
  private scheduled: ScheduledNoteRegistry;
  private drumTimers: number[];
  private noteCounter: number;

  constructor(baseConfig: RuntimeConfig) {
    this.config = cloneConfig(baseConfig);
    this.context = null;
    this.synth = null;
    this.started = false;
    this.startTime = 0;
    this.scheduled = this.createScheduleRegistry();
    this.drumTimers = [];
    this.noteCounter = 0;
  }

  private createScheduleRegistry(): ScheduledNoteRegistry {
    return {
      BASS: new Map(),
      PIANO: new Map(),
      SAX: new Map(),
    };
  }

  async prepare(config: RuntimeConfig): Promise<boolean> {
    this.config = cloneConfig(config);
    this.cancelAllTimers();
    this.scheduled = this.createScheduleRegistry();
    this.noteCounter = 0;
    if (!this.context) {
      const AudioContextCtor =
        window.AudioContext ?? (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!AudioContextCtor) {
        throw new Error('Web Audio is not supported in this browser.');
      }
      this.context = new AudioContextCtor();
    }
    if (this.context.state === 'suspended') {
      await this.context.resume();
    }
    if (!this.synth) {
      this.synth = await createSynthesizer(this.context);
    }
    applyProgramMap(this.synth, this.config);
    this.started = false;
    this.startTime = this.context.currentTime + 0.1;
    return true;
  }

  enqueueStep(instrument: InstrumentName, stepIndex: number, step: TrackerStep): void {
    if (!this.context || !this.synth) {
      return;
    }
    const start =
      this.startTime +
      this.stepStartSeconds(stepIndex, 60 / this.config.tempo, (60 / this.config.tempo) / 4, (60 / this.config.tempo) / 2);
    if (!this.started) {
      this.started = true;
    }
    if (instrument === 'DRUMS') {
      this.scheduleDrums(step, start);
      return;
    }
    const melodicInstrument = instrument as MelodicInstrument;
    this.stopInstrument(melodicInstrument);
    if (step.isRest || step.isTie) {
      return;
    }
    const duration = this.stepDurationSeconds(stepIndex);
    for (const note of step.notes) {
      this.scheduleNote(melodicInstrument, note.pitch, note.velocity, start, duration);
    }
  }

  stopAll(): void {
    this.cancelAllTimers();
    this.scheduled = this.createScheduleRegistry();
    if (this.synth) {
      this.synth.allSoundsOff();
    }
  }

  shutdown(): void {
    this.stopAll();
    if (this.synth) {
      this.synth.disconnect();
      this.synth = null;
    }
    if (this.context) {
      void this.context.close();
      this.context = null;
    }
  }

  private cancelAllTimers(): void {
    for (const map of Object.values(this.scheduled)) {
      for (const entry of map.values()) {
        window.clearTimeout(entry.timerOn);
        window.clearTimeout(entry.timerOff);
      }
      map.clear();
    }
    for (const timer of this.drumTimers) {
      window.clearTimeout(timer);
    }
    this.drumTimers = [];
  }

  private scheduleNote(instrument: MelodicInstrument, pitch: number, velocity: number, startTime: number, duration: number): void {
    if (!this.context || !this.synth) return;
    const channel = this.config.channels[instrument];
    const now = this.context.currentTime;
    const delayMs = Math.max(0, (startTime - now) * 1000);
    const sustainMs = Math.max(50, duration * 1000);

    const onTimer = window.setTimeout(() => {
      this.synth?.noteOn(channel, pitch, Math.max(1, Math.min(127, velocity)));
    }, delayMs);
    const offTimer = window.setTimeout(() => {
      this.synth?.noteOff(channel, pitch);
    }, delayMs + sustainMs);

    const key = `${pitch}-${this.noteCounter++}`;
    this.scheduled[instrument].set(key, { pitch, timerOn: onTimer, timerOff: offTimer });
  }

  private scheduleDrums(step: TrackerStep, startTime: number): void {
    if (!this.context || !this.synth) return;
    if (step.isRest || step.isTie) return;
    const now = this.context.currentTime;
    const delayMs = Math.max(0, (startTime - now) * 1000);
    for (const note of step.notes) {
      const onTimer = window.setTimeout(() => {
        if (!this.synth) return;
        this.synth.noteOn(DRUM_CHANNEL, note.pitch, Math.max(1, Math.min(127, note.velocity)));
        const offTimer = window.setTimeout(() => {
          this.synth?.noteOff(DRUM_CHANNEL, note.pitch);
        }, 120);
        this.drumTimers.push(offTimer);
      }, delayMs);
      this.drumTimers.push(onTimer);
    }
  }

  private stopInstrument(instrument: MelodicInstrument): void {
    const voices = this.scheduled[instrument];
    for (const timers of Array.from(voices.values())) {
      window.clearTimeout(timers.timerOn);
      window.clearTimeout(timers.timerOff);
      this.synth?.noteOff(this.config.channels[instrument], timers.pitch);
    }
    voices.clear();
  }

  private stepDurationSeconds(stepIndex: number): number {
    const quarter = 60 / this.config.tempo;
    const base = quarter / 4;
    const pairDuration = base * 2;
    const start = this.stepStartSeconds(stepIndex, quarter, base, pairDuration);
    const end = this.stepStartSeconds(stepIndex + 1, quarter, base, pairDuration);
    return Math.max(0.05, end - start);
  }

  private stepStartSeconds(stepIndex: number, quarter: number, base: number, pairDuration: number): number {
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
}

class WebMidiPlayback implements PlaybackBackend {
  private config: RuntimeConfig;
  private midiAccess: MIDIAccess | null;
  private midiOutput: MIDIOutput | null;
  private midiStartTimeMs: number;
  private midiVoices: MidiVoiceRegistry;
  private active: boolean;

  constructor(baseConfig: RuntimeConfig) {
    this.config = cloneConfig(baseConfig);
    this.midiAccess = null;
    this.midiOutput = null;
    this.midiStartTimeMs = performance.now();
    this.midiVoices = {
      BASS: new Set(),
      DRUMS: new Set(),
      PIANO: new Set(),
      SAX: new Set(),
    };
    this.active = false;
  }

  async prepare(config: RuntimeConfig): Promise<boolean> {
    this.config = cloneConfig(config);
    this.midiVoices = {
      BASS: new Set(),
      DRUMS: new Set(),
      PIANO: new Set(),
      SAX: new Set(),
    };
    this.midiStartTimeMs = performance.now() + 200;

    if (!('requestMIDIAccess' in navigator)) {
      this.clearMidi();
      this.active = false;
      return false;
    }

    try {
      this.midiAccess = await navigator.requestMIDIAccess();
      const outputs = Array.from(this.midiAccess.outputs.values());
      this.midiOutput = outputs[0] ?? null;
      this.active = Boolean(this.midiOutput);
      if (this.active) {
        this.sendProgramChanges();
      }
    } catch (error) {
      console.warn('Failed to initialize Web MIDI output', error);
      this.clearMidi();
      this.active = false;
    }

    return this.active;
  }

  enqueueStep(instrument: InstrumentName, stepIndex: number, step: TrackerStep): void {
    if (!this.active || !this.midiOutput) {
      return;
    }
    if (step.isTie) {
      return;
    }

    const startSeconds = this.stepStartSeconds(stepIndex, 60 / this.config.tempo, (60 / this.config.tempo) / 4, (60 / this.config.tempo) / 2);
    const startTimeMs = this.midiStartTimeMs + startSeconds * 1000;

    if (instrument === 'DRUMS') {
      this.enqueueMidiDrums(step, startTimeMs);
      return;
    }

    this.stopMidiInstrument(instrument, startTimeMs);
    if (step.isRest) {
      return;
    }
    const durationMs = this.stepDurationSeconds(stepIndex) * 1000;
    const channel = this.config.channels[instrument];
    for (const note of step.notes) {
      const velocity = Math.max(1, Math.min(127, note.velocity));
      this.midiOutput.send([0x90 | channel, note.pitch, velocity], startTimeMs);
      this.midiOutput.send([0x80 | channel, note.pitch, 0], startTimeMs + durationMs);
      this.midiVoices[instrument].add(note.pitch);
    }
  }

  stopAll(): void {
    if (!this.midiOutput) return;
    const now = performance.now();
    for (const instrument of Object.keys(this.midiVoices) as InstrumentName[]) {
      this.stopMidiInstrument(instrument, now);
      const channel = this.config.channels[instrument];
      this.midiOutput.send([0xb0 | channel, 120, 0], now);
      this.midiOutput.send([0xb0 | channel, 123, 0], now);
    }
  }

  shutdown(): void {
    this.stopAll();
    this.clearMidi();
    this.active = false;
  }

  private clearMidi(): void {
    this.midiOutput = null;
    this.midiAccess = null;
  }

  private stepDurationSeconds(stepIndex: number): number {
    const quarter = 60 / this.config.tempo;
    const base = quarter / 4;
    const pairDuration = base * 2;
    const start = this.stepStartSeconds(stepIndex, quarter, base, pairDuration);
    const end = this.stepStartSeconds(stepIndex + 1, quarter, base, pairDuration);
    return Math.max(0.05, end - start);
  }

  private stepStartSeconds(stepIndex: number, quarter: number, base: number, pairDuration: number): number {
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

  private enqueueMidiDrums(step: TrackerStep, startTimeMs: number): void {
    if (!this.midiOutput) return;
    if (step.isRest || step.isTie) return;
    const channel = this.config.channels.DRUMS;
    for (const note of step.notes) {
      const velocity = Math.max(1, Math.min(127, note.velocity));
      this.midiOutput.send([0x99 | channel, note.pitch, velocity], startTimeMs);
      this.midiOutput.send([0x89 | channel, note.pitch, 0], startTimeMs + 120);
      this.midiVoices.DRUMS.add(note.pitch);
    }
  }

  private stopMidiInstrument(instrument: InstrumentName, atTimeMs: number): void {
    if (!this.midiOutput) return;
    const channel = this.config.channels[instrument];
    const voices = this.midiVoices[instrument];
    voices.forEach((pitch) => {
      const status = instrument === 'DRUMS' ? 0x89 : 0x80;
      this.midiOutput!.send([status | channel, pitch, 0], atTimeMs);
    });
    voices.clear();
  }

  private sendProgramChanges(): void {
    if (!this.midiOutput) return;
    const now = performance.now() + 50;
    for (const instrument of ['BASS', 'PIANO', 'SAX'] as MelodicInstrument[]) {
      const channel = this.config.channels[instrument];
      const program = this.config.gmPrograms[instrument];
      this.midiOutput.send([0xc0 | channel, program], now);
    }
  }
}
