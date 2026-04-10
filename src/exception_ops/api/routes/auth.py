from __future__ import annotations

from html import escape

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from exception_ops.api.forms import parse_form_body
from exception_ops.api.operator_ui import render_page
from exception_ops.auth import (
    authenticate_operator,
    clear_login_csrf_cookie,
    clear_session_cookie,
    generate_csrf_token,
    get_authenticated_session,
    get_optional_operator,
    is_operator_auth_configured,
    issue_login_csrf_cookie,
    sanitize_next_path,
    set_session_cookie,
    validate_login_csrf,
    validate_session_csrf,
)

router = APIRouter(prefix="/operator", tags=["operator-auth"])


@router.get("/login", response_class=HTMLResponse)
def operator_login_page(request: Request) -> Response:
    operator = get_optional_operator(request)
    if operator is not None:
        target = sanitize_next_path(request.query_params.get("next"))
        return RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)

    if not is_operator_auth_configured():
        return HTMLResponse(
            render_page(
                "Operator Login",
                (
                    "<h1>Operator Login</h1>"
                    "<p>Operator authentication is not configured.</p>"
                ),
            ),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return _render_login_page(
        next_path=sanitize_next_path(request.query_params.get("next")),
        message=request.query_params.get("message"),
    )


@router.post("/login", response_class=HTMLResponse)
async def operator_login(request: Request) -> Response:
    if not is_operator_auth_configured():
        return HTMLResponse(
            render_page(
                "Operator Login",
                (
                    "<h1>Operator Login</h1>"
                    "<p>Operator authentication is not configured.</p>"
                ),
            ),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    form_data = await parse_form_body(request)
    next_path = sanitize_next_path(form_data.get("next"))
    try:
        validate_login_csrf(request, form_data.get("csrf_token"))
    except HTTPException:
        return _render_login_page(
            next_path=next_path,
            error="Invalid CSRF token.",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    operator = authenticate_operator(
        form_data.get("username", ""),
        form_data.get("password", ""),
    )
    if operator is None:
        return _render_login_page(
            next_path=next_path,
            error="Invalid username or password.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    session_csrf_token = generate_csrf_token()
    response = RedirectResponse(url=next_path, status_code=status.HTTP_303_SEE_OTHER)
    set_session_cookie(response, operator.username, session_csrf_token)
    clear_login_csrf_cookie(response)
    return response


@router.post("/logout")
async def operator_logout(request: Request) -> Response:
    operator = get_optional_operator(request)
    if operator is None:
        return RedirectResponse(url="/operator/login", status_code=status.HTTP_303_SEE_OTHER)

    auth_session = get_authenticated_session(request)
    form_data = await parse_form_body(request)
    try:
        validate_session_csrf(form_data.get("csrf_token"), auth_session.csrf_token)
    except HTTPException:
        return HTMLResponse(
            render_page(
                "Forbidden",
                "<h1>Forbidden</h1><p>invalid_csrf_token</p>",
                operator=operator,
                csrf_token=auth_session.csrf_token,
            ),
            status_code=status.HTTP_403_FORBIDDEN,
        )

    response = RedirectResponse(
        url="/operator/login?message=Logged%20out.",
        status_code=status.HTTP_303_SEE_OTHER,
    )
    clear_session_cookie(response)
    clear_login_csrf_cookie(response)
    return response


def _render_login_page(
    *,
    next_path: str,
    error: str | None = None,
    message: str | None = None,
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    csrf_token = generate_csrf_token()
    response = HTMLResponse(
        render_page(
            "Operator Login",
            _build_login_body(
                next_path=next_path,
                csrf_token=csrf_token,
                error=error,
                message=message,
            ),
        ),
        status_code=status_code,
    )
    issue_login_csrf_cookie(response, csrf_token)
    return response


def _build_login_body(
    *,
    next_path: str,
    csrf_token: str,
    error: str | None,
    message: str | None,
) -> str:
    error_block = f'<p class="error">{escape(error)}</p>' if error else ""
    message_block = f'<p class="message">{escape(message)}</p>' if message else ""
    return (
        "<h1>Operator Login</h1>"
        "<p>Sign in to access the protected operator review and action surface.</p>"
        f"{message_block}"
        f"{error_block}"
        '<form method="post" action="/operator/login">'
        f'<input type="hidden" name="next" value="{escape(next_path)}">'
        f'<input type="hidden" name="csrf_token" value="{escape(csrf_token)}">'
        '<label>Username<input type="text" name="username" maxlength="255" required></label>'
        '<label>Password<input type="password" name="password" maxlength="255" required></label>'
        '<button type="submit">Login</button>'
        "</form>"
    )
