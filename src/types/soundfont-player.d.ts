declare module 'soundfont-player' {
  export interface PlayOptions {
    gain?: number;
    duration?: number;
    attack?: number;
    decay?: number;
    sustain?: number;
    release?: number;
  }

  export interface Playable {
    stop(time?: number): void;
  }

  export interface Instrument {
    play(note: number | string, when?: number, options?: PlayOptions): Playable;
    stop(): void;
  }

  export interface InstrumentOptions {
    soundfont?: string;
    format?: 'mp3' | 'ogg';
    destination?: AudioNode;
    url?: string | ((details: { instrument: string; format: string; soundfont: string }) => string);
    gain?: number;
  }

  interface Soundfont {
    instrument(
      context: AudioContext,
      name: string,
      options?: InstrumentOptions
    ): Promise<Instrument>;
  }

  const Soundfont: Soundfont;
  export default Soundfont;
}
