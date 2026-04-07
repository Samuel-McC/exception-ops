# ExceptionOps

ExceptionOps is an AI-assisted exception-resolution platform.

It ingests operational exceptions, gathers evidence through deterministic activities, uses bounded LLM assistance to classify issues and draft remediation plans, routes risky actions to explicit approval, and executes approved actions through durable workflows.

## Why this exists

Most AI demos stop at “the model answered.”

This project focuses on the harder engineering problems around AI automation:

- durable workflow orchestration
- explicit exception state transitions
- structured AI outputs
- bounded tool use
- approval-gated execution
- auditability
- failure handling and retries
- clear separation between AI recommendation and deterministic execution

The goal is to build a production-minded automation system, not a generic chatbot or unconstrained agent demo.

## Planned stack

- Python
- FastAPI
- Temporal
- PostgreSQL
- OpenAI
- Pydantic
- Docker
- Pytest

## Planned core flow

1. ingest exception
2. classify exception
3. gather evidence
4. generate remediation plan
5. require approval for risky actions
6. execute approved actions
7. audit everything

## Current status

This repo currently implements:
- Phase 1 exception ingestion with persistence and ingest audit records
- Phase 2 Temporal workflow kickoff on exception creation
- stored workflow linkage on each exception case
- minimal replay-safe workflow coordination without AI, approvals, evidence gathering, or execution yet

When `POST /exceptions` succeeds, the exception case and ingest audit record are always persisted first. The API then attempts workflow kickoff and stores one of:
- `started`
- `start_failed`

This keeps exception ingestion durable even if Temporal is temporarily unavailable.

## Design principles

- workflows first, not agent sprawl
- deterministic execution remains authoritative
- AI can classify, summarize, and recommend
- AI must not autonomously approve or execute risky actions
- approvals remain explicit
- auditability is a first-class requirement
- each phase should stay small and testable
