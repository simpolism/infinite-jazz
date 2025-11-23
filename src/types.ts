export type InstrumentName = 'BASS' | 'DRUMS' | 'PIANO' | 'SAX';

export interface ChannelMap {
  BASS: number;
  DRUMS: number;
  PIANO: number;
  SAX: number;
}

export interface ProgramMap {
  BASS: number;
  PIANO: number;
  SAX: number;
}

export interface DrumMap {
  [key: string]: number;
}

export interface RuntimeConfig {
  tempo: number;
  resolution: '16th';
  swingEnabled: boolean;
  swingRatio: number;
  ticksPerBeat: number;
  barsPerGeneration: number;
  timeSignature: [number, number];
  channels: ChannelMap;
  gmPrograms: ProgramMap;
  gmDrums: DrumMap;
}

export interface NoteEvent {
  pitch: number;
  velocity: number;
}

export interface TrackerStep {
  notes: NoteEvent[];
  isRest: boolean;
  isTie: boolean;
}

export interface TrackerLineEvent {
  instrument: InstrumentName;
  stepIndex: number;
  step: TrackerStep;
  line: string;
}

export interface ParsedTrack {
  instrument: InstrumentName;
  steps: TrackerStep[];
}

export type ParsedTracker = Partial<Record<InstrumentName, ParsedTrack>>;

export interface GenerationResult {
  trackerText: string;
  config: RuntimeConfig;
  aborted?: boolean;
}
