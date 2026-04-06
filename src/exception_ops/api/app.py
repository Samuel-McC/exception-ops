from __future__ import annotations

from fastapi import FastAPI

from exception_ops.api.routes.health import router as health_router

app = FastAPI(
    title="ExceptionOps",
    version="0.1.0",
    description="AI-assisted exception-resolution platform.",
)

app.include_router(health_router)
