from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from exception_ops.api.routes.exceptions import router as exceptions_router
from exception_ops.api.routes.health import router as health_router
from exception_ops.config import settings
from exception_ops.db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.db_auto_create:
        init_db()
    yield

app = FastAPI(
    title="ExceptionOps",
    version="0.1.0",
    description="AI-assisted exception-resolution platform.",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(exceptions_router)
