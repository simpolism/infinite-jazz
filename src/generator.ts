import { PromptBuilder } from './promptBuilder.js';
import { TrackerParser, TrackerStreamParser } from './trackerParser.js';
import { cloneConfig } from './config.js';
import type { GenerationResult, RuntimeConfig, TrackerLineEvent } from './types.js';

function buildMessages(promptText: string) {
  return [
    {
      role: 'system',
      content:
        'You are Infinite Jazz, a meticulous jazz tracker generator. Output must follow the exact tracker format with clean numbering and instrument ordering.',
    },
    {
      role: 'user',
      content: promptText,
    },
  ] as const;
}

interface StreamSessionOptions {
  apiKey?: string | null;
  baseUrl: string;
  model: string;
  extraPrompt?: string;
  promptOverride?: string;
  previousContext?: string;
  barsPerGeneration: number;
  tempo: number;
  swingEnabled: boolean;
  swingRatio: number;
  onTrackerLine?: (event: TrackerLineEvent) => void;
  onStatus?: (message: string) => void;
}

function mergePromptSections(basePrompt: string, previousContext: string, extraPrompt: string): string {
  let text = basePrompt.trimEnd();
  if (previousContext) {
    text += `\n\nPREVIOUS SECTION:\n${previousContext}\n\nCRITICAL: Do not copy the previous section verbatim. Vary rhythm, contour, and voicings.`;
  }
  if (extraPrompt) {
    text += `\n\nPLAYER DIRECTION:\n${extraPrompt}`;
  }
  return text;
}

export class JazzGenerator {
  private config: RuntimeConfig;
  private promptBuilder: PromptBuilder;
  private activeController: AbortController | null;
  private streamParser: TrackerStreamParser;

  constructor(baseConfig: RuntimeConfig) {
    this.config = cloneConfig(baseConfig);
    this.promptBuilder = new PromptBuilder(this.config);
    this.activeController = null;
    this.streamParser = new TrackerStreamParser(this.config);
  }

  abort(): void {
    if (this.activeController) {
      this.activeController.abort();
      this.activeController = null;
    }
  }

  async streamSession(options: StreamSessionOptions): Promise<GenerationResult> {
    const {
      apiKey,
      baseUrl,
      model,
      extraPrompt,
      previousContext,
      barsPerGeneration,
      tempo,
      swingEnabled,
      swingRatio,
      onTrackerLine,
      onStatus,
    } = options;

    this.abort();
    this.config = cloneConfig({
      tempo,
      barsPerGeneration,
      swingEnabled,
      swingRatio,
    });
    this.promptBuilder = new PromptBuilder(this.config);
    this.streamParser = new TrackerStreamParser(this.config);

    const overrideText = options.promptOverride?.trim();
    const promptText =
      overrideText && overrideText.length > 0
        ? mergePromptSections(overrideText, previousContext ?? '', extraPrompt ?? '')
        : this.promptBuilder.buildQuartetPrompt({
            previousContext: previousContext ?? '',
            extraPrompt: extraPrompt ?? '',
          });

    const payload = {
      model,
      temperature: 0.85,
      messages: buildMessages(promptText),
    };

    const url = baseUrl.endsWith('/v1/chat/completions')
      ? baseUrl
      : `${baseUrl.replace(/\/$/, '')}/v1/chat/completions`;

    const controller = new AbortController();
    this.activeController = controller;

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (apiKey) {
      headers.Authorization = `Bearer ${apiKey}`;
    }

    let response: Response;
    try {
      onStatus?.('Contacting model…');
      response = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
    } catch (error) {
      if (controller.signal.aborted) {
        onStatus?.('Session aborted.');
        return { trackerText: '', config: this.config, aborted: true };
      }
      const err = error as Error;
      throw new Error(`Failed to contact API: ${err.message}`);
    }

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`API responded with ${response.status}: ${text}`);
    }

    onStatus?.('Awaiting tracker data…');

    let content = '';
    try {
      const json = (await response.json()) as {
        choices?: Array<{ message?: { content?: string } | null }>;
      };
      content = json?.choices?.[0]?.message?.content ?? '';
    } catch (error) {
      const text = await response.text();
      throw new Error(`Failed to parse response JSON: ${(error as Error).message}\n${text}`);
    }

    if (!content.trim()) {
      throw new Error('Received empty tracker response from model.');
    }

    const additions = this.streamParser.appendChunk(content);
    for (const addition of additions) {
      onTrackerLine?.(addition);
    }

    const tailSteps = this.streamParser.finalize();
    for (const addition of tailSteps) {
      onTrackerLine?.(addition);
    }

    onStatus?.('Generation complete.');
    this.activeController = null;

    return {
      trackerText: this.streamParser.getRawTrackerText(),
      config: this.config,
    };
  }
}

export { TrackerParser };
