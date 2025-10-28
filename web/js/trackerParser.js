import { totalSteps } from './config.js';

const NOTE_MAP = {
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

export function noteToMidi(noteName) {
  const match = /^([A-G][#b]?)(-?\d+)$/.exec(noteName.trim());
  if (!match) {
    throw new Error(`Invalid note name: ${noteName}`);
  }
  let [, note, octaveStr] = match;
  let octave = Number.parseInt(octaveStr, 10);
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

export function midiToFrequency(midi) {
  return 440 * Math.pow(2, (midi - 69) / 12);
}

function cleanEntry(entry) {
  return entry.trim().replace(/[.,;]+$/g, '').trim();
}

export function parseNoteEntry(entry) {
  const cleaned = cleanEntry(entry);
  if (!cleaned || cleaned === '.') {
    return { notes: [], isTie: false };
  }
  if (cleaned === '^') {
    return { notes: [], isTie: true };
  }
  const notes = [];
  const parts = cleaned.split(',');
  for (const rawPart of parts) {
    const part = rawPart.trim();
    if (!part) continue;
    const [pitchPart, velocityPart] = part.split(':');
    if (!velocityPart) {
      throw new Error(`Invalid note format (expected NOTE:VELOCITY): ${part}`);
    }
    const velocityDigits = (velocityPart.match(/\d+/g) || []).join('');
    if (!velocityDigits) {
      throw new Error(`No valid velocity found in: ${velocityPart}`);
    }
    let velocity = Number.parseInt(velocityDigits, 10);
    velocity = Math.min(127, Math.max(0, velocity));
    const pitch = noteToMidi(pitchPart.trim());
    notes.push({ pitch, velocity });
  }
  return { notes, isTie: false };
}

function stripLineNumber(line) {
  return line.replace(/^\s*\d+\.?\s+/, '').trim();
}

export function parseTrack(instrument, lines) {
  const steps = [];
  let lineNumber = 0;
  for (const raw of lines) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    lineNumber += 1;
    const body = stripLineNumber(line);
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
  static parse(trackerText) {
    const lines = trackerText
      .split(/\r?\n/)
      .map((line) => line.trimEnd());
    const instruments = ['BASS', 'DRUMS', 'PIANO', 'SAX'];
    const tracks = {};
    let currentInstrument = null;
    let currentLines = [];
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) continue;
      if (instruments.includes(trimmed)) {
        if (currentInstrument && currentLines.length) {
          tracks[currentInstrument] = parseTrack(currentInstrument, currentLines);
        }
        currentInstrument = trimmed;
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
  constructor(config) {
    this.config = config;
    this.totalSteps = totalSteps(config);
    this.reset();
  }

  reset() {
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

  appendChunk(chunk) {
    const decoded = chunk.replace(/\r/g, '');
    const lines = (this.partialLine + decoded).split('\n');
    this.partialLine = lines.pop();
    const newSteps = [];
    for (const line of lines) {
      this._processLine(line, newSteps);
    }
    return newSteps;
  }

  finalize() {
    if (this.partialLine) {
      const newSteps = [];
      this._processLine(this.partialLine, newSteps);
      this.partialLine = '';
      return newSteps;
    }
    return [];
  }

  _processLine(line, newSteps) {
    const trimmed = line.trim();
    if (!trimmed) return;
    this.rawLines.push(trimmed);
    const instruments = ['BASS', 'DRUMS', 'PIANO', 'SAX'];
    if (trimmed.startsWith('#')) {
      return;
    }
    if (instruments.includes(trimmed)) {
      this.currentInstrument = trimmed;
      return;
    }
    if (!this.currentInstrument) {
      return;
    }
    if (this.currentStepCounts[this.currentInstrument] >= this.totalSteps) {
      return;
    }
    const body = stripLineNumber(trimmed);
    let parsed;
    try {
      parsed = parseNoteEntry(body);
    } catch (error) {
      console.warn('Skipping malformed tracker line', { line: trimmed, error });
      return;
    }
    const stepIndex = this.currentStepCounts[this.currentInstrument];
    this.currentStepCounts[this.currentInstrument] += 1;
    const step = {
      notes: parsed.notes,
      isRest: parsed.notes.length === 0 && !parsed.isTie,
      isTie: parsed.isTie,
    };
    this.sections[this.currentInstrument].push({
      ...step,
      index: stepIndex,
      line: trimmed,
    });
    newSteps.push({
      instrument: this.currentInstrument,
      stepIndex,
      step,
      line: trimmed,
    });
  }

  getRawTrackerText() {
    const parts = [];
    for (const instrument of ['BASS', 'DRUMS', 'PIANO', 'SAX']) {
      const header = `${instrument}`;
      parts.push(header);
      const steps = this.sections[instrument];
      for (const { line } of steps) {
        parts.push(line);
      }
      parts.push('');
    }
    return parts.join('\n').trim();
  }
}
