import { PromptBuilder } from './promptBuilder.js';
import { TrackerStreamParser } from './trackerParser.js';
import { cloneConfig } from './config.js';

function buildMessages(promptText) {
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
  ];
}

function readEventStreamChunk(buffer, emit) {
  const segments = buffer.split('\n\n');
  let carry = segments.pop();
  for (const segment of segments) {
    const line = segment.trim();
    if (!line) continue;
    if (!line.startsWith('data:')) continue;
    const payload = line.slice(5).trim();
    if (payload === '[DONE]') {
      emit({ done: true });
      continue;
    }
    try {
      const json = JSON.parse(payload);
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

export class JazzGenerator {
  constructor(baseConfig) {
    this.config = cloneConfig(baseConfig);
    this.promptBuilder = new PromptBuilder(this.config);
    this.activeController = null;
    this.streamParser = new TrackerStreamParser(this.config);
  }

  abort() {
    if (this.activeController) {
      this.activeController.abort();
      this.activeController = null;
    }
  }

  async streamSession({
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
  }) {
    this.abort();
    this.config = cloneConfig({
      tempo,
      barsPerGeneration,
      swingEnabled,
      swingRatio,
    });
    this.promptBuilder = new PromptBuilder(this.config);
    this.streamParser = new TrackerStreamParser(this.config);

    const promptText = this.promptBuilder.buildQuartetPrompt({
      previousContext,
      extraPrompt,
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

    const headers = {
      'Content-Type': 'application/json',
    };
    if (apiKey) {
      headers.Authorization = `Bearer ${apiKey}`;
    }

    let response;
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
        return { aborted: true };
      }
      throw new Error(`Failed to contact API: ${error.message}`);
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

    const flush = (lineInfo) => {
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
