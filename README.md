# Sma3ni 🎙️ — Tunisian voice notes → text

> Can't listen to a voice note right now? Share it to Sma3ni and read it in seconds.
> Built for **Tunisian Darija**, including the Darija + French mix everyone actually speaks.

_Working name. Can be renamed (Kteb, Fhemni…) before store launch._

## What it does
1. In WhatsApp (or any app), long-press a voice note → **Share** → **Sma3ni**
2. Get the transcript in **Arabic script** or **Arabizi** (3aslema, ya5i…)
3. Optional: a **summary** for long notes, a **French/English translation**, and **quick replies**
4. Audio is **deleted right after transcription**. Nothing is stored without consent.

## Why
- Off-the-shelf speech models (including plain Whisper) perform very poorly on Tunisian dialect.
- Research datasets and models exist (LinTO, TuniSpeech, TEDxTN), but **no consumer product** targets real, noisy, code-switched WhatsApp voice notes.

## How it works
```
WhatsApp voice note ──Share──▶ Sma3ni app ──HTTPS──▶ API (FastAPI)
                                                     1. check + clean the audio (ffmpeg)
                                                     2. Whisper large-v3-turbo (Groq, for now)
                                                     3. Darija spelling rules → Arabic or Arabizi
                                                     4. delete the audio
                     transcript (kept on the phone only) ◀──┘
```
- **Today:** the API is live on Render's free tier with Groq's Whisper: a 30 s note takes about **2 s**. The app (Phase 4) is next.
- **Next model:** our own Whisper fine-tuned on real Tunisian voice notes (Phases 1–2), swapped in with one setting.
- **Privacy:** no accounts, audio deleted after each request, metadata stripped before anything leaves the server, transcripts never stored on the server. See [docs/PRIVACY.md](docs/PRIVACY.md).

## Repo layout
```
sma3ni/
├── AGENTS.md            # Instructions for AI coding agents (read first)
├── CLAUDE.md            # Points to AGENTS.md
├── CONTRIBUTING.md
├── LICENSE              # Apache-2.0
├── NOTICE               # Copyright / attribution notice
├── render.yaml          # Free hosting of the API (Render Blueprint)
├── docs/
│   ├── PRD.md                       # Product requirements
│   ├── ARCHITECTURE.md              # System design
│   ├── ROADMAP.md                   # Phases & milestones
│   ├── ML_PLAN.md                   # Data, training, evaluation
│   ├── TRANSCRIPTION_GUIDELINES.md  # Spelling convention (critical!)
│   ├── API.md                       # Backend API contract
│   ├── MOBILE.md                    # iOS/Android app + share extension
│   ├── PRIVACY.md                   # Privacy & data handling
│   ├── STORE_RELEASE.md             # App Store / Play Store checklist
│   └── LINKEDIN_PLAN.md             # Build-in-public plan
├── ml/        # Benchmarking, fine-tuning, export (Python)
├── server/    # FastAPI inference service (Python) + Dockerfile
└── mobile/    # Expo / React Native app + native share extensions
```

## Quick start
| Part | Command |
|---|---|
| ML benchmark | `cd ml && uv sync && uv run python -m sma3ni_ml.benchmark --config configs/benchmark.yaml` |
| Server | `cd server && uv sync && uv run uvicorn app.main:app --reload` (needs ffmpeg). Default: Whisper `small` on CPU, downloaded once (~480 MB). Faster: put `ASR_BACKEND=groq` and a free [Groq](https://console.groq.com) key in `server/.env` (see `.env.example`) |
| Server image | `docker build -f server/Dockerfile -t sma3ni-server .` (from the repo root) |
| Mobile | `cd mobile && npm install && npx expo start` |

See each folder's `AGENTS.md` / `README.md` for details.

## Status
| Phase | State |
|---|---|
| 1. Benchmark (collect + transcribe real voice notes) | 🚧 collecting data |
| 2. Fine-tune our Darija model | ⏳ after Phase 1 |
| 3. API | ✅ live: free hosting (Render + Groq), 30 s note in ~2 s |
| 4. Mobile app (Android first) | 🚧 next |
| 5. Summaries, translation, store launch | ⏳ |

Details: [docs/ROADMAP.md](docs/ROADMAP.md).

## License
- Code: [Apache-2.0](LICENSE), © 2026 Hsan Jebri. Redistributions must keep the [NOTICE](NOTICE) file.
- Models: released on Hugging Face under a license compatible with their training data (see `docs/ML_PLAN.md`)
- Not affiliated with WhatsApp or Meta.
