from __future__ import annotations

from html import escape
from json import dumps
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from exception_ops.api.forms import parse_form_body
from exception_ops.api.exception_cases import (
    ApprovalDecisionRequest,
    ExceptionCaseDetailResponse,
    build_exception_case_detail_response,
    build_exception_case_response,
    load_exception_case_detail_or_404,
    submit_approval_decision,
)
from exception_ops.api.operator_ui import render_page
from exception_ops.auth import (
    OperatorIdentity,
    OperatorRole,
    build_operator_login_redirect,
    get_operator_page_context,
    validate_session_csrf,
)
from exception_ops.db import get_session
from exception_ops.db.repositories import list_exception_cases
from exception_ops.domain.enums import ApprovalDecisionType, ApprovalState, WorkflowLifecycleState
from exception_ops.temporal import WorkflowSignaler, get_workflow_signaler

router = APIRouter(prefix="/operator", tags=["operator"])
REVIEW_ROLES = (
    OperatorRole.REVIEWER,
    OperatorRole.APPROVER,
    OperatorRole.EXECUTOR,
    OperatorRole.ADMIN,
)
APPROVAL_ROLES = (
    OperatorRole.APPROVER,
    OperatorRole.ADMIN,
)


@router.get("/exceptions", response_class=HTMLResponse)
def operator_exceptions(
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    page_context = _get_operator_page_context(request, *REVIEW_ROLES)
    if isinstance(page_context, RedirectResponse):
        return page_context

    operator, csrf_token = page_context
    items = [build_exception_case_response(item) for item in list_exception_cases(session)]
    rows = "".join(
        (
            "<tr>"
            f"<td><a href=\"/operator/exceptions/{escape(item.case_id)}\">{escape(item.case_id)}</a></td>"
            f"<td>{escape(item.summary)}</td>"
            f"<td>{escape(item.exception_type.value)}</td>"
            f"<td>{escape(item.risk_level.value)}</td>"
            f"<td>{escape(item.approval_state.value)}</td>"
            f"<td>{escape(item.execution_state.value)}</td>"
            f"<td>{escape(item.workflow_lifecycle_state.value)}</td>"
            f"<td>{escape(item.created_at.isoformat())}</td>"
            "</tr>"
        )
        for item in items
    )
    table_rows = rows or '<tr><td colspan="8">No exceptions found.</td></tr>'
    body = (
        "<h1>ExceptionOps Operator View</h1>"
        "<p>Minimal operator UI for approval review and bounded execution visibility.</p>"
        "<table>"
        "<thead><tr><th>Case ID</th><th>Summary</th><th>Type</th><th>Risk</th>"
        "<th>Approval</th><th>Execution</th><th>Workflow</th><th>Created</th></tr></thead>"
        f"<tbody>{table_rows}</tbody>"
        "</table>"
    )
    return HTMLResponse(render_page("Exceptions", body, operator=operator, csrf_token=csrf_token))


@router.get("/exceptions/{case_id}", response_class=HTMLResponse)
def operator_exception_detail(
    case_id: str,
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    page_context = _get_operator_page_context(request, *REVIEW_ROLES)
    if isinstance(page_context, RedirectResponse):
        return page_context

    operator, csrf_token = page_context
    try:
        detail = _load_operator_detail(session, case_id)
    except HTTPException as exc:
        return HTMLResponse(
            render_page(
                "Case Not Found",
                (
                    f"<h1>Case {escape(case_id)}</h1>"
                    f"<p>{escape(str(exc.detail))}</p>"
                    '<p><a href="/operator/exceptions">Back to exceptions</a></p>'
                ),
                operator=operator,
                csrf_token=csrf_token,
            ),
            status_code=exc.status_code,
        )

    message = request.query_params.get("message")
    error = request.query_params.get("error")
    return HTMLResponse(
        render_page(
            f"Case {case_id}",
            _render_detail_page(detail, message, error, operator=operator, csrf_token=csrf_token),
            operator=operator,
            csrf_token=csrf_token,
        )
    )


@router.post("/exceptions/{case_id}/approve")
async def operator_approve_exception(
    case_id: str,
    request: Request,
    session: Session = Depends(get_session),
    workflow_signaler: WorkflowSignaler = Depends(get_workflow_signaler),
) -> Response:
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
) -> Response:
    return await _handle_operator_decision(
        case_id=case_id,
        decision=ApprovalDecisionType.REJECTED,
        request=request,
        session=session,
        workflow_signaler=workflow_signaler,
    )


def _load_operator_detail(session: Session, case_id: str) -> ExceptionCaseDetailResponse:
    return build_exception_case_detail_response(load_exception_case_detail_or_404(session, case_id))


async def _handle_operator_decision(
    *,
    case_id: str,
    decision: ApprovalDecisionType,
    request: Request,
    session: Session,
    workflow_signaler: WorkflowSignaler,
) -> Response:
    page_context = _get_operator_page_context(request, *APPROVAL_ROLES)
    if isinstance(page_context, RedirectResponse):
        return page_context

    operator, csrf_token = page_context
    form_data = await parse_form_body(request)
    try:
        validate_session_csrf(form_data.get("csrf_token"), csrf_token)
    except HTTPException:
        return HTMLResponse(
            render_page(
                "Forbidden",
                "<h1>Forbidden</h1><p>invalid_csrf_token</p>",
                operator=operator,
                csrf_token=csrf_token,
            ),
            status_code=403,
        )

    try:
        await submit_approval_decision(
            session=session,
            workflow_signaler=workflow_signaler,
            case_id=case_id,
            decision=decision,
            actor=operator.username,
            request=ApprovalDecisionRequest(
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


def _render_detail_page(
    detail: ExceptionCaseDetailResponse,
    message: str | None,
    error: str | None,
    *,
    operator: OperatorIdentity,
    csrf_token: str,
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
            f"<dt>Execution State</dt><dd>{escape(detail.execution_state.value)}</dd>"
            f"<dt>Workflow State</dt><dd>{escape(detail.workflow_lifecycle_state.value)}</dd>"
            f"<dt>Workflow ID</dt><dd>{escape(detail.temporal_workflow_id or 'n/a')}</dd>"
            f"<dt>Run ID</dt><dd>{escape(detail.temporal_run_id or 'n/a')}</dd>"
            f"<dt>Source System</dt><dd>{escape(detail.source_system)}</dd>"
            f"<dt>External Reference</dt><dd>{escape(detail.external_reference or 'n/a')}</dd>"
            "</dl>",
            "<h2>Raw Context</h2>",
            _render_json_block(detail.raw_context_json),
            "<h2>Approval Controls</h2>",
            _render_approval_controls(detail, operator=operator, csrf_token=csrf_token),
            "<h2>AI Metadata</h2>",
            _render_ai_section(detail),
            "<h2>Approval History</h2>",
            _render_approval_history(detail),
            "<h2>Execution</h2>",
            _render_execution(detail),
            "<h2>Audit History</h2>",
            _render_audit_history(detail),
        ]
    )
    return "".join(sections)


def _render_approval_controls(
    detail: ExceptionCaseDetailResponse,
    *,
    operator: OperatorIdentity,
    csrf_token: str,
) -> str:
    if not operator.has_any_role(*APPROVAL_ROLES):
        return "<p>Approval actions are unavailable for your role.</p>"

    if detail.approval_state is ApprovalState.PENDING:
        return (
            _approval_form(
                detail.case_id,
                ApprovalDecisionType.APPROVED,
                "Approve case",
                csrf_token=csrf_token,
            )
            + _approval_form(
                detail.case_id,
                ApprovalDecisionType.REJECTED,
                "Reject case",
                csrf_token=csrf_token,
            )
        )

    if (
        detail.workflow_lifecycle_state is WorkflowLifecycleState.STARTED
        and detail.latest_approval_decision is not None
        and detail.approval_state in {ApprovalState.APPROVED, ApprovalState.REJECTED}
    ):
        action = detail.latest_approval_decision.decision
        label = "Retry workflow signal"
        return _approval_form(
            detail.case_id,
            action,
            label,
            csrf_token=csrf_token,
            retry_only=True,
        )

    return "<p>No approval action is currently available.</p>"


def _approval_form(
    case_id: str,
    decision: ApprovalDecisionType,
    label: str,
    *,
    csrf_token: str,
    retry_only: bool = False,
) -> str:
    path = "approve" if decision is ApprovalDecisionType.APPROVED else "reject"
    fields = ""
    if not retry_only:
        fields = (
            '<label>Reason<textarea name="reason" maxlength="2000" required></textarea></label>'
        )
    return (
        f'<form method="post" action="/operator/exceptions/{escape(case_id)}/{path}">'
        f'<input type="hidden" name="csrf_token" value="{escape(csrf_token)}">'
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


def _render_execution(detail: ExceptionCaseDetailResponse) -> str:
    parts = [
        f"<p><strong>Execution State:</strong> {escape(detail.execution_state.value)}</p>",
    ]
    if detail.latest_execution is None:
        parts.append("<p>No execution records recorded.</p>")
    else:
        parts.extend(
            [
                "<h3>Latest Execution</h3>",
                _render_json_block(detail.latest_execution.model_dump()),
            ]
        )
    if detail.execution_history:
        items = "".join(
            (
                "<li>"
                f"{escape(item.action_name)} by {escape(item.initiated_by)} "
                f"with status {escape(item.status.value)} at {escape(item.started_at.isoformat())}"
                "</li>"
            )
            for item in detail.execution_history
        )
        parts.append(f"<ul>{items}</ul>")
    return "".join(parts)


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

def _get_operator_page_context(
    request: Request,
    *roles: OperatorRole,
) -> tuple[OperatorIdentity, str] | RedirectResponse:
    try:
        operator, auth_session = get_operator_page_context(request, *roles)
    except HTTPException:
        return HTMLResponse(
            render_page("Forbidden", "<h1>Forbidden</h1><p>insufficient_role</p>"),
            status_code=403,
        )

    if operator is None or auth_session is None:
        return build_operator_login_redirect(request)
    return operator, auth_session.csrf_token
