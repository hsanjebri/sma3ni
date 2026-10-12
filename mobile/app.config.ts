import type { ExpoConfig } from 'expo/config';

// App ids are placeholders until the store launch (docs/STORE_RELEASE.md).
const config: ExpoConfig = {
  name: 'Sma3ni',
  slug: 'sma3ni',
  version: '0.1.0',
  scheme: 'sma3ni',
  orientation: 'portrait',
  icon: './assets/icon.png',
  userInterfaceStyle: 'automatic',
  ios: {
    bundleIdentifier: 'com.hsanjebri.sma3ni',
    supportsTablet: true,
  },
  android: {
    package: 'com.hsanjebri.sma3ni',
    adaptiveIcon: {
      backgroundColor: '#E6F4FE',
      foregroundImage: './assets/android-icon-foreground.png',
      backgroundImage: './assets/android-icon-background.png',
      monochromeImage: './assets/android-icon-monochrome.png',
    },
  },
  web: {
    favicon: './assets/favicon.png',
  },
  plugins: [
    'expo-router',
    'expo-status-bar',
    [
      'expo-localization',
      {
        supportedLocales: { ios: ['ar', 'fr', 'en'], android: ['ar', 'fr', 'en'] },
        // Arabic is right-to-left. SDK 57 needs this opt-in (the default from SDK 58).
        supportsRTL: true,
      },
    ],
  ],
};

export default config;
