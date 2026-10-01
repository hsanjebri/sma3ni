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

## Repo layout
```
sma3ni/
├── AGENTS.md            # Instructions for AI coding agents (read first)
├── CLAUDE.md            # Points to AGENTS.md
├── CONTRIBUTING.md
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
├── server/    # FastAPI inference service (Python)
└── mobile/    # Expo / React Native app + native share extensions
```

## Quick start
| Part | Command |
|---|---|
| ML benchmark | `cd ml && uv sync && uv run python -m sma3ni_ml.benchmark --config configs/benchmark.yaml` |
| Server | `cd server && uv sync && uv run uvicorn app.main:app --reload` |
| Mobile | `cd mobile && npm install && npx expo start` |

See each folder's `AGENTS.md` / `README.md` for details.

## Status
🚧 Phase 1: benchmark. See [docs/ROADMAP.md](docs/ROADMAP.md).

## License
- Code: Apache-2.0
- Models: released on Hugging Face under a license compatible with their training data (see `docs/ML_PLAN.md`)
- Not affiliated with WhatsApp or Meta.
