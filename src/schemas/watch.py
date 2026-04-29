"""Pydantic schemas for Watch API requests and responses."""
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.db.models.watch import AlertSeverity, WatchCadence, WatchRunStatus, WatchScopeType, WatchType


class CreateWatchRequest(BaseModel):
    name: str
    description: Optional[str] = None
    scope_type: WatchScopeType = Field(alias="scopeType")
    scope_ref: Optional[str] = Field(None, alias="scopeRef")
    watch_type: WatchType = Field(alias="watchType")
    cadence: WatchCadence

    model_config = ConfigDict(populate_by_name=True)


class UpdateWatchRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    scope_ref: Optional[str] = Field(None, alias="scopeRef")
    cadence: Optional[WatchCadence] = None
    is_active: Optional[bool] = Field(None, alias="isActive")

    model_config = ConfigDict(populate_by_name=True)


class WatchResponse(BaseModel):
    id: UUID
    account_id: int = Field(alias="accountId")
    name: str
    description: Optional[str] = None
    scope_type: WatchScopeType = Field(alias="scopeType")
    scope_ref: Optional[str] = Field(None, alias="scopeRef")
    watch_type: WatchType = Field(alias="watchType")
    cadence: WatchCadence
    is_active: bool = Field(alias="isActive")
    created_at: datetime = Field(alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")
    last_run_at: Optional[datetime] = Field(None, alias="lastRunAt")
    last_alert_at: Optional[datetime] = Field(None, alias="lastAlertAt")

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_model(cls, watch: Any) -> "WatchResponse":
        return cls(
            id=watch.id,
            accountId=watch.account_id,
            name=watch.name,
            description=watch.description,
            scopeType=watch.scope_type,
            scopeRef=watch.scope_ref,
            watchType=watch.watch_type,
            cadence=watch.cadence,
            isActive=watch.is_active,
            createdAt=watch.created_at,
            updatedAt=watch.updated_at,
            lastRunAt=watch.last_run_at,
            lastAlertAt=watch.last_alert_at,
        )


class WatchRunResponse(BaseModel):
    id: UUID
    watch_id: UUID = Field(alias="watchId")
    started_at: datetime = Field(alias="startedAt")
    completed_at: Optional[datetime] = Field(None, alias="completedAt")
    status: WatchRunStatus
    summary: Optional[str] = None
    raw_result_json: Optional[Dict[str, Any]] = Field(None, alias="rawResultJson")
    error_message: Optional[str] = Field(None, alias="errorMessage")

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_model(cls, run: Any) -> "WatchRunResponse":
        return cls(
            id=run.id,
            watchId=run.watch_id,
            startedAt=run.started_at,
            completedAt=run.completed_at,
            status=run.status,
            summary=run.summary,
            rawResultJson=run.raw_result_json,
            errorMessage=run.error_message,
        )


class AlertResponse(BaseModel):
    id: UUID
    watch_id: UUID = Field(alias="watchId")
    watch_run_id: Optional[UUID] = Field(None, alias="watchRunId")
    severity: AlertSeverity
    title: str
    message: str
    evidence_json: Optional[Dict[str, Any]] = Field(None, alias="evidenceJson")
    sent_at: Optional[datetime] = Field(None, alias="sentAt")
    suppressed_reason: Optional[str] = Field(None, alias="suppressedReason")
    created_at: datetime = Field(alias="createdAt")

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_model(cls, alert: Any) -> "AlertResponse":
        return cls(
            id=alert.id,
            watchId=alert.watch_id,
            watchRunId=alert.watch_run_id,
            severity=alert.severity,
            title=alert.title,
            message=alert.message,
            evidenceJson=alert.evidence_json,
            sentAt=alert.sent_at,
            suppressedReason=alert.suppressed_reason,
            createdAt=alert.created_at,
        )
