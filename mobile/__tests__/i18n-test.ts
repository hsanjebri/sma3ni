import { type Language, messages, pickLanguage, t } from '@/i18n';

describe('messages', () => {
  const languages = Object.keys(messages) as Language[];

  test.each(languages)('%s has every key, none empty', (lang) => {
    expect(Object.keys(messages[lang]).sort()).toEqual(Object.keys(messages.en).sort());
    for (const value of Object.values(messages[lang])) {
      expect(value.trim()).not.toBe('');
    }
  });
});

describe('pickLanguage', () => {
  test('takes the first supported phone language', () => {
    expect(pickLanguage(['de', 'fr', 'ar'])).toBe('fr');
    expect(pickLanguage(['ar'])).toBe('ar');
  });

  test('falls back to English', () => {
    expect(pickLanguage(['de', null])).toBe('en');
    expect(pickLanguage([])).toBe('en');
  });
});

test('t() reads the requested language', () => {
  expect(t('appName', 'ar')).toBe('سمعني');
  expect(t('appName', 'en')).toBe('Sma3ni');
});
