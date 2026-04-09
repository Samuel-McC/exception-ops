from __future__ import annotations

from html import escape
from json import dumps
from urllib.parse import parse_qs, quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from exception_ops.api.routes.exceptions import (
    ApprovalDecisionRequest,
    ExceptionCaseDetailResponse,
    _build_exception_case_detail_response,
    _build_exception_case_response,
    _load_exception_detail_or_404,
    _submit_approval_decision,
)
from exception_ops.db import get_session
from exception_ops.db.repositories import list_exception_cases
from exception_ops.domain.enums import ApprovalDecisionType, ApprovalState, WorkflowLifecycleState
from exception_ops.temporal import WorkflowSignaler, get_workflow_signaler

router = APIRouter(prefix="/operator", tags=["operator"])


@router.get("/exceptions", response_class=HTMLResponse)
def operator_exceptions(session: Session = Depends(get_session)) -> HTMLResponse:
    items = [_build_exception_case_response(item) for item in list_exception_cases(session)]
    rows = "".join(
        (
            "<tr>"
            f"<td><a href=\"/operator/exceptions/{escape(item.case_id)}\">{escape(item.case_id)}</a></td>"
            f"<td>{escape(item.summary)}</td>"
            f"<td>{escape(item.exception_type.value)}</td>"
            f"<td>{escape(item.risk_level.value)}</td>"
            f"<td>{escape(item.approval_state.value)}</td>"
            f"<td>{escape(item.workflow_lifecycle_state.value)}</td>"
            f"<td>{escape(item.created_at.isoformat())}</td>"
            "</tr>"
        )
        for item in items
    )
    table_rows = rows or '<tr><td colspan="7">No exceptions found.</td></tr>'
    body = (
        "<h1>ExceptionOps Operator View</h1>"
        "<p>Minimal Phase 4 operator UI for approval review.</p>"
        "<table>"
        "<thead><tr><th>Case ID</th><th>Summary</th><th>Type</th><th>Risk</th>"
        "<th>Approval</th><th>Workflow</th><th>Created</th></tr></thead>"
        f"<tbody>{table_rows}</tbody>"
        "</table>"
    )
    return HTMLResponse(_page("Exceptions", body))


@router.get("/exceptions/{case_id}", response_class=HTMLResponse)
def operator_exception_detail(
    case_id: str,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    try:
        detail = _load_operator_detail(session, case_id)
    except HTTPException as exc:
        return HTMLResponse(
            _page(
                "Case Not Found",
                (
                    f"<h1>Case {escape(case_id)}</h1>"
                    f"<p>{escape(str(exc.detail))}</p>"
                    '<p><a href="/operator/exceptions">Back to exceptions</a></p>'
                ),
            ),
            status_code=exc.status_code,
        )

    message = request.query_params.get("message")
    error = request.query_params.get("error")
    return HTMLResponse(_page(f"Case {case_id}", _render_detail_page(detail, message, error)))


@router.post("/exceptions/{case_id}/approve")
async def operator_approve_exception(
    case_id: str,
    request: Request,
    session: Session = Depends(get_session),
    workflow_signaler: WorkflowSignaler = Depends(get_workflow_signaler),
) -> RedirectResponse:
    return await _handle_operator_decision(
        case_id=case_id,
        decision=ApprovalDecisionType.APPROVED,
        request=request,
        session=session,
        workflow_signaler=workflow_signaler,
    )


@router.post("/exceptions/{case_id}/reject")
async def operator_reject_exception(
    case_id: str,
    request: Request,
    session: Session = Depends(get_session),
    workflow_signaler: WorkflowSignaler = Depends(get_workflow_signaler),
) -> RedirectResponse:
    return await _handle_operator_decision(
        case_id=case_id,
        decision=ApprovalDecisionType.REJECTED,
        request=request,
        session=session,
        workflow_signaler=workflow_signaler,
    )


def _load_operator_detail(session: Session, case_id: str) -> ExceptionCaseDetailResponse:
    exception_case, audit_history, latest_ai_records, approval_history = _load_exception_detail_or_404(
        session, case_id
    )
    return _build_exception_case_detail_response(
        exception_case,
        audit_history,
        latest_ai_records,
        approval_history,
    )


async def _handle_operator_decision(
    *,
    case_id: str,
    decision: ApprovalDecisionType,
    request: Request,
    session: Session,
    workflow_signaler: WorkflowSignaler,
) -> RedirectResponse:
    form_data = await _parse_form_body(request)
    try:
        await _submit_approval_decision(
            session=session,
            workflow_signaler=workflow_signaler,
            case_id=case_id,
            decision=decision,
            request=ApprovalDecisionRequest(
                actor=form_data.get("actor"),
                reason=form_data.get("reason"),
            ),
        )
    except HTTPException as exc:
        return RedirectResponse(
            url=f"/operator/exceptions/{case_id}?error={quote(str(exc.detail))}",
            status_code=303,
        )

    action = "approved" if decision is ApprovalDecisionType.APPROVED else "rejected"
    return RedirectResponse(
        url=f"/operator/exceptions/{case_id}?message={quote(f'Case {action}.')}",
        status_code=303,
    )


async def _parse_form_body(request: Request) -> dict[str, str]:
    body = (await request.body()).decode()
    parsed = parse_qs(body, keep_blank_values=True)
    return {key: values[0] for key, values in parsed.items() if values}


def _render_detail_page(
    detail: ExceptionCaseDetailResponse,
    message: str | None,
    error: str | None,
) -> str:
    sections = [
        f"<h1>Exception {escape(detail.case_id)}</h1>",
        '<p><a href="/operator/exceptions">Back to exceptions</a></p>',
    ]
    if message:
        sections.append(f'<p class="message">{escape(message)}</p>')
    if error:
        sections.append(f'<p class="error">{escape(error)}</p>')

    sections.extend(
        [
            "<h2>Case</h2>",
            "<dl>"
            f"<dt>Summary</dt><dd>{escape(detail.summary)}</dd>"
            f"<dt>Type</dt><dd>{escape(detail.exception_type.value)}</dd>"
            f"<dt>Risk</dt><dd>{escape(detail.risk_level.value)}</dd>"
            f"<dt>Status</dt><dd>{escape(detail.status.value)}</dd>"
            f"<dt>Approval State</dt><dd>{escape(detail.approval_state.value)}</dd>"
            f"<dt>Approval Required</dt><dd>{_format_optional(detail.approval_required)}</dd>"
            f"<dt>Workflow State</dt><dd>{escape(detail.workflow_lifecycle_state.value)}</dd>"
            f"<dt>Workflow ID</dt><dd>{escape(detail.temporal_workflow_id or 'n/a')}</dd>"
            f"<dt>Run ID</dt><dd>{escape(detail.temporal_run_id or 'n/a')}</dd>"
            f"<dt>Source System</dt><dd>{escape(detail.source_system)}</dd>"
            f"<dt>External Reference</dt><dd>{escape(detail.external_reference or 'n/a')}</dd>"
            "</dl>",
            "<h2>Raw Context</h2>",
            _render_json_block(detail.raw_context_json),
            "<h2>Approval Controls</h2>",
            _render_approval_controls(detail),
            "<h2>AI Metadata</h2>",
            _render_ai_section(detail),
            "<h2>Approval History</h2>",
            _render_approval_history(detail),
            "<h2>Audit History</h2>",
            _render_audit_history(detail),
        ]
    )
    return "".join(sections)


def _render_approval_controls(detail: ExceptionCaseDetailResponse) -> str:
    if detail.approval_state is ApprovalState.PENDING:
        return (
            _approval_form(detail.case_id, ApprovalDecisionType.APPROVED, "Approve case")
            + _approval_form(detail.case_id, ApprovalDecisionType.REJECTED, "Reject case")
        )

    if (
        detail.workflow_lifecycle_state is WorkflowLifecycleState.STARTED
        and detail.latest_approval_decision is not None
        and detail.approval_state in {ApprovalState.APPROVED, ApprovalState.REJECTED}
    ):
        action = detail.latest_approval_decision.decision
        label = "Retry workflow signal"
        return _approval_form(detail.case_id, action, label, retry_only=True)

    return "<p>No approval action is currently available.</p>"


def _approval_form(
    case_id: str,
    decision: ApprovalDecisionType,
    label: str,
    *,
    retry_only: bool = False,
) -> str:
    path = "approve" if decision is ApprovalDecisionType.APPROVED else "reject"
    fields = ""
    if not retry_only:
        fields = (
            '<label>Actor<input type="text" name="actor" maxlength="255" required></label>'
            '<label>Reason<textarea name="reason" maxlength="2000" required></textarea></label>'
        )
    return (
        f'<form method="post" action="/operator/exceptions/{escape(case_id)}/{path}">'
        f"{fields}"
        f'<button type="submit">{escape(label)}</button>'
        "</form>"
    )


def _render_ai_section(detail: ExceptionCaseDetailResponse) -> str:
    parts = [
        "<h3>Classification</h3>",
        _render_ai_record(detail.latest_classification.model_dump() if detail.latest_classification else None),
        "<h3>Remediation</h3>",
        _render_ai_record(detail.latest_remediation.model_dump() if detail.latest_remediation else None),
    ]
    return "".join(parts)


def _render_ai_record(record: dict[str, object] | None) -> str:
    if record is None:
        return "<p>Not available.</p>"
    return _render_json_block(record)


def _render_approval_history(detail: ExceptionCaseDetailResponse) -> str:
    if not detail.approval_history:
        return "<p>No approval decisions recorded.</p>"
    items = "".join(
        (
            "<li>"
            f"<strong>{escape(item.decision.value)}</strong> by {escape(item.actor)} "
            f"at {escape(item.decided_at.isoformat())}<br>"
            f"{escape(item.reason)}"
            "</li>"
        )
        for item in detail.approval_history
    )
    return f"<ul>{items}</ul>"


def _render_audit_history(detail: ExceptionCaseDetailResponse) -> str:
    if not detail.audit_history:
        return "<p>No audit events recorded.</p>"
    items = "".join(
        (
            "<li>"
            f"{escape(item.event_type.value)} by {escape(item.actor)} "
            f"at {escape(item.created_at.isoformat())}"
            "</li>"
        )
        for item in detail.audit_history
    )
    return f"<ul>{items}</ul>"


def _render_json_block(value: object) -> str:
    rendered = dumps(value, indent=2, sort_keys=True, default=str)
    return f"<pre>{escape(rendered)}</pre>"


def _format_optional(value: bool | None) -> str:
    if value is None:
        return "pending workflow policy"
    return "yes" if value else "no"


def _page(title: str, body: str) -> str:
    return (
        "<!doctype html>"
        "<html><head>"
        f"<title>{escape(title)}</title>"
        "<style>"
        "body{font-family:system-ui,sans-serif;max-width:980px;margin:2rem auto;padding:0 1rem;line-height:1.5;}"
        "table{border-collapse:collapse;width:100%;}"
        "th,td{border:1px solid #d4d4d4;padding:0.5rem;text-align:left;vertical-align:top;}"
        "dl{display:grid;grid-template-columns:max-content 1fr;gap:0.25rem 1rem;}"
        "dt{font-weight:700;}"
        "pre{background:#f5f5f5;padding:1rem;overflow:auto;}"
        "form{border:1px solid #d4d4d4;padding:1rem;margin:0 0 1rem 0;}"
        "label{display:block;font-weight:600;margin-bottom:0.5rem;}"
        "input,textarea{display:block;width:100%;margin-top:0.25rem;margin-bottom:1rem;}"
        "textarea{min-height:6rem;}"
        "button{padding:0.5rem 0.75rem;}"
        ".message{background:#ecfdf3;border:1px solid #86efac;padding:0.75rem;}"
        ".error{background:#fef2f2;border:1px solid #fca5a5;padding:0.75rem;}"
        "</style>"
        "</head><body>"
        f"{body}"
        "</body></html>"
    )
