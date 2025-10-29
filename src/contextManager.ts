import type { InstrumentName } from './types.js';

const TRACKER_INSTRUMENTS: InstrumentName[] = ['BASS', 'DRUMS', 'PIANO', 'SAX'];

type InstrumentBuckets = Record<InstrumentName, string[]>;
type TrimmedFlags = Record<InstrumentName, boolean>;

function emptyBuckets(): InstrumentBuckets {
  return {
    BASS: [],
    DRUMS: [],
    PIANO: [],
    SAX: [],
  };
}

function emptyFlags(): TrimmedFlags {
  return {
    BASS: false,
    DRUMS: false,
    PIANO: false,
    SAX: false,
  };
}

function stripLineNumber(line: string): string {
  return line.replace(/^\s*\d+\.?\s+/, '').trim();
}

function extractInstrumentSections(trackerText: string): InstrumentBuckets {
  const sections = emptyBuckets();
  let current: InstrumentName | null = null;
  for (const rawLine of trackerText.split(/\r?\n/)) {
    const trimmed = rawLine.trim();
    if (!trimmed) continue;
    if ((TRACKER_INSTRUMENTS as string[]).includes(trimmed)) {
      current = trimmed as InstrumentName;
      continue;
    }
    if (!current) continue;
    sections[current].push(trimmed);
  }
  return sections;
}

export class TrackerContext {
  private maxSteps: number;
  private history: InstrumentBuckets;
  private trimmed: TrimmedFlags;

  constructor(maxSteps: number) {
    this.maxSteps = Math.max(0, maxSteps);
    this.history = emptyBuckets();
    this.trimmed = emptyFlags();
  }

  reset(): void {
    this.history = emptyBuckets();
    this.trimmed = emptyFlags();
  }

  incorporate(trackerText: string): void {
    if (!this.maxSteps) {
      this.reset();
      return;
    }
    const sections = extractInstrumentSections(trackerText);
    for (const instrument of TRACKER_INSTRUMENTS) {
      const existing = this.history[instrument];
      const additions = sections[instrument].map((entry) => stripLineNumber(entry));
      const combined = existing.concat(additions);
      const trimmed = combined.length > this.maxSteps;
      this.history[instrument] = trimmed ? combined.slice(-this.maxSteps) : combined;
      this.trimmed[instrument] = trimmed;
    }
  }

  buildPromptChunk(): string {
    if (!this.maxSteps) return '';
    const parts: string[] = [];
    for (const instrument of TRACKER_INSTRUMENTS) {
      const lines = this.history[instrument];
      if (!lines.length) continue;
      const prefix = this.trimmed[instrument] ? '...' : '';
      parts.push(`${instrument} (recent):\n${prefix}${lines.join('\n')}`);
    }
    return parts.join('\n\n');
  }
}
