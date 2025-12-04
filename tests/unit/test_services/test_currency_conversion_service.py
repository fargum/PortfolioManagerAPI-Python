"""
Unit tests for CurrencyConversionService.

Tests cover:
- Same currency conversions (no conversion needed)
- Direct exchange rate lookups
- Inverse exchange rate calculations
- Missing database session handling
- Missing exchange rate handling
- Edge cases (zero rates, missing data)
"""
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.currency_conversion_service import CurrencyConversionService
from src.core.constants import CurrencyConstants


# ==================== Local Test Fixtures ====================
# Note: mock_currency_service is available from conftest.py but we need
# a real service instance with mock database for testing the actual logic.

@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def currency_service(mock_db_session):
    """Create a CurrencyConversionService with mock database."""
    return CurrencyConversionService(db=mock_db_session)


@pytest.fixture
def currency_service_no_db():
    """Create a CurrencyConversionService without database session."""
    return CurrencyConversionService(db=None)


class TestSameCurrencyConversion:
    """Test conversions where source and target currencies are the same."""
    
    @pytest.mark.asyncio
    async def test_same_currency_no_conversion(self, currency_service):
        """Test that converting same currency returns original amount with rate 1.0."""
        amount = Decimal("1000.50")
        valuation_date = date(2024, 1, 15)
        
        converted, rate, source = await currency_service.convert_currency_async(
            amount, "GBP", "GBP", valuation_date
        )
        
        assert converted == amount
        assert rate == Decimal("1.0")
        assert source == "SAME_CURRENCY"
    
    @pytest.mark.asyncio
    async def test_same_currency_case_insensitive(self, currency_service):
        """Test that currency comparison is case-insensitive."""
        amount = Decimal("500.00")
        valuation_date = date(2024, 1, 15)
        
        converted, rate, source = await currency_service.convert_currency_async(
            amount, "usd", "USD", valuation_date
        )
        
        assert converted == amount
        assert rate == Decimal("1.0")
        assert source == "SAME_CURRENCY"


class TestDirectExchangeRateLookup:
    """Test conversions using direct exchange rate lookups."""
    
    @pytest.mark.asyncio
    async def test_usd_to_gbp_conversion(self, currency_service, mock_db_session):
        """Test converting USD to GBP with direct rate."""
        amount = Decimal("1000.00")
        valuation_date = date(2024, 1, 15)
        
        # Mock exchange rate: 1 USD = 0.79 GBP
        mock_rate = MagicMock()
        mock_rate.base_currency = "USD"
        mock_rate.target_currency = "GBP"
        mock_rate.rate = Decimal("0.79")
        mock_rate.rate_date = date(2024, 1, 15)
        mock_rate.source = "ECB"
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_rate
        mock_db_session.execute.return_value = mock_result
        
        converted, rate, source = await currency_service.convert_currency_async(
            amount, "USD", "GBP", valuation_date
        )
        
        assert converted == Decimal("790.00")
        assert rate == Decimal("0.79")
        assert source == "ECB"
    
    @pytest.mark.asyncio
    async def test_eur_to_gbp_conversion(self, currency_service, mock_db_session):
        """Test converting EUR to GBP with direct rate."""
        amount = Decimal("500.00")
        valuation_date = date(2024, 2, 20)
        
        # Mock exchange rate: 1 EUR = 0.86 GBP
        mock_rate = MagicMock()
        mock_rate.base_currency = "EUR"
        mock_rate.target_currency = "GBP"
        mock_rate.rate = Decimal("0.86")
        mock_rate.rate_date = date(2024, 2, 20)
        mock_rate.source = "BOE"
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_rate
        mock_db_session.execute.return_value = mock_result
        
        converted, rate, source = await currency_service.convert_currency_async(
            amount, "EUR", "GBP", valuation_date
        )
        
        assert converted == Decimal("430.00")
        assert rate == Decimal("0.86")
        assert source == "BOE"
    
    @pytest.mark.asyncio
    async def test_uses_latest_rate_on_or_before_date(self, currency_service, mock_db_session):
        """Test that service uses the latest available rate on or before valuation date."""
        amount = Decimal("100.00")
        valuation_date = date(2024, 1, 20)
        
        # Mock rate from Jan 18 (should be used even though valuation is Jan 20)
        mock_rate = MagicMock()
        mock_rate.base_currency = "USD"
        mock_rate.target_currency = "GBP"
        mock_rate.rate = Decimal("0.80")
        mock_rate.rate_date = date(2024, 1, 18)
        mock_rate.source = "ECB"
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_rate
        mock_db_session.execute.return_value = mock_result
        
        converted, rate, source = await currency_service.convert_currency_async(
            amount, "USD", "GBP", valuation_date
        )
        
        assert converted == Decimal("80.00")
        assert rate == Decimal("0.80")


class TestInverseExchangeRate:
    """Test conversions using inverse exchange rates."""
    
    @pytest.mark.asyncio
    async def test_inverse_rate_calculation(self, currency_service, mock_db_session):
        """Test that inverse rates are calculated when direct rate not available."""
        amount = Decimal("1000.00")
        valuation_date = date(2024, 1, 15)
        
        # First call returns None (no direct USD->GBP rate)
        # Second call returns GBP->USD rate which can be inverted
        mock_inverse_rate = MagicMock()
        mock_inverse_rate.base_currency = "GBP"
        mock_inverse_rate.target_currency = "USD"
        mock_inverse_rate.rate = Decimal("1.27")  # 1 GBP = 1.27 USD
        mock_inverse_rate.rate_date = date(2024, 1, 15)
        mock_inverse_rate.source = "ECB"
        
        mock_result_none = MagicMock()
        mock_result_none.scalar_one_or_none.return_value = None
        
        mock_result_inverse = MagicMock()
        mock_result_inverse.scalar_one_or_none.return_value = mock_inverse_rate
        
        mock_db_session.execute.side_effect = [mock_result_none, mock_result_inverse]
        
        converted, rate, source = await currency_service.convert_currency_async(
            amount, "USD", "GBP", valuation_date
        )
        
        # Rate should be 1/1.27 ≈ 0.7874
        expected_rate = Decimal("1") / Decimal("1.27")
        expected_converted = amount * expected_rate
        
        assert converted == expected_converted
        assert rate == expected_rate
        assert source == "INVERSE_ECB"
    
    @pytest.mark.asyncio
    async def test_inverse_rate_precision(self, currency_service, mock_db_session):
        """Test that inverse rate calculations maintain precision."""
        amount = Decimal("500.00")
        valuation_date = date(2024, 1, 15)
        
        # Mock inverse rate with specific precision
        mock_inverse_rate = MagicMock()
        mock_inverse_rate.base_currency = "GBP"
        mock_inverse_rate.target_currency = "EUR"
        mock_inverse_rate.rate = Decimal("1.16")
        mock_inverse_rate.rate_date = date(2024, 1, 15)
        mock_inverse_rate.source = "ECB"
        
        mock_result_none = MagicMock()
        mock_result_none.scalar_one_or_none.return_value = None
        
        mock_result_inverse = MagicMock()
        mock_result_inverse.scalar_one_or_none.return_value = mock_inverse_rate
        
        mock_db_session.execute.side_effect = [mock_result_none, mock_result_inverse]
        
        converted, rate, source = await currency_service.convert_currency_async(
            amount, "EUR", "GBP", valuation_date
        )
        
        # Should use precise decimal division
        assert isinstance(rate, Decimal)
        assert isinstance(converted, Decimal)


class TestNoDatabaseSession:
    """Test behavior when no database session is available."""
    
    @pytest.mark.asyncio
    async def test_no_db_returns_unconverted(self, currency_service_no_db):
        """Test that missing DB session returns unconverted amount."""
        amount = Decimal("1000.00")
        valuation_date = date(2024, 1, 15)
        
        converted, rate, source = await currency_service_no_db.convert_currency_async(
            amount, "USD", "GBP", valuation_date
        )
        
        assert converted == amount
        assert rate == Decimal("1.0")
        assert source == "NO_CONVERSION_AVAILABLE"
    
    @pytest.mark.asyncio
    async def test_no_db_logs_warning(self, currency_service_no_db, caplog):
        """Test that warning is logged when DB session is missing."""
        amount = Decimal("1000.00")
        valuation_date = date(2024, 1, 15)
        
        await currency_service_no_db.convert_currency_async(
            amount, "USD", "GBP", valuation_date
        )
        
        assert "No database session available" in caplog.text


class TestMissingExchangeRate:
    """Test behavior when exchange rates are not available."""
    
    @pytest.mark.asyncio
    async def test_no_rate_available(self, currency_service, mock_db_session):
        """Test handling when no exchange rate exists."""
        amount = Decimal("1000.00")
        valuation_date = date(2024, 1, 15)
        
        # Both direct and inverse lookups return None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        converted, rate, source = await currency_service.convert_currency_async(
            amount, "USD", "GBP", valuation_date
        )
        
        assert converted == amount
        assert rate == Decimal("1.0")
        assert source == "NO_CONVERSION_AVAILABLE"
    
    @pytest.mark.asyncio
    async def test_no_rate_logs_warning(self, currency_service, mock_db_session, caplog):
        """Test that warning is logged when no rate is available."""
        amount = Decimal("1000.00")
        valuation_date = date(2024, 1, 15)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        await currency_service.convert_currency_async(
            amount, "USD", "GBP", valuation_date
        )
        
        assert "No exchange rate available" in caplog.text


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.mark.asyncio
    async def test_zero_inverse_rate_handling(self, currency_service, mock_db_session):
        """Test that zero inverse rates don't cause division by zero."""
        amount = Decimal("1000.00")
        valuation_date = date(2024, 1, 15)
        
        # Mock inverse rate with zero (invalid but should be handled)
        mock_inverse_rate = MagicMock()
        mock_inverse_rate.base_currency = "GBP"
        mock_inverse_rate.target_currency = "USD"
        mock_inverse_rate.rate = Decimal("0")
        mock_inverse_rate.rate_date = date(2024, 1, 15)
        mock_inverse_rate.source = "ECB"
        
        mock_result_none = MagicMock()
        mock_result_none.scalar_one_or_none.return_value = None
        
        mock_result_zero = MagicMock()
        mock_result_zero.scalar_one_or_none.return_value = mock_inverse_rate
        
        mock_db_session.execute.side_effect = [mock_result_none, mock_result_zero]
        
        converted, rate, source = await currency_service.convert_currency_async(
            amount, "USD", "GBP", valuation_date
        )
        
        # Should fall back to no conversion available
        assert converted == amount
        assert rate == Decimal("1.0")
        assert source == "NO_CONVERSION_AVAILABLE"
    
    @pytest.mark.asyncio
    async def test_database_error_rollback(self, currency_service, mock_db_session):
        """Test that database errors trigger rollback and re-raise exception."""
        amount = Decimal("1000.00")
        valuation_date = date(2024, 1, 15)
        
        # Mock database error
        mock_db_session.execute.side_effect = Exception("Database connection failed")
        
        with pytest.raises(Exception, match="Database connection failed"):
            await currency_service.convert_currency_async(
                amount, "USD", "GBP", valuation_date
            )
        
        # Verify rollback was called
        mock_db_session.rollback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_none_currency_defaults_to_gbp(self, currency_service):
        """Test that None currencies default to GBP (default base currency)."""
        amount = Decimal("1000.00")
        valuation_date = date(2024, 1, 15)
        
        converted, rate, source = await currency_service.convert_currency_async(
            amount, None, None, valuation_date
        )
        
        # Both None should default to GBP, so it's same currency
        assert converted == amount
        assert rate == Decimal("1.0")
        assert source == "SAME_CURRENCY"
    
    @pytest.mark.asyncio
    async def test_case_normalization(self, currency_service, mock_db_session):
        """Test that currency codes are normalized to uppercase."""
        amount = Decimal("100.00")
        valuation_date = date(2024, 1, 15)
        
        mock_rate = MagicMock()
        mock_rate.base_currency = "USD"
        mock_rate.target_currency = "GBP"
        mock_rate.rate = Decimal("0.79")
        mock_rate.rate_date = date(2024, 1, 15)
        mock_rate.source = "ECB"
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_rate
        mock_db_session.execute.return_value = mock_result
        
        # Pass lowercase currency codes
        converted, rate, source = await currency_service.convert_currency_async(
            amount, "usd", "gbp", valuation_date
        )
        
        assert converted == Decimal("79.00")
        assert rate == Decimal("0.79")


class TestConversionSupport:
    """Test is_conversion_supported method."""
    
    def test_same_currency_supported(self, currency_service):
        """Test that same currency conversion is always supported."""
        assert currency_service.is_conversion_supported("GBP", "GBP") is True
        assert currency_service.is_conversion_supported("USD", "USD") is True
    
    def test_different_currencies_not_supported_in_mvp(self, currency_service):
        """Test that cross-currency conversion is not supported in MVP."""
        assert currency_service.is_conversion_supported("USD", "GBP") is False
        assert currency_service.is_conversion_supported("EUR", "GBP") is False
    
    def test_case_insensitive_support_check(self, currency_service):
        """Test that support check is case-insensitive."""
        assert currency_service.is_conversion_supported("gbp", "GBP") is True
        assert currency_service.is_conversion_supported("Usd", "usd") is True
    
    def test_none_currency_support(self, currency_service):
        """Test that None currencies are treated as default (GBP) and supported."""
        assert currency_service.is_conversion_supported(None, None) is True


class TestDecimalPrecision:
    """Test that decimal precision is maintained throughout conversions."""
    
    @pytest.mark.asyncio
    async def test_high_precision_rate(self, currency_service, mock_db_session):
        """Test conversion with high precision exchange rate."""
        amount = Decimal("1234.56")
        valuation_date = date(2024, 1, 15)
        
        # High precision rate
        mock_rate = MagicMock()
        mock_rate.base_currency = "USD"
        mock_rate.target_currency = "GBP"
        mock_rate.rate = Decimal("0.7894736842")
        mock_rate.rate_date = date(2024, 1, 15)
        mock_rate.source = "ECB"
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_rate
        mock_db_session.execute.return_value = mock_result
        
        converted, rate, source = await currency_service.convert_currency_async(
            amount, "USD", "GBP", valuation_date
        )
        
        # Verify precision maintained
        assert isinstance(converted, Decimal)
        assert isinstance(rate, Decimal)
        expected = amount * mock_rate.rate
        assert converted == expected
    
    @pytest.mark.asyncio
    async def test_small_amount_precision(self, currency_service, mock_db_session):
        """Test that small amounts maintain precision."""
        amount = Decimal("0.01")
        valuation_date = date(2024, 1, 15)
        
        mock_rate = MagicMock()
        mock_rate.base_currency = "USD"
        mock_rate.target_currency = "GBP"
        mock_rate.rate = Decimal("0.79")
        mock_rate.rate_date = date(2024, 1, 15)
        mock_rate.source = "ECB"
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_rate
        mock_db_session.execute.return_value = mock_result
        
        converted, rate, source = await currency_service.convert_currency_async(
            amount, "USD", "GBP", valuation_date
        )
        
        assert converted == Decimal("0.0079")
