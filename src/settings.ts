export interface StoredSettings {
  apiKey?: string;
  baseUrl?: string;
  model?: string;
  prompt?: string;
  bars?: number;
  tempo?: number;
  swing?: boolean;
}

const STORAGE_KEY = 'infinite_jazz_settings_v1';

export function loadSettings(): StoredSettings {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as StoredSettings;
    return parsed ?? {};
  } catch (error) {
    console.warn('Failed to load settings', error);
    return {};
  }
}

export function saveSettings(settings: StoredSettings): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch (error) {
    console.warn('Failed to save settings', error);
  }
}
