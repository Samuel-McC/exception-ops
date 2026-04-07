from __future__ import annotations

import os
from pydantic import BaseModel


def _as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings(BaseModel):
    env: str = os.getenv("ENV", "dev")

    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://exceptionops:exceptionops@db:5432/exceptionops",
    )
    db_auto_create: bool = _as_bool(os.getenv("DB_AUTO_CREATE", "false"), default=False)

    temporal_host: str = os.getenv("TEMPORAL_HOST", "temporal:7233")
    temporal_namespace: str = os.getenv("TEMPORAL_NAMESPACE", "default")
    temporal_task_queue: str = os.getenv("TEMPORAL_TASK_QUEUE", "exception-resolution")

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    ai_provider: str = os.getenv("AI_PROVIDER", "openai")
    ai_model: str = os.getenv("AI_MODEL", "gpt-5.4-mini")
    ai_enabled: bool = _as_bool(os.getenv("AI_ENABLED", "true"), default=True)

    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("APP_PORT", "8000"))


settings = Settings()
