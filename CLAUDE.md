# CLAUDE.md — grc-rcm-gate

## Statefulness Exception

This service is the **explicit statefulness exception** per CLAUDE.md Rule 2 of the grc-toolkit-orchestrator. It is not optional statefulness — it is the designated single owner of persistent gate state for the entire RCM pipeline:

- `rule_cache` table — validated routing decisions promoted by human reviewers
- `gate_events` table — immutable audit log of every gate evaluation
- `review_queue` table — active queue of records awaiting human action

No other service may replicate or cache this state.

## Architecture

```
src/
  api/main.py           — FastAPI entry point; all endpoints
  core/database.py      — SQLAlchemy engine, session factory, init_db()
  core/logging_config.py
  models/schemas.py     — SQLAlchemy ORM models + Pydantic v2 request/response models
  services/
    gate_evaluator.py   — evaluate() and resolve() — the two main workflows
    rule_cache.py       — find_matching_rule(), CRUD
    audit_log.py        — write_event(), list_events() — NO update/delete functions
    review_queue.py     — enqueue(), resolve_entry(), list_queue()
data/                   — gate.db lives here at runtime (volume-mounted)
```

## Critical Invariants

1. `audit_log.py` contains NO `update()` or `delete()` calls — ever.
2. The only permitted "update" to a gate event is resolution field population, and it lives exclusively in `gate_evaluator.resolve()`.
3. `LOW`-origin records may never be promoted to `BYPASS` mode. This is enforced in `gate_evaluator.resolve()` before any DB write.
4. Every `evaluate()` call writes to the audit log before returning. Bypassing this step is a critical defect.
5. `gate_event_id` is the primary key for all post-evaluate workflows (resolve, audit lookup).
6. `queue_entry_id` is the secondary key for queue display only.

## Commands

```bash
# Install dependencies
uv sync

# Run locally
uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Build and run via Docker
docker compose up -d --build
```
