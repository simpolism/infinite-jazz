import type { InstrumentName, RuntimeConfig } from './types.js';

const SOUNDFONT_PATH = '/soundfonts/gm.sf2';
const FLUIDSYNTH_SCRIPT = '/libfluidsynth/libfluidsynth-2.4.6.js';
export const DRUM_CHANNEL = 9; // GM percussion channel (0-indexed)

const GM_PRESET_MAP: Record<Exclude<InstrumentName, 'DRUMS'>, number> = {
  BASS: 32,
  PIANO: 0,
  SAX: 65,
};

type SynthModule = typeof import('js-synthesizer');

let modulePromise: Promise<SynthModule> | null = null;
let scriptPromise: Promise<void> | null = null;

function ensureFluidSynthScript(): Promise<void> {
  if (!scriptPromise) {
    scriptPromise = new Promise<void>((resolve, reject) => {
      // If the script is already present, resolve immediately
      if (document.querySelector(`script[data-fluidsynth="true"]`)) {
        resolve();
        return;
      }
      const tag = document.createElement('script');
      tag.src = FLUIDSYNTH_SCRIPT;
      tag.async = true;
      tag.dataset.fluidsynth = 'true';
      tag.onload = () => resolve();
      tag.onerror = () => reject(new Error('Failed to load libfluidsynth script.'));
      document.head.appendChild(tag);
    });
  }
  return scriptPromise;
}

async function loadSynthModule(): Promise<SynthModule> {
  await ensureFluidSynthScript();
  if (!modulePromise) {
    modulePromise = import('js-synthesizer');
  }
  return modulePromise;
}

export class FluidSynthBridge {
  private synth: import('js-synthesizer').Synthesizer | null;
  private audioNode: AudioNode | null;
  private context: AudioContext;
  private soundFontId: number | null;
  private readyPromise: Promise<void>;

  constructor(context: AudioContext) {
    this.context = context;
    this.synth = null;
    this.audioNode = null;
    this.soundFontId = null;
    this.readyPromise = this.initialize();
  }

  private async initialize(): Promise<void> {
    const module = await loadSynthModule();
    await module.waitForReady();
    this.synth = new module.Synthesizer();
    this.synth.init(this.context.sampleRate);

    const response = await fetch(SOUNDFONT_PATH);
    if (!response.ok) {
      throw new Error(`Failed to load GM soundfont: ${response.status}`);
    }
    const arrayBuffer = await response.arrayBuffer();
    this.soundFontId = await this.synth.loadSFont(arrayBuffer);

    const audioNode = this.synth.createAudioNode(this.context);
    audioNode.connect(this.context.destination);
    this.audioNode = audioNode;

    this.synth.midiSetChannelType(DRUM_CHANNEL, true);
  }

  async waitUntilReady(): Promise<void> {
    await this.readyPromise;
  }

  applyPresetMap(config: RuntimeConfig): void {
    if (!this.synth) return;
    for (const instrument of Object.keys(GM_PRESET_MAP) as Array<Exclude<InstrumentName, 'DRUMS'>>) {
      const channel = config.channels[instrument];
      const program = config.gmPrograms[instrument] ?? GM_PRESET_MAP[instrument];
      this.synth.midiProgramChange(channel, program);
      this.synth.midiSetChannelType(channel, false);
    }
    this.synth.midiSetChannelType(DRUM_CHANNEL, true);
  }

  noteOn(channel: number, note: number, velocity: number): void {
    this.synth?.midiNoteOn(channel, note, velocity);
  }

  noteOff(channel: number, note: number): void {
    this.synth?.midiNoteOff(channel, note);
  }

  allSoundsOff(): void {
    this.synth?.midiAllSoundsOff();
  }

  disconnect(): void {
    if (this.audioNode) {
      this.audioNode.disconnect();
      this.audioNode = null;
    }
    if (this.synth) {
      if (this.soundFontId !== null) {
        try {
          this.synth.unloadSFont(this.soundFontId);
        } catch (error) {
          console.warn('Failed to unload soundfont', error);
        }
      }
      this.synth.close();
      this.synth = null;
    }
  }
}

export async function createSynthesizer(context: AudioContext): Promise<FluidSynthBridge> {
  const bridge = new FluidSynthBridge(context);
  await bridge.waitUntilReady();
  return bridge;
}

export function applyProgramMap(bridge: FluidSynthBridge, config: RuntimeConfig): void {
  bridge.applyPresetMap(config);
}
