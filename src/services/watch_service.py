"""Business logic service for the Watch evaluation system."""
import logging
from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.watch import (
    Alert,
    AlertSeverity,
    Watch,
    WatchCadence,
    WatchRun,
    WatchRunStatus,
    WatchScopeType,
    WatchType,
)
from src.services.result_objects import (
    AlertListResult,
    AlertResult,
    ErrorCode,
    WatchListResult,
    WatchResult,
    WatchRunListResult,
    WatchRunResult,
)

logger = logging.getLogger(__name__)


class WatchService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_watch(
        self,
        account_id: int,
        name: str,
        description: Optional[str],
        scope_type: WatchScopeType,
        scope_ref: Optional[str],
        watch_type: WatchType,
        cadence: WatchCadence,
    ) -> WatchResult:
        try:
            watch = Watch(
                id=uuid4(),
                account_id=account_id,
                name=name,
                description=description,
                scope_type=scope_type,
                scope_ref=scope_ref,
                watch_type=watch_type,
                cadence=cadence,
                is_active=True,
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(watch)
            await self.db.commit()
            await self.db.refresh(watch)
            logger.info(f"Created watch {watch.id} for account {account_id}")
            return WatchResult(success=True, message="Watch created successfully", watch=watch)
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating watch: {e}", exc_info=True)
            return WatchResult(
                success=False,
                message="An error occurred while creating the watch",
                errors=[str(e)],
                error_code=ErrorCode.INTERNAL_ERROR,
            )

    async def get_watch(self, watch_id: UUID, account_id: int) -> WatchResult:
        try:
            result = await self.db.execute(select(Watch).where(Watch.id == watch_id))
            watch = result.scalar_one_or_none()
            if watch is None:
                return WatchResult(
                    success=False,
                    message=f"Watch {watch_id} not found",
                    errors=["Watch not found"],
                    error_code=ErrorCode.NOT_FOUND,
                )
            if watch.account_id != account_id:
                return WatchResult(
                    success=False,
                    message=f"Watch {watch_id} is not accessible",
                    errors=["Watch does not belong to this account"],
                    error_code=ErrorCode.NOT_ACCESSIBLE,
                )
            return WatchResult(success=True, message="Watch retrieved successfully", watch=watch)
        except Exception as e:
            logger.error(f"Error retrieving watch {watch_id}: {e}", exc_info=True)
            return WatchResult(
                success=False,
                message="An error occurred while retrieving the watch",
                errors=[str(e)],
                error_code=ErrorCode.INTERNAL_ERROR,
            )

    async def list_watches(self, account_id: int, active_only: bool = False) -> WatchListResult:
        try:
            conditions: List[Any] = [Watch.account_id == account_id]
            if active_only:
                conditions.append(Watch.is_active == True)  # noqa: E712
            result = await self.db.execute(
                select(Watch).where(and_(*conditions)).order_by(Watch.created_at.desc())
            )
            watches = list(result.scalars().all())
            return WatchListResult(
                success=True, message=f"Retrieved {len(watches)} watches", watches=watches
            )
        except Exception as e:
            logger.error(f"Error listing watches for account {account_id}: {e}", exc_info=True)
            return WatchListResult(
                success=False,
                message="An error occurred while listing watches",
                errors=[str(e)],
                error_code=ErrorCode.INTERNAL_ERROR,
            )

    async def update_watch(
        self,
        watch_id: UUID,
        account_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        scope_ref: Optional[str] = None,
        cadence: Optional[WatchCadence] = None,
        is_active: Optional[bool] = None,
    ) -> WatchResult:
        try:
            get_result = await self.get_watch(watch_id, account_id)
            if not get_result.success:
                return get_result
            watch = get_result.watch
            if name is not None:
                watch.name = name
            if description is not None:
                watch.description = description
            if scope_ref is not None:
                watch.scope_ref = scope_ref
            if cadence is not None:
                watch.cadence = cadence
            if is_active is not None:
                watch.is_active = is_active
            watch.updated_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(watch)
            logger.info(f"Updated watch {watch_id}")
            return WatchResult(success=True, message="Watch updated successfully", watch=watch)
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating watch {watch_id}: {e}", exc_info=True)
            return WatchResult(
                success=False,
                message="An error occurred while updating the watch",
                errors=[str(e)],
                error_code=ErrorCode.INTERNAL_ERROR,
            )

    async def deactivate_watch(self, watch_id: UUID, account_id: int) -> WatchResult:
        return await self.update_watch(watch_id, account_id, is_active=False)

    async def list_due_watches(
        self, cadence: Optional[WatchCadence] = None
    ) -> WatchListResult:
        """Return active watches due for evaluation. Excludes manual-cadence watches when no cadence filter given."""
        try:
            conditions: List[Any] = [Watch.is_active == True]  # noqa: E712
            if cadence is not None:
                conditions.append(Watch.cadence == cadence)
            else:
                conditions.append(Watch.cadence != WatchCadence.manual)
            result = await self.db.execute(
                select(Watch).where(and_(*conditions)).order_by(Watch.last_run_at.asc())
            )
            watches = list(result.scalars().all())
            return WatchListResult(
                success=True, message=f"Retrieved {len(watches)} due watches", watches=watches
            )
        except Exception as e:
            logger.error(f"Error listing due watches: {e}", exc_info=True)
            return WatchListResult(
                success=False,
                message="An error occurred while listing due watches",
                errors=[str(e)],
                error_code=ErrorCode.INTERNAL_ERROR,
            )

    async def start_watch_run(self, watch_id: UUID) -> WatchRunResult:
        """Create a WatchRun with status=started and update watch.last_run_at. No ownership check — internal use."""
        try:
            result = await self.db.execute(select(Watch).where(Watch.id == watch_id))
            watch = result.scalar_one_or_none()
            if watch is None:
                return WatchRunResult(
                    success=False,
                    message=f"Watch {watch_id} not found",
                    errors=["Watch not found"],
                    error_code=ErrorCode.NOT_FOUND,
                )
            now = datetime.now(timezone.utc)
            run = WatchRun(
                id=uuid4(),
                watch_id=watch_id,
                started_at=now,
                status=WatchRunStatus.started,
            )
            self.db.add(run)
            watch.last_run_at = now
            watch.updated_at = now
            await self.db.commit()
            await self.db.refresh(run)
            logger.info(f"Started watch run {run.id} for watch {watch_id}")
            return WatchRunResult(success=True, message="Watch run started", watch_run=run)
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error starting watch run for watch {watch_id}: {e}", exc_info=True)
            return WatchRunResult(
                success=False,
                message="An error occurred while starting the watch run",
                errors=[str(e)],
                error_code=ErrorCode.INTERNAL_ERROR,
            )

    async def complete_watch_run(
        self,
        run_id: UUID,
        summary: str,
        raw_result_json: Optional[dict] = None,
    ) -> WatchRunResult:
        try:
            result = await self.db.execute(select(WatchRun).where(WatchRun.id == run_id))
            run = result.scalar_one_or_none()
            if run is None:
                return WatchRunResult(
                    success=False,
                    message=f"WatchRun {run_id} not found",
                    errors=["WatchRun not found"],
                    error_code=ErrorCode.NOT_FOUND,
                )
            run.status = WatchRunStatus.completed
            run.completed_at = datetime.now(timezone.utc)
            run.summary = summary
            run.raw_result_json = raw_result_json
            await self.db.commit()
            await self.db.refresh(run)
            logger.info(f"Completed watch run {run_id}")
            return WatchRunResult(success=True, message="Watch run completed", watch_run=run)
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error completing watch run {run_id}: {e}", exc_info=True)
            return WatchRunResult(
                success=False,
                message="An error occurred while completing the watch run",
                errors=[str(e)],
                error_code=ErrorCode.INTERNAL_ERROR,
            )

    async def fail_watch_run(self, run_id: UUID, error_message: str) -> WatchRunResult:
        try:
            result = await self.db.execute(select(WatchRun).where(WatchRun.id == run_id))
            run = result.scalar_one_or_none()
            if run is None:
                return WatchRunResult(
                    success=False,
                    message=f"WatchRun {run_id} not found",
                    errors=["WatchRun not found"],
                    error_code=ErrorCode.NOT_FOUND,
                )
            run.status = WatchRunStatus.failed
            run.completed_at = datetime.now(timezone.utc)
            run.error_message = error_message
            await self.db.commit()
            await self.db.refresh(run)
            logger.info(f"Failed watch run {run_id}: {error_message}")
            return WatchRunResult(success=True, message="Watch run marked as failed", watch_run=run)
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error failing watch run {run_id}: {e}", exc_info=True)
            return WatchRunResult(
                success=False,
                message="An error occurred while failing the watch run",
                errors=[str(e)],
                error_code=ErrorCode.INTERNAL_ERROR,
            )

    async def create_alert(
        self,
        watch_id: UUID,
        watch_run_id: Optional[UUID],
        severity: AlertSeverity,
        title: str,
        message: str,
        evidence_json: Optional[dict] = None,
    ) -> AlertResult:
        try:
            now = datetime.now(timezone.utc)
            alert = Alert(
                id=uuid4(),
                watch_id=watch_id,
                watch_run_id=watch_run_id,
                severity=severity,
                title=title,
                message=message,
                evidence_json=evidence_json,
                created_at=now,
            )
            self.db.add(alert)
            watch_result = await self.db.execute(select(Watch).where(Watch.id == watch_id))
            watch = watch_result.scalar_one_or_none()
            if watch is not None:
                watch.last_alert_at = now
                watch.updated_at = now
            await self.db.commit()
            await self.db.refresh(alert)
            logger.info(f"Created alert {alert.id} for watch {watch_id} with severity {severity}")
            return AlertResult(success=True, message="Alert created successfully", alert=alert)
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating alert for watch {watch_id}: {e}", exc_info=True)
            return AlertResult(
                success=False,
                message="An error occurred while creating the alert",
                errors=[str(e)],
                error_code=ErrorCode.INTERNAL_ERROR,
            )

    async def list_alerts(
        self,
        account_id: int,
        watch_id: Optional[UUID] = None,
        severity: Optional[AlertSeverity] = None,
    ) -> AlertListResult:
        """List alerts for an account's watches. Joins Alert→Watch to enforce ownership."""
        try:
            conditions: List[Any] = [Watch.account_id == account_id]
            if watch_id is not None:
                conditions.append(Alert.watch_id == watch_id)
            if severity is not None:
                conditions.append(Alert.severity == severity)
            result = await self.db.execute(
                select(Alert)
                .join(Watch, Alert.watch_id == Watch.id)
                .where(and_(*conditions))
                .order_by(Alert.created_at.desc())
            )
            alerts = list(result.scalars().all())
            return AlertListResult(
                success=True, message=f"Retrieved {len(alerts)} alerts", alerts=alerts
            )
        except Exception as e:
            logger.error(f"Error listing alerts for account {account_id}: {e}", exc_info=True)
            return AlertListResult(
                success=False,
                message="An error occurred while listing alerts",
                errors=[str(e)],
                error_code=ErrorCode.INTERNAL_ERROR,
            )

    async def list_watch_runs(self, watch_id: UUID, account_id: int) -> WatchRunListResult:
        try:
            get_result = await self.get_watch(watch_id, account_id)
            if not get_result.success:
                return WatchRunListResult(
                    success=False,
                    message=get_result.message,
                    errors=get_result.errors,
                    error_code=get_result.error_code,
                )
            result = await self.db.execute(
                select(WatchRun)
                .where(WatchRun.watch_id == watch_id)
                .order_by(WatchRun.started_at.desc())
            )
            runs = list(result.scalars().all())
            return WatchRunListResult(
                success=True, message=f"Retrieved {len(runs)} watch runs", watch_runs=runs
            )
        except Exception as e:
            logger.error(f"Error listing runs for watch {watch_id}: {e}", exc_info=True)
            return WatchRunListResult(
                success=False,
                message="An error occurred while listing watch runs",
                errors=[str(e)],
                error_code=ErrorCode.INTERNAL_ERROR,
            )
