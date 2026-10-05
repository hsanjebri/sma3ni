# Roadmap — Sma3ni

Part-time estimate (~15–20 h/week). Each phase ends with a LinkedIn post (see `LINKEDIN_PLAN.md`).

## Two tracks
The app does not need our fine-tuned model: the server loads whatever `MODEL_PATH` points to. So the product is built against an off-the-shelf model while the data is collected, and our model replaces it later with a config change.

| Track | Phases | Gated on |
|---|---|---|
| **A — Model** | 1 Benchmark → 2 Fine-tune | Collecting and transcribing consented voice notes: slow, people-dependent |
| **B — Product** | 3 API → 4 Mobile | Nothing: starts now |

Running them side by side does not add hours. It removes waiting: while clips come in and get transcribed, the coding hours go to track B. Phase 5 needs both.

## Phase 1 — Benchmark (track A, weeks 1–2) 🚧 current
- [ ] Write `TRANSCRIPTION_GUIDELINES.md` v1 and freeze it
- [ ] Collect 1–2 h of real voice notes from friends/family with signed consent
- [ ] Transcribe them by hand (two people per clip for 10% of clips to measure agreement)
- [ ] Freeze the test set (`ml/data/test_v1` manifest, hash recorded in `ml/RESULTS.md`)
- [ ] Benchmark: whisper-large-v3, whisper-large-v3-turbo, TuniSpeech fine-tune, a multi-dialect Arabic fine-tune, w2v-BERT 2.0 (if a Tunisian fine-tune exists)
- [ ] Benchmark Groq's `whisper-large-v3-turbo` too: it is what the free MVP serves, and it decodes differently from a local run
- [ ] Publish results table + blog/LinkedIn post
**Exit:** reproducible benchmark with one command.

## Phase 2 — Fine-tune (track A, weeks 3–6)
- [ ] Data pipeline: LinTO + TuniSpeech + TEDxTN + own train data → normalized HF dataset
- [ ] Augmentation: noise, speed ±10%, Opus re-encoding at 16–24 kbps
- [ ] LoRA fine-tune whisper-small (Kaggle/Colab) → sanity check
- [ ] LoRA fine-tune large-v3-turbo (rented A100)
- [ ] Compare against baseline; pick a winner
- [ ] Publish model + model card on Hugging Face
- [ ] Export to CTranslate2 and point the server's `MODEL_PATH` at it
**Exit:** WER clearly better than best baseline on frozen test set.

## Phase 3 — API (track B, weeks 1–4) 🚧 current
- [x] `server/` skeleton: config, error envelope, `GET /v1/health`, CI
- [x] Audio: ffmpeg decode, size/duration limits, temp files deleted in `finally`
- [x] `POST /v1/transcribe` with an off-the-shelf model (CPU `small` for dev); text through `sma3ni_ml.text`
- [x] `POST /v1/install`, bearer token, daily rate limit
- [ ] Dockerfile; deploy to serverless GPU
- [ ] Summary / translation / replies via LLM
- [ ] Load test: p95 latency for 30 s notes
**Exit:** public HTTPS endpoint, < 3 s p50.

## Phase 4 — Mobile MVP (track B, weeks 2–6)
- [ ] Expo app skeleton: TypeScript strict, Expo Router, i18n (ar/fr/en, RTL), CI
- [ ] "Pick audio file" → transcript screen with copy (works without any native code)
- [ ] Android share intent → APK for friends
- [ ] History, settings
- [ ] Arabizi output toggle
- [ ] iOS Share Extension → TestFlight (needs Apple Developer account; after the Android beta works)
**Exit:** 20+ beta testers using it daily.

## Phase 5 — Flywheel & launch (weeks 10–12)
- [ ] "Correct transcript" + opt-in donation
- [ ] Onboarding, privacy policy, store assets (`STORE_RELEASE.md`)
- [ ] Google Play closed test (12 testers / 14 days) → production
- [ ] App Store submission
- [ ] Launch post + demo video
**Exit:** live on both stores.

## Phase 6 — v2 (after launch)
- On-device model (whisper.cpp, quantized small/base) for offline + free inference
- Monthly retraining with donated data
- Algerian / Moroccan dialects
- Paper / write-up for master's applications
