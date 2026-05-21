# grc-rcm-gate

RCM Gate Infrastructure — audit backbone for the Reverse Mapping Methodology pipeline.

## Overview

`grc-rcm-gate` is the sole persistent-state service in the RCM pipeline. It owns:

- **Rule Cache** — validated routing decisions promoted by human reviewers. Used by the gate evaluator to route future records programmatically.
- **Gate Event Audit Log** — immutable record of every gate evaluation, regardless of tier.
- **Review Queue** — active queue of records awaiting human action (ONE_TOUCH or HARD_REVIEW).

All other pipeline services are stateless. This service is the explicit statefulness exception per CLAUDE.md Rule 2.

## Gate Tier Model

Every evaluation produces one of three tiers:

| Tier | Code | Description |
|---|---|---|
| Auto-Proceed | `AUTO_PROCEED` | Record proceeds without human action. Event is still recorded. |
| One-Touch | `ONE_TOUCH` | Pre-populated decision requiring single human confirm/reject. |
| Hard Review | `HARD_REVIEW` | Full human review required before record may proceed. |

See the [RCM Microservice Specification](https://github.com/Darth-Ginger/grc-toolkit-orchestrator/blob/master/docs/Risk_Control_Mapping_Microservice_Specification.md) §3.6 for the complete decision matrix.

## API

- `POST /api/v1/gate/evaluate` — evaluate a record and assign a gate tier
- `POST /api/v1/gate/resolve` — submit a human resolution for a queued record
- `GET /api/v1/gate/queue` — list queued items awaiting human review
- `GET /api/v1/gate/rules` — list rule cache entries
- `GET /api/v1/gate/audit` — query the audit log
- `GET /health` — health check

Swagger UI available at `/docs`.

## Running

```bash
# Standalone
docker compose up -d --build

# Via orchestrator
docker compose up -d --build grc-rcm-gate
```

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `GRC_ADMIN_SECRET_KEY` | — | Required for `X-Admin-Token` on write endpoints |
| `DATABASE_PATH` | `/app/data/gate.db` | SQLite database path |
| `PORT` | `8000` | Internal listen port |
