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
    ai_provider: str = os.getenv("AI_PROVIDER", "mock")
    ai_model: str = os.getenv("AI_MODEL", "mock-heuristic-v1")
    ai_triage_provider: str = os.getenv("AI_TRIAGE_PROVIDER", "")
    ai_triage_model: str = os.getenv("AI_TRIAGE_MODEL", "")
    ai_planner_provider: str = os.getenv("AI_PLANNER_PROVIDER", "")
    ai_planner_model: str = os.getenv("AI_PLANNER_MODEL", "")
    ai_planner_escalation_provider: str = os.getenv("AI_PLANNER_ESCALATION_PROVIDER", "")
    ai_planner_escalation_model: str = os.getenv("AI_PLANNER_ESCALATION_MODEL", "")
    ai_fallback_provider: str = os.getenv("AI_FALLBACK_PROVIDER", "")
    ai_fallback_model: str = os.getenv("AI_FALLBACK_MODEL", "")
    ai_triage_confidence_threshold: float = float(
        os.getenv("AI_TRIAGE_CONFIDENCE_THRESHOLD", "0.8")
    )
    ai_enabled: bool = _as_bool(os.getenv("AI_ENABLED", "true"), default=True)
    evidence_adapter: str = os.getenv("EVIDENCE_ADAPTER", "mock")
    execution_adapter: str = os.getenv("EXECUTION_ADAPTER", "mock")

    operator_session_secret: str = os.getenv("OPERATOR_SESSION_SECRET", "")
    operator_session_ttl_seconds: int = int(os.getenv("OPERATOR_SESSION_TTL_SECONDS", "28800"))
    operator_secure_cookies: bool = _as_bool(
        os.getenv("OPERATOR_SECURE_COOKIES", "false"),
        default=False,
    )
    operator_users_json: str = os.getenv("OPERATOR_USERS_JSON", "")
    operator_users_file: str = os.getenv("OPERATOR_USERS_FILE", "")

    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("APP_PORT", "8000"))


settings = Settings()
