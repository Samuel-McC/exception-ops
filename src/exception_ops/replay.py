from __future__ import annotations

import argparse
import asyncio
import json
from contextlib import contextmanager
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from exception_ops.activities.approval import evaluate_approval_gate, finalize_approval_decision
from exception_ops.activities.classification import classify_exception
from exception_ops.activities.evidence import collect_evidence
from exception_ops.activities.execution import execute_action
from exception_ops.activities.remediation import generate_remediation_plan
from exception_ops.config import settings
from exception_ops.db import get_session_factory
from exception_ops.db.repositories import (
    create_approval_decision,
    create_exception_case,
    get_exception_case,
    get_latest_ai_records,
    get_latest_execution_record,
    list_evidence_records,
)
from exception_ops.domain.enums import (
    AIRecordKind,
    AIRecordStatus,
    ApprovalDecisionType,
    ApprovalState,
    ExecutionAction,
    ExecutionRecordStatus,
    ExecutionState,
    ExceptionType,
    RiskLevel,
    WorkflowLifecycleState,
)

DEFAULT_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "v1_cases.json"
REPLAY_INGEST_ACTOR = "system:replay"


class ReplayStage(StrEnum):
    EVIDENCE = "evidence"
    CLASSIFICATION = "classification"
    REMEDIATION = "remediation"
    APPROVAL_GATE = "approval_gate"
    APPROVAL_DECISION = "approval_decision"
    EXECUTION = "execution"


class ReplaySettingsOverrides(BaseModel):
    ai_provider: str | None = None
    ai_model: str | None = None
    openai_api_key: str | None = None
    evidence_adapter: str | None = None
    execution_adapter: str | None = None


class ReplayRequest(BaseModel):
    exception_type: ExceptionType
    risk_level: RiskLevel
    summary: str
    source_system: str
    external_reference: str | None = None
    raw_context_json: dict[str, Any] = Field(default_factory=dict)


class ReplayApprovalDecision(BaseModel):
    decision: ApprovalDecisionType
    actor: str = "fixture:approver"
    reason: str


class ReplayExpectation(BaseModel):
    approval_state: ApprovalState
    execution_state: ExecutionState
    workflow_lifecycle_state: WorkflowLifecycleState
    classification_status: AIRecordStatus
    remediation_status: AIRecordStatus
    normalized_exception_type: ExceptionType | None = None
    recommended_action: ExecutionAction | None = None
    latest_execution_action_name: ExecutionAction | None = None
    latest_execution_status: ExecutionRecordStatus | None = None
    evidence_succeeded: int
    evidence_failed: int


class ReplayFixture(BaseModel):
    fixture_id: str
    title: str
    description: str
    request: ReplayRequest
    settings_overrides: ReplaySettingsOverrides = Field(default_factory=ReplaySettingsOverrides)
    approval_decision: ReplayApprovalDecision | None = None
    expectations: ReplayExpectation


class ReplayFixtureCorpus(BaseModel):
    corpus_version: str
    fixtures: list[ReplayFixture]


class ReplayStageResult(BaseModel):
    stage: ReplayStage
    result: dict[str, Any]


class ReplayOutcome(BaseModel):
    fixture_id: str
    case_id: str
    approval_state: ApprovalState
    execution_state: ExecutionState
    workflow_lifecycle_state: WorkflowLifecycleState
    classification_status: AIRecordStatus | None = None
    remediation_status: AIRecordStatus | None = None
    normalized_exception_type: ExceptionType | None = None
    recommended_action: ExecutionAction | None = None
    latest_execution_action_name: ExecutionAction | None = None
    latest_execution_status: ExecutionRecordStatus | None = None
    evidence_succeeded: int
    evidence_failed: int
    stopped_after_stage: ReplayStage | None = None
    stage_results: list[ReplayStageResult] = Field(default_factory=list)


def load_replay_corpus(path: Path | None = None) -> ReplayFixtureCorpus:
    fixture_path = path or DEFAULT_FIXTURE_PATH
    return ReplayFixtureCorpus.model_validate_json(fixture_path.read_text())


def load_replay_fixtures(path: Path | None = None) -> list[ReplayFixture]:
    return load_replay_corpus(path).fixtures


def get_replay_fixture(fixture_id: str, path: Path | None = None) -> ReplayFixture:
    for fixture in load_replay_fixtures(path):
        if fixture.fixture_id == fixture_id:
            return fixture
    raise ValueError(f"Replay fixture not found: {fixture_id}")


async def replay_fixture(
    fixture: ReplayFixture,
    *,
    session_factory: sessionmaker[Session] | None = None,
    until_stage: ReplayStage = ReplayStage.EXECUTION,
) -> ReplayOutcome:
    factory = session_factory or get_session_factory()
    with _apply_settings_overrides(fixture.settings_overrides):
        session = factory()
        try:
            exception_case, _ = create_exception_case(
                session,
                exception_type=fixture.request.exception_type,
                risk_level=fixture.request.risk_level,
                summary=fixture.request.summary,
                source_system=fixture.request.source_system,
                external_reference=fixture.request.external_reference,
                raw_context_json=fixture.request.raw_context_json,
                actor=REPLAY_INGEST_ACTOR,
            )
            case_id = exception_case.case_id
        finally:
            session.close()

        stage_results: list[ReplayStageResult] = []

        evidence_result = await collect_evidence(case_id)
        stage_results.append(ReplayStageResult(stage=ReplayStage.EVIDENCE, result=evidence_result))
        if until_stage is ReplayStage.EVIDENCE:
            return _build_replay_outcome(
                factory,
                fixture_id=fixture.fixture_id,
                case_id=case_id,
                stage_results=stage_results,
                stopped_after_stage=ReplayStage.EVIDENCE,
            )

        classification_result = await classify_exception(case_id)
        stage_results.append(
            ReplayStageResult(stage=ReplayStage.CLASSIFICATION, result=classification_result)
        )
        if until_stage is ReplayStage.CLASSIFICATION:
            return _build_replay_outcome(
                factory,
                fixture_id=fixture.fixture_id,
                case_id=case_id,
                stage_results=stage_results,
                stopped_after_stage=ReplayStage.CLASSIFICATION,
            )

        remediation_result = await generate_remediation_plan(case_id)
        stage_results.append(
            ReplayStageResult(stage=ReplayStage.REMEDIATION, result=remediation_result)
        )
        if until_stage is ReplayStage.REMEDIATION:
            return _build_replay_outcome(
                factory,
                fixture_id=fixture.fixture_id,
                case_id=case_id,
                stage_results=stage_results,
                stopped_after_stage=ReplayStage.REMEDIATION,
            )

        approval_gate_result = await evaluate_approval_gate(case_id)
        stage_results.append(
            ReplayStageResult(stage=ReplayStage.APPROVAL_GATE, result=approval_gate_result)
        )
        if until_stage is ReplayStage.APPROVAL_GATE:
            return _build_replay_outcome(
                factory,
                fixture_id=fixture.fixture_id,
                case_id=case_id,
                stage_results=stage_results,
                stopped_after_stage=ReplayStage.APPROVAL_GATE,
            )

        if (
            fixture.approval_decision is None
            and approval_gate_result["approval_state"] == ApprovalState.PENDING.value
        ):
            return _build_replay_outcome(
                factory,
                fixture_id=fixture.fixture_id,
                case_id=case_id,
                stage_results=stage_results,
                stopped_after_stage=ReplayStage.APPROVAL_GATE,
            )

        if fixture.approval_decision is not None:
            session = factory()
            try:
                _, decision = create_approval_decision(
                    session,
                    case_id=case_id,
                    decision=fixture.approval_decision.decision,
                    actor=fixture.approval_decision.actor,
                    reason=fixture.approval_decision.reason,
                )
            finally:
                session.close()

            approval_result = await finalize_approval_decision(decision.decision_id)
            stage_results.append(
                ReplayStageResult(stage=ReplayStage.APPROVAL_DECISION, result=approval_result)
            )
            if until_stage is ReplayStage.APPROVAL_DECISION:
                return _build_replay_outcome(
                    factory,
                    fixture_id=fixture.fixture_id,
                    case_id=case_id,
                    stage_results=stage_results,
                    stopped_after_stage=ReplayStage.APPROVAL_DECISION,
                )
        elif until_stage is ReplayStage.APPROVAL_DECISION:
            raise ValueError(
                f"Replay fixture {fixture.fixture_id} does not include an approval_decision stage"
            )

        execution_result = await execute_action(case_id)
        stage_results.append(ReplayStageResult(stage=ReplayStage.EXECUTION, result=execution_result))
        return _build_replay_outcome(
            factory,
            fixture_id=fixture.fixture_id,
            case_id=case_id,
            stage_results=stage_results,
            stopped_after_stage=ReplayStage.EXECUTION if until_stage is ReplayStage.EXECUTION else None,
        )


def validate_replay_outcome(
    outcome: ReplayOutcome,
    expectations: ReplayExpectation,
) -> list[str]:
    mismatches: list[str] = []

    expected_pairs = {
        "approval_state": expectations.approval_state,
        "execution_state": expectations.execution_state,
        "workflow_lifecycle_state": expectations.workflow_lifecycle_state,
        "classification_status": expectations.classification_status,
        "remediation_status": expectations.remediation_status,
        "normalized_exception_type": expectations.normalized_exception_type,
        "recommended_action": expectations.recommended_action,
        "latest_execution_action_name": expectations.latest_execution_action_name,
        "latest_execution_status": expectations.latest_execution_status,
        "evidence_succeeded": expectations.evidence_succeeded,
        "evidence_failed": expectations.evidence_failed,
    }

    actual_pairs = {
        "approval_state": outcome.approval_state,
        "execution_state": outcome.execution_state,
        "workflow_lifecycle_state": outcome.workflow_lifecycle_state,
        "classification_status": outcome.classification_status,
        "remediation_status": outcome.remediation_status,
        "normalized_exception_type": outcome.normalized_exception_type,
        "recommended_action": outcome.recommended_action,
        "latest_execution_action_name": outcome.latest_execution_action_name,
        "latest_execution_status": outcome.latest_execution_status,
        "evidence_succeeded": outcome.evidence_succeeded,
        "evidence_failed": outcome.evidence_failed,
    }

    for field_name, expected_value in expected_pairs.items():
        actual_value = actual_pairs[field_name]
        if actual_value != expected_value:
            mismatches.append(
                f"{field_name}: expected {expected_value!r}, got {actual_value!r}"
            )

    return mismatches


def main() -> None:
    args = _parse_args()
    outcomes = asyncio.run(
        _run_cli(
            fixture_path=args.fixture_path,
            fixture_id=args.fixture_id,
            run_all=args.all,
            until_stage=ReplayStage(args.until_stage),
        )
    )
    print(json.dumps(outcomes, indent=2))


async def _run_cli(
    *,
    fixture_path: Path,
    fixture_id: str | None,
    run_all: bool,
    until_stage: ReplayStage,
) -> list[dict[str, Any]]:
    fixtures = load_replay_fixtures(fixture_path)
    if fixture_id:
        fixtures = [fixture for fixture in fixtures if fixture.fixture_id == fixture_id]
    elif not run_all:
        fixtures = fixtures[:1]

    if not fixtures:
        raise ValueError("No replay fixtures matched the requested selection.")

    outcomes: list[dict[str, Any]] = []
    for fixture in fixtures:
        outcome = await replay_fixture(fixture, until_stage=until_stage)
        outcomes.append(outcome.model_dump(mode="json"))
    return outcomes


def _build_replay_outcome(
    session_factory: sessionmaker[Session],
    *,
    fixture_id: str,
    case_id: str,
    stage_results: list[ReplayStageResult],
    stopped_after_stage: ReplayStage | None,
) -> ReplayOutcome:
    session = session_factory()
    try:
        exception_case = get_exception_case(session, case_id)
        if exception_case is None:
            raise ValueError(f"Replay case not found: {case_id}")

        evidence_history = list_evidence_records(session, case_id)
        latest_ai_records = get_latest_ai_records(session, case_id)
        latest_execution_record = get_latest_execution_record(session, case_id)
    finally:
        session.close()

    classification_record = latest_ai_records.get(AIRecordKind.CLASSIFICATION)
    remediation_record = latest_ai_records.get(AIRecordKind.REMEDIATION)
    evidence_succeeded = sum(1 for item in evidence_history if item.status.value == "succeeded")
    evidence_failed = sum(1 for item in evidence_history if item.status.value == "failed")

    return ReplayOutcome(
        fixture_id=fixture_id,
        case_id=case_id,
        approval_state=exception_case.approval_state,
        execution_state=exception_case.execution_state,
        workflow_lifecycle_state=exception_case.workflow_lifecycle_state,
        classification_status=classification_record.status if classification_record else None,
        remediation_status=remediation_record.status if remediation_record else None,
        normalized_exception_type=_coerce_exception_type(
            classification_record.payload_json.get("normalized_exception_type")
            if classification_record and classification_record.payload_json
            else None
        ),
        recommended_action=_coerce_execution_action(
            remediation_record.payload_json.get("recommended_action")
            if remediation_record and remediation_record.payload_json
            else None
        ),
        latest_execution_action_name=(
            latest_execution_record.action_name if latest_execution_record else None
        ),
        latest_execution_status=latest_execution_record.status if latest_execution_record else None,
        evidence_succeeded=evidence_succeeded,
        evidence_failed=evidence_failed,
        stopped_after_stage=stopped_after_stage,
        stage_results=stage_results,
    )


def _coerce_exception_type(value: Any) -> ExceptionType | None:
    if value is None:
        return None
    try:
        return ExceptionType(str(value))
    except ValueError:
        return None


def _coerce_execution_action(value: Any) -> ExecutionAction | None:
    if value is None:
        return None
    try:
        return ExecutionAction(str(value))
    except ValueError:
        return None


@contextmanager
def _apply_settings_overrides(overrides: ReplaySettingsOverrides):
    field_names = (
        "ai_provider",
        "ai_model",
        "openai_api_key",
        "evidence_adapter",
        "execution_adapter",
    )
    original = {field_name: getattr(settings, field_name) for field_name in field_names}
    try:
        for field_name in field_names:
            override_value = getattr(overrides, field_name)
            if override_value is not None:
                setattr(settings, field_name, override_value)
        yield
    finally:
        for field_name, original_value in original.items():
            setattr(settings, field_name, original_value)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay bounded ExceptionOps V1 fixtures.")
    parser.add_argument(
        "--fixture-path",
        type=Path,
        default=DEFAULT_FIXTURE_PATH,
        help="Path to the replay fixture corpus JSON file.",
    )
    parser.add_argument(
        "--fixture-id",
        help="Replay only the fixture with this identifier.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Replay every fixture in the corpus. Defaults to the first fixture when omitted.",
    )
    parser.add_argument(
        "--until-stage",
        choices=[stage.value for stage in ReplayStage],
        default=ReplayStage.EXECUTION.value,
        help="Stop after the selected explicit stage.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
