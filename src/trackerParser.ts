import { totalSteps } from './config.js';
import type {
  InstrumentName,
  NoteEvent,
  ParsedTrack,
  ParsedTracker,
  RuntimeConfig,
  TrackerLineEvent,
  TrackerStep,
} from './types.js';

const NOTE_MAP: Record<string, number> = {
  C: 0,
  'C#': 1,
  Db: 1,
  D: 2,
  'D#': 3,
  Eb: 3,
  E: 4,
  Fb: 4,
  'E#': 5,
  F: 5,
  'F#': 6,
  Gb: 6,
  G: 7,
  'G#': 8,
  Ab: 8,
  A: 9,
  'A#': 10,
  Bb: 10,
  B: 11,
  Cb: 11,
  'B#': 0,
};

function normalizeAccidentals(note: string): string {
  return note.replace(/♯/g, '#').replace(/♭/g, 'b').replace(/♮/g, '');
}

const TRACKER_INSTRUMENTS: InstrumentName[] = ['BASS', 'DRUMS', 'PIANO', 'SAX'];

interface ParsedNoteEntry {
  notes: NoteEvent[];
  isTie: boolean;
}

interface SectionStep extends TrackerStep {
  index: number;
  line: string;
}

function cleanEntry(entry: string): string {
  return entry.trim().replace(/[.,;]+$/g, '').trim();
}

function stripLineNumber(line: string): string {
  return line.replace(/^\s*\d+\.?\s+/, '').trim();
}

export function noteToMidi(noteName: string): number {
  const normalized = normalizeAccidentals(noteName.trim());
  const match = /^([A-G][#b]?)(-?\d+)$/.exec(normalized);
  if (!match) {
    throw new Error(`Invalid note name: ${noteName}`);
  }
  const [, rawNote, octaveStr] = match;
  let octave = Number.parseInt(octaveStr, 10);
  const note = rawNote as keyof typeof NOTE_MAP;
  if (note === 'Cb') {
    octave -= 1;
  } else if (note === 'B#') {
    octave += 1;
  }
  const offset = NOTE_MAP[note];
  if (offset === undefined) {
    throw new Error(`Unsupported note: ${noteName}`);
  }
  const midi = (octave + 1) * 12 + offset;
  if (midi < 0 || midi > 127) {
    throw new Error(`Note ${noteName} out of MIDI range (0-127): ${midi}`);
  }
  return midi;
}

export function midiToFrequency(midi: number): number {
  return 440 * Math.pow(2, (midi - 69) / 12);
}

export function parseNoteEntry(entry: string): ParsedNoteEntry {
  const cleaned = cleanEntry(entry);
  if (!cleaned || cleaned === '.') {
    return { notes: [], isTie: false };
  }
  if (cleaned === '^') {
    return { notes: [], isTie: true };
  }
  const notes: NoteEvent[] = [];
  const parts = cleaned.split(',');
  for (const rawPart of parts) {
    const part = rawPart.trim();
    if (!part) continue;
    const [pitchPart, velocityPart] = part.split(':');
    if (!velocityPart) {
      throw new Error(`Invalid note format (expected NOTE:VELOCITY): ${part}`);
    }
    const velocityDigits = (velocityPart.match(/\d+/g) ?? []).join('');
    if (!velocityDigits) {
      throw new Error(`No valid velocity found in: ${velocityPart}`);
    }
    const velocity = Math.min(127, Math.max(0, Number.parseInt(velocityDigits, 10)));
    const pitch = noteToMidi(normalizeAccidentals(pitchPart.trim()));
    notes.push({ pitch, velocity });
  }
  return { notes, isTie: false };
}

export function parseTrack(instrument: InstrumentName, lines: string[]): ParsedTrack {
  const steps: TrackerStep[] = [];
  for (const raw of lines) {
    const trimmed = raw.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const body = stripLineNumber(trimmed);
    const { notes, isTie } = parseNoteEntry(body);
    steps.push({
      notes,
      isRest: notes.length === 0 && !isTie,
      isTie,
    });
  }
  return { instrument, steps };
}

export class TrackerParser {
  static parse(trackerText: string): ParsedTracker {
    const lines = trackerText.split(/\r?\n/).map((line) => line.trimEnd());
    const tracks: ParsedTracker = {};
    let currentInstrument: InstrumentName | null = null;
    let currentLines: string[] = [];
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) continue;
      if ((TRACKER_INSTRUMENTS as string[]).includes(trimmed)) {
        if (currentInstrument && currentLines.length) {
          tracks[currentInstrument] = parseTrack(currentInstrument, currentLines);
        }
        currentInstrument = trimmed as InstrumentName;
        currentLines = [];
      } else if (currentInstrument) {
        currentLines.push(trimmed);
      }
    }
    if (currentInstrument && currentLines.length) {
      tracks[currentInstrument] = parseTrack(currentInstrument, currentLines);
    }
    return tracks;
  }
}

export class TrackerStreamParser {
  private config: RuntimeConfig;
  private totalStepsExpected: number;
  private partialLine: string;
  private currentInstrument: InstrumentName | null;
  private currentStepCounts: Record<InstrumentName, number>;
  private sections: Record<InstrumentName, SectionStep[]>;
  private rawLines: string[];

  constructor(config: RuntimeConfig) {
    this.config = config;
    this.totalStepsExpected = totalSteps(config);
    this.partialLine = '';
    this.currentInstrument = null;
    this.currentStepCounts = {
      BASS: 0,
      DRUMS: 0,
      PIANO: 0,
      SAX: 0,
    };
    this.sections = {
      BASS: [],
      DRUMS: [],
      PIANO: [],
      SAX: [],
    };
    this.rawLines = [];
  }

  reset(): void {
    this.partialLine = '';
    this.currentInstrument = null;
    this.currentStepCounts = {
      BASS: 0,
      DRUMS: 0,
      PIANO: 0,
      SAX: 0,
    };
    this.sections = {
      BASS: [],
      DRUMS: [],
      PIANO: [],
      SAX: [],
    };
    this.rawLines = [];
  }

  appendChunk(chunk: string): TrackerLineEvent[] {
    const decoded = chunk.replace(/\r/g, '');
    const lines = (this.partialLine + decoded).split('\n');
    this.partialLine = lines.pop() ?? '';
    const newSteps: TrackerLineEvent[] = [];
    for (const line of lines) {
      this.processLine(line, newSteps);
    }
    return newSteps;
  }

  finalize(): TrackerLineEvent[] {
    if (!this.partialLine) {
      return [];
    }
    const newSteps: TrackerLineEvent[] = [];
    this.processLine(this.partialLine, newSteps);
    this.partialLine = '';
    return newSteps;
  }

  getRawTrackerText(): string {
    const parts: string[] = [];
    for (const instrument of TRACKER_INSTRUMENTS) {
      parts.push(`${instrument}`);
      const steps = this.sections[instrument];
      for (const { line } of steps) {
        parts.push(line);
      }
      parts.push('');
    }
    return parts.join('\n').trim();
  }

  private processLine(line: string, newSteps: TrackerLineEvent[]): void {
    const trimmed = line.trim();
    if (!trimmed) return;
    this.rawLines.push(trimmed);
    if (trimmed.startsWith('#')) {
      return;
    }
    if ((TRACKER_INSTRUMENTS as string[]).includes(trimmed)) {
      this.currentInstrument = trimmed as InstrumentName;
      return;
    }
    if (!this.currentInstrument) {
      return;
    }
    if (this.currentStepCounts[this.currentInstrument] >= this.totalStepsExpected) {
      return;
    }
    const body = stripLineNumber(trimmed);
    let parsed: ParsedNoteEntry;
    try {
      parsed = parseNoteEntry(body);
    } catch (error) {
      console.warn('Skipping malformed tracker line', { line: trimmed, error });
      return;
    }
    const stepIndex = this.currentStepCounts[this.currentInstrument];
    this.currentStepCounts[this.currentInstrument] += 1;
    const step: TrackerStep = {
      notes: parsed.notes,
      isRest: parsed.notes.length === 0 && !parsed.isTie,
      isTie: parsed.isTie,
    };
    const sectionStep: SectionStep = {
      ...step,
      index: stepIndex,
      line: trimmed,
    };
    this.sections[this.currentInstrument].push(sectionStep);
    newSteps.push({
      instrument: this.currentInstrument,
      stepIndex,
      step,
      line: trimmed,
    });
  }
}
