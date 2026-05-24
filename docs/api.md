# grc-rcm-gate API Reference

See `/docs` (Swagger UI) when the service is running for interactive documentation.

## Key ID Semantics

- **`gate_event_id`** — primary key returned by `POST /evaluate`. Use this in `POST /resolve` and `GET /audit/{id}`.
- **`queue_entry_id`** — secondary key for queue management only. Null when `gate_tier = AUTO_PROCEED`.

## Evaluate

`POST /api/v1/gate/evaluate`

Evaluates a record from RCM-SVC-03 or RCM-SVC-04 against the Rule Cache and assigns a gate tier.

**Flow:**
1. Sub-band is computed from `confidence_score` + `confidence_qualifier`
2. Rule Cache is queried (TEXT_MATCH first, DOMAIN_TYPE_MATCH as fallback)
3. Tier is assigned per §3.6.2 matrix
4. Gate event is written to audit log (always, before return)
5. If tier is ONE_TOUCH or HARD_REVIEW, record is enqueued for human review

**Response includes `gate_event_id` (for resolve) and `queue_entry_id` (null for AUTO_PROCEED).**

## Resolve

`POST /api/v1/gate/resolve`

Submits a human resolution for a queued gate event.

**Constraints:**
- Event must be in `AWAITING_HUMAN` state
- LOW-origin records cannot be promoted to BYPASS mode (422)
- HUMAN_REJECTED + promote_to_rule is rejected (422)

## Admin Endpoints

The following require `X-Admin-Token` header matching `GRC_ADMIN_SECRET_KEY`:

- `PATCH /api/v1/gate/rules/{rule_id}/deactivate`
- `PATCH /api/v1/gate/rules/{rule_id}/expiry`
