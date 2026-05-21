import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from src.core.database import get_db, init_db
from src.core.logging_config import configure_logging
from src.models.schemas import (
    GateEvaluationRequest,
    GateEvaluationResponse,
    GateEventResponse,
    GateResolutionRequest,
    GateResolutionResponse,
    ReviewQueueEntryResponse,
    RuleResponse,
    UpdateExpiryRequest,
)
from src.services import audit_log, gate_evaluator, review_queue, rule_cache

_admin_key_header = APIKeyHeader(name="X-Admin-Token", auto_error=False)


def _require_admin(token: str | None = Depends(_admin_key_header)) -> None:
    secret = os.getenv("GRC_ADMIN_SECRET_KEY", "")
    if not secret or token != secret:
        raise HTTPException(status_code=401, detail="Invalid admin token")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_db()
    yield


app = FastAPI(title="grc-rcm-gate", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


@app.get("/health")
def health():
    return {"status": "ok", "service": "grc-rcm-gate"}


# ---------------------------------------------------------------------------
# Gate evaluation
# ---------------------------------------------------------------------------

@app.post("/api/v1/gate/evaluate", response_model=GateEvaluationResponse)
def evaluate(request: GateEvaluationRequest, db: Session = Depends(get_db)):
    return gate_evaluator.evaluate(request, db)


@app.post("/api/v1/gate/resolve", response_model=GateResolutionResponse)
def resolve(request: GateResolutionRequest, db: Session = Depends(get_db)):
    return gate_evaluator.resolve(request, db)


# ---------------------------------------------------------------------------
# Review queue
# ---------------------------------------------------------------------------

@app.get("/api/v1/gate/queue", response_model=list[ReviewQueueEntryResponse])
def get_queue(
    gate_id: str | None = None,
    gate_tier: str | None = None,
    document_id: str | None = None,
    priority: int | None = None,
    db: Session = Depends(get_db),
):
    return review_queue.list_queue(db, gate_id=gate_id, gate_tier=gate_tier, document_id=document_id, priority=priority)


@app.get("/api/v1/gate/queue/{queue_entry_id}", response_model=ReviewQueueEntryResponse)
def get_queue_entry(queue_entry_id: str, db: Session = Depends(get_db)):
    return review_queue.get_entry(queue_entry_id, db)


# ---------------------------------------------------------------------------
# Rule cache
# ---------------------------------------------------------------------------

@app.get("/api/v1/gate/rules", response_model=list[RuleResponse])
def list_rules(db: Session = Depends(get_db)):
    return rule_cache.list_rules(db)


@app.get("/api/v1/gate/rules/{rule_id}", response_model=RuleResponse)
def get_rule(rule_id: str, db: Session = Depends(get_db)):
    return rule_cache.get_rule(rule_id, db)


@app.patch("/api/v1/gate/rules/{rule_id}/deactivate", response_model=RuleResponse)
def deactivate_rule(
    rule_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(_require_admin),
):
    return rule_cache.deactivate_rule(rule_id, db)


@app.patch("/api/v1/gate/rules/{rule_id}/expiry", response_model=RuleResponse)
def update_expiry(
    rule_id: str,
    request: UpdateExpiryRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_require_admin),
):
    return rule_cache.update_expiry(rule_id, request.expiry, db)


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

@app.get("/api/v1/gate/audit", response_model=list[GateEventResponse])
def list_audit(
    document_id: str | None = None,
    gate_id: str | None = None,
    resolution: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = Depends(get_db),
):
    return audit_log.list_events(
        db,
        document_id=document_id,
        gate_id=gate_id,
        resolution=resolution,
        date_from=date_from,
        date_to=date_to,
    )


@app.get("/api/v1/gate/audit/{gate_event_id}", response_model=GateEventResponse)
def get_audit_event(gate_event_id: str, db: Session = Depends(get_db)):
    return audit_log.get_event(gate_event_id, db)
