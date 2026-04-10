from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable
from urllib.parse import quote

from fastapi import HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response

from exception_ops.auth.models import OperatorIdentity, OperatorRole
from exception_ops.auth.security import get_operator_identity, load_signed_payload, sign_payload
from exception_ops.config import settings

SESSION_COOKIE_NAME = "exception_ops_session"
DEFAULT_OPERATOR_PATH = "/operator/exceptions"


@dataclass(frozen=True, slots=True)
class AuthenticatedSession:
    username: str
    expires_at: int
    csrf_token: str


def build_operator_login_redirect(request: Request) -> RedirectResponse:
    next_path = DEFAULT_OPERATOR_PATH
    if request.method == "GET":
        next_path = sanitize_next_path(str(request.url.path))
    return RedirectResponse(
        url=f"/operator/login?next={quote(next_path)}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def sanitize_next_path(next_path: str | None) -> str:
    if not next_path:
        return DEFAULT_OPERATOR_PATH
    if not next_path.startswith("/") or next_path.startswith("//"):
        return DEFAULT_OPERATOR_PATH
    if next_path.startswith("/operator/login"):
        return DEFAULT_OPERATOR_PATH
    return next_path


def create_session_token(username: str, csrf_token: str) -> tuple[str, int]:
    expires_at = int(time.time()) + settings.operator_session_ttl_seconds
    token = sign_payload(
        {
            "sub": username,
            "exp": expires_at,
            "csrf": csrf_token,
        },
        settings.operator_session_secret,
    )
    return token, expires_at


def set_session_cookie(response: Response, username: str, csrf_token: str) -> None:
    token, expires_at = create_session_token(username, csrf_token)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=max(0, expires_at - int(time.time())),
        httponly=True,
        samesite="lax",
        secure=settings.operator_secure_cookies,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        samesite="lax",
        secure=settings.operator_secure_cookies,
        path="/",
    )


def get_optional_session(request: Request) -> AuthenticatedSession | None:
    cached_session = getattr(request.state, "operator_session", None)
    if cached_session is not None:
        return cached_session

    token = request.cookies.get(SESSION_COOKIE_NAME)
    payload = load_signed_payload(token or "", settings.operator_session_secret)
    if payload is None:
        return None

    try:
        auth_session = AuthenticatedSession(
            username=str(payload["sub"]),
            expires_at=int(payload["exp"]),
            csrf_token=str(payload["csrf"]),
        )
    except (KeyError, TypeError, ValueError):
        return None

    if auth_session.expires_at <= int(time.time()):
        return None

    request.state.operator_session = auth_session
    return auth_session


def get_authenticated_session(request: Request) -> AuthenticatedSession:
    auth_session = get_optional_session(request)
    if auth_session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="auth_required",
        )
    return auth_session


def get_optional_operator(request: Request) -> OperatorIdentity | None:
    cached_operator = getattr(request.state, "operator_identity", None)
    if cached_operator is not None:
        return cached_operator

    auth_session = get_optional_session(request)
    if auth_session is None:
        return None

    operator = get_operator_identity(auth_session.username)
    if operator is None:
        return None

    request.state.operator_identity = operator
    return operator


def get_authenticated_operator(request: Request) -> OperatorIdentity:
    operator = get_optional_operator(request)
    if operator is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="auth_required",
        )
    return operator


def ensure_operator_roles(operator: OperatorIdentity, *roles: OperatorRole) -> OperatorIdentity:
    if not operator.has_any_role(*roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="insufficient_role",
        )
    return operator


def require_api_roles(*roles: OperatorRole) -> Callable[[Request], OperatorIdentity]:
    def dependency(request: Request) -> OperatorIdentity:
        operator = get_authenticated_operator(request)
        return ensure_operator_roles(operator, *roles)

    return dependency


def get_operator_page_context(
    request: Request,
    *roles: OperatorRole,
) -> tuple[OperatorIdentity | None, AuthenticatedSession | None]:
    operator = get_optional_operator(request)
    if operator is None:
        return None, None
    ensure_operator_roles(operator, *roles)
    return operator, get_authenticated_session(request)
