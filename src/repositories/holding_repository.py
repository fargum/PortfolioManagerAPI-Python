"""Repository for Holdings data access."""
from typing import List, Optional
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.db.models.holding import Holding
from src.db.models.instrument import Instrument
from src.db.models.platform import Platform
from src.db.models.portfolio import Portfolio
from src.repositories.base import BaseRepository


class HoldingRepository(BaseRepository[Holding]):
    """Repository for Holdings with specialized queries including instrument joins."""
    
    def __init__(self, db: AsyncSession):
        super().__init__(Holding, db)
    
    async def get_by_portfolio_id(
        self,
        portfolio_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[dict]:
        """Get all holdings for a specific portfolio with instrument, platform, and portfolio details."""
        result = await self.db.execute(
            select(
                Holding,
                Instrument.symbol,
                Instrument.name.label('instrument_name'),
                Platform.name.label('platform_name'),
                Portfolio.name.label('portfolio_name')
            )
            .join(Instrument, Holding.instrument_id == Instrument.id)
            .join(Platform, Holding.platform_id == Platform.id)
            .join(Portfolio, Holding.portfolio_id == Portfolio.id)
            .where(Holding.portfolio_id == portfolio_id)
            .offset(skip)
            .limit(limit)
            .order_by(Instrument.symbol)
        )
        
        # Convert rows to dicts with holding and related data
        holdings_with_details = []
        for row in result:
            holding_dict = {
                **row[0].__dict__,
                'symbol': row[1],
                'name': row[2],
                'platform_name': row[3],
                'portfolio_name': row[4]
            }
            # Remove SQLAlchemy internal state
            holding_dict.pop('_sa_instance_state', None)
            holdings_with_details.append(holding_dict)
        
        return holdings_with_details
    
    async def get_by_portfolio_and_instrument(
        self,
        portfolio_id: int,
        instrument_id: int
    ) -> Optional[Holding]:
        """Get a specific holding by portfolio and instrument."""
        result = await self.db.execute(
            select(Holding)
            .where(
                Holding.portfolio_id == portfolio_id,
                Holding.instrument_id == instrument_id
            )
        )
        return result.scalar_one_or_none()
    
    async def get_by_symbol(self, symbol: str) -> List[dict]:
        """Get all holdings for a specific symbol across all portfolios."""
        result = await self.db.execute(
            select(
                Holding,
                Instrument.symbol,
                Instrument.name.label('instrument_name'),
                Platform.name.label('platform_name'),
                Portfolio.name.label('portfolio_name')
            )
            .join(Instrument, Holding.instrument_id == Instrument.id)
            .join(Platform, Holding.platform_id == Platform.id)
            .join(Portfolio, Holding.portfolio_id == Portfolio.id)
            .where(Instrument.symbol == symbol)
            .order_by(Holding.portfolio_id)
        )
        
        holdings_with_details = []
        for row in result:
            holding_dict = {
                **row[0].__dict__,
                'symbol': row[1],
                'name': row[2],
                'platform_name': row[3],
                'portfolio_name': row[4]
            }
            holding_dict.pop('_sa_instance_state', None)
            holdings_with_details.append(holding_dict)
        
        return holdings_with_details
    
    async def get_portfolio_summary(self, portfolio_id: int) -> dict:
        """
        Get aggregated summary for a portfolio.
        
        Returns total bought value, current value, and profit/loss.
        """
        result = await self.db.execute(
            select(
                func.count(Holding.id).label("total_holdings"),
                func.sum(Holding.bought_value).label("total_bought_value"),
                func.sum(Holding.current_value).label("total_current_value"),
            )
            .where(Holding.portfolio_id == portfolio_id)
        )
        
        row = result.one()
        
        total_bought_value = row.total_bought_value or Decimal("0")
        total_current_value = row.total_current_value or Decimal("0")
        total_profit_loss = total_current_value - total_bought_value
        
        # Calculate percentage
        total_profit_loss_percentage = Decimal("0")
        if total_bought_value > 0:
            total_profit_loss_percentage = (
                (total_profit_loss / total_bought_value) * 100
            )
        
        return {
            "total_holdings": row.total_holdings or 0,
            "total_bought_value": total_bought_value,
            "total_current_value": total_current_value,
            "total_profit_loss": total_profit_loss,
            "total_profit_loss_percentage": total_profit_loss_percentage,
        }
    
    async def count_by_portfolio(self, portfolio_id: int) -> int:
        """Count holdings in a portfolio."""
        result = await self.db.execute(
            select(func.count())
            .select_from(Holding)
            .where(Holding.portfolio_id == portfolio_id)
        )
        return result.scalar_one()
