# server/AGENTS.md

Read the root `AGENTS.md` first. The API contract is `docs/API.md`.

## Scope
FastAPI inference service: decode audio, run ASR, normalize, optional LLM post-processing.

## Layout
```
server/
├── pyproject.toml
├── Dockerfile
├── .env.example
├── app/
│   ├── main.py            # app factory, routers, lifespan (loads model once)
│   ├── config.py          # pydantic-settings, all env vars
│   ├── schemas.py         # request/response models (match API.md exactly)
│   ├── routes/            # transcribe.py, feedback.py, install.py, health.py
│   ├── services/
│   │   ├── audio.py       # ffmpeg decode → 16 kHz mono, temp-file handling
│   │   ├── asr.py         # faster-whisper wrapper
│   │   ├── text.py        # normalize + arabizi (shared logic with ml/, keep in sync)
│   │   └── llm.py         # summary / translate / replies
│   └── security.py        # token auth, rate limit
└── tests/                 # pytest + httpx AsyncClient; small fixture audio only
```

## Rules
- **Privacy:** audio in a temp dir, deleted in `finally`; never log text or audio; scrub Sentry events. Add a test that asserts no temp files remain after a request (success and failure).
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
