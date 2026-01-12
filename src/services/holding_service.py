"""Business logic service for Holdings."""
from typing import Any, List, Optional, Sequence
from datetime import datetime, date
from decimal import Decimal
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.db.models.holding import Holding
from src.db.models.instrument import Instrument
from src.db.models.portfolio import Portfolio
from src.db.models.platform import Platform
from src.schemas.holding import AddHoldingApiRequest, PortfolioHoldingDto, AccountHoldingsResponse
from src.services.result_objects import (
    AddHoldingResult,
    UpdateHoldingResult,
    DeleteHoldingResult,
    ErrorCode
)
from src.services.eod_market_data_tool import EodMarketDataTool
from src.services.pricing_calculation_service import PricingCalculationService

logger = logging.getLogger(__name__)


class HoldingService:
    """Service layer for Holdings business logic."""
    
    def __init__(
        self, 
        db: AsyncSession, 
        eod_tool: Optional[EodMarketDataTool] = None,
        pricing_calculation_service: Optional[PricingCalculationService] = None
    ):
        self.db = db
        self.eod_tool = eod_tool
        self.pricing_calculation_service = pricing_calculation_service
       
    async def get_holdings_by_account_and_date_async(
        self,
        account_id: int,
        valuation_date: date
    ) -> Optional[AccountHoldingsResponse]:
        """
        Get holdings for an account on a specific date with aggregated totals.
        Supports both historical data retrieval and real-time pricing for current date.
        
        Args:
            account_id: Account ID from authenticated user
            valuation_date: Date to retrieve holdings for
            
        Returns:
            AccountHoldingsResponse with holdings list and aggregated totals, or None if not found
        """
        logger.info(f"Retrieving holdings for account {account_id} on date {valuation_date}")
        
        today = date.today()
        
        # Determine if we need real-time pricing
        is_today = valuation_date == today
        
        # Get all portfolios for this account
        result = await self.db.execute(
            select(Portfolio.id).where(Portfolio.account_id == account_id)
        )
        portfolio_ids = [row[0] for row in result.all()]
        
        if not portfolio_ids:
            return None
        
        # For today's date, get the latest available holdings
        # For historical dates, get holdings for the specific date
        from sqlalchemy import func, cast, Date
        
        if is_today:
            # Get the latest valuation date in the database
            latest_date_result = await self.db.execute(
                select(func.max(cast(Holding.valuation_date, Date)))
                .where(Holding.portfolio_id.in_(portfolio_ids))
            )
            latest_date = latest_date_result.scalar()
            
            if not latest_date:
                logger.warning(f"No historical holdings found for account {account_id}")
                return None
            
            query_date = latest_date
            logger.info(f"Using latest holdings date {latest_date} for real-time pricing")
        else:
            query_date = valuation_date
        
        # Query holdings for the determined date
        holdings_result = await self.db.execute(
            select(
                Holding,
                Instrument.ticker,
                Instrument.name.label('instrument_name'),
                Instrument.description,
                Instrument.currency_code,
                Instrument.quote_unit,
                Portfolio.name.label('portfolio_name'),
                Portfolio.id.label('portfolio_id_joined')
            )
            .join(Instrument, Holding.instrument_id == Instrument.id)
            .join(Portfolio, Holding.portfolio_id == Portfolio.id)
            .where(
                Holding.portfolio_id.in_(portfolio_ids),
                cast(Holding.valuation_date, Date) == query_date
            )
            .order_by(Portfolio.name, Instrument.ticker)
        )
        
        holdings_rows = holdings_result.all()
        
        if not holdings_rows:
            return None
        
        logger.info(f"Retrieved {len(holdings_rows)} holdings from database")
        
        # Apply real-time pricing if it's today and EOD tool is available
        if is_today and self.eod_tool:
            logger.info("Applying real-time pricing for today's date")
            holdings_with_details = await self._apply_real_time_pricing(holdings_rows, valuation_date)
        else:
            # Use historical data as-is
            holdings_with_details = self._build_holdings_response(holdings_rows, valuation_date)
        
        if not holdings_with_details:
            return None
        
        # Convert to DTOs and calculate aggregated totals
        return self._build_account_holdings_response(account_id, valuation_date, holdings_with_details)
    
    def _build_holdings_response(
        self, 
        holdings_rows: Sequence[Any], 
        valuation_date: date
    ) -> List[dict]:
        """Build holdings response from database rows without real-time pricing."""
        return [
            {
                'holding_id': (holding := row[0]).id,
                'portfolio_id': row[7],
                'portfolio_name': row[6],
                'platform_id': holding.platform_id,
                'platform_name': '',  # TODO: Join platform table
                'ticker': row[1],
                'instrument_name': row[2],
                'units': holding.unit_amount,
                'bought_value': holding.bought_value,
                'current_value': holding.current_value,
                'current_price': holding.current_value / holding.unit_amount if holding.unit_amount > 0 else None,
                'gain_loss': holding.current_value - holding.bought_value,
                'gain_loss_percentage': ((holding.current_value - holding.bought_value) / holding.bought_value * 100) if holding.bought_value > 0 else Decimal('0'),
                'currency_code': row[4] or 'USD',
                'valuation_date': valuation_date
            }
            for row in holdings_rows
        ]
    
    def _build_account_holdings_response(
        self,
        account_id: int,
        valuation_date: date,
        holdings_list: List[dict]
    ) -> AccountHoldingsResponse:
        """Build AccountHoldingsResponse with aggregated totals."""
        # Convert to DTOs
        holding_dtos = [PortfolioHoldingDto(**h) for h in holdings_list]
        
        # Calculate aggregated totals
        total_current_value = sum(h.current_value for h in holding_dtos)
        total_bought_value = sum(h.bought_value for h in holding_dtos)
        total_gain_loss = total_current_value - total_bought_value
        total_gain_loss_percentage = (
            (total_gain_loss / total_bought_value * 100) 
            if total_bought_value > 0 
            else Decimal('0')
        )
        
        return AccountHoldingsResponse(
            accountId=account_id,
            valuationDate=valuation_date,
            holdings=holding_dtos,
            totalHoldings=len(holding_dtos),
            totalCurrentValue=total_current_value,
            totalBoughtValue=total_bought_value,
            totalGainLoss=total_gain_loss,
            totalGainLossPercentage=total_gain_loss_percentage
        )
    
    async def _apply_real_time_pricing(
        self, 
        holdings_rows: Sequence[Any], 
        valuation_date: date
    ) -> List[dict]:
        """Apply real-time pricing to holdings using EOD market data with proper pricing calculations (no persistence)."""
        from src.core.constants import ExchangeConstants
        
        try:
            if not self.eod_tool:
                logger.warning("EOD market data tool not available for real-time pricing")
                return self._build_holdings_response(holdings_rows, valuation_date)
            
            if not self.pricing_calculation_service:
                logger.warning("Pricing calculation service not available, using direct price multiplication")
                # Fall back to simple calculation if service not available
            
            # Extract unique tickers, excluding CASH (which doesn't need pricing)
            tickers = list(set(
                row[1] for row in holdings_rows 
                if row[1] and row[1].upper() != ExchangeConstants.CASH_TICKER
            ))  # row[1] is ticker
            
            if not tickers:
                logger.warning("No tickers found for real-time pricing")
                return self._build_holdings_response(holdings_rows, valuation_date)
            
            logger.info(f"Fetching real-time prices for {len(tickers)} tickers")
            
            # Fetch real-time prices
            prices = await self.eod_tool.get_real_time_prices_async(tickers)
            
            logger.info(f"Fetched {len(prices)} real-time prices for {len(tickers)} tickers")
            
            # Build response with real-time pricing
            holdings_with_details = []
            
            for row in holdings_rows:
                holding = row[0]
                ticker = row[1]
                instrument_name = row[2]
                description = row[3]
                currency_code = row[4]
                quote_unit = row[5]  # Now we have quote_unit
                portfolio_name = row[6]
                portfolio_id_joined = row[7]
                
                # Check if this is CASH - no pricing needed, units = value
                if ticker and ticker.upper() == ExchangeConstants.CASH_TICKER:
                    logger.info(f"CASH instrument detected for holding {holding.id}, using units as current value")
                    holdings_with_details.append({
                        'holding_id': holding.id,
                        'portfolio_id': portfolio_id_joined,
                        'portfolio_name': portfolio_name,
                        'platform_id': holding.platform_id,
                        'platform_name': '',
                        'ticker': ticker,
                        'instrument_name': instrument_name,
                        'units': holding.unit_amount,
                        'bought_value': holding.bought_value,
                        'current_value': holding.unit_amount,  # For CASH, units = value
                        'current_price': Decimal('1.0'),  # CASH always has price of 1.0
                        'gain_loss': holding.unit_amount - holding.bought_value,
                        'gain_loss_percentage': ((holding.unit_amount - holding.bought_value) / holding.bought_value * 100) if holding.bought_value > 0 else Decimal('0'),
                        'currency_code': currency_code or 'GBP',
                        'valuation_date': valuation_date
                    })
                    continue
                
                # Check if we have real-time price for this ticker
                if ticker in prices:
                    real_time_price = prices[ticker]
                    
                    # Apply pricing calculation service if available
                    if self.pricing_calculation_service:
                        # Step 1: Apply scaling factor (e.g., ISF ticker)
                        scaled_price = self.pricing_calculation_service.apply_scaling_factor(
                            Decimal(str(real_time_price)), 
                            ticker
                        )
                        
                        # Step 2: Calculate current value with quote unit and currency conversion
                        # Use currency_code from database - it must be correct
                        # If missing or wrong, that's a data quality issue that should fail
                        logger.info(
                            f"Calling pricing calc for {ticker}: units={holding.unit_amount}, "
                            f"scaled_price={scaled_price}, quote_unit={quote_unit}, "
                            f"currency_code={currency_code}"
                        )
                        new_current_value = await self.pricing_calculation_service.calculate_current_value_async(
                            holding.unit_amount,
                            scaled_price,
                            quote_unit,
                            currency_code,  # Use database currency_code directly
                            valuation_date
                        )
                        
                        logger.info(
                            f"Calculated holding {holding.id} for {ticker}: "
                            f"Units={holding.unit_amount}, RawPrice={real_time_price}, "
                            f"ScaledPrice={scaled_price}, QuoteUnit={quote_unit}, "
                            f"NewValue={new_current_value}"
                        )
                    else:
                        # Fallback: Simple multiplication without conversions
                        new_current_value = holding.unit_amount * Decimal(str(real_time_price))
                        scaled_price = Decimal(str(real_time_price))
                    
                    # Calculate daily P&L (change from database value to real-time value)
                    daily_change = new_current_value - holding.current_value
                    daily_change_percentage = (daily_change / holding.current_value * 100) if holding.current_value > 0 else Decimal('0')
                    
                    logger.info(
                        f"Updated holding {holding.id} for {ticker}: "
                        f"Original value {holding.current_value} -> New value {new_current_value}, "
                        f"Daily P/L: {daily_change} ({daily_change_percentage:.2f}%)"
                    )
                    
                    holdings_with_details.append({
                        'holding_id': holding.id,
                        'portfolio_id': portfolio_id_joined,
                        'portfolio_name': portfolio_name,
                        'platform_id': holding.platform_id,
                        'platform_name': '',  # TODO: Join platform table
                        'ticker': ticker,
                        'instrument_name': instrument_name,
                        'units': holding.unit_amount,
                        'bought_value': holding.bought_value,
                        'current_value': new_current_value,  # Real-time value converted to GBP
                        'current_price': scaled_price,  # Scaled real-time price
                        'gain_loss': new_current_value - holding.bought_value,  # Total gain/loss
                        'gain_loss_percentage': ((new_current_value - holding.bought_value) / holding.bought_value * 100) if holding.bought_value > 0 else Decimal('0'),
                        'currency_code': currency_code or 'USD',
                        'valuation_date': valuation_date
                    })
                else:
                    # No real-time price available, use database values
                    logger.warning(f"No real-time price available for {ticker}, using database value")
                    holdings_with_details.append({
                        'holding_id': holding.id,
                        'portfolio_id': portfolio_id_joined,
                        'portfolio_name': portfolio_name,
                        'platform_id': holding.platform_id,
                        'platform_name': '',  # TODO: Join platform table
                        'ticker': ticker,
                        'instrument_name': instrument_name,
                        'units': holding.unit_amount,
                        'bought_value': holding.bought_value,
                        'current_value': holding.current_value,
                        'current_price': holding.current_value / holding.unit_amount if holding.unit_amount > 0 else None,
                        'gain_loss': holding.current_value - holding.bought_value,
                        'gain_loss_percentage': ((holding.current_value - holding.bought_value) / holding.bought_value * 100) if holding.bought_value > 0 else Decimal('0'),
                        'currency_code': currency_code or 'USD',
                        'valuation_date': valuation_date
                    })
            
            logger.info(f"Successfully applied real-time pricing to {len(holdings_with_details)} holdings")
            return holdings_with_details
            
        except Exception as ex:
            logger.error(f"Error applying real-time pricing: {ex}", exc_info=True)
            # Fall back to database values
            return self._build_holdings_response(holdings_rows, valuation_date)
    
    async def add_holding_async(
        self,
        portfolio_id: int,
        request: AddHoldingApiRequest,
        account_id: int
    ) -> AddHoldingResult:
        """
        Add a new holding to a portfolio.
        
        Creates instrument if it doesn't exist, validates ownership, prevents duplicates.
        
        Args:
            portfolio_id: Portfolio ID to add holding to
            request: AddHoldingApiRequest with holding details
            account_id: Account ID from authenticated user
            
        Returns:
            AddHoldingResult with success status and created holding details
        """
        try:
            # Validate portfolio belongs to user
            portfolio_result = await self.db.execute(
                select(Portfolio).where(
                    Portfolio.id == portfolio_id,
                    Portfolio.account_id == account_id
                )
            )
            portfolio = portfolio_result.scalar_one_or_none()
            
            if not portfolio:
                return AddHoldingResult(
                    success=False,
                    message=f"Portfolio {portfolio_id} not found or not accessible",
                    errors=["Portfolio not found or does not belong to this account"],
                    error_code=ErrorCode.NOT_FOUND
                )
            
            # Find or create instrument
            instrument_result = await self.db.execute(
                select(Instrument).where(Instrument.ticker == request.ticker)
            )
            instrument = instrument_result.scalar_one_or_none()
            instrument_created = False
            
            if not instrument:
                # Create new instrument
                instrument = Instrument(
                    ticker=request.ticker,
                    name=request.instrument_name or request.ticker,
                    description=request.description,
                    instrument_type_id=request.instrument_type_id,
                    currency_code=request.currency_code,
                    quote_unit=request.quote_unit
                )
                self.db.add(instrument)
                await self.db.flush()  # Get the ID
                instrument_created = True
            
            # Get latest valuation date
            latest_date = date.today()
            
            # Check for duplicate holding
            duplicate_check = await self.db.execute(
                select(Holding).where(
                    Holding.portfolio_id == portfolio_id,
                    Holding.instrument_id == instrument.id,
                    Holding.platform_id == request.platform_id,
                    Holding.valuation_date == latest_date
                )
            )
            existing_holding = duplicate_check.scalar_one_or_none()
            
            if existing_holding:
                return AddHoldingResult(
                    success=False,
                    message=f"Holding for {request.ticker} on platform {request.platform_id} already exists for this date",
                    errors=["Duplicate holding for this instrument and date"],
                    error_code=ErrorCode.DUPLICATE
                )
            
            # Calculate current value (would use real-time pricing in production)
            current_price = request.bought_value / request.units if request.units > 0 else Decimal('0')
            current_value = request.units * current_price
            
            # Create new holding
            new_holding = Holding(
                valuation_date=latest_date,
                instrument_id=instrument.id,
                platform_id=request.platform_id,
                portfolio_id=portfolio_id,
                unit_amount=request.units,
                bought_value=request.bought_value,
                current_value=current_value,
                daily_profit_loss=current_value - request.bought_value,
                daily_profit_loss_percentage=((current_value - request.bought_value) / request.bought_value * 100) if request.bought_value > 0 else Decimal('0')
            )
            
            self.db.add(new_holding)
            await self.db.commit()
            await self.db.refresh(new_holding)
            await self.db.refresh(instrument)
            
            return AddHoldingResult(
                success=True,
                message=f"Successfully added holding for {request.ticker}",
                created_holding=new_holding,
                instrument=instrument,
                instrument_created=instrument_created,
                current_price=current_price,
                current_value=current_value
            )
            
        except Exception as e:
            await self.db.rollback()
            return AddHoldingResult(
                success=False,
                message="An error occurred while adding the holding",
                errors=[str(e)],
                error_code=ErrorCode.INTERNAL_ERROR
            )
    
    async def update_holding_units_async(
        self,
        holding_id: int,
        new_units: Decimal,
        account_id: int
    ) -> UpdateHoldingResult:
        """
        Update units for a holding.
        
        Args:
            holding_id: Holding ID to update
            new_units: New unit amount
            account_id: Account ID from authenticated user
            
        Returns:
            UpdateHoldingResult with success status and before/after values
        """
        try:
            # Get holding with portfolio check
            holding_result = await self.db.execute(
                select(Holding, Portfolio, Instrument)
                .join(Portfolio, Holding.portfolio_id == Portfolio.id)
                .join(Instrument, Holding.instrument_id == Instrument.id)
                .where(
                    Holding.id == holding_id,
                    Portfolio.account_id == account_id
                )
            )
            row = holding_result.first()
            
            if not row:
                return UpdateHoldingResult(
                    success=False,
                    message=f"Holding {holding_id} not found or not accessible",
                    errors=["Holding not found or does not belong to this account"],
                    error_code=ErrorCode.NOT_FOUND
                )
            
            holding, portfolio, instrument = row
            
            # Store previous values
            previous_units = holding.unit_amount
            previous_current_value = holding.current_value
            
            # Calculate new current value (would use real-time pricing)
            current_price = holding.current_value / holding.unit_amount if holding.unit_amount > 0 else Decimal('0')
            new_current_value = new_units * current_price
            
            # Update holding
            holding.unit_amount = new_units
            holding.current_value = new_current_value
            holding.daily_profit_loss = new_current_value - holding.bought_value
            holding.daily_profit_loss_percentage = ((new_current_value - holding.bought_value) / holding.bought_value * 100) if holding.bought_value > 0 else Decimal('0')
            holding.updated_at = datetime.utcnow()
            
            await self.db.commit()
            await self.db.refresh(holding)
            
            return UpdateHoldingResult(
                success=True,
                message=f"Successfully updated units for {instrument.ticker}",
                updated_holding=holding,
                previous_units=previous_units,
                new_units=new_units,
                previous_current_value=previous_current_value,
                new_current_value=new_current_value
            )
            
        except Exception as e:
            await self.db.rollback()
            return UpdateHoldingResult(
                success=False,
                message="An error occurred while updating the holding",
                errors=[str(e)],
                error_code=ErrorCode.INTERNAL_ERROR,
                previous_units=Decimal('0'),
                new_units=Decimal('0'),
                previous_current_value=Decimal('0'),
                new_current_value=Decimal('0')
            )
    
    async def delete_holding_async(
        self,
        holding_id: int,
        account_id: int
    ) -> DeleteHoldingResult:
        """
        Delete a holding.
        
        Args:
            holding_id: Holding ID to delete
            account_id: Account ID from authenticated user
            
        Returns:
            DeleteHoldingResult with success status and deleted holding details
        """
        try:
            # Get holding with portfolio check
            holding_result = await self.db.execute(
                select(Holding, Portfolio, Instrument)
                .join(Portfolio, Holding.portfolio_id == Portfolio.id)
                .join(Instrument, Holding.instrument_id == Instrument.id)
                .where(
                    Holding.id == holding_id,
                    Portfolio.account_id == account_id
                )
            )
            row = holding_result.first()
            
            if not row:
                return DeleteHoldingResult(
                    success=False,
                    message=f"Holding {holding_id} not found or not accessible",
                    errors=["Holding not found or does not belong to this account"],
                    error_code=ErrorCode.NOT_FOUND
                )
            
            holding, portfolio, instrument = row
            
            # Store details before deletion
            ticker = instrument.ticker
            portfolio_id = holding.portfolio_id
            
            # Delete holding
            await self.db.delete(holding)
            await self.db.commit()
            
            return DeleteHoldingResult(
                success=True,
                message=f"Successfully deleted holding for {ticker}",
                deleted_holding_id=holding_id,
                deleted_ticker=ticker,
                portfolio_id=portfolio_id
            )
            
        except Exception as e:
            await self.db.rollback()
            return DeleteHoldingResult(
                success=False,
                message="An error occurred while deleting the holding",
                errors=[str(e)],
                error_code=ErrorCode.INTERNAL_ERROR
            )
