from __future__ import annotations

from fastapi import APIRouter

from exception_ops.config import settings

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "exception-ops",
        "env": settings.env,
    }
