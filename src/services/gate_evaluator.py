from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.models.schemas import (
    GateEvaluationRequest,
    GateEvaluationResponse,
    GateEventORM,
    GateResolutionRequest,
    GateResolutionResponse,
    RuleCacheORM,
)
from src.services import audit_log, review_queue, rule_cache


def _compute_subband(score: float, qualifier: str) -> str:
    if qualifier == "HIGH":
        return "HIGH"
    if qualifier == "MODERATE":
        return "MODERATE_H" if score >= 0.65 else "MODERATE_L"
    return "LOW"


def _assign_tier(subband: str, rule: RuleCacheORM | None) -> tuple[str, str | None]:
    """Return (gate_tier, gate_mode). First-match wins per spec §3.6.2."""
    if subband == "HIGH":
        return "AUTO_PROCEED", None

    if subband == "MODERATE_H":
        if rule and rule.gate_mode == "BYPASS":
            return "AUTO_PROCEED", "BYPASS"
        return "ONE_TOUCH", (rule.gate_mode if rule else None)

    if subband == "MODERATE_L":
        if rule and rule.gate_mode == "BYPASS":
            return "AUTO_PROCEED", "BYPASS"
        if rule and rule.gate_mode == "ONE_TOUCH":
            return "ONE_TOUCH", "ONE_TOUCH"
        return "HARD_REVIEW", None

    # LOW — ceiling is ONE_TOUCH; AUTO_PROCEED is structurally impossible
    if rule:
        return "ONE_TOUCH", "ONE_TOUCH"
    return "HARD_REVIEW", None


def evaluate(request: GateEvaluationRequest, db: Session) -> GateEvaluationResponse:
    subband = _compute_subband(request.confidence_score, request.confidence_qualifier)
    matched_rule = rule_cache.find_matching_rule(request, db)
    gate_tier, gate_mode = _assign_tier(subband, matched_rule)

    # Structural invariant — LOW qualifier can never reach AUTO_PROCEED
    if subband == "LOW" and gate_tier == "AUTO_PROCEED":
        raise RuntimeError("Logic defect: AUTO_PROCEED assigned to LOW qualifier")

    resolution = "AUTO_APPROVED" if gate_tier == "AUTO_PROCEED" else "AWAITING_HUMAN"

    event = audit_log.write_event(
        {
            "gate_event_id": str(uuid4()),
            "gate_id": request.gate_id,
            "chunk_id": request.chunk_id,
            "document_id": request.document_id,
            "text_fingerprint": request.text_fingerprint,
            "scf_domain": request.scf_domain,
            "control_type": request.control_type,
            "evaluated_at": datetime.now(timezone.utc).replace(tzinfo=None),
            "confidence_score": request.confidence_score,
            "confidence_qualifier": request.confidence_qualifier,
            "rule_applied": matched_rule.rule_id if matched_rule else None,
            "rule_type_applied": matched_rule.rule_type if matched_rule else None,
            "gate_tier": gate_tier,
            "gate_mode": gate_mode,
            "resolution": resolution,
            "correction_applied": False,
            "promoted_to_rule": False,
        },
        db,
    )

    if matched_rule:
        rule_cache.record_rule_applied(matched_rule.rule_id, db)

    queue_entry_id = None
    if gate_tier in ("ONE_TOUCH", "HARD_REVIEW"):
        queue_entry = review_queue.enqueue(event, request, db)
        queue_entry_id = queue_entry.queue_entry_id

    return GateEvaluationResponse(
        gate_event_id=event.gate_event_id,
        gate_id=event.gate_id,
        chunk_id=event.chunk_id,
        document_id=event.document_id,
        gate_tier=gate_tier,
        resolution=resolution,
        rule_applied=matched_rule.rule_id if matched_rule else None,
        rule_type_applied=matched_rule.rule_type if matched_rule else None,
        gate_mode=gate_mode,
        queue_entry_id=queue_entry_id,
    )


def resolve(request: GateResolutionRequest, db: Session) -> GateResolutionResponse:
    event = db.get(GateEventORM, request.gate_event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Gate event not found")
    if event.resolution != "AWAITING_HUMAN":
        raise HTTPException(status_code=422, detail="Gate event is not awaiting human resolution")

    if (
        request.promote_to_rule
        and request.rule_promotion
        and event.confidence_qualifier == "LOW"
        and request.rule_promotion.gate_mode == "BYPASS"
    ):
        raise HTTPException(
            status_code=422,
            detail="LOW-origin records cannot be promoted to BYPASS mode",
        )

    if request.resolution == "HUMAN_REJECTED" and request.promote_to_rule:
        raise HTTPException(
            status_code=422,
            detail="Rejected records cannot be promoted to a rule",
        )

    promoted_rule_id = None
    if request.promote_to_rule and request.rule_promotion:
        rule = rule_cache.create_rule(
            rule_promotion=request.rule_promotion,
            gate_event=event,
            created_by=request.resolved_by,
            db=db,
        )
        promoted_rule_id = rule.rule_id

    event.resolution = request.resolution
    event.resolved_by = request.resolved_by
    event.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
    event.correction_applied = bool(request.corrected_fields)
    event.corrected_fields = request.corrected_fields
    event.promoted_to_rule = bool(promoted_rule_id)
    event.promoted_rule_id = promoted_rule_id
    db.commit()

    review_queue.resolve_entry(request.gate_event_id, db)

    return GateResolutionResponse(
        gate_event_id=event.gate_event_id,
        resolution=event.resolution,
        promoted_rule_id=promoted_rule_id,
    )
