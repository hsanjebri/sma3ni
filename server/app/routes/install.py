"""`POST /v1/install` (docs/API.md): one anonymous token per app install."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas import InstallResponse
from app.security import TokenSigner

router = APIRouter()


@router.post("/install")
async def install(request: Request) -> InstallResponse:
    # TODO(question): anyone can call this as often as they like, so the
    # per-token limit caps an app, not an abuser. Options before a public
    # launch: Play Integrity / App Attest, a per-IP limit on installs (CGNAT
    # means many Tunisians share one IP), or a global daily cap on GPU time.
    signer: TokenSigner = request.app.state.token_signer
    return InstallResponse(token=signer.issue())
