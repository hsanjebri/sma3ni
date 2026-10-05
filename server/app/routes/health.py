from __future__ import annotations

from fastapi import APIRouter, Request

from app.config import Settings
from app.schemas import HealthResponse

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> HealthResponse:
    settings: Settings = request.app.state.settings
    return HealthResponse(status="ok", model_version=settings.model_version)
