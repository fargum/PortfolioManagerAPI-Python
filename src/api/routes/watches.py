"""FastAPI routes for the Watch evaluation system."""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import get_current_account_id
from src.db.models.watch import AlertSeverity
from src.db.session import get_db
from src.schemas.watch import (
    AlertResponse,
    CreateWatchRequest,
    UpdateWatchRequest,
    WatchResponse,
    WatchRunResponse,
)
from src.services.result_objects import ErrorCode
from src.services.watch_service import WatchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/watches", tags=["watches"])
alerts_router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def get_watch_service(db: AsyncSession = Depends(get_db)) -> WatchService:
    return WatchService(db)


def _http_status(error_code: ErrorCode) -> int:
    if error_code == ErrorCode.NOT_FOUND:
        return status.HTTP_404_NOT_FOUND
    if error_code == ErrorCode.NOT_ACCESSIBLE:
        return status.HTTP_403_FORBIDDEN
    return status.HTTP_400_BAD_REQUEST


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_watch(
    request: CreateWatchRequest,
    account_id: int = Depends(get_current_account_id),
    service: WatchService = Depends(get_watch_service),
):
    result = await service.create_watch(
        account_id=account_id,
        name=request.name,
        description=request.description,
        scope_type=request.scope_type,
        scope_ref=request.scope_ref,
        watch_type=request.watch_type,
        cadence=request.cadence,
    )
    if not result.success:
        return JSONResponse(
            status_code=_http_status(result.error_code),
            content={"success": False, "message": result.message, "errors": result.errors},
        )
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=WatchResponse.from_model(result.watch).model_dump(by_alias=True, mode="json"),
    )


@router.get("")
async def list_watches(
    active_only: bool = False,
    account_id: int = Depends(get_current_account_id),
    service: WatchService = Depends(get_watch_service),
):
    result = await service.list_watches(account_id=account_id, active_only=active_only)
    if not result.success:
        return JSONResponse(
            status_code=_http_status(result.error_code),
            content={"success": False, "message": result.message, "errors": result.errors},
        )
    return JSONResponse(
        content=[
            WatchResponse.from_model(w).model_dump(by_alias=True, mode="json")
            for w in result.watches
        ]
    )


@router.get("/{watch_id}")
async def get_watch(
    watch_id: UUID,
    account_id: int = Depends(get_current_account_id),
    service: WatchService = Depends(get_watch_service),
):
    result = await service.get_watch(watch_id=watch_id, account_id=account_id)
    if not result.success:
        return JSONResponse(
            status_code=_http_status(result.error_code),
            content={"success": False, "message": result.message, "errors": result.errors},
        )
    return JSONResponse(
        content=WatchResponse.from_model(result.watch).model_dump(by_alias=True, mode="json")
    )


@router.patch("/{watch_id}")
async def update_watch(
    watch_id: UUID,
    request: UpdateWatchRequest,
    account_id: int = Depends(get_current_account_id),
    service: WatchService = Depends(get_watch_service),
):
    result = await service.update_watch(
        watch_id=watch_id,
        account_id=account_id,
        name=request.name,
        description=request.description,
        scope_ref=request.scope_ref,
        cadence=request.cadence,
        is_active=request.is_active,
    )
    if not result.success:
        return JSONResponse(
            status_code=_http_status(result.error_code),
            content={"success": False, "message": result.message, "errors": result.errors},
        )
    return JSONResponse(
        content=WatchResponse.from_model(result.watch).model_dump(by_alias=True, mode="json")
    )


@router.post("/{watch_id}/deactivate")
async def deactivate_watch(
    watch_id: UUID,
    account_id: int = Depends(get_current_account_id),
    service: WatchService = Depends(get_watch_service),
):
    result = await service.deactivate_watch(watch_id=watch_id, account_id=account_id)
    if not result.success:
        return JSONResponse(
            status_code=_http_status(result.error_code),
            content={"success": False, "message": result.message, "errors": result.errors},
        )
    return JSONResponse(
        content=WatchResponse.from_model(result.watch).model_dump(by_alias=True, mode="json")
    )


@router.get("/{watch_id}/runs")
async def list_watch_runs(
    watch_id: UUID,
    account_id: int = Depends(get_current_account_id),
    service: WatchService = Depends(get_watch_service),
):
    result = await service.list_watch_runs(watch_id=watch_id, account_id=account_id)
    if not result.success:
        return JSONResponse(
            status_code=_http_status(result.error_code),
            content={"success": False, "message": result.message, "errors": result.errors},
        )
    return JSONResponse(
        content=[
            WatchRunResponse.from_model(r).model_dump(by_alias=True, mode="json")
            for r in result.watch_runs
        ]
    )


@router.post("/{watch_id}/run")
async def manual_run_watch(
    watch_id: UUID,
    account_id: int = Depends(get_current_account_id),
    service: WatchService = Depends(get_watch_service),
):
    """Placeholder manual watch run. Verifies ownership, creates a WatchRun, and immediately completes it."""
    get_result = await service.get_watch(watch_id=watch_id, account_id=account_id)
    if not get_result.success:
        return JSONResponse(
            status_code=_http_status(get_result.error_code),
            content={"success": False, "message": get_result.message, "errors": get_result.errors},
        )

    start_result = await service.start_watch_run(watch_id=watch_id)
    if not start_result.success:
        return JSONResponse(
            status_code=_http_status(start_result.error_code),
            content={"success": False, "message": start_result.message, "errors": start_result.errors},
        )

    complete_result = await service.complete_watch_run(
        run_id=start_result.watch_run.id,
        summary="Manual watch execution placeholder",
    )
    if not complete_result.success:
        return JSONResponse(
            status_code=_http_status(complete_result.error_code),
            content={"success": False, "message": complete_result.message, "errors": complete_result.errors},
        )

    return JSONResponse(
        content=WatchRunResponse.from_model(complete_result.watch_run).model_dump(by_alias=True, mode="json")
    )


@alerts_router.get("")
async def list_alerts(
    watch_id: Optional[UUID] = None,
    severity: Optional[AlertSeverity] = None,
    account_id: int = Depends(get_current_account_id),
    service: WatchService = Depends(get_watch_service),
):
    result = await service.list_alerts(
        account_id=account_id,
        watch_id=watch_id,
        severity=severity,
    )
    if not result.success:
        return JSONResponse(
            status_code=_http_status(result.error_code),
            content={"success": False, "message": result.message, "errors": result.errors},
        )
    return JSONResponse(
        content=[
            AlertResponse.from_model(a).model_dump(by_alias=True, mode="json")
            for a in result.alerts
        ]
    )
