# server/AGENTS.md

Read the root `AGENTS.md` first. The API contract is `docs/API.md`.

## Scope
FastAPI inference service: decode audio, run ASR, normalize, optional LLM post-processing.

## Layout
```
server/
├── pyproject.toml
├── Dockerfile                                                   (not written)
├── .env.example
├── app/
│   ├── main.py            # app factory, routers, lifespan (sweeps audio leftovers; loads model once)
│   ├── config.py          # pydantic-settings, all env vars
│   ├── schemas.py         # request/response models (match API.md exactly)
│   ├── errors.py          # ApiError → error envelope; unhandled errors logged by type only
│   ├── routes/            # health.py; transcribe.py, feedback.py, install.py (not written)
│   ├── services/
│   │   ├── audio.py       # upload → size/format/duration checks → 16 kHz mono WAV; temp dir per request
│   │   ├── asr.py         # faster-whisper wrapper                (not written)
│   │   ├── text.py        # calls sma3ni_ml.text (path dependency on ../ml), never a copy (not written)
│   │   └── llm.py         # summary / translate / replies         (not written)
│   └── security.py        # token auth, rate limit                (not written)
└── tests/                 # pytest + httpx AsyncClient; small fixture audio only
```

Modules marked *not written* arrive with their step in `docs/ROADMAP.md` (Phase 3); don't stub them early.

## Rules
- **Privacy:** audio in a temp dir, deleted in `finally`; never log text or audio; scrub Sentry events. Add a test that asserts no temp files remain after a request (success and failure).
- **Errors:** raise `ApiError(ErrorCode.X, message)`; the HTTP status comes from the code (`errors.STATUS`, the table in `API.md`). Never put user text in a message. Anything else that escapes a route becomes `internal_error`, and only its exception type is logged, because exception messages can quote a transcript.
- Validate size/duration **before** running the model. `services.audio.prepared_audio()` does both and is the only way audio enters the server: it gives each request a `req-*` dir under `AUDIO_TMP_DIR` and removes it in `finally`. It blocks (copy + ffmpeg), so call it from a worker thread.
- Model loaded once at startup (lifespan); expose `model_version` in responses and `/v1/health`.
- Heavy work (ASR) off the event loop (`run_in_threadpool` or a worker), with a concurrency limit per GPU.
- All config via env vars (`config.py`); update `.env.example` when adding one.
- Tests must not need a GPU: mock `asr.py` in unit tests; one optional integration test with `tiny` model marked `@pytest.mark.slow`.

## Env vars (see `.env.example`)
`MODEL_PATH`, `MODEL_VERSION`, `DEVICE`, `COMPUTE_TYPE`, `MAX_AUDIO_SECONDS`, `MAX_UPLOAD_MB`, `AUDIO_TMP_DIR`, `RATE_LIMIT_PER_DAY`, `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`, `SENTRY_DSN`, `DONATION_BUCKET`

## System dependencies
`ffmpeg` and `ffprobe` on `PATH`, for the server and for the tests (they decode synthetic clips).
Windows: `winget install Gyan.FFmpeg` · macOS: `brew install ffmpeg` · Debian/Ubuntu: `apt install ffmpeg`.

## Commands
```bash
uv sync
uv run pytest
uv run uvicorn app.main:app --reload
docker build -t sma3ni-server . && docker run --gpus all -p 8000:8000 --env-file .env sma3ni-server
```
