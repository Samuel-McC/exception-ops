from __future__ import annotations

from html import escape

from exception_ops.auth import OperatorIdentity


def render_page(
    title: str,
    body: str,
    *,
    operator: OperatorIdentity | None = None,
    csrf_token: str | None = None,
) -> str:
    return (
        "<!doctype html>"
        "<html><head>"
        f"<title>{escape(title)}</title>"
        "<style>"
        "body{font-family:system-ui,sans-serif;max-width:980px;margin:2rem auto;padding:0 1rem;line-height:1.5;}"
        "header{display:flex;justify-content:space-between;align-items:center;gap:1rem;margin-bottom:2rem;}"
        "nav{display:flex;gap:1rem;align-items:center;}"
        "table{border-collapse:collapse;width:100%;}"
        "th,td{border:1px solid #d4d4d4;padding:0.5rem;text-align:left;vertical-align:top;}"
        "dl{display:grid;grid-template-columns:max-content 1fr;gap:0.25rem 1rem;}"
        "dt{font-weight:700;}"
        "pre{background:#f5f5f5;padding:1rem;overflow:auto;}"
        "form{border:1px solid #d4d4d4;padding:1rem;margin:0 0 1rem 0;}"
        "header form{border:0;padding:0;margin:0;}"
        "label{display:block;font-weight:600;margin-bottom:0.5rem;}"
        "input,textarea{display:block;width:100%;margin-top:0.25rem;margin-bottom:1rem;}"
        "textarea{min-height:6rem;}"
        "button{padding:0.5rem 0.75rem;}"
        ".message{background:#ecfdf3;border:1px solid #86efac;padding:0.75rem;}"
        ".error{background:#fef2f2;border:1px solid #fca5a5;padding:0.75rem;}"
        ".muted{color:#57534e;}"
        "</style>"
        "</head><body>"
        f"{render_operator_header(operator, csrf_token)}"
        f"{body}"
        "</body></html>"
    )


def render_operator_header(
    operator: OperatorIdentity | None,
    csrf_token: str | None,
) -> str:
    if operator is None:
        return "<header><nav><a href=\"/operator/login\">Operator Login</a></nav></header>"

    role_list = ", ".join(sorted(role.value for role in operator.roles))
    logout_form = ""
    if csrf_token:
        logout_form = (
            '<form method="post" action="/operator/logout">'
            f'<input type="hidden" name="csrf_token" value="{escape(csrf_token)}">'
            '<button type="submit">Logout</button>'
            "</form>"
        )

    return (
        "<header>"
        '<nav><a href="/operator/exceptions">Exceptions</a></nav>'
        "<div>"
        f'<strong>{escape(operator.username)}</strong> <span class="muted">({escape(role_list)})</span>'
        f"{logout_form}"
        "</div>"
        "</header>"
    )
