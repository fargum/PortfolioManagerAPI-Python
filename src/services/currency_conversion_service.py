"""
Currency conversion service for handling multi-currency conversions.
"""
import logging
from datetime import date
from typing import Optional, Tuple
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.core.constants import CurrencyConstants
from src.db.models.exchange_rate import ExchangeRate

logger = logging.getLogger(__name__)


class CurrencyConversionService:
    """
    Service for handling currency conversions between GBP, USD, EUR.
    
    This implementation:
    - Looks up exchange rates from database
    - Supports inverse rate calculations (e.g., if USD/GBP not found, uses 1/GBP/USD)
    - Uses latest available rate on or before valuation date
    """
    
    def __init__(self, db: Optional[AsyncSession] = None):
        """
        Initialize the currency conversion service.
        
        Args:
            db: Optional database session for exchange rate lookups
        """
        self.db = db
        self.supported_currencies = [
            CurrencyConstants.GBP,
            CurrencyConstants.USD,
            CurrencyConstants.EUR,
            CurrencyConstants.GBX
        ]
    
    async def convert_currency_async(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        valuation_date: date
    ) -> Tuple[Decimal, Decimal, str]:
        """
        Convert amount from one currency to another.
        
        Args:
            amount: Amount to convert
            from_currency: Source currency code (GBP, USD, EUR, GBX)
            to_currency: Target currency code (GBP, USD, EUR)
            valuation_date: Date for exchange rate lookup
            
        Returns:
            Tuple of (converted_amount, exchange_rate, rate_source)
            
        Raises:
            ValueError: If currencies are not supported
        """
        from_currency = from_currency.upper() if from_currency else CurrencyConstants.DEFAULT_BASE_CURRENCY
        to_currency = to_currency.upper() if to_currency else CurrencyConstants.DEFAULT_BASE_CURRENCY
        
        # Same currency - no conversion needed
        if from_currency == to_currency:
            return (amount, Decimal("1.0"), "SAME_CURRENCY")
        
        # Get exchange rate from database
        if not self.db:
            logger.warning(
                f"No database session available for currency conversion from {from_currency} to {to_currency}. "
                f"Returning unconverted amount."
            )
            return (amount, Decimal("1.0"), "NO_CONVERSION_AVAILABLE")
        
        try:
            exchange_rate = await self._get_latest_rate_async(from_currency, to_currency, valuation_date)
            
            if exchange_rate:
                converted_amount = amount * exchange_rate.rate
                logger.info(
                    f"Converted {amount} {from_currency} to {converted_amount} {to_currency} "
                    f"using rate {exchange_rate.rate} from {exchange_rate.source}"
                )
                return (converted_amount, exchange_rate.rate, exchange_rate.source)
            
            # Try inverse rate (e.g., if we need USD/GBP but only have GBP/USD)
            inverse_rate = await self._get_latest_rate_async(to_currency, from_currency, valuation_date)
            
            if inverse_rate and inverse_rate.rate != 0:
                rate = Decimal("1") / inverse_rate.rate
                converted_amount = amount * rate
                logger.info(
                    f"Converted {amount} {from_currency} to {converted_amount} {to_currency} "
                    f"using inverse rate {rate} from {inverse_rate.source}"
                )
                return (converted_amount, rate, f"INVERSE_{inverse_rate.source}")
            
            # No exchange rate available
            logger.warning(
                f"No exchange rate available for {from_currency}/{to_currency} on or before {valuation_date}. "
                f"Returning unconverted amount."
            )
            return (amount, Decimal("1.0"), "NO_CONVERSION_AVAILABLE")
            
        except Exception as ex:
            logger.error(
                f"Database error during currency conversion from {from_currency} to {to_currency}: {ex}"
            )
            # Rollback the transaction if it's in a failed state
            try:
                await self.db.rollback()
                logger.info("Rolled back failed transaction")
            except Exception as rollback_ex:
                logger.warning(f"Failed to rollback transaction: {rollback_ex}")
            # Re-raise the exception instead of silently returning unconverted amount
            # This ensures errors are visible and don't get swallowed
            raise
    
    def is_conversion_supported(self, from_currency: str, to_currency: str) -> bool:
        """
        Check if conversion between two currencies is supported.
        
        Args:
            from_currency: Source currency code
            to_currency: Target currency code
            
        Returns:
            True if conversion is supported
        """
        from_curr = from_currency.upper() if from_currency else CurrencyConstants.DEFAULT_BASE_CURRENCY
        to_curr = to_currency.upper() if to_currency else CurrencyConstants.DEFAULT_BASE_CURRENCY
        
        # Same currency is always supported
        if from_curr == to_curr:
            return True
               
        # For MVP, other conversions are not fully supported
        return False
    
    async def _get_latest_rate_async(
        self,
        base_currency: str,
        target_currency: str,
        on_or_before_date: date
    ) -> Optional[ExchangeRate]:
        """
        Get the latest exchange rate for a currency pair on or before a specific date.
        
        Args:
            base_currency: Base currency (e.g., "USD")
            target_currency: Target currency (e.g., "GBP")
            on_or_before_date: Date to find rate for
            
        Returns:
            ExchangeRate if found, None otherwise
        """
        if not self.db:
            return None
        
        result = await self.db.execute(
            select(ExchangeRate)
            .where(
                ExchangeRate.base_currency == base_currency.upper(),
                ExchangeRate.target_currency == target_currency.upper(),
                ExchangeRate.rate_date <= on_or_before_date
            )
            .order_by(ExchangeRate.rate_date.desc())
            .limit(1)
        )
        
        return result.scalar_one_or_none()
