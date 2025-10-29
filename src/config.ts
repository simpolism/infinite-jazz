import type { RuntimeConfig, ChannelMap, ProgramMap, DrumMap } from './types.js';

export const DEFAULT_CONFIG: RuntimeConfig = {
  tempo: 120,
  resolution: '16th',
  swingEnabled: true,
  swingRatio: 0.67,
  ticksPerBeat: 480,
  barsPerGeneration: 2,
  timeSignature: [4, 4],
  channels: {
    BASS: 0,
    DRUMS: 9,
    PIANO: 1,
    SAX: 2,
  },
  gmPrograms: {
    BASS: 32,
    PIANO: 0,
    SAX: 65,
  },
  gmDrums: {
    KICK: 36,
    SNARE: 38,
    CLOSED_HH: 42,
    OPEN_HH: 46,
    TOM_LOW: 45,
    TOM_MID: 48,
    TOM_HIGH: 50,
    CRASH: 49,
    RIDE: 51,
  },
};

type ConfigOverrides = Partial<
  Omit<RuntimeConfig, 'channels' | 'gmPrograms' | 'gmDrums' | 'timeSignature'>
> & {
  channels?: Partial<ChannelMap>;
  gmPrograms?: Partial<ProgramMap>;
  gmDrums?: Partial<DrumMap>;
  timeSignature?: RuntimeConfig['timeSignature'];
};

export function cloneConfig(overrides: ConfigOverrides = {}): RuntimeConfig {
  const channels: ChannelMap = {
    ...DEFAULT_CONFIG.channels,
    ...(overrides.channels ?? {}),
  };
  const gmPrograms: ProgramMap = {
    ...DEFAULT_CONFIG.gmPrograms,
    ...(overrides.gmPrograms ?? {}),
  };
  const gmDrums = {
    ...DEFAULT_CONFIG.gmDrums,
    ...(overrides.gmDrums ?? {}),
  } as DrumMap;

  return {
    ...DEFAULT_CONFIG,
    ...overrides,
    channels,
    gmPrograms,
    gmDrums,
    timeSignature: overrides.timeSignature
      ? [...overrides.timeSignature]
      : [...DEFAULT_CONFIG.timeSignature],
  };
}

export function stepsPerBar(config: RuntimeConfig): number {
  return config.timeSignature[0] * 4;
}

export function totalSteps(config: RuntimeConfig): number {
  return stepsPerBar(config) * config.barsPerGeneration;
}

export function ticksPerStep(config: RuntimeConfig): number {
  return Math.floor(config.ticksPerBeat / 4);
}
