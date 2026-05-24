from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.models.schemas import GateEventORM


def write_event(data: dict, db: Session) -> GateEventORM:
    event = GateEventORM(**data)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_event(gate_event_id: str, db: Session) -> GateEventORM:
    event = db.get(GateEventORM, gate_event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Gate event not found")
    return event


def list_events(
    db: Session,
    document_id: str | None = None,
    gate_id: str | None = None,
    resolution: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[GateEventORM]:
    query = db.query(GateEventORM)
    if document_id:
        query = query.filter(GateEventORM.document_id == document_id)
    if gate_id:
        query = query.filter(GateEventORM.gate_id == gate_id)
    if resolution:
        query = query.filter(GateEventORM.resolution == resolution)
    if date_from:
        query = query.filter(GateEventORM.evaluated_at >= date_from)
    if date_to:
        query = query.filter(GateEventORM.evaluated_at <= date_to)
    return query.order_by(GateEventORM.evaluated_at.desc()).all()
