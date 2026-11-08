import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import relationship

from app.db.session import Base

# Portable JSON type: uses JSONB on PostgreSQL, falls back to JSON on SQLite/others
JsonType = JSONB().with_variant(JSON(), "sqlite")


def utc_now():
    return datetime.now(timezone.utc)


class Run(Base):
    __tablename__ = "runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, default="Untitled Ingestion Run")
    status = Column(String(50), nullable=False, default="created")  # created, ready, running, paused, completed, failed
    browser_session_id = Column(String(64), nullable=True, index=True)  # legacy identifier
    session_hash = Column(String(64), nullable=True, index=True)  # SHA-256 hash of HttpOnly cookie secret
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    metadata_json = Column(JsonType, nullable=False, default=dict)

    episodes = relationship("EpisodeRecord", back_populates="run", cascade="all, delete-orphan", order_by="EpisodeRecord.episode_number")
    promos = relationship("PromoCandidate", back_populates="run", cascade="all, delete-orphan")
    model_calls = relationship("ModelCall", back_populates="run", cascade="all, delete-orphan")


class EpisodeRecord(Base):
    __tablename__ = "episodes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    internal_id = Column(String(64), nullable=False, index=True)
    episode_number = Column(Integer, nullable=True, index=True)
    filename = Column(String(255), nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    duration_ms = Column(Integer, nullable=False)
    logline = Column(Text, nullable=True)
    continuity_notes = Column(Text, nullable=True)
    scenes_json = Column(JsonType, nullable=False, default=list)
    events_json = Column(JsonType, nullable=False, default=list)
    warnings_json = Column(JsonType, nullable=False, default=list)
    parser_version = Column(String(20), nullable=False)
    
    # Milestone 3 Per-Episode persistence, execution state & atomic lease claims
    analysis_status = Column(String(50), nullable=False, default="pending", index=True)  # pending, analyzing, completed, failed, paused
    analysis_result_json = Column(JsonType, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    lease_token = Column(String(64), nullable=True, index=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    attempt_number = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    run = relationship("Run", back_populates="episodes")
    promos = relationship("PromoCandidate", back_populates="episode")

    __table_args__ = (
        UniqueConstraint("run_id", "content_hash", name="uq_run_content_hash"),
    )


class PromoCandidate(Base):
    __tablename__ = "promos"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True, index=True)
    rank = Column(Integer, nullable=True, index=True)
    show_rank = Column(Integer, nullable=True, index=True)
    editorial_title = Column(String(255), nullable=True)
    overall_score = Column(Float, nullable=True, index=True)
    duration_ms = Column(Integer, nullable=False)
    hook_description = Column(Text, nullable=False)
    cliffhanger_description = Column(Text, nullable=False)
    why_it_works = Column(Text, nullable=False)
    unresolved_question = Column(Text, nullable=True)
    segments_json = Column(JsonType, nullable=False, default=list)
    editorial_flags_json = Column(JsonType, nullable=False, default=list)
    candidate_data_json = Column(JsonType, nullable=True)
    status = Column(String(50), nullable=False, default="suggested")  # suggested, approved, rejected
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    run = relationship("Run", back_populates="promos")
    episode = relationship("EpisodeRecord", back_populates="promos")


class ModelCall(Base):
    __tablename__ = "model_calls"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=True, index=True)
    provider = Column(String(50), nullable=False)  # openai, gemini, anthropic
    model_identifier = Column(String(100), nullable=False)
    prompt_version = Column(String(50), nullable=False)
    prompt_messages_json = Column(JsonType, nullable=False, default=list)
    raw_response_text = Column(Text, nullable=False)
    parsed_response_json = Column(JsonType, nullable=True)
    status = Column(String(50), nullable=False, default="success")  # success, error, rate_limited
    usage_metadata_json = Column(JsonType, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    run = relationship("Run", back_populates="model_calls")
