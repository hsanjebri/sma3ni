# Architecture — Sma3ni

## Overview
```
 WhatsApp / any app
        │  Share (audio file: .opus/.ogg/.m4a/.aac)
        ▼
┌──────────────────────────┐
│ Mobile app (Expo/RN)     │
│  • iOS Share Extension   │  Swift: receives file, hands it to the app group
│  • Android share intent  │  Kotlin: ACTION_SEND audio/*
│  • Local history (SQLite)│  on-device only
└───────────┬──────────────┘
            │ HTTPS  POST /v1/transcribe  (multipart, ≤ 5 min audio)
            ▼
┌──────────────────────────┐
│ Inference API (FastAPI)  │
│  1. validate + ffmpeg →  │  16 kHz mono WAV, in temp dir
│  2. ASR model            │  faster-whisper (CTranslate2), fine-tuned
│  3. normalize text       │  per TRANSCRIPTION_GUIDELINES.md
│  4. optional LLM step    │  summary / translation / quick replies
│  5. delete audio (finally)
└───────────┬──────────────┘
            │ JSON
            ▼
       Transcript in app
```

## Components

### `ml/` — training & evaluation (offline)
- `sma3ni_ml.data`: load LinTO, TuniSpeech, TEDxTN, our own data; normalize per guidelines; build HF `datasets`
- `sma3ni_ml.benchmark`: run N models on the frozen test set → WER / CER / code-switch F1 → `ml/RESULTS.md`
- `sma3ni_ml.train`: LoRA / full fine-tune with HF Transformers + PEFT; tracked in Weights & Biases
- `sma3ni_ml.export`: merge LoRA → convert to CTranslate2 (server) and GGML/whisper.cpp (on-device, v2)
- Models published to Hugging Face (`sma3ni/whisper-darija-*`)

### `server/` — inference API
- **FastAPI**, Python 3.11, pydantic schemas
- **faster-whisper** with the exported model; model loaded once at startup
- **ffmpeg** for decoding WhatsApp Opus/OGG
- **LLM** (provider via env var) for summary / translation / replies, called only when requested
- **Deployment:** container on a serverless GPU (Modal or RunPod) with scale-to-zero; CPU fallback with `small` model for dev
- **Auth:** per-install anonymous token (issued on first launch) + rate limit per token
- **Observability:** structured logs with metadata only (request id, duration, latency, model version); Sentry for errors (with content scrubbing)

### `mobile/` — app
- Expo (React Native, TypeScript, Expo Router) with config plugins for native targets
- iOS: Share Extension target in Swift → writes file to App Group container → opens main app via URL scheme, or transcribes inside the extension (memory limit ~120 MB, so prefer handoff)
- Android: intent filter `ACTION_SEND` / `audio/*` on a dedicated activity
- Local storage: SQLite (`expo-sqlite`) for history; settings in MMKV
- See `MOBILE.md`

## Data flow & privacy
- Audio: phone → server (TLS) → temp file → deleted in `finally`. Never written to object storage.
- Transcript: returned to phone, stored **only on the phone**.
- Donation (opt-in only): audio + corrected transcript uploaded to a separate, access-controlled bucket, tagged with consent version. See `PRIVACY.md`.

## Key decisions
| Decision | Choice | Why |
|---|---|---|
| ASR base model | Whisper large-v3-turbo (server), whisper-small (on-device) | Best fine-tuned dialect results; turbo is fast |
| Fine-tuning | LoRA first, full fine-tune if budget allows | Cheap, one GPU |
| Serving runtime | faster-whisper / CTranslate2 | ~4× faster than HF pipeline, int8 |
| Hosting | Serverless GPU | Pay per use, scale to zero |
| Mobile | Expo + native share extensions | One UI codebase, native where required |
| No backend DB for content | — | Privacy + simplicity |

## Latency budget (30 s note, p50)
| Step | Target |
|---|---|
| Upload (Opus is small) | 300 ms |
| Decode + resample | 100 ms |
| ASR (turbo, int8, GPU) | 1.2 s |
| Normalize | 10 ms |
| Summary (optional) | 1.0 s |
| **Total** | **< 3 s** |

Cold starts on serverless GPU can add 5–15 s: keep one warm instance during peak hours (evenings, Tunis time).
