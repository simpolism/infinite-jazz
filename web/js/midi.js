import { cloneConfig, ticksPerStep, totalSteps } from './config.js';

function writeUint32BE(value) {
  return [
    (value >> 24) & 0xff,
    (value >> 16) & 0xff,
    (value >> 8) & 0xff,
    value & 0xff,
  ];
}

function writeUint16BE(value) {
  return [
    (value >> 8) & 0xff,
    value & 0xff,
  ];
}

function encodeVLQ(value) {
  const bytes = [];
  let buffer = value & 0x7f;
  while ((value >>= 7)) {
    buffer <<= 8;
    buffer |= (value & 0x7f) | 0x80;
  }
  while (true) {
    bytes.push(buffer & 0xff);
    if (buffer & 0x80) {
      buffer >>= 8;
    } else {
      break;
    }
  }
  return bytes;
}

function midiTrackChunk(dataBytes) {
  const header = [0x4d, 0x54, 0x72, 0x6b]; // 'MTrk'
  const length = writeUint32BE(dataBytes.length);
  return new Uint8Array([...header, ...length, ...dataBytes]);
}

function midiHeaderChunk(trackCount, division) {
  const header = [0x4d, 0x54, 0x68, 0x64]; // 'MThd'
  const length = writeUint32BE(6);
  const formatType = writeUint16BE(trackCount > 1 ? 1 : 0);
  const tracks = writeUint16BE(trackCount);
  const divisionBytes = writeUint16BE(division);
  return new Uint8Array([...header, ...length, ...formatType, ...tracks, ...divisionBytes]);
}

function buildTempoTrack(config) {
  const events = [];
  const tempo = Math.round(60000000 / config.tempo);
  events.push(0x00, 0xff, 0x51, 0x03, (tempo >> 16) & 0xff, (tempo >> 8) & 0xff, tempo & 0xff);
  events.push(0x00, 0xff, 0x2f, 0x00);
  return midiTrackChunk(events);
}

function stepTick(config, stepIndex) {
  const tps = ticksPerStep(config);
  const pairTicks = tps * 2;
  if (stepIndex >= totalSteps(config)) {
    return stepIndex * tps;
  }
  const pairIndex = Math.floor(stepIndex / 2);
  const base = pairIndex * pairTicks;
  const isOffbeat = stepIndex % 2 === 1;
  if (!config.swingEnabled || !isOffbeat) {
    return base;
  }
  return base + Math.round(pairTicks * config.swingRatio);
}

function addEvent(events, state, tick, bytes) {
  const delta = Math.max(0, tick - state.lastTick);
  events.push(...encodeVLQ(delta), ...bytes);
  state.lastTick = tick;
}

function addZeroDelta(events, bytes) {
  events.push(0x00, ...bytes);
}

function buildInstrumentTrack(config, instrumentName, track) {
  const channel = config.channels[instrumentName] ?? 0;
  const events = [];
  const state = { lastTick: 0 };

  // Track name
  const nameBytes = new TextEncoder().encode(instrumentName);
  events.push(0x00, 0xff, 0x03, nameBytes.length, ...nameBytes);

  if (instrumentName !== 'DRUMS') {
    const program = config.gmPrograms[instrumentName] ?? 0;
    addEvent(events, state, 0, [0xc0 | channel, program]);
  }

  const activeNotes = new Map();
  const stepCount = track.steps.length;

  for (let idx = 0; idx < stepCount; idx += 1) {
    const step = track.steps[idx];
    const tick = stepTick(config, idx);

    if (instrumentName === 'DRUMS') {
      if (step.isRest || step.isTie || step.notes.length === 0) {
        continue;
      }
      const noteOnBytes = [0x90 | channel, 0, 0];
      let first = true;
      for (const note of step.notes) {
        noteOnBytes[1] = note.pitch;
        noteOnBytes[2] = Math.max(1, Math.min(127, note.velocity));
        if (first) {
          addEvent(events, state, tick, [...noteOnBytes]);
          first = false;
        } else {
          addZeroDelta(events, [...noteOnBytes]);
        }
      }
      const offTick = tick + Math.max(12, Math.round(ticksPerStep(config) / 2));
      let offFirst = true;
      for (const note of step.notes) {
        const offBytes = [0x80 | channel, note.pitch, 0x00];
        if (offFirst) {
          addEvent(events, state, offTick, offBytes);
          offFirst = false;
        } else {
          addZeroDelta(events, offBytes);
        }
      }
      continue;
    }

    if (step.isTie) {
      continue;
    }

    if (activeNotes.size > 0) {
      let first = true;
      for (const pitch of activeNotes.keys()) {
        const offBytes = [0x80 | channel, pitch, 0x00];
        if (first) {
          addEvent(events, state, tick, offBytes);
          first = false;
        } else {
          addZeroDelta(events, offBytes);
        }
      }
      activeNotes.clear();
    }

    if (step.isRest || step.notes.length === 0) {
      continue;
    }

    let firstOn = true;
    for (const note of step.notes) {
      const onBytes = [0x90 | channel, note.pitch, Math.max(1, Math.min(127, note.velocity))];
      if (firstOn) {
        addEvent(events, state, tick, onBytes);
        firstOn = false;
      } else {
        addZeroDelta(events, onBytes);
      }
      activeNotes.set(note.pitch, true);
    }
  }

  const finalTick = stepTick(config, totalSteps(config));
  if (activeNotes.size > 0) {
    let first = true;
    for (const pitch of activeNotes.keys()) {
      const offBytes = [0x80 | channel, pitch, 0x00];
      if (first) {
        addEvent(events, state, finalTick, offBytes);
        first = false;
      } else {
        addZeroDelta(events, offBytes);
      }
    }
    activeNotes.clear();
  }

  events.push(0x00, 0xff, 0x2f, 0x00);
  return midiTrackChunk(events);
}

export class MidiExporter {
  constructor(baseConfig) {
    this.config = cloneConfig(baseConfig);
  }

  setConfig(config) {
    this.config = cloneConfig(config);
  }

  createFile(tracks) {
    const division = this.config.ticksPerBeat;
    const entries = Object.entries(tracks);
    const header = midiHeaderChunk(entries.length + 1, division);
    const tempoTrack = buildTempoTrack(this.config);
    const trackChunks = entries.map(([instrument, track]) =>
      buildInstrumentTrack(this.config, instrument, track)
    );
    const allChunks = [header, tempoTrack, ...trackChunks];
    const totalLength = allChunks.reduce((acc, chunk) => acc + chunk.byteLength, 0);
    const combined = new Uint8Array(totalLength);
    let offset = 0;
    for (const chunk of allChunks) {
      combined.set(chunk, offset);
      offset += chunk.byteLength;
    }
    return new Blob([combined], { type: 'audio/midi' });
  }
}
