"""
Pricing calculation service for handling quote unit conversions, scaling factors,
and currency conversions.
"""
import logging
from datetime import date
from decimal import Decimal
from typing import Optional

from src.core.constants import CurrencyConstants, ExchangeConstants
from src.services.currency_conversion_service import CurrencyConversionService

logger = logging.getLogger(__name__)


class PricingCalculationService:
    """
    Service for calculating pricing with proper currency conversion and unit handling.
    
    This service handles:
    - Quote unit conversion (GBX to GBP: divide by 100)
    - Scaling factors for special instruments (ISF)
    - Currency inference from ticker symbols
    - Currency conversion to GBP base currency
    """
    
    def __init__(self, currency_conversion_service: CurrencyConversionService):
        """
        Initialize the pricing calculation service.
        
        Args:
            currency_conversion_service: Service for currency conversions
        """
        self.currency_conversion_service = currency_conversion_service
    
    async def calculate_current_value_async(
        self,
        unit_amount: Decimal,
        price: Decimal,
        quote_unit: Optional[str],
        price_currency: Optional[str],
        valuation_date: date
    ) -> Decimal:
        """
        Calculate current value with quote unit scaling and currency conversion to GBP.
        
        Quote unit determines the scale (e.g., GBX means divide by 100).
        Price currency determines what currency it's in (USD, GBP, EUR).
        
        Args:
            unit_amount: Number of shares/units
            price: Price per unit in the quote unit
            quote_unit: Quote unit (GBX, GBP, USD, etc.) - the scale/denomination
            price_currency: Currency of the price (USD, GBP, EUR) - the actual currency
            valuation_date: Date for exchange rate lookup
            
        Returns:
            Current value in GBP
        """
        # Normalize inputs
        quote_unit = quote_unit.upper() if quote_unit else CurrencyConstants.DEFAULT_QUOTE_UNIT
        price_currency = price_currency.upper() if price_currency else CurrencyConstants.DEFAULT_BASE_CURRENCY
        
        # Step 1: Apply quote unit scaling (only GBX needs adjustment)
        scaled_price = price / Decimal("100") if quote_unit == CurrencyConstants.GBX else price
        
        # Step 2: Calculate value in original currency
        value_in_original_currency = unit_amount * scaled_price
        
        # Step 3: Determine actual currency (GBX is just pence, currency is GBP)
        actual_currency = CurrencyConstants.GBP if quote_unit == CurrencyConstants.GBX else price_currency
        
        # Step 4: Convert to GBP if needed
        if actual_currency == CurrencyConstants.GBP:
            return value_in_original_currency
        
        # Need currency conversion
        converted_amount, rate, source = await self.currency_conversion_service.convert_currency_async(
            value_in_original_currency,
            actual_currency,
            CurrencyConstants.GBP,
            valuation_date
        )
        
        logger.info(
            f"Converted {value_in_original_currency} {actual_currency} to {converted_amount} GBP "
            f"(rate: {rate}, source: {source})"
        )
        
        return converted_amount
    
    def apply_scaling_factor(self, price: Decimal, ticker: str) -> Decimal:
        """
        Apply scaling factor for proxy instruments that require price adjustments.
        """

        if ticker.upper() == ExchangeConstants.ISF_TICKER:
            scaled_price = price * Decimal(str(ExchangeConstants.ISF_SCALING_FACTOR))
            logger.info(
                f"Applied scaling factor {ExchangeConstants.ISF_SCALING_FACTOR} to {ticker}: "
                f"Original price={price}, Scaled price={scaled_price}"
            )
            return scaled_price
        
        # No scaling needed for this ticker
        return price
