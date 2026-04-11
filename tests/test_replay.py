from __future__ import annotations

import asyncio

import pytest
from sqlalchemy.orm import Session, sessionmaker

from exception_ops.domain.enums import ApprovalState, ExecutionState
from exception_ops.replay import (
    ReplayStage,
    get_replay_fixture,
    load_replay_fixtures,
    replay_fixture,
    validate_replay_outcome,
)

REPLAY_FIXTURES = load_replay_fixtures()


@pytest.mark.parametrize(
    "fixture",
    REPLAY_FIXTURES,
    ids=[fixture.fixture_id for fixture in REPLAY_FIXTURES],
)
def test_replay_fixture_matches_expected_v1_outcome(
    fixture,
    session_factory: sessionmaker[Session],
    activity_db_overrides: None,
) -> None:
    outcome = asyncio.run(replay_fixture(fixture, session_factory=session_factory))
    mismatches = validate_replay_outcome(outcome, fixture.expectations)

    assert mismatches == []


def test_replay_can_stop_after_explicit_selected_stage(
    session_factory: sessionmaker[Session],
    activity_db_overrides: None,
) -> None:
    fixture = get_replay_fixture("approval-required-provider-failure")

    outcome = asyncio.run(
        replay_fixture(
            fixture,
            session_factory=session_factory,
            until_stage=ReplayStage.APPROVAL_GATE,
        )
    )

    assert outcome.stopped_after_stage is ReplayStage.APPROVAL_GATE
    assert outcome.approval_state is ApprovalState.PENDING
    assert outcome.execution_state is ExecutionState.PENDING
    assert outcome.latest_execution_status is None
    assert [item.stage for item in outcome.stage_results] == [
        ReplayStage.EVIDENCE,
        ReplayStage.CLASSIFICATION,
        ReplayStage.REMEDIATION,
        ReplayStage.APPROVAL_GATE,
    ]


def test_replay_stops_at_approval_gate_when_decision_is_not_supplied(
    session_factory: sessionmaker[Session],
    activity_db_overrides: None,
) -> None:
    fixture = get_replay_fixture("approval-required-provider-failure").model_copy(
        update={"approval_decision": None}
    )

    outcome = asyncio.run(replay_fixture(fixture, session_factory=session_factory))

    assert outcome.stopped_after_stage is ReplayStage.APPROVAL_GATE
    assert outcome.approval_state is ApprovalState.PENDING
    assert outcome.execution_state is ExecutionState.PENDING
    assert outcome.latest_execution_status is None
