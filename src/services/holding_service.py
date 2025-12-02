"""Business logic service for Holdings."""
from typing import List, Optional
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.db.models.holding import Holding
from src.db.models.instrument import Instrument
from src.db.models.portfolio import Portfolio
from src.schemas.holding import AddHoldingApiRequest
from src.services.result_objects import (
    AddHoldingResult,
    UpdateHoldingResult,
    DeleteHoldingResult
)


class HoldingService:
    """Service layer for Holdings business logic."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
       
    async def get_holdings_by_account_and_date_async(
        self,
        account_id: int,
        valuation_date: date
    ) -> Optional[List[dict]]:
        """
        Get holdings for an account on a specific date.
        
        Args:
            account_id: Account ID from authenticated user
            valuation_date: Date to retrieve holdings for
            
        Returns:
            List of holdings with instrument/platform/portfolio details, or None if not found
        """
        # Get all portfolios for this account
        result = await self.db.execute(
            select(Portfolio.id).where(Portfolio.account_id == account_id)
        )
        portfolio_ids = [row[0] for row in result.all()]
        
        if not portfolio_ids:
            return None
        
        # Get all holdings for these portfolios on the specified date
        # Convert date to datetime for comparison (database stores datetime with timezone)
        from sqlalchemy import func, cast, Date
        
        holdings_result = await self.db.execute(
            select(
                Holding,
                Instrument.ticker,
                Instrument.name.label('instrument_name'),
                Instrument.description,
                Instrument.currency_code,
                Portfolio.name.label('portfolio_name'),
                Portfolio.id.label('portfolio_id_joined')
            )
            .join(Instrument, Holding.instrument_id == Instrument.id)
            .join(Portfolio, Holding.portfolio_id == Portfolio.id)
            .where(
                Holding.portfolio_id.in_(portfolio_ids),
                cast(Holding.valuation_date, Date) == valuation_date
            )
            .order_by(Portfolio.name, Instrument.ticker)
        )
        
        holdings_with_details = []
        for row in holdings_result:
            holding = row[0]
            symbol = row[1]
            instrument_name = row[2]
            description = row[3]
            currency_code = row[4]
            portfolio_name = row[5]
            portfolio_id_joined = row[6]
            
            holdings_with_details.append({
                'holding_id': holding.id,
                'portfolio_id': portfolio_id_joined,
                'portfolio_name': portfolio_name,
                'platform_id': holding.platform_id,
                'platform_name': '',  # Need to join platform table
                'ticker': symbol,
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
        
        return holdings_with_details if holdings_with_details else None
    
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
                    errors=["Portfolio not found or does not belong to this account"]
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
                    errors=["Duplicate holding for this instrument and date"]
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
                errors=[str(e)]
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
                    errors=["Holding not found or does not belong to this account"]
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
                    errors=["Holding not found or does not belong to this account"]
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
                errors=[str(e)]
            )
