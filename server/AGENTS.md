# server/AGENTS.md

Read the root `AGENTS.md` first. The API contract is `docs/API.md`.

## Scope
FastAPI inference service: decode audio, run ASR, normalize, optional LLM post-processing.

## Layout
```
server/
├── pyproject.toml
├── Dockerfile             # build from the repo root (needs ml/); also what the HF Space builds
├── deploy/
│   ├── hf_space.py        # deploy to a Hugging Face Docker Space (free MVP host)
│   └── space-card.md      # the Space's README
├── .env.example
├── app/
│   ├── main.py            # app factory, routers, lifespan (sweeps audio leftovers; loads model once)
│   ├── config.py          # pydantic-settings, all env vars
│   ├── schemas.py         # request/response models (match API.md exactly)
│   ├── errors.py          # ApiError → error envelope; unhandled errors logged by type only
│   ├── routes/            # health.py, install.py, transcribe.py; feedback.py (not written)
│   ├── services/
│   │   ├── audio.py       # upload → size/format/duration checks → 16 kHz mono WAV; temp dir per request
│   │   ├── asr.py         # ASR_BACKEND: local faster-whisper (decodes like the benchmark) or Groq
│   │   ├── text.py        # calls sma3ni_ml.text (path dependency on ../ml), never a copy
│   │   └── llm.py         # summary / translate / replies         (not written)
│   └── security.py        # signed install tokens, daily quota per token
└── tests/                 # pytest + httpx AsyncClient; small fixture audio only
```

Modules marked *not written* arrive with their step in `docs/ROADMAP.md` (Phase 3); don't stub them early.

## Rules
- **Privacy:** audio in a temp dir, deleted in `finally`; never log text or audio; scrub Sentry events. Add a test that asserts no temp files remain after a request (success and failure).
- **Errors:** raise `ApiError(ErrorCode.X, message)`; the HTTP status comes from the code (`errors.STATUS`, the table in `API.md`). Never put user text in a message. Anything else that escapes a route becomes `internal_error`, and only its exception type is logged, because exception messages can quote a transcript.
- Validate size/duration **before** running the model. `services.audio.prepared_audio()` does both and is the only way audio enters the server: it gives each request a `req-*` dir under `AUDIO_TMP_DIR` and removes it in `finally`. It blocks (copy + ffmpeg), so call it from a worker thread.
- **Auth:** every endpoint except `health` and `install` takes `token_id: TokenId`; anything that costs GPU time runs inside `daily_quota()`, which only counts successful requests. Never log a token.
- Model loaded once at startup (lifespan); expose `model_version` in responses and `/v1/health`.
- **Deploy:** `deploy/hf_space.py` uploads sources only and sets non-secret Space variables. Secrets (`GROQ_API_KEY`, `TOKEN_SECRET`) live in the Space settings, never in the repo or the script's output: `--set-groq-key` copies the key from `server/.env` (gitignored), e.g. after rotating it. One container, one process, so `MemoryUsageStore` is enough there; it resets when the Space restarts.
- **Two ASR backends** behind `asr.Transcriber`: `local` (faster-whisper here) and `groq` (Whisper on Groq's API, the free MVP: no GPU, but the audio goes to Groq, see `docs/PRIVACY.md`). Provider trouble (429, 5xx, timeout) is `503 busy`, never `500`.
- **Decode like the benchmark:** `services/asr.DECODE_OPTIONS` matches `sma3ni_ml.benchmark.FasterWhisperBackend`, so `ml/RESULTS.md` describes what users get. Change both together, and only on benchmark evidence.
- Heavy work (ASR) off the event loop (`run_in_threadpool` or a worker), with a concurrency limit per GPU.
- All config via env vars (`config.py`); update `.env.example` when adding one.
- Tests must not need a GPU: mock `asr.py` in unit tests; one optional integration test with `tiny` model marked `@pytest.mark.slow`.

## Env vars (see `.env.example`)
`ASR_BACKEND`, `GROQ_API_KEY`, `GROQ_MODEL`, `MODEL_PATH`, `MODEL_VERSION`, `DEVICE`, `COMPUTE_TYPE`, `MAX_AUDIO_SECONDS`, `MAX_UPLOAD_MB`, `AUDIO_TMP_DIR`, `ASR_CONCURRENCY`, `RATE_LIMIT_PER_DAY`, `TOKEN_SECRET`, `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`, `SENTRY_DSN`, `DONATION_BUCKET`

## System dependencies
`ffmpeg` and `ffprobe` on `PATH`, for the server and for the tests (they decode synthetic clips).
Windows: `winget install Gyan.FFmpeg` · macOS: `brew install ffmpeg` · Debian/Ubuntu: `apt install ffmpeg`.

## Commands
```bash
uv sync
uv run pytest                        # fast: Whisper is faked
uv run pytest -m slow                # real Whisper `tiny` on CPU (downloads it once)
uv run uvicorn app.main:app --reload # first start downloads Whisper `small` (~480 MB)
# Image (from the repo root): runs as uid 1000 on port 7860, like the Space
docker build -f server/Dockerfile -t sma3ni-server .
docker run --rm -p 7860:7860 --env-file server/.env sma3ni-server
# Deploy the free MVP (needs `uv run hf auth login` with a write token once)
uv run python deploy/hf_space.py <user>/<space> --dry-run
uv run python deploy/hf_space.py <user>/<space>
```
