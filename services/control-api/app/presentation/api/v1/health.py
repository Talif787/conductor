"""Liveness and readiness probes."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/livez")
async def livez() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/readyz")
async def readyz(request: Request, response: Response) -> dict[str, str]:
    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        return {"status": "ready", "database": "not-configured"}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not-ready", "database": "unavailable"}
    return {"status": "ready", "database": "ok"}
