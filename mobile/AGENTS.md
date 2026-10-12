# mobile/AGENTS.md

Read the root `AGENTS.md` first, then `docs/MOBILE.md` and `docs/API.md`.

## Scope
Expo / React Native app (TypeScript) + native share handling (Swift Share Extension, Kotlin intent).

## Layout
```
mobile/
├── app.config.ts          # Expo config, plugins (router, localization + RTL), app ids
├── src/
│   ├── app/               # Expo Router: every file is a screen, _layout.tsx a navigator
│   │   ├── _layout.tsx
│   │   ├── index.tsx      # Home: pick a voice note, transcribe, open the transcript
│   │   └── transcript/[id].tsx  # text, copy, share
│   ├── i18n/              # en.json (defines the keys), fr.json, ar.json, t()
│   ├── theme/             # light/dark colors
│   ├── api/               # typed client for docs/API.md: token, 401 re-install, busy retries
│   ├── db/                # expo-sqlite schema + queries                (not written)
│   ├── components/                                                     (not written)
│   └── lib/               # pick + delete cached audio, error messages, transcripts (memory)
├── __tests__/             # jest-expo + React Native Testing Library (`*-test.ts(x)`)
├── plugins/               # config plugins for share extension / intent (not written)
├── ios-share-extension/   # Swift sources                               (not written)
└── android-share/         # Kotlin sources                              (not written)
```
Expo's current convention puts routes in `src/app/`; import app code as `@/...`
(maps to `src/`). Modules marked *not written* arrive with their step in
`docs/ROADMAP.md` (Phase 4); don't stub them early.

**Expo changes every SDK release:** before using an Expo / React Native API,
check the docs for the SDK in `package.json` (57 now) at
`https://docs.expo.dev/versions/v57.0.0/`, not memory. Add packages with
`npx expo install` (it picks SDK-compatible versions), then make sure test and
lint tools land in `devDependencies`.

## Rules
- TypeScript strict; no `any` without a comment.
- API base URL: `EXPO_PUBLIC_API_URL`, else the live Render server. The client (`src/api`) owns every retry docs/API.md allows; react-query must not add its own.
- Tests (React Native Testing Library 14): `render` and `fireEvent.*` return Promises: always `await` them, or state updates escape `act()` and tests flake.
- All user-facing strings through `t()` from `@/i18n` (ar/fr/en); a key missing from a language is a type error. Arabic is RTL (`supportsRTL` in `app.config.ts`): use `start`/`end`, never `left`/`right`, in layouts.
- API types must match `docs/API.md`; ignore unknown fields.
- Transcripts stored **only** in local SQLite. No analytics events containing text.
- Delete cached audio after a successful transcription; "Delete all" must wipe DB + cache.
- Native code changes go through config plugins so `npx expo prebuild --clean` stays reproducible. Never hand-edit generated `ios/` / `android/` folders.
- The iOS Share Extension must not load React Native (memory limit).

## Commands
```bash
npm install
npm run lint && npm run typecheck && npm test
npx expo export --platform android   # bundle check, no device (CI runs it)
npx expo start            # Expo Go is enough until native share code lands
npx expo run:android      # dev build on device/emulator
npx expo run:ios          # needs a Mac
eas build -p android --profile preview   # APK for testers
eas build -p ios --profile preview       # TestFlight
```
