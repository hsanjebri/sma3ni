# Sma3ni API image. Build from the repo root, since it needs ml/ for sma3ni_ml:
#   docker build -f server/Dockerfile -t sma3ni-server .
#   docker run --rm -p 7860:7860 --env-file server/.env sma3ni-server
# Hugging Face Spaces builds this same file (server/deploy/hf_space.py).
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /usr/local/bin/uv

# Hugging Face Spaces runs containers as uid 1000: build everything as that user.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    AUDIO_TMP_DIR=/tmp/sma3ni-audio \
    PORT=7860
WORKDIR /home/user/app

# Dependencies before the server code, so a code change doesn't reinstall them.
COPY --chown=user ml/pyproject.toml ml/uv.lock ml/
COPY --chown=user ml/src ml/src
COPY --chown=user server/pyproject.toml server/uv.lock server/
# --no-cache: the wheels are installed; a cache would add ~450 MB to the image.
RUN cd server && uv sync --frozen --no-dev --no-cache
COPY --chown=user server/app server/app

WORKDIR /home/user/app/server
ENV PATH="/home/user/app/server/.venv/bin:$PATH"
EXPOSE 7860
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
