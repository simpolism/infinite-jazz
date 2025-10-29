import { totalSteps } from './config.js';
import type { RuntimeConfig } from './types.js';

const EXAMPLE_SNIPPET: readonly string[] = [
  'FORMAT EXAMPLE:',
  'BASS',
  '1 C2:80',
  '2 .',
  '3 E2:75',
  '4 .',
  '',
  'DRUMS',
  '1 C2:90,D#3:60',
  '2 .',
  '3 .',
  '4 F#2:52',
  '',
  'PIANO',
  '1 C3:65,E3:60,G3:62',
  '2 .',
  '3 .',
  '4 F3:70,A3:64,C4:60',
  '',
  'SAX',
  '1 E4:85',
  '2 .',
  '3 B4:90',
  '4 ^',
] as const;

interface PromptOptions {
  previousContext?: string;
  extraPrompt?: string;
}

export class PromptBuilder {
  private config: RuntimeConfig;

  constructor(config: RuntimeConfig) {
    this.config = config;
  }

  buildQuartetPrompt({ previousContext = '', extraPrompt = '' }: PromptOptions = {}): string {
    const steps = totalSteps(this.config);
    const bars = this.config.barsPerGeneration;
    const tempo = this.config.tempo;

    const promptLines: string[] = [
      `You are a jazz quartet generating ${bars} bars of music.`,
      'Output all 4 instruments in tracker format exactly as specified.',
      `Approximate tempo: ${tempo} BPM on a 16th-note grid.`,
      '',
      'FORMAT RULES:',
      `- ${steps} numbered lines per instrument (one line = one 16th-note step)`,
      '- Each line: NUMBER NOTE:VELOCITY (e.g., "1 C2:80"), NUMBER . (rest), or NUMBER ^ (tie)',
      '- Chords: NUMBER NOTE:VELOCITY,NOTE:VELOCITY (e.g., "1 C3:65,E3:62,G3:60")',
      '- Velocity range: 0-127 (60-90 typical for jazz)',
      '',
      'INSTRUMENT ROLES (treated as tendencies, not rules):',
      'BASS – Walking foundation (E1–G2). Outline harmony but feel free to slip in approach tones.',
      'DRUMS – Swing pulse using GM mapping (kick/snare/cymbals) yet break the ride pattern when inspiration hits.',
      'PIANO – Mid-range comping (C3–C5) with open voicings; leave pockets of silence or punchy stabs at will.',
      'SAX – Monophonic lead (A3–F5). Think in gestures rather than patterns—rests, flurries, and ties are all welcome.',
      'SAX: Vary your rhythmic motifs; if you play a figure twice, twist or displace it on the next pass.',
      'SAX: Approach this chorus like a fearless improviser—chase tension, embrace wide intervals, and resolve phrases in surprising ways while keeping the tracker format clean.',
      '',
      ...EXAMPLE_SNIPPET,
      '',
      'EXAMPLE USAGE NOTE: This illustration is for format only—your rhythms and note choices must differ significantly from it.',
      '',
      'GUIDELINES:',
      '- Let each chorus mutate; avoid recycling the previous cadence.',
      '- Rests and unexpected accents are encouraged—rhythmic surprises keep the quartet alive.',
      '- Stay in range and obey the tracker format, everything else is yours to reinvent.',
    ];

    if (previousContext) {
      promptLines.push(
        '',
        'PREVIOUS SECTION:',
        previousContext,
        '',
        'CRITICAL: Do not copy the previous section verbatim. Vary rhythm, contour, and voicings.'
      );
    }

    if (extraPrompt) {
      promptLines.push('', 'PLAYER DIRECTION:', extraPrompt);
    }

    promptLines.push(
      '',
      'OUTPUT REQUIREMENTS:',
      '1. First line must be: BASS',
      `2. Follow with exactly ${steps} numbered lines for bass`,
      '3. Then: DRUMS (blank line before is OK)',
      `4. Follow with exactly ${steps} numbered lines for drums`,
      '5. Then: PIANO',
      `6. Follow with exactly ${steps} numbered lines for piano`,
      '7. Then: SAX',
      `8. Follow with exactly ${steps} numbered lines for sax`,
      '',
      'Generate the tracker data now:'
    );

    return promptLines.join('\n');
  }
}
