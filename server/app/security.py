"""Install tokens and the per-token daily limit (docs/API.md, "Auth").

Tokens are signed, not stored: `<id>.<HMAC-SHA256(TOKEN_SECRET, id)>`. The
server checks one without keeping a list of installs, and all it remembers per
token is how many transcriptions it had today. Never log a token: it is a
credential.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import math
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated, Protocol

from fastapi import Depends, Header, Request

from app.config import Settings
from app.errors import ApiError
from app.schemas import ErrorCode


class TokenSigner:
    def __init__(self, secret: bytes) -> None:
        self._secret = secret

    def issue(self) -> str:
        token_id = secrets.token_urlsafe(16)
        return f"{token_id}.{self._sign(token_id)}"

    def verify(self, token: str) -> str | None:
        """The token's id if we signed it, else None."""
        token_id, _, signature = token.partition(".")
        if not token_id or not signature:
            return None
        # Bytes, not str: compare_digest rejects non-ASCII strings with an error.
        if not hmac.compare_digest(signature.encode(), self._sign(token_id).encode()):
            return None
        return token_id

    def _sign(self, token_id: str) -> str:
        digest = hmac.new(self._secret, token_id.encode(), hashlib.sha256).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


class UsageStore(Protocol):
    """Today's transcription count per token."""

    async def reserve(self, day: str, token_id: str, limit: int) -> bool: ...

    async def release(self, day: str, token_id: str) -> None: ...


class MemoryUsageStore:
    """Counts in process memory: each worker counts alone, and a restart resets.

    Enough for dev and a single instance. A deployment that scales out or to
    zero needs a shared store with the same interface (ROADMAP Phase 3, deploy).
    """

    def __init__(self) -> None:
        self._day = ""
        self._counts: dict[str, int] = {}

    async def reserve(self, day: str, token_id: str, limit: int) -> bool:
        if day != self._day:
            # Yesterday's counts are dropped, not archived.
            self._day, self._counts = day, {}
        used = self._counts.get(token_id, 0)
        if used >= limit:
            return False
        self._counts[token_id] = used + 1
        return True

    async def release(self, day: str, token_id: str) -> None:
        if day == self._day and self._counts.get(token_id, 0) > 0:
            self._counts[token_id] -= 1


async def require_token(
    request: Request, authorization: Annotated[str | None, Header()] = None
) -> str:
    """The caller's token id, or `401 unauthorized`."""
    scheme, _, token = (authorization or "").partition(" ")
    signer: TokenSigner = request.app.state.token_signer
    token_id = signer.verify(token.strip()) if scheme.lower() == "bearer" else None
    if token_id is None:
        raise ApiError(
            ErrorCode.UNAUTHORIZED, "Missing or invalid token. Get a new one from POST /v1/install."
        )
    return token_id


TokenId = Annotated[str, Depends(require_token)]


@asynccontextmanager
async def daily_quota(request: Request, token_id: str) -> AsyncIterator[None]:
    """Take one of today's transcriptions (UTC day); give it back if the request fails.

    So only successful transcriptions count, and a burst of parallel requests
    cannot get past the limit.
    """
    settings: Settings = request.app.state.settings
    store: UsageStore = request.app.state.usage
    now = datetime.now(UTC)
    day = now.date().isoformat()
    if not await store.reserve(day, token_id, settings.rate_limit_per_day):
        next_day = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        raise ApiError(
            ErrorCode.RATE_LIMITED,
            f"Daily limit of {settings.rate_limit_per_day} transcriptions reached.",
            headers={"Retry-After": str(math.ceil((next_day - now).total_seconds()))},
        )
    try:
        yield
    except BaseException:
        await store.release(day, token_id)
        raise
