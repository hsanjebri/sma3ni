# Roadmap — Sma3ni

Part-time estimate (~15–20 h/week). Each phase ends with a LinkedIn post (see `LINKEDIN_PLAN.md`).

## Phase 1 — Benchmark (weeks 1–2) 🚧 current
- [ ] Write `TRANSCRIPTION_GUIDELINES.md` v1 and freeze it
- [ ] Collect 1–2 h of real voice notes from friends/family with signed consent
- [ ] Transcribe them by hand (two people per clip for 10% of clips to measure agreement)
- [ ] Freeze the test set (`ml/data/test_v1` manifest, hash recorded in `ml/RESULTS.md`)
- [ ] Benchmark: whisper-large-v3, whisper-large-v3-turbo, TuniSpeech fine-tune, a multi-dialect Arabic fine-tune, w2v-BERT 2.0 (if a Tunisian fine-tune exists)
- [ ] Publish results table + blog/LinkedIn post
**Exit:** reproducible benchmark with one command.

## Phase 2 — Fine-tune (weeks 3–6)
- [ ] Data pipeline: LinTO + TuniSpeech + TEDxTN + own train data → normalized HF dataset
- [ ] Augmentation: noise, speed ±10%, Opus re-encoding at 16–24 kbps
- [ ] LoRA fine-tune whisper-small (Kaggle/Colab) → sanity check
- [ ] LoRA fine-tune large-v3-turbo (rented A100)
- [ ] Compare against baseline; pick a winner
- [ ] Publish model + model card on Hugging Face
**Exit:** WER clearly better than best baseline on frozen test set.

## Phase 3 — API (weeks 6–7)
- [ ] FastAPI service per `API.md`
- [ ] Export model to CTranslate2; deploy to serverless GPU
- [ ] Summary / translation / replies via LLM
- [ ] Load test: p95 latency for 30 s notes
**Exit:** public HTTPS endpoint, < 3 s p50.

## Phase 4 — Mobile MVP (weeks 7–9)
- [ ] Expo app: home, transcript screen, history, settings
- [ ] Android share intent → APK for friends
- [ ] iOS Share Extension → TestFlight (needs Apple Developer account)
- [ ] Arabizi output toggle
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
