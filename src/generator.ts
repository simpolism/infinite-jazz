import { PromptBuilder } from './promptBuilder.js';
import { TrackerParser, TrackerStreamParser } from './trackerParser.js';
import { cloneConfig } from './config.js';
import type { GenerationResult, RuntimeConfig, TrackerLineEvent } from './types.js';

type StreamEmitPayload = { done?: true; chunk?: string };

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

function readEventStreamChunk(buffer: string, emit: (payload: StreamEmitPayload) => void): string {
  const segments = buffer.split('\n\n');
  let carry = segments.pop() ?? '';
  for (const segment of segments) {
    const line = segment.trim();
    if (!line || !line.startsWith('data:')) continue;
    const payload = line.slice(5).trim();
    if (payload === '[DONE]') {
      emit({ done: true });
      continue;
    }
    try {
      const json = JSON.parse(payload) as {
        choices?: Array<{ delta?: { content?: string } }>;
      };
      const delta = json?.choices?.[0]?.delta?.content ?? '';
      if (delta) {
        emit({ chunk: delta });
      }
    } catch (error) {
      console.warn('Failed to parse stream payload', error, payload);
    }
  }
  return carry;
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
      stream: true,
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

    onStatus?.('Streaming tracker data…');

    if (!response.body) {
      throw new Error('No response body available for streaming.');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let carry = '';

    const flush = (lineInfo: StreamEmitPayload) => {
      if (lineInfo.done) {
        onStatus?.('Generation complete.');
        return;
      }
      if (!lineInfo.chunk) return;
      const additions = this.streamParser.appendChunk(lineInfo.chunk);
      for (const addition of additions) {
        onTrackerLine?.(addition);
      }
    };

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      carry += decoder.decode(value, { stream: true });
      carry = readEventStreamChunk(carry, flush);
    }

    if (carry.trim()) {
      readEventStreamChunk(carry, flush);
    }

    const tailSteps = this.streamParser.finalize();
    for (const addition of tailSteps) {
      onTrackerLine?.(addition);
    }

    onStatus?.('Session finished.');
    this.activeController = null;

    return {
      trackerText: this.streamParser.getRawTrackerText(),
      config: this.config,
    };
  }
}

export { TrackerParser };
