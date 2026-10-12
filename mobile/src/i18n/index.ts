import { getLocales } from 'expo-localization';

import ar from './ar.json';
import en from './en.json';
import fr from './fr.json';

// Every user-facing string goes through t() (mobile/AGENTS.md). en.json defines
// the keys; the type makes a key missing from ar.json or fr.json a type error.
export type Language = 'ar' | 'fr' | 'en';
export type MessageKey = keyof typeof en;

export const messages: Record<Language, Record<MessageKey, string>> = { ar, fr, en };

/** The first of the phone's languages we support, else English. */
export function pickLanguage(languageCodes: readonly (string | null)[]): Language {
  for (const code of languageCodes) {
    if (code === 'ar' || code === 'fr' || code === 'en') {
      return code;
    }
  }
  return 'en';
}

export const language: Language = pickLanguage(getLocales().map((locale) => locale.languageCode));

export function t(key: MessageKey, lang: Language = language): string {
  return messages[lang][key];
}
