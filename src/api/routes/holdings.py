from datetime import datetime
from functools import lru_cache
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.telemetry import get_tracer
from src.db.session import get_db
from src.schemas.holding import (
    AccountHoldingsResponse,
    AddHoldingApiRequest,
    AddHoldingApiResponse,
    DeleteHoldingApiResponse,
    InstrumentInfo,
    UpdateHoldingApiResponse,
    UpdateHoldingUnitsApiRequest,
)
from src.services.currency_conversion_service import CurrencyConversionService
from src.services.eod_market_data_tool import EodMarketDataTool
from src.services.holding_service import HoldingService
from src.services.metrics_service import MetricsService, get_metrics_service
from src.services.pricing_calculation_service import PricingCalculationService
from src.services.result_objects import ErrorCode

router = APIRouter(prefix="/api/holdings", tags=["holdings"])


@lru_cache()
def get_eod_tool() -> Optional[EodMarketDataTool]:
    """Dependency to get EOD Market Data Tool instance (singleton)."""
    if settings.eod_api_token:
        return EodMarketDataTool(
            api_token=settings.eod_api_token,
            base_url=settings.eod_api_base_url,
            timeout_seconds=settings.eod_api_timeout_seconds
        )
    return None


def get_currency_conversion_service(
    db: AsyncSession = Depends(get_db)
) -> CurrencyConversionService:
    """Dependency to get CurrencyConversionService instance."""
    return CurrencyConversionService(db)


def get_pricing_calculation_service(
    currency_service: CurrencyConversionService = Depends(get_currency_conversion_service)
) -> PricingCalculationService:
    """Dependency to get PricingCalculationService instance."""
    return PricingCalculationService(currency_service)


def get_holding_service(
    db: AsyncSession = Depends(get_db),
    eod_tool: Optional[EodMarketDataTool] = Depends(get_eod_tool),
    pricing_service: Optional[PricingCalculationService] = Depends(get_pricing_calculation_service)
) -> HoldingService:
    """Dependency to get HoldingService instance."""
    return HoldingService(db, eod_tool, pricing_service)


async def get_current_account_id() -> int:
    """
    Placeholder for authentication - gets current account ID.
    TODO: Replace with actual authentication logic.
    """
    return 1  # Hardcoded for now, replace with actual auth


@router.get("/date/{valuation_date}", response_model=AccountHoldingsResponse)
async def get_holdings_by_date(
    valuation_date: str,
    account_id: int = Depends(get_current_account_id),
    service: HoldingService = Depends(get_holding_service),
    metrics: MetricsService = Depends(get_metrics_service)
):
    """
    Get all holdings for an account on a specific valuation date.

    Args:
        valuation_date: Date in YYYY-MM-DD format
        account_id: Account ID from authenticated user (automatic)

    Returns:
        AccountHoldingsResponse with all holdings for the account on that date

    Responses:
        200: Successfully retrieved holdings
        400: Invalid date format
        404: No holdings found for this date
        500: Internal server error
    """
    import logging
    logger = logging.getLogger(__name__)
    tracer = get_tracer()

    with tracer.start_as_current_span("GetHoldingsByDate") as span:
        span.set_attribute("account.id", account_id)
        span.set_attribute("valuation.date", valuation_date)

        with metrics.track_holdings_request(account_id):
            try:
                logger.info(f"Getting holdings for account {account_id} on date {valuation_date}")

                # Parse date
                try:
                    date_only = datetime.strptime(valuation_date, "%Y-%m-%d").date()
                except ValueError as e:
                    logger.warning(f"Invalid date format: {valuation_date} - {e}")
                    span.set_attribute("error", True)
                    span.set_attribute("error.type", "validation_error")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid date format. Date must be in YYYY-MM-DD format"
                    )

                # Get holdings with aggregated totals from service
                response = await service.get_holdings_by_account_and_date_async(account_id, date_only)

                if not response:
                    logger.info(f"No holdings found for account {account_id} on date {date_only}")
                    span.set_attribute("holdings.count", 0)
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"No holdings found for account {account_id} on date {date_only}"
                    )

                logger.info(f"Found {response.total_holdings} holdings for account {account_id}")
                span.set_attribute("holdings.count", response.total_holdings)

                return response
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Unexpected error in get_holdings_by_date: {e}", exc_info=True)
                span.set_attribute("error", True)
                span.record_exception(e)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Internal server error: {str(e)}"
                )


@router.post(
    "/portfolio/{portfolio_id}",
    response_model=AddHoldingApiResponse,
    status_code=status.HTTP_201_CREATED
)
async def add_holding(
    portfolio_id: int,
    request: AddHoldingApiRequest,
    account_id: int = Depends(get_current_account_id),
    service: HoldingService = Depends(get_holding_service),
    metrics: MetricsService = Depends(get_metrics_service)
):
    """
    Add a new holding to a portfolio.

    Args:
        portfolio_id: Portfolio ID to add holding to
        request: AddHoldingApiRequest with holding details
        account_id: Account ID from authenticated user (automatic)

    Returns:
        AddHoldingApiResponse with success status and created holding details

    Responses:
        201: Holding successfully added
        400: Invalid request data or validation errors
        404: Portfolio not found or not accessible
        409: Duplicate holding already exists
        500: Internal server error
    """
    tracer = get_tracer()

    with tracer.start_as_current_span("AddHolding") as span:
        span.set_attribute("account.id", account_id)
        span.set_attribute("portfolio.id", portfolio_id)
        span.set_attribute("ticker", request.ticker)

        with metrics.track_holdings_mutation("add", account_id):
            result = await service.add_holding_async(portfolio_id, request, account_id)

            # Build response
            response = AddHoldingApiResponse(
                success=result.success,
                message=result.message,
                errors=result.errors if result.errors else None,
                holdingId=result.created_holding.id if result.created_holding else None,
                instrumentCreated=result.instrument_created,
                currentPrice=result.current_price,
                currentValue=result.current_value
            )

            # Add instrument info if available
            if result.instrument:
                response.instrument = InstrumentInfo(
                    id=result.instrument.id,
                    ticker=result.instrument.ticker,
                    name=result.instrument.name,
                    description=result.instrument.description,
                    currencyCode=result.instrument.currency_code or "USD",
                    quoteUnit=result.instrument.quote_unit,
                    instrumentTypeId=result.instrument.instrument_type_id
                )

            span.set_attribute("success", result.success)

            if not result.success:
                span.set_attribute("error", True)
                # Determine appropriate status code based on error_code
                if result.error_code in (ErrorCode.NOT_FOUND, ErrorCode.NOT_ACCESSIBLE):
                    return JSONResponse(
                        status_code=status.HTTP_404_NOT_FOUND,
                        content=response.model_dump(by_alias=True)
                    )
                elif result.error_code == ErrorCode.DUPLICATE:
                    return JSONResponse(
                        status_code=status.HTTP_409_CONFLICT,
                        content=response.model_dump(by_alias=True)
                    )
                else:
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content=response.model_dump(by_alias=True)
                    )

            return response


@router.put("/{holding_id}/units", response_model=UpdateHoldingApiResponse)
async def update_holding_units(
    holding_id: int,
    request: UpdateHoldingUnitsApiRequest,
    account_id: int = Depends(get_current_account_id),
    service: HoldingService = Depends(get_holding_service),
    metrics: MetricsService = Depends(get_metrics_service)
):
    """
    Update the units of an existing holding.

    Args:
        holding_id: Holding ID to update
        request: UpdateHoldingUnitsApiRequest with new units
        account_id: Account ID from authenticated user (automatic)

    Returns:
        UpdateHoldingApiResponse with success status and before/after values

    Responses:
        200: Holding successfully updated
        400: Invalid request data or validation errors
        404: Holding not found or not accessible
        500: Internal server error
    """
    tracer = get_tracer()

    with tracer.start_as_current_span("UpdateHoldingUnits") as span:
        span.set_attribute("account.id", account_id)
        span.set_attribute("holding.id", holding_id)

        with metrics.track_holdings_mutation("update", account_id):
            result = await service.update_holding_units_async(holding_id, request.units, account_id)

            # Get ticker from updated holding
            ticker = None
            if result.updated_holding and hasattr(result.updated_holding, 'instrument'):
                ticker = result.updated_holding.instrument.ticker
                span.set_attribute("ticker", ticker)

            response = UpdateHoldingApiResponse(
                success=result.success,
                message=result.message,
                errors=result.errors if result.errors else None,
                holdingId=holding_id,
                previousUnits=result.previous_units,
                newUnits=result.new_units,
                previousCurrentValue=result.previous_current_value,
                newCurrentValue=result.new_current_value,
                ticker=ticker
            )

            span.set_attribute("success", result.success)

            if not result.success:
                span.set_attribute("error", True)
                if result.error_code in (ErrorCode.NOT_FOUND, ErrorCode.NOT_ACCESSIBLE):
                    return JSONResponse(
                        status_code=status.HTTP_404_NOT_FOUND,
                        content=response.model_dump(by_alias=True)
                    )
                else:
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content=response.model_dump(by_alias=True)
                    )

            return response


@router.delete("/{holding_id}", response_model=DeleteHoldingApiResponse)
async def delete_holding(
    holding_id: int,
    account_id: int = Depends(get_current_account_id),
    service: HoldingService = Depends(get_holding_service),
    metrics: MetricsService = Depends(get_metrics_service)
):
    """
    Delete a holding from a portfolio.

    Args:
        holding_id: Holding ID to delete
        account_id: Account ID from authenticated user (automatic)

    Returns:
        DeleteHoldingApiResponse with success status and deleted holding details

    Responses:
        200: Holding successfully deleted
        404: Holding not found or not accessible
        500: Internal server error
    """
    tracer = get_tracer()

    with tracer.start_as_current_span("DeleteHolding") as span:
        span.set_attribute("account.id", account_id)
        span.set_attribute("holding.id", holding_id)

        with metrics.track_holdings_mutation("delete", account_id):
            result = await service.delete_holding_async(holding_id, account_id)

            if result.deleted_ticker:
                span.set_attribute("ticker", result.deleted_ticker)

            response = DeleteHoldingApiResponse(
                success=result.success,
                message=result.message,
                errors=result.errors if result.errors else None,
                deletedHoldingId=result.deleted_holding_id,
                deletedTicker=result.deleted_ticker,
                portfolioId=result.portfolio_id
            )

            span.set_attribute("success", result.success)

            if not result.success:
                span.set_attribute("error", True)
                if result.error_code in (ErrorCode.NOT_FOUND, ErrorCode.NOT_ACCESSIBLE):
                    return JSONResponse(
                        status_code=status.HTTP_404_NOT_FOUND,
                        content=response.model_dump(by_alias=True)
                    )
                else:
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content=response.model_dump(by_alias=True)
                    )

            return response

