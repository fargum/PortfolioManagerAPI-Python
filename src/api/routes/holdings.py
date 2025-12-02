from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.services.holding_service import HoldingService
from src.services.eod_market_data_tool import EodMarketDataTool
from src.services.pricing_calculation_service import PricingCalculationService
from src.services.currency_conversion_service import CurrencyConversionService
from src.core.config import settings
from src.schemas.holding import (
    AccountHoldingsResponse,
    AddHoldingApiRequest,
    AddHoldingApiResponse,
    UpdateHoldingUnitsApiRequest,
    UpdateHoldingApiResponse,
    DeleteHoldingApiResponse,
    PortfolioHoldingDto,
    InstrumentInfo
)

router = APIRouter(prefix="/api/holdings", tags=["holdings"])


def get_eod_tool() -> Optional[EodMarketDataTool]:
    """Dependency to get EOD Market Data Tool instance."""
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
    service: HoldingService = Depends(get_holding_service)
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
    
    try:
        logger.info(f"Getting holdings for account {account_id} on date {valuation_date}")
        
        # Parse date
        try:
            date_only = datetime.strptime(valuation_date, "%Y-%m-%d").date()
        except ValueError as e:
            logger.warning(f"Invalid date format: {valuation_date} - {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Date must be in YYYY-MM-DD format"
            )
        
        # Get holdings
        holdings = await service.get_holdings_by_account_and_date_async(account_id, date_only)
        
        if not holdings:
            logger.info(f"No holdings found for account {account_id} on date {date_only}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No holdings found for account {account_id} on date {date_only}"
            )
        
        logger.info(f"Found {len(holdings)} holdings for account {account_id}")
        
        # Convert to PortfolioHoldingDto objects
        holding_dtos = [PortfolioHoldingDto(**h) for h in holdings]
        
        # Calculate totals
        total_current_value = sum(h.current_value for h in holding_dtos)
        total_bought_value = sum(h.bought_value for h in holding_dtos)
        total_gain_loss = total_current_value - total_bought_value
        total_gain_loss_percentage = (
            (total_gain_loss / total_bought_value * 100) 
            if total_bought_value > 0 
            else 0
        )
        
        return AccountHoldingsResponse(
            account_id=account_id,
            valuation_date=date_only,
            holdings=holding_dtos,
            total_holdings=len(holding_dtos),
            total_current_value=total_current_value,
            total_bought_value=total_bought_value,
            total_gain_loss=total_gain_loss,
            total_gain_loss_percentage=total_gain_loss_percentage
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_holdings_by_date: {e}", exc_info=True)
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
    service: HoldingService = Depends(get_holding_service)
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
    result = await service.add_holding_async(portfolio_id, request, account_id)
    
    # Build response
    response = AddHoldingApiResponse(
        success=result.success,
        message=result.message,
        errors=result.errors if result.errors else None,
        holding_id=result.created_holding.id if result.created_holding else None,
        instrument_created=result.instrument_created,
        current_price=result.current_price,
        current_value=result.current_value
    )
    
    # Add instrument info if available
    if result.instrument:
        response.instrument = InstrumentInfo(
            id=result.instrument.id,
            ticker=result.instrument.ticker,
            name=result.instrument.name,
            description=result.instrument.description,
            currency_code=result.instrument.currency_code or "USD",
            quote_unit=result.instrument.quote_unit,
            instrument_type_id=result.instrument.instrument_type_id
        )
    
    if not result.success:
        # Determine appropriate status code
        if "not found" in result.message.lower() or "not accessible" in result.message.lower():
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=response.model_dump(by_alias=True)
            )
        elif "already exists" in result.message.lower() or "duplicate" in result.message.lower():
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
    service: HoldingService = Depends(get_holding_service)
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
    result = await service.update_holding_units_async(holding_id, request.units, account_id)
    
    # Get ticker from updated holding
    ticker = None
    if result.updated_holding and hasattr(result.updated_holding, 'instrument'):
        ticker = result.updated_holding.instrument.ticker
    
    response = UpdateHoldingApiResponse(
        success=result.success,
        message=result.message,
        errors=result.errors if result.errors else None,
        holding_id=holding_id,
        previous_units=result.previous_units,
        new_units=result.new_units,
        previous_current_value=result.previous_current_value,
        new_current_value=result.new_current_value,
        ticker=ticker
    )
    
    if not result.success:
        if "not found" in result.message.lower() or "not accessible" in result.message.lower():
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
    service: HoldingService = Depends(get_holding_service)
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
    result = await service.delete_holding_async(holding_id, account_id)
    
    response = DeleteHoldingApiResponse(
        success=result.success,
        message=result.message,
        errors=result.errors if result.errors else None,
        deleted_holding_id=result.deleted_holding_id,
        deleted_ticker=result.deleted_ticker,
        portfolio_id=result.portfolio_id
    )
    
    if not result.success:
        if "not found" in result.message.lower() or "not accessible" in result.message.lower():
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

