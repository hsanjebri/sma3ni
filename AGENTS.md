# AGENTS.md — instructions for AI coding agents

Read this file fully before making changes. Then read the `AGENTS.md` in the folder you are working in (`ml/`, `server/`, `mobile/`).

## Project in one paragraph
Sma3ni transcribes Tunisian Darija voice notes (often mixed with French/English) into text, with optional summary, translation and quick replies. It is a monorepo with three parts: `ml/` (benchmark + fine-tune speech models), `server/` (FastAPI inference API), and `mobile/` (Expo/React Native app with native share extensions on iOS and Android).

## Source of truth
| Topic | File |
|---|---|
| What we build and why | `docs/PRD.md` |
| How the system fits together | `docs/ARCHITECTURE.md` |
| What to work on now | `docs/ROADMAP.md` |
| ML data / training / eval | `docs/ML_PLAN.md` |
| How Darija is written in transcripts | `docs/TRANSCRIPTION_GUIDELINES.md` |
| API contract | `docs/API.md` |
| Mobile app details | `docs/MOBILE.md` |
| Privacy rules | `docs/PRIVACY.md` |

If code and docs disagree, **stop and flag it**. Don't silently pick one. If you change behavior, update the relevant doc in the same change.

## Non-negotiable rules
1. **Privacy first.** Never persist user audio or transcripts on the server. Audio lives in memory or a temp file and is deleted in a `finally` block. Never log audio content or transcript text, only metadata (duration, latency, model version). See `docs/PRIVACY.md`.
2. **No secrets in code.** Use environment variables and `.env.example`. Never commit `.env`, API keys, model tokens or keystores.
3. **Don't touch `data/`** contents or commit datasets/audio. `data/` is gitignored. Datasets are referenced by path or Hugging Face ID.
4. **Respect the API contract** in `docs/API.md`. Breaking changes need a new version prefix (`/v2`).
5. **Transcription convention** in `docs/TRANSCRIPTION_GUIDELINES.md` applies to every text normalization function, dataset preparation script and evaluation metric.
6. **Small, reviewable steps.** One concern per commit, each with its tests. Each phase or big feature lives on its own branch (`phase/3-api`...), see `CONTRIBUTING.md`.
7. **No WhatsApp scraping or private APIs.** Audio enters the app only through the OS share sheet / file picker.

## Tooling conventions
- **Python** (ml/, server/): Python 3.11+, `uv` for env/deps, `ruff` (lint + format), `pytest`, type hints everywhere, `pydantic` for schemas.
- **TypeScript** (mobile/): strict mode, ESLint + Prettier, Expo Router, no `any` unless justified in a comment.
- **Native**: Swift for the iOS Share Extension, Kotlin for Android share intent handling.
- **Commits**: Conventional Commits (`feat:`, `fix:`, `docs:`, `ml:`, `chore:`).

## Commands
```bash
# ML
cd ml && uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run python -m sma3ni_ml.benchmark --config configs/benchmark.yaml

# Server
cd server && uv sync
uv run pytest
uv run uvicorn app.main:app --reload

# Mobile
cd mobile && npm install
npm run lint && npm run typecheck && npm test
npx expo start
```

## Definition of done
- Tests pass and lint is clean
- Relevant docs updated
- No new logging of user content
- For ML changes: metrics reported (WER, CER, code-switch F1) on the **frozen test set** and compared to the current baseline in `ml/RESULTS.md`
- For API changes: `docs/API.md` and the mobile client updated together

## When unsure
Prefer asking (leave a `TODO(question):` comment and mention it in the PR) over guessing on: spelling conventions, privacy-affecting behavior, store policy, or anything that changes the frozen test set.
