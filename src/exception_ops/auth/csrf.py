from __future__ import annotations

import secrets
import time

from fastapi import HTTPException, Request, status
from fastapi.responses import Response

from exception_ops.auth.security import load_signed_payload, sign_payload
from exception_ops.config import settings

LOGIN_CSRF_COOKIE_NAME = "exception_ops_login_csrf"


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def issue_login_csrf_cookie(response: Response, csrf_token: str | None = None) -> str:
    csrf_token = csrf_token or generate_csrf_token()
    signed_token = sign_payload(
        {
            "csrf": csrf_token,
            "exp": int(time.time()) + settings.operator_session_ttl_seconds,
        },
        settings.operator_session_secret,
    )
    response.set_cookie(
        key=LOGIN_CSRF_COOKIE_NAME,
        value=signed_token,
        max_age=settings.operator_session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.operator_secure_cookies,
        path="/",
    )
    return csrf_token


def clear_login_csrf_cookie(response: Response) -> None:
    response.delete_cookie(
        key=LOGIN_CSRF_COOKIE_NAME,
        httponly=True,
        samesite="lax",
        secure=settings.operator_secure_cookies,
        path="/",
    )


def validate_login_csrf(request: Request, form_token: str | None) -> None:
    signed_token = request.cookies.get(LOGIN_CSRF_COOKIE_NAME, "")
    payload = load_signed_payload(signed_token, settings.operator_session_secret)
    if payload is None:
        raise_invalid_csrf()

    try:
        cookie_token = str(payload["csrf"])
        expires_at = int(payload["exp"])
    except (KeyError, TypeError, ValueError):
        raise_invalid_csrf()

    if expires_at <= int(time.time()) or cookie_token != (form_token or ""):
        raise_invalid_csrf()


def validate_session_csrf(form_token: str | None, session_token: str | None) -> None:
    if not form_token or not session_token or form_token != session_token:
        raise_invalid_csrf()


def raise_invalid_csrf() -> None:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="invalid_csrf_token",
    )
