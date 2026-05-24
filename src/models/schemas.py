from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


# ---------------------------------------------------------------------------
# SQLAlchemy ORM models
# ---------------------------------------------------------------------------

class RuleCacheORM(Base):
    __tablename__ = "rule_cache"

    rule_id: Mapped[str] = mapped_column(String, primary_key=True)
    rule_type: Mapped[str] = mapped_column(String, nullable=False)  # TEXT_MATCH | DOMAIN_TYPE_MATCH
    text_fingerprint: Mapped[str | None] = mapped_column(String, nullable=True)
    scf_domain: Mapped[str | None] = mapped_column(String, nullable=True)
    control_type: Mapped[str | None] = mapped_column(String, nullable=True)
    gate_mode: Mapped[str] = mapped_column(String, nullable=False)  # BYPASS | ONE_TOUCH
    confidence_floor: Mapped[float] = mapped_column(Float, nullable=False)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    apply_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expiry: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    origin_qualifier: Mapped[str | None] = mapped_column(String, nullable=True)
    approved_output_service_id: Mapped[str | None] = mapped_column(String, nullable=True)
    approved_output_field: Mapped[str | None] = mapped_column(String, nullable=True)
    approved_output_value: Mapped[str | None] = mapped_column(String, nullable=True)


class GateEventORM(Base):
    __tablename__ = "gate_events"

    gate_event_id: Mapped[str] = mapped_column(String, primary_key=True)
    gate_id: Mapped[str] = mapped_column(String, nullable=False)  # GATE_1 | GATE_2
    chunk_id: Mapped[str] = mapped_column(String, nullable=False)
    document_id: Mapped[str] = mapped_column(String, nullable=False)
    text_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    scf_domain: Mapped[str | None] = mapped_column(String, nullable=True)
    control_type: Mapped[str | None] = mapped_column(String, nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_qualifier: Mapped[str] = mapped_column(String, nullable=False)  # HIGH | MODERATE | LOW
    rule_applied: Mapped[str | None] = mapped_column(String, nullable=True)
    rule_type_applied: Mapped[str | None] = mapped_column(String, nullable=True)
    gate_tier: Mapped[str] = mapped_column(String, nullable=False)  # AUTO_PROCEED | ONE_TOUCH | HARD_REVIEW
    gate_mode: Mapped[str | None] = mapped_column(String, nullable=True)  # BYPASS | ONE_TOUCH
    resolution: Mapped[str] = mapped_column(String, nullable=False)
    resolved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    correction_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    corrected_fields: Mapped[list | None] = mapped_column(JSON, nullable=True)
    promoted_to_rule: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    promoted_rule_id: Mapped[str | None] = mapped_column(String, nullable=True)


class ReviewQueueORM(Base):
    __tablename__ = "review_queue"

    queue_entry_id: Mapped[str] = mapped_column(String, primary_key=True)
    gate_event_id: Mapped[str] = mapped_column(
        String, ForeignKey("gate_events.gate_event_id"), nullable=False, unique=True
    )
    gate_id: Mapped[str] = mapped_column(String, nullable=False)
    gate_tier: Mapped[str] = mapped_column(String, nullable=False)
    chunk_id: Mapped[str] = mapped_column(String, nullable=False)
    document_id: Mapped[str] = mapped_column(String, nullable=False)
    text_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_qualifier: Mapped[str] = mapped_column(String, nullable=False)
    enqueued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class GateEvaluationRequest(BaseModel):
    gate_id: Literal["GATE_1", "GATE_2"]
    chunk_id: str
    document_id: str
    text_fingerprint: str
    confidence_score: float
    confidence_qualifier: Literal["HIGH", "MODERATE", "LOW"]
    scf_domain: str | None = None
    control_type: Literal["PREVENTIVE", "DETECTIVE", "CORRECTIVE", "COMPENSATING"] | None = None

    @field_validator("confidence_score")
    @classmethod
    def score_in_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence_score must be in [0.0, 1.0]")
        return v


class RulePromotionInput(BaseModel):
    rule_type: Literal["TEXT_MATCH", "DOMAIN_TYPE_MATCH"]
    gate_mode: Literal["BYPASS", "ONE_TOUCH"]
    confidence_floor: float
    expiry: datetime | None = None

    @field_validator("confidence_floor")
    @classmethod
    def floor_in_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence_floor must be in [0.0, 1.0]")
        return v


class GateResolutionRequest(BaseModel):
    gate_event_id: str
    resolution: Literal["HUMAN_CONFIRMED", "HUMAN_CORRECTED", "HUMAN_REJECTED"]
    resolved_by: str
    corrected_fields: list[str] | None = None
    promote_to_rule: bool = False
    rule_promotion: RulePromotionInput | None = None


class UpdateExpiryRequest(BaseModel):
    expiry: datetime | None


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------

class GateEvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    gate_event_id: str
    gate_id: str
    chunk_id: str
    document_id: str
    gate_tier: str
    resolution: str
    rule_applied: str | None
    rule_type_applied: str | None
    gate_mode: str | None
    queue_entry_id: str | None


class GateResolutionResponse(BaseModel):
    gate_event_id: str
    resolution: str
    promoted_rule_id: str | None


class GateEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    gate_event_id: str
    gate_id: str
    chunk_id: str
    document_id: str
    text_fingerprint: str
    scf_domain: str | None
    control_type: str | None
    evaluated_at: datetime
    confidence_score: float
    confidence_qualifier: str
    rule_applied: str | None
    rule_type_applied: str | None
    gate_tier: str
    gate_mode: str | None
    resolution: str
    resolved_by: str | None
    resolved_at: datetime | None
    correction_applied: bool
    corrected_fields: list[str] | None
    promoted_to_rule: bool
    promoted_rule_id: str | None


class RuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rule_id: str
    rule_type: str
    text_fingerprint: str | None
    scf_domain: str | None
    control_type: str | None
    gate_mode: str
    confidence_floor: float
    created_by: str
    created_at: datetime
    last_applied_at: datetime | None
    apply_count: int
    expiry: datetime | None
    active: bool
    origin_qualifier: str | None
    approved_output_service_id: str | None
    approved_output_field: str | None
    approved_output_value: str | None


class ReviewQueueEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    queue_entry_id: str
    gate_event_id: str
    gate_id: str
    gate_tier: str
    chunk_id: str
    document_id: str
    text_fingerprint: str
    confidence_score: float
    confidence_qualifier: str
    enqueued_at: datetime
    priority: int
