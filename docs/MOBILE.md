# Mobile — Sma3ni

## Stack
- Expo SDK (latest), React Native, TypeScript strict, Expo Router
- Native targets via config plugins / prebuild (no Expo Go for share extensions)
- `expo-sqlite` (history), `react-native-mmkv` (settings), `@tanstack/react-query` (API)
- i18n: Arabic (RTL), French, English

## Screens
| Screen | Content |
|---|---|
| Onboarding (3 steps) | What it does → how to share from WhatsApp (GIF) → privacy promise |
| Home | Recent transcripts, "Pick audio file" button, tip on how to share |
| Transcript | Text (Arabic/Arabizi toggle), copy, share, summary, translate, replies, "Correct" |
| History | Search, swipe to delete |
| Settings | Default script, auto-summary, language, donation opt-in, delete all, privacy policy |

## Getting audio into the app
### Android
- Activity with intent filter:
  ```xml
  <intent-filter>
    <action android:name="android.intent.action.SEND" />
    <category android:name="android.intent.category.DEFAULT" />
    <data android:mimeType="audio/*" />
  </intent-filter>
  ```
- Copy the `content://` URI to app cache, then hand to JS. WhatsApp shares `.opus` as `audio/ogg`.
- Library option: `expo-share-intent`, or a small custom Kotlin module.

### iOS
- **Share Extension** target (Swift), activation rule for `public.audio`.
- Extension copies the file into the **App Group** container and opens the main app (`sma3ni://transcribe?file=...`), or shows a compact UI and calls the API directly.
- Keep extension memory low (limit ~120 MB): no React Native inside the extension.
- Requires a paid Apple Developer account for TestFlight/App Store and App Groups on device.

## Local data
- History stored only on the device (SQLite): id, created_at, duration, text, script, summary.
- Cached audio deleted after successful transcription.
- "Delete all" wipes SQLite + cache.

## Testing on devices
| Stage | How |
|---|---|
| UI dev | Expo dev client (`npx expo run:android` / `run:ios`) |
| Android beta | `eas build -p android --profile preview` → APK |
| iOS beta | `eas build -p ios` → TestFlight |
| Without share extension | "Pick audio file" button works in any build |

## Quality
- Test on: low-end Android (2–3 GB RAM), recent iPhone, RTL layout, dark mode, slow 3G
- Error states: offline, server busy (503 retry), audio too long
- Accessibility: dynamic font size, screen reader labels
