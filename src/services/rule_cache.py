from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.models.schemas import GateEvaluationRequest, GateEventORM, RuleCacheORM, RulePromotionInput


def find_matching_rule(request: GateEvaluationRequest, db: Session) -> RuleCacheORM | None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # 1. TEXT_MATCH rules — evaluated first
    text_matches = (
        db.query(RuleCacheORM)
        .filter(
            RuleCacheORM.rule_type == "TEXT_MATCH",
            RuleCacheORM.text_fingerprint == request.text_fingerprint,
            RuleCacheORM.confidence_floor <= request.confidence_score,
            RuleCacheORM.active.is_(True),
            or_(RuleCacheORM.expiry.is_(None), RuleCacheORM.expiry > now),
        )
        .order_by(RuleCacheORM.confidence_floor.desc())
        .all()
    )
    if text_matches:
        return text_matches[0]

    # 2. DOMAIN_TYPE_MATCH fallback — both scf_domain and control_type must be present
    if not request.scf_domain or not request.control_type:
        return None

    domain_matches = (
        db.query(RuleCacheORM)
        .filter(
            RuleCacheORM.rule_type == "DOMAIN_TYPE_MATCH",
            RuleCacheORM.scf_domain == request.scf_domain,
            RuleCacheORM.control_type == request.control_type,
            RuleCacheORM.confidence_floor <= request.confidence_score,
            RuleCacheORM.active.is_(True),
            or_(RuleCacheORM.expiry.is_(None), RuleCacheORM.expiry > now),
        )
        .order_by(RuleCacheORM.confidence_floor.desc())
        .all()
    )
    if domain_matches:
        return domain_matches[0]

    return None


def record_rule_applied(rule_id: str, db: Session) -> None:
    rule = db.get(RuleCacheORM, rule_id)
    if rule:
        rule.last_applied_at = datetime.now(timezone.utc).replace(tzinfo=None)
        rule.apply_count = (rule.apply_count or 0) + 1
        db.commit()


def create_rule(
    rule_promotion: RulePromotionInput,
    gate_event: GateEventORM,
    created_by: str,
    db: Session,
) -> RuleCacheORM:
    rule = RuleCacheORM(
        rule_id=str(uuid4()),
        rule_type=rule_promotion.rule_type,
        text_fingerprint=gate_event.text_fingerprint if rule_promotion.rule_type == "TEXT_MATCH" else None,
        scf_domain=gate_event.scf_domain if rule_promotion.rule_type == "DOMAIN_TYPE_MATCH" else None,
        control_type=gate_event.control_type if rule_promotion.rule_type == "DOMAIN_TYPE_MATCH" else None,
        gate_mode=rule_promotion.gate_mode,
        confidence_floor=rule_promotion.confidence_floor,
        created_by=created_by,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        expiry=rule_promotion.expiry,
        active=True,
        apply_count=0,
        origin_qualifier=gate_event.confidence_qualifier,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def get_rule(rule_id: str, db: Session) -> RuleCacheORM:
    rule = db.get(RuleCacheORM, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


def list_rules(db: Session) -> list[RuleCacheORM]:
    return db.query(RuleCacheORM).order_by(RuleCacheORM.created_at.desc()).all()


def deactivate_rule(rule_id: str, db: Session) -> RuleCacheORM:
    rule = get_rule(rule_id, db)
    rule.active = False
    db.commit()
    db.refresh(rule)
    return rule


def update_expiry(rule_id: str, expiry: datetime | None, db: Session) -> RuleCacheORM:
    rule = get_rule(rule_id, db)
    rule.expiry = expiry
    db.commit()
    db.refresh(rule)
    return rule
