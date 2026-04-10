from __future__ import annotations

from urllib.parse import parse_qs

from fastapi import Request


async def parse_form_body(request: Request) -> dict[str, str]:
    body = (await request.body()).decode()
    parsed = parse_qs(body, keep_blank_values=True)
    return {key: values[0] for key, values in parsed.items() if values}
