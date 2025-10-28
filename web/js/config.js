export const DEFAULT_CONFIG = {
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
    BASS: 32, // Acoustic Bass
    PIANO: 0, // Acoustic Grand
    SAX: 65, // Alto Sax
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

export function cloneConfig(overrides = {}) {
  return {
    ...DEFAULT_CONFIG,
    ...overrides,
    channels: { ...DEFAULT_CONFIG.channels, ...(overrides.channels || {}) },
    gmPrograms: { ...DEFAULT_CONFIG.gmPrograms, ...(overrides.gmPrograms || {}) },
    gmDrums: { ...DEFAULT_CONFIG.gmDrums, ...(overrides.gmDrums || {}) },
    timeSignature: overrides.timeSignature || [...DEFAULT_CONFIG.timeSignature],
  };
}

export function stepsPerBar(config) {
  return config.timeSignature[0] * 4;
}

export function totalSteps(config) {
  return stepsPerBar(config) * config.barsPerGeneration;
}

export function ticksPerStep(config) {
  return Math.floor(config.ticksPerBeat / 4);
}
