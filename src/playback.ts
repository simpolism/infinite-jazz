import { cloneConfig, totalSteps } from './config.js';
import type { InstrumentName, RuntimeConfig, TrackerStep } from './types.js';
import { createSynthesizer, applyProgramMap, FluidSynthBridge, DRUM_CHANNEL } from './soundfontBridge.js';

type MelodicInstrument = Exclude<InstrumentName, 'DRUMS'>;

type MidiVoiceRegistry = Record<InstrumentName, Set<number>>;

type ScheduledNote = {
  pitch: number;
  startTime: number;
  endTime: number;
  onEvent: ScheduledEvent | null;
  offEvent: ScheduledEvent | null;
};

type ScheduledNoteRegistry = Record<MelodicInstrument, Set<ScheduledNote>>;

const EPSILON = 1e-4;
const INITIAL_LOOKAHEAD = 0.4;
const SECTION_LOOKAHEAD = 0.25;
const INSTRUMENTS: InstrumentName[] = ['BASS', 'DRUMS', 'PIANO', 'SAX'];
const SCHEDULER_GUARD = 0.025;
const SECTION_BUFFER = 4;

interface ScheduledEvent {
  cancel(): void;
}

interface InternalScheduledEvent {
  time: number;
  priority: number;
  id: number;
  label?: string;
  data?: Record<string, unknown>;
  callback: () => void;
  cancelled: boolean;
}

interface ScheduleOptions {
  priority?: number;
  label?: string;
  data?: Record<string, unknown>;
}

class TimelineScheduler {
  private events: InternalScheduledEvent[];
  private timerId: number | null;
  private counter: number;
  private readonly getTime: () => number;

  constructor(getTime: () => number) {
    this.events = [];
    this.timerId = null;
    this.counter = 0;
    this.getTime = getTime;
  }

  schedule(time: number, callback: () => void, options: ScheduleOptions = {}): ScheduledEvent {
    const event: InternalScheduledEvent = {
      time,
      priority: options.priority ?? 0,
      label: options.label,
      data: options.data,
      id: this.counter++,
      callback,
      cancelled: false,
    };
    this.events.push(event);
    this.events.sort((a, b) => {
      if (Math.abs(a.time - b.time) > EPSILON) {
        return a.time - b.time;
      }
      if (a.priority !== b.priority) {
        return a.priority - b.priority;
      }
      return a.id - b.id;
    });
    if (this.events[0] === event) {
      this.resetTimer();
    }
    return {
      cancel: () => {
        event.cancelled = true;
        if (this.events[0] === event) {
          this.resetTimer();
        }
      },
    };
  }

  clear(): void {
    if (this.timerId !== null) {
      window.clearTimeout(this.timerId);
      this.timerId = null;
    }
    this.events = [];
  }

  private resetTimer(): void {
    if (this.timerId !== null) {
      window.clearTimeout(this.timerId);
      this.timerId = null;
    }
    while (this.events.length && this.events[0].cancelled) {
      this.events.shift();
    }
    if (!this.events.length) {
      return;
    }
    const head = this.events[0];
    const now = this.getTime();
    const guardAdjusted = head.time - now - SCHEDULER_GUARD;
    const delayMs = Math.max(0, guardAdjusted * 1000);
    this.timerId = window.setTimeout(() => this.flush(), delayMs);
  }

  private flush(): void {
    this.timerId = null;
    const now = this.getTime();
    while (this.events.length) {
      const event = this.events[0];
      if (event.time - now > EPSILON) {
        break;
      }
      this.events.shift();
      if (!event.cancelled) {
        event.callback();
      }
    }
    if (this.events.length) {
      this.resetTimer();
    }
  }
}
interface PlaybackBackend {
  prepare(config: RuntimeConfig): Promise<boolean> | boolean;
  enqueueStep(instrument: InstrumentName, stepIndex: number, step: TrackerStep): void;
  stopAll(): void;
  shutdown(): void;
  getLeadSeconds(): number;
  getSectionDuration(): number;
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

  getLeadSeconds(): number {
    return this.activeBackend.getLeadSeconds();
  }

  getSectionDuration(): number {
    return this.activeBackend.getSectionDuration();
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
  private scheduler: TimelineScheduler;
  private sectionDuration: number;
  private maxSectionStart: number;
  private lastStepIndices: Record<InstrumentName, number>;
  private instrumentSections: Record<InstrumentName, number>;
  private sectionStartTimes: Map<number, number>;
  private pendingSections: Map<number, Map<number, Partial<Record<InstrumentName, TrackerStep>>>>;

  constructor(baseConfig: RuntimeConfig) {
    this.config = cloneConfig(baseConfig);
    this.context = null;
    this.synth = null;
    this.started = false;
    this.startTime = 0;
    this.scheduled = this.createScheduleRegistry();
    this.scheduler = new TimelineScheduler(() => this.context?.currentTime ?? performance.now() / 1000);
    this.sectionDuration = 0;
    this.maxSectionStart = 0;
    this.lastStepIndices = { BASS: -1, DRUMS: -1, PIANO: -1, SAX: -1 };
    this.instrumentSections = { BASS: 0, DRUMS: 0, PIANO: 0, SAX: 0 };
    this.sectionStartTimes = new Map();
    this.pendingSections = new Map();
  }

  private createScheduleRegistry(): ScheduledNoteRegistry {
    return {
      BASS: new Set(),
      PIANO: new Set(),
      SAX: new Set(),
    };
  }

  async prepare(config: RuntimeConfig): Promise<boolean> {
    this.config = cloneConfig(config);
    this.cancelAllTimers();
    this.scheduled = this.createScheduleRegistry();
    this.lastStepIndices = { BASS: -1, DRUMS: -1, PIANO: -1, SAX: -1 };
    this.instrumentSections = { BASS: 0, DRUMS: 0, PIANO: 0, SAX: 0 };
    this.sectionStartTimes = new Map();
    this.pendingSections = new Map();
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
    const quarter = 60 / this.config.tempo;
    const base = quarter / 4;
    const pairDuration = base * 2;
    const total = totalSteps(this.config);
    this.sectionDuration = this.stepStartSeconds(total, quarter, base, pairDuration);
    if (this.sectionDuration <= 0) {
      this.sectionDuration = Math.max(base, total * base);
    }
    const bufferLead = this.sectionDuration * SECTION_BUFFER;
    this.startTime = this.context.currentTime + bufferLead + INITIAL_LOOKAHEAD;
    this.maxSectionStart = this.startTime;
    // Initialize section 0's start time
    this.sectionStartTimes.set(0, this.startTime);
    return true;
  }

  enqueueStep(instrument: InstrumentName, stepIndex: number, step: TrackerStep): void {
    if (!this.context || !this.synth) {
      return;
    }

    const quarter = 60 / this.config.tempo;
    const base = quarter / 4;
    const pairDuration = base * 2;

    // Detect section transition: if this instrument looped back to a lower step
    const lastStep = this.lastStepIndices[instrument];
    if (lastStep >= 0 && stepIndex < lastStep) {
      // This instrument looped - increment its section counter
      this.instrumentSections[instrument]++;

      const newSection = this.instrumentSections[instrument];

      // Check if we need to set the start time for this new section
      if (!this.sectionStartTimes.has(newSection)) {
        // First instrument to reach this section - compute its start time
        const prevSectionStart = this.sectionStartTimes.get(newSection - 1) ?? this.startTime;
        const idealStart = prevSectionStart + this.sectionDuration;
        const now = this.getAudioTime();
        const minLeadStart = now + SECTION_LOOKAHEAD;

        // Use ideal time if we're on schedule, otherwise push forward slightly
        const actualStart = Math.max(idealStart, minLeadStart);
        this.sectionStartTimes.set(newSection, actualStart);
        this.maxSectionStart = Math.max(this.maxSectionStart, actualStart);
      }
    }
    this.lastStepIndices[instrument] = stepIndex;

    // Get the start time for this instrument's current section
    const currentSection = this.instrumentSections[instrument];
    this.bufferStep(currentSection, stepIndex, instrument, step);
  }

  stopAll(): void {
    this.cancelAllTimers();
    this.scheduled = this.createScheduleRegistry();
    this.pendingSections = new Map();
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
    this.scheduler.clear();
    for (const voices of Object.values(this.scheduled)) {
      voices.clear();
    }
  }

  private scheduleAt(time: number, callback: () => void, priority = 0): ScheduledEvent {
    return this.scheduler.schedule(time, callback, { priority });
  }

  private getAudioTime(): number {
    return this.context?.currentTime ?? performance.now() / 1000;
  }

  getLeadSeconds(): number {
    const latestEnd = this.maxSectionStart + this.sectionDuration;
    const lead = latestEnd - this.getAudioTime();
    return lead > 0 ? lead : 0;
  }

  getSectionDuration(): number {
    return this.sectionDuration;
  }

  private bufferStep(section: number, stepIndex: number, instrument: InstrumentName, step: TrackerStep): void {
    let sectionSteps = this.pendingSections.get(section);
    if (!sectionSteps) {
      sectionSteps = new Map();
      this.pendingSections.set(section, sectionSteps);
    }
    const existing = sectionSteps.get(stepIndex) ?? {};
    existing[instrument] = step;
    sectionSteps.set(stepIndex, existing);
    if (INSTRUMENTS.every((name) => existing[name])) {
      this.pendingSections.get(section)?.delete(stepIndex);
      if ((this.pendingSections.get(section)?.size ?? 0) === 0) {
        this.pendingSections.delete(section);
      }
      this.scheduleCombinedStep(section, stepIndex, existing as Record<InstrumentName, TrackerStep>);
    }
  }

  private scheduleCombinedStep(
    section: number,
    stepIndex: number,
    steps: Record<InstrumentName, TrackerStep>
  ): void {
    const quarter = 60 / this.config.tempo;
    const base = quarter / 4;
    const pairDuration = base * 2;
    let sectionStartTime = this.sectionStartTimes.get(section) ?? this.startTime;
    const stepOffset = this.stepStartSeconds(stepIndex, quarter, base, pairDuration);
    const now = this.getAudioTime();
    let start = sectionStartTime + stepOffset;
    const minimumStart = now + SECTION_LOOKAHEAD;
    if (start < minimumStart) {
      const shift = minimumStart - start;
      sectionStartTime += shift;
      this.sectionStartTimes.set(section, sectionStartTime);
      this.maxSectionStart = Math.max(this.maxSectionStart, sectionStartTime);
      start = sectionStartTime + stepOffset;
      // shift future sections by same amount to preserve ordering
      for (const key of Array.from(this.sectionStartTimes.keys())) {
        if (key > section) {
          const updated = this.sectionStartTimes.get(key);
          if (updated !== undefined) {
            this.sectionStartTimes.set(key, updated + shift);
            this.maxSectionStart = Math.max(this.maxSectionStart, updated + shift);
          }
        }
      }
    }
    if (!this.started) {
      this.started = true;
    }
    for (const instrument of INSTRUMENTS) {
      const step = steps[instrument];
      if (instrument === 'DRUMS') {
        this.scheduleDrums(step, start);
        continue;
      }
      const melodicInstrument = instrument as MelodicInstrument;
      if (step.isTie) {
        const tieDuration = this.stepDurationSeconds(stepIndex);
        this.extendInstrumentWithTie(melodicInstrument, start, start + tieDuration);
        continue;
      }
      if (step.isRest) {
        this.releaseInstrumentAt(melodicInstrument, start);
        continue;
      }
      this.releaseInstrumentAt(melodicInstrument, start);
      const duration = this.stepDurationSeconds(stepIndex);
      for (const note of step.notes) {
        this.scheduleNote(melodicInstrument, note.pitch, note.velocity, start, duration);
      }
    }
  }

  private scheduleNote(instrument: MelodicInstrument, pitch: number, velocity: number, startTime: number, duration: number): void {
    const context = this.context;
    const synth = this.synth;
    if (!context || !synth) return;
    const channel = this.config.channels[instrument];
    const endTime = startTime + duration;
    const voices = this.scheduled[instrument];
    const note: ScheduledNote = {
      pitch,
      startTime,
      endTime,
      onEvent: null,
      offEvent: null,
    };

    voices.add(note);

    note.onEvent = this.scheduler.schedule(
      startTime,
      () => {
        synth.noteOn(channel, pitch, Math.max(1, Math.min(127, velocity)));
        note.onEvent = null;
      },
      {
        priority: 0,
        label: 'noteOn',
        data: { instrument, pitch, startTime: startTime.toFixed(3) },
      }
    );

    note.offEvent = this.scheduler.schedule(
      endTime,
      () => {
        synth.noteOff(channel, pitch);
        note.offEvent = null;
        voices.delete(note);
      },
      {
        priority: 1,
        label: 'noteOff',
        data: { instrument, pitch, endTime: endTime.toFixed(3) },
      }
    );
  }

  private cancelEvent(event: ScheduledEvent | null): void {
    event?.cancel();
  }

  private releaseInstrumentAt(instrument: MelodicInstrument, releaseTime: number): void {
    const context = this.context;
    const synth = this.synth;
    if (!context || !synth) return;
    const voices = this.scheduled[instrument];
    if (voices.size === 0) return;
    const channel = this.config.channels[instrument];
    const now = this.getAudioTime();
    for (const note of Array.from(voices)) {
      const targetTime = Math.min(releaseTime, note.endTime);
      if (targetTime <= note.startTime + EPSILON) {
        this.cancelEvent(note.onEvent);
        note.onEvent = null;
        this.cancelEvent(note.offEvent);
        note.offEvent = null;
        synth.noteOff(channel, note.pitch);
        voices.delete(note);
        continue;
      }
      if (targetTime <= now + EPSILON) {
        this.cancelEvent(note.offEvent);
        note.offEvent = null;
        synth.noteOff(channel, note.pitch);
        voices.delete(note);
        continue;
      }
      if (Math.abs(targetTime - note.endTime) <= EPSILON) {
        continue;
      }
      this.cancelEvent(note.offEvent);
      note.offEvent = null;
      note.endTime = targetTime;
      note.offEvent = this.scheduler.schedule(
        targetTime,
        () => {
          synth.noteOff(channel, note.pitch);
          note.offEvent = null;
          voices.delete(note);
        },
        {
          priority: -1,
          label: 'noteRelease',
          data: { instrument, pitch: note.pitch, targetTime: targetTime.toFixed(3) },
        }
      );
    }
  }

  private extendInstrumentWithTie(instrument: MelodicInstrument, tieStart: number, newEndTime: number): void {
    const context = this.context;
    const synth = this.synth;
    if (!context || !synth) return;
    const voices = this.scheduled[instrument];
    if (voices.size === 0) return;
    const channel = this.config.channels[instrument];
    const now = this.getAudioTime();
    for (const note of Array.from(voices)) {
      if (note.endTime + EPSILON < tieStart) {
        continue;
      }
      if (newEndTime <= note.endTime + EPSILON) {
        continue;
      }
      this.cancelEvent(note.offEvent);
      note.offEvent = null;
      note.endTime = newEndTime;
      if (newEndTime <= now + EPSILON) {
        synth.noteOff(channel, note.pitch);
        voices.delete(note);
        continue;
      }
      note.offEvent = this.scheduler.schedule(
        newEndTime,
        () => {
          synth.noteOff(channel, note.pitch);
          note.offEvent = null;
          voices.delete(note);
        },
        {
          priority: -1,
          label: 'tieRelease',
          data: { instrument, pitch: note.pitch, newEndTime: newEndTime.toFixed(3) },
        }
      );
    }
  }

  private scheduleDrums(step: TrackerStep, startTime: number): void {
    const context = this.context;
    const synth = this.synth;
    if (!context || !synth) return;
    if (step.isRest || step.isTie) return;
    for (const note of step.notes) {
      this.scheduler.schedule(
        startTime,
        () => {
          const velocity = Math.max(1, Math.min(127, note.velocity));
          synth.noteOn(DRUM_CHANNEL, note.pitch, velocity);
          const releaseTime = startTime + 0.12;
          this.scheduler.schedule(
            releaseTime,
            () => {
              synth.noteOff(DRUM_CHANNEL, note.pitch);
            },
            {
              priority: 1,
              label: 'drumOff',
              data: { pitch: note.pitch, releaseTime: releaseTime.toFixed(3) },
            }
          );
        },
        {
          priority: 0,
          label: 'drumOn',
          data: { pitch: note.pitch, startTime: startTime.toFixed(3) },
        }
      );
    }
  }

  private stepDurationSeconds(stepIndex: number): number {
    const quarter = 60 / this.config.tempo;
    const base = quarter / 4;
    const pairDuration = base * 2;
    const start = this.stepStartSeconds(stepIndex, quarter, base, pairDuration);
    const end = this.stepStartSeconds(stepIndex + 1, quarter, base, pairDuration);
    return Math.max(0.05, end - start);
  }

  private stepStartSeconds(stepIndex: number, _quarter: number, base: number, pairDuration: number): number {
    if (stepIndex <= 0) {
      return 0;
    }
    const pairIndex = Math.floor(stepIndex / 2);
    const pairStart = pairIndex * pairDuration;
    const isOffbeat = stepIndex % 2 === 1;
    if (!isOffbeat) {
      return pairStart;
    }
    if (!this.config.swingEnabled) {
      return pairStart + base;
    }
    const swingRatio = Math.min(Math.max(this.config.swingRatio, 0), 1);
    return pairStart + pairDuration * swingRatio;
  }
}

class WebMidiPlayback implements PlaybackBackend {
  private config: RuntimeConfig;
  private midiAccess: MIDIAccess | null;
  private midiOutput: MIDIOutput | null;
  private midiStartTimeMs: number;
  private midiVoices: MidiVoiceRegistry;
  private active: boolean;
  private sectionDuration: number;
  private latestSectionEndMs: number;

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
    this.sectionDuration = 0;
    this.latestSectionEndMs = this.midiStartTimeMs;
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
    const quarter = 60 / this.config.tempo;
    const base = quarter / 4;
    const pairDuration = base * 2;
    const total = totalSteps(this.config);
    this.sectionDuration = this.stepStartSeconds(total, quarter, base, pairDuration);
    this.latestSectionEndMs = this.midiStartTimeMs + this.sectionDuration * 1000;

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
    const sectionEndMs = startTimeMs + this.sectionDuration * 1000;
    if (sectionEndMs > this.latestSectionEndMs) {
      this.latestSectionEndMs = sectionEndMs;
    }

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

  getLeadSeconds(): number {
    if (!this.active) return 0;
    const lead = this.latestSectionEndMs - performance.now();
    return lead > 0 ? lead / 1000 : 0;
  }

  getSectionDuration(): number {
    return this.sectionDuration;
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

  private stepStartSeconds(stepIndex: number, _quarter: number, base: number, pairDuration: number): number {
    if (stepIndex <= 0) {
      return 0;
    }
    const pairIndex = Math.floor(stepIndex / 2);
    const pairStart = pairIndex * pairDuration;
    const isOffbeat = stepIndex % 2 === 1;
    if (!isOffbeat) {
      return pairStart;
    }
    if (!this.config.swingEnabled) {
      return pairStart + base;
    }
    const swingRatio = Math.min(Math.max(this.config.swingRatio, 0), 1);
    return pairStart + pairDuration * swingRatio;
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
