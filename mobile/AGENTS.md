# mobile/AGENTS.md

Read the root `AGENTS.md` first, then `docs/MOBILE.md` and `docs/API.md`.

## Scope
Expo / React Native app (TypeScript) + native share handling (Swift Share Extension, Kotlin intent).

## Layout
```
mobile/
├── app.config.ts          # Expo config, plugins, bundle ids
├── app/                   # Expo Router screens
│   ├── (onboarding)/
│   ├── index.tsx          # Home
│   ├── transcript/[id].tsx
│   ├── history.tsx
│   └── settings.tsx
├── src/
│   ├── api/               # typed client generated from / matching docs/API.md
│   ├── db/                # expo-sqlite schema + queries
│   ├── i18n/              # ar.json, fr.json, en.json
│   ├── components/
│   └── lib/               # arabizi toggle helpers, file utils
├── plugins/               # Expo config plugins for share extension / intent
├── ios-share-extension/   # Swift sources
└── android-share/         # Kotlin sources
```

## Rules
- TypeScript strict; no `any` without a comment.
- All user-facing strings through i18n (ar/fr/en). Arabic is RTL: test layouts with `I18nManager.forceRTL`.
- API types must match `docs/API.md`; ignore unknown fields.
- Transcripts stored **only** in local SQLite. No analytics events containing text.
- Delete cached audio after a successful transcription; "Delete all" must wipe DB + cache.
- Native code changes go through config plugins so `npx expo prebuild --clean` stays reproducible. Never hand-edit generated `ios/` / `android/` folders.
- The iOS Share Extension must not load React Native (memory limit).

## Commands
```bash
npm install
npm run lint && npm run typecheck && npm test
npx expo run:android      # dev build on device/emulator
npx expo run:ios          # needs a Mac
eas build -p android --profile preview   # APK for testers
eas build -p ios --profile preview       # TestFlight
```
