"""Watch, WatchRun, and Alert models for the scheduled watch-evaluation system."""
import enum
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

from src.db.session import Base


class WatchScopeType(str, enum.Enum):
    portfolio = "portfolio"
    holding = "holding"
    theme = "theme"
    market = "market"


class WatchType(str, enum.Enum):
    portfolio_health = "portfolio_health"
    holding_news = "holding_news"
    unusual_move = "unusual_move"
    market_context = "market_context"
    investment_thesis = "investment_thesis"
    income_risk = "income_risk"


class WatchCadence(str, enum.Enum):
    manual = "manual"
    morning = "morning"
    afternoon = "afternoon"
    daily = "daily"
    twice_daily = "twice_daily"
    weekly = "weekly"
    monthly = "monthly"


class WatchRunStatus(str, enum.Enum):
    started = "started"
    completed = "completed"
    failed = "failed"
    suppressed = "suppressed"


class AlertSeverity(str, enum.Enum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"


class Watch(Base):
    """Persistent investment monitoring brief evaluated periodically."""
    __tablename__ = "watches"
    __table_args__ = (
        Index("ix_watches_account_id", "account_id"),
        Index("ix_watches_is_active", "is_active"),
        Index("ix_watches_cadence", "cadence"),
        {"schema": "app"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True)
    account_id = Column(Integer, ForeignKey("app.accounts.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    scope_type = Column(
        SAEnum(WatchScopeType, name="watch_scope_type", native_enum=False),
        nullable=False,
    )
    scope_ref = Column(String, nullable=True)
    watch_type = Column(
        SAEnum(WatchType, name="watch_type_enum", native_enum=False),
        nullable=False,
    )
    cadence = Column(
        SAEnum(WatchCadence, name="watch_cadence", native_enum=False),
        nullable=False,
    )
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=datetime.utcnow)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    last_alert_at = Column(DateTime(timezone=True), nullable=True)

    runs = relationship("WatchRun", back_populates="watch", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="watch", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Watch(id={self.id}, name={self.name}, cadence={self.cadence})>"


class WatchRun(Base):
    """Single execution of a watch evaluation."""
    __tablename__ = "watch_runs"
    __table_args__ = (
        Index("ix_watch_runs_watch_id", "watch_id"),
        {"schema": "app"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True)
    watch_id = Column(UUID(as_uuid=True), ForeignKey("app.watches.id"), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(
        SAEnum(WatchRunStatus, name="watch_run_status", native_enum=False),
        nullable=False,
    )
    summary = Column(Text, nullable=True)
    raw_result_json = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    watch = relationship("Watch", back_populates="runs")
    alerts = relationship("Alert", back_populates="watch_run")

    def __repr__(self) -> str:
        return f"<WatchRun(id={self.id}, watch_id={self.watch_id}, status={self.status})>"


class Alert(Base):
    """Alert triggered by a watch evaluation."""
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_watch_id", "watch_id"),
        Index("ix_alerts_watch_run_id", "watch_run_id"),
        {"schema": "app"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True)
    watch_id = Column(UUID(as_uuid=True), ForeignKey("app.watches.id"), nullable=False)
    watch_run_id = Column(UUID(as_uuid=True), ForeignKey("app.watch_runs.id"), nullable=True)
    severity = Column(
        SAEnum(AlertSeverity, name="alert_severity", native_enum=False),
        nullable=False,
    )
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    evidence_json = Column(JSON, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    suppressed_reason = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    watch = relationship("Watch", back_populates="alerts")
    watch_run = relationship("WatchRun", back_populates="alerts")

    def __repr__(self) -> str:
        return f"<Alert(id={self.id}, watch_id={self.watch_id}, severity={self.severity})>"
