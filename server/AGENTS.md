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
│   ├── main.py            # app factory, routers, lifespan (loads model once)
│   ├── config.py          # pydantic-settings, all env vars
│   ├── schemas.py         # request/response models (match API.md exactly)
│   ├── errors.py          # ApiError → error envelope; unhandled errors logged by type only
│   ├── routes/            # health.py; transcribe.py, feedback.py, install.py (not written)
│   ├── services/                                                (not written)
│   │   ├── audio.py       # ffmpeg decode → 16 kHz mono, temp-file handling
│   │   ├── asr.py         # faster-whisper wrapper
│   │   ├── text.py        # calls sma3ni_ml.text (path dependency on ../ml), never a copy
│   │   └── llm.py         # summary / translate / replies
│   └── security.py        # token auth, rate limit                (not written)
└── tests/                 # pytest + httpx AsyncClient; small fixture audio only
```

Modules marked *not written* arrive with their step in `docs/ROADMAP.md` (Phase 3); don't stub them early.

## Rules
- **Privacy:** audio in a temp dir, deleted in `finally`; never log text or audio; scrub Sentry events. Add a test that asserts no temp files remain after a request (success and failure).
- **Errors:** raise `ApiError(ErrorCode.X, message)`; the HTTP status comes from the code (`errors.STATUS`, the table in `API.md`). Never put user text in a message. Anything else that escapes a route becomes `internal_error`, and only its exception type is logged, because exception messages can quote a transcript.
- Validate size/duration **before** running the model.
- Model loaded once at startup (lifespan); expose `model_version` in responses and `/v1/health`.
- Heavy work (ASR) off the event loop (`run_in_threadpool` or a worker), with a concurrency limit per GPU.
- All config via env vars (`config.py`); update `.env.example` when adding one.
- Tests must not need a GPU: mock `asr.py` in unit tests; one optional integration test with `tiny` model marked `@pytest.mark.slow`.

## Env vars (see `.env.example`)
`MODEL_PATH`, `MODEL_VERSION`, `DEVICE`, `COMPUTE_TYPE`, `MAX_AUDIO_SECONDS`, `MAX_UPLOAD_MB`, `RATE_LIMIT_PER_DAY`, `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`, `SENTRY_DSN`, `DONATION_BUCKET`

## Commands
```bash
uv sync
uv run pytest
uv run uvicorn app.main:app --reload
docker build -t sma3ni-server . && docker run --gpus all -p 8000:8000 --env-file .env sma3ni-server
```
