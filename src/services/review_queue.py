from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.models.schemas import GateEvaluationRequest, GateEventORM, ReviewQueueORM


def enqueue(event: GateEventORM, request: GateEvaluationRequest, db: Session) -> ReviewQueueORM:
    entry = ReviewQueueORM(
        queue_entry_id=str(uuid4()),
        gate_event_id=event.gate_event_id,
        gate_id=event.gate_id,
        gate_tier=event.gate_tier,
        chunk_id=event.chunk_id,
        document_id=event.document_id,
        text_fingerprint=request.text_fingerprint,
        confidence_score=event.confidence_score,
        confidence_qualifier=event.confidence_qualifier,
        enqueued_at=datetime.now(timezone.utc).replace(tzinfo=None),
        priority=0,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_entry(queue_entry_id: str, db: Session) -> ReviewQueueORM:
    entry = db.get(ReviewQueueORM, queue_entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Queue entry not found")
    return entry


def list_queue(
    db: Session,
    gate_id: str | None = None,
    gate_tier: str | None = None,
    document_id: str | None = None,
    priority: int | None = None,
) -> list[ReviewQueueORM]:
    query = db.query(ReviewQueueORM)
    if gate_id:
        query = query.filter(ReviewQueueORM.gate_id == gate_id)
    if gate_tier:
        query = query.filter(ReviewQueueORM.gate_tier == gate_tier)
    if document_id:
        query = query.filter(ReviewQueueORM.document_id == document_id)
    if priority is not None:
        query = query.filter(ReviewQueueORM.priority == priority)
    return query.order_by(ReviewQueueORM.priority.desc(), ReviewQueueORM.enqueued_at.asc()).all()


def resolve_entry(gate_event_id: str, db: Session) -> None:
    entry = db.query(ReviewQueueORM).filter(ReviewQueueORM.gate_event_id == gate_event_id).first()
    if entry:
        db.delete(entry)
        db.commit()
