from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from pathlib import Path
from typing import Any

from exception_ops.auth.models import ConfiguredOperator, OperatorIdentity, OperatorRole
from exception_ops.config import settings

PBKDF2_ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 390_000


def _urlsafe_b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _urlsafe_b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def sign_payload(payload: dict[str, Any], secret: str) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    return f"{_urlsafe_b64encode(body)}.{_urlsafe_b64encode(signature)}"


def load_signed_payload(token: str, secret: str) -> dict[str, Any] | None:
    if not token or "." not in token or not secret:
        return None

    body_token, signature_token = token.split(".", 1)
    try:
        body = _urlsafe_b64decode(body_token)
        signature = _urlsafe_b64decode(signature_token)
    except (ValueError, TypeError):
        return None

    expected_signature = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected_signature):
        return None

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    salt_value = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt_value,
        PBKDF2_ITERATIONS,
    )
    return (
        f"{PBKDF2_ALGORITHM}${PBKDF2_ITERATIONS}$"
        f"{_urlsafe_b64encode(salt_value)}${_urlsafe_b64encode(digest)}"
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt_token, digest_token = password_hash.split("$", 3)
    except ValueError:
        return False

    if algorithm != PBKDF2_ALGORITHM:
        return False

    try:
        salt = _urlsafe_b64decode(salt_token)
        expected_digest = _urlsafe_b64decode(digest_token)
        derived_digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt,
            int(iterations),
        )
    except (TypeError, ValueError):
        return False

    return hmac.compare_digest(derived_digest, expected_digest)


def _load_raw_operator_config() -> str:
    operator_users_file = settings.operator_users_file.strip()
    if operator_users_file:
        return Path(operator_users_file).read_text(encoding="utf-8")
    return settings.operator_users_json.strip()


def load_configured_operators() -> dict[str, ConfiguredOperator]:
    raw_config = _load_raw_operator_config()
    if not raw_config:
        return {}

    payload = json.loads(raw_config)
    if not isinstance(payload, dict):
        raise ValueError("Operator configuration must be a JSON object keyed by username")

    operators: dict[str, ConfiguredOperator] = {}
    for username, definition in payload.items():
        if not isinstance(definition, dict):
            raise ValueError("Each operator entry must be a JSON object")

        password_hash = str(definition.get("password_hash", "")).strip()
        if not password_hash:
            raise ValueError(f"Operator {username!r} is missing password_hash")

        role_values = definition.get("roles", [])
        if not isinstance(role_values, list) or not role_values:
            raise ValueError(f"Operator {username!r} must define at least one role")

        roles = frozenset(OperatorRole(value) for value in role_values)
        operators[username] = ConfiguredOperator(
            username=username,
            password_hash=password_hash,
            roles=roles,
        )

    return operators


def is_operator_auth_configured() -> bool:
    return bool(settings.operator_session_secret.strip()) and bool(load_configured_operators())


def get_operator_identity(username: str) -> OperatorIdentity | None:
    operator = load_configured_operators().get(username)
    if operator is None:
        return None
    return OperatorIdentity(username=operator.username, roles=operator.roles)


def authenticate_operator(username: str, password: str) -> OperatorIdentity | None:
    normalized_username = username.strip()
    if not normalized_username or not password:
        return None

    configured_operator = load_configured_operators().get(normalized_username)
    if configured_operator is None:
        return None
    if not verify_password(password, configured_operator.password_hash):
        return None

    return OperatorIdentity(
        username=configured_operator.username,
        roles=configured_operator.roles,
    )
