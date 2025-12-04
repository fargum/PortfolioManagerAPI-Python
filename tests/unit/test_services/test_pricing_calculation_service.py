"""
Unit tests for PricingCalculationService.

Tests cover:
- Quote unit conversions (GBX to GBP)
- Scaling factors (ISF proxy instrument)
- Currency conversions (USD, EUR to GBP)
- Edge cases and error handling
"""
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

from src.services.pricing_calculation_service import PricingCalculationService
from src.services.currency_conversion_service import CurrencyConversionService
from src.core.constants import CurrencyConstants, ExchangeConstants


@pytest.fixture
def mock_currency_service():
    """Mock CurrencyConversionService for testing."""
    mock = Mock(spec=CurrencyConversionService)
    # Default: 1 USD = 0.8 GBP
    mock.convert_currency_async = AsyncMock(
        return_value=(Decimal("800.00"), Decimal("0.8"), "test")
    )
    return mock


@pytest.fixture
def pricing_service(mock_currency_service):
    """Create PricingCalculationService instance with mocked currency service."""
    return PricingCalculationService(mock_currency_service)


class TestQuoteUnitConversion:
    """Test quote unit conversions (primarily GBX to GBP)."""
    
    @pytest.mark.unit
    async def test_gbx_to_gbp_conversion(self, pricing_service, mock_currency_service):
        """Test that GBX quote unit is divided by 100 and no currency conversion occurs."""
        # Arrange
        unit_amount = Decimal("10")
        price = Decimal("15050")  # 150.50 GBP in pence
        quote_unit = "GBX"
        price_currency = "GBP"
        valuation_date = date(2025, 12, 4)
        
        # Act
        result = await pricing_service.calculate_current_value_async(
            unit_amount, price, quote_unit, price_currency, valuation_date
        )
        
        # Assert
        expected = Decimal("1505.00")  # 10 * (15050/100)
        assert result == expected
        # Should NOT call currency conversion for GBX -> GBP
        mock_currency_service.convert_currency_async.assert_not_called()
    
    @pytest.mark.unit
    async def test_gbp_no_conversion_needed(self, pricing_service, mock_currency_service):
        """Test that GBP prices don't require conversion."""
        # Arrange
        unit_amount = Decimal("10")
        price = Decimal("150.50")
        quote_unit = "GBP"
        price_currency = "GBP"
        valuation_date = date(2025, 12, 4)
        
        # Act
        result = await pricing_service.calculate_current_value_async(
            unit_amount, price, quote_unit, price_currency, valuation_date
        )
        
        # Assert
        expected = Decimal("1505.00")  # 10 * 150.50
        assert result == expected
        mock_currency_service.convert_currency_async.assert_not_called()
    
    @pytest.mark.unit
    async def test_case_insensitive_quote_unit(self, pricing_service, mock_currency_service):
        """Test that quote units are case-insensitive."""
        # Arrange
        unit_amount = Decimal("10")
        price = Decimal("15050")
        quote_unit = "gbx"  # lowercase
        price_currency = "GBP"
        valuation_date = date(2025, 12, 4)
        
        # Act
        result = await pricing_service.calculate_current_value_async(
            unit_amount, price, quote_unit, price_currency, valuation_date
        )
        
        # Assert
        expected = Decimal("1505.00")
        assert result == expected


class TestCurrencyConversion:
    """Test currency conversions to GBP."""
    
    @pytest.mark.unit
    async def test_usd_to_gbp_conversion(self, pricing_service, mock_currency_service):
        """Test USD to GBP currency conversion."""
        # Arrange
        unit_amount = Decimal("10")
        price = Decimal("150.50")  # USD
        quote_unit = "USD"
        price_currency = "USD"
        valuation_date = date(2025, 12, 4)
        
        # Mock returns: (converted_amount, rate, source)
        mock_currency_service.convert_currency_async.return_value = (
            Decimal("1204.00"),  # 1505 * 0.8
            Decimal("0.8"),
            "database"
        )
        
        # Act
        result = await pricing_service.calculate_current_value_async(
            unit_amount, price, quote_unit, price_currency, valuation_date
        )
        
        # Assert
        assert result == Decimal("1204.00")
        mock_currency_service.convert_currency_async.assert_called_once_with(
            Decimal("1505.00"),  # 10 * 150.50
            "USD",
            "GBP",
            valuation_date
        )
    
    @pytest.mark.unit
    async def test_eur_to_gbp_conversion(self, pricing_service, mock_currency_service):
        """Test EUR to GBP currency conversion."""
        # Arrange
        unit_amount = Decimal("5")
        price = Decimal("200.00")  # EUR
        quote_unit = "EUR"
        price_currency = "EUR"
        valuation_date = date(2025, 12, 4)
        
        # Mock returns 1 EUR = 0.85 GBP
        mock_currency_service.convert_currency_async.return_value = (
            Decimal("850.00"),  # 1000 * 0.85
            Decimal("0.85"),
            "exchange_rate_api"
        )
        
        # Act
        result = await pricing_service.calculate_current_value_async(
            unit_amount, price, quote_unit, price_currency, valuation_date
        )
        
        # Assert
        assert result == Decimal("850.00")
        mock_currency_service.convert_currency_async.assert_called_once_with(
            Decimal("1000.00"),  # 5 * 200
            "EUR",
            "GBP",
            valuation_date
        )
    
    @pytest.mark.unit
    async def test_default_currency_when_none(self, pricing_service, mock_currency_service):
        """Test that None price_currency defaults to GBP."""
        # Arrange
        unit_amount = Decimal("10")
        price = Decimal("100.00")
        quote_unit = "GBP"
        price_currency = None  # Should default to GBP
        valuation_date = date(2025, 12, 4)
        
        # Act
        result = await pricing_service.calculate_current_value_async(
            unit_amount, price, quote_unit, price_currency, valuation_date
        )
        
        # Assert
        expected = Decimal("1000.00")
        assert result == expected
        # No conversion needed
        mock_currency_service.convert_currency_async.assert_not_called()


class TestScalingFactor:
    """Test scaling factor application for special instruments."""
    
    @pytest.mark.unit
    def test_isf_scaling_factor_applied(self, pricing_service):
        """Test that ISF.LSE ticker gets scaling factor applied."""
        # Arrange
        price = Decimal("100.00")
        ticker = ExchangeConstants.ISF_TICKER  # "ISF.LSE"
        
        # Act
        result = pricing_service.apply_scaling_factor(price, ticker)
        
        # Assert
        expected = Decimal("100.00") * Decimal(str(ExchangeConstants.ISF_SCALING_FACTOR))
        assert result == expected
    
    @pytest.mark.unit
    def test_isf_case_insensitive(self, pricing_service):
        """Test that ISF.LSE ticker is case-insensitive."""
        # Arrange
        price = Decimal("100.00")
        
        # Act
        result_upper = pricing_service.apply_scaling_factor(price, "ISF.LSE")
        result_lower = pricing_service.apply_scaling_factor(price, "isf.lse")
        result_mixed = pricing_service.apply_scaling_factor(price, "Isf.Lse")
        
        # Assert
        expected = Decimal("100.00") * Decimal(str(ExchangeConstants.ISF_SCALING_FACTOR))
        assert result_upper == expected
        assert result_lower == expected
        assert result_mixed == expected
    
    @pytest.mark.unit
    def test_no_scaling_for_regular_tickers(self, pricing_service):
        """Test that regular tickers don't get scaled."""
        # Arrange
        price = Decimal("150.50")
        tickers = ["AAPL", "MSFT", "GOOGL", "TSLA"]
        
        # Act & Assert
        for ticker in tickers:
            result = pricing_service.apply_scaling_factor(price, ticker)
            assert result == price  # No scaling applied


class TestComplexScenarios:
    """Test complex scenarios combining multiple features."""
    
    @pytest.mark.unit
    async def test_gbx_with_currency_mismatch(self, pricing_service, mock_currency_service):
        """Test that GBX correctly maps to GBP regardless of price_currency parameter."""
        # Arrange - Quote unit is GBX but price_currency says USD (should be ignored)
        unit_amount = Decimal("100")
        price = Decimal("50000")  # 500 GBP in pence
        quote_unit = "GBX"
        price_currency = "USD"  # This should be ignored when quote_unit is GBX
        valuation_date = date(2025, 12, 4)
        
        # Act
        result = await pricing_service.calculate_current_value_async(
            unit_amount, price, quote_unit, price_currency, valuation_date
        )
        
        # Assert
        expected = Decimal("50000.00")  # 100 * (50000/100) = 50000
        assert result == expected
        # GBX is treated as GBP, so no currency conversion
        mock_currency_service.convert_currency_async.assert_not_called()
    
    @pytest.mark.unit
    async def test_fractional_units(self, pricing_service, mock_currency_service):
        """Test calculation with fractional share units."""
        # Arrange
        unit_amount = Decimal("10.5")  # Fractional shares
        price = Decimal("150.75")
        quote_unit = "GBP"
        price_currency = "GBP"
        valuation_date = date(2025, 12, 4)
        
        # Act
        result = await pricing_service.calculate_current_value_async(
            unit_amount, price, quote_unit, price_currency, valuation_date
        )
        
        # Assert
        expected = Decimal("10.5") * Decimal("150.75")
        assert result == expected
    
    @pytest.mark.unit
    async def test_very_small_amounts(self, pricing_service, mock_currency_service):
        """Test calculation with very small amounts."""
        # Arrange
        unit_amount = Decimal("0.001")
        price = Decimal("50000.00")
        quote_unit = "USD"
        price_currency = "USD"
        valuation_date = date(2025, 12, 4)
        
        mock_currency_service.convert_currency_async.return_value = (
            Decimal("40.00"),  # 50 * 0.8
            Decimal("0.8"),
            "test"
        )
        
        # Act
        result = await pricing_service.calculate_current_value_async(
            unit_amount, price, quote_unit, price_currency, valuation_date
        )
        
        # Assert
        assert result == Decimal("40.00")
        # Verify conversion was called with correct amount
        mock_currency_service.convert_currency_async.assert_called_once_with(
            Decimal("50.00"),  # 0.001 * 50000
            "USD",
            "GBP",
            valuation_date
        )
    
    @pytest.mark.unit
    async def test_large_portfolio_value(self, pricing_service, mock_currency_service):
        """Test calculation with large amounts."""
        # Arrange
        unit_amount = Decimal("10000")
        price = Decimal("1500.50")
        quote_unit = "USD"
        price_currency = "USD"
        valuation_date = date(2025, 12, 4)
        
        # 15,005,000 USD * 0.8 = 12,004,000 GBP
        mock_currency_service.convert_currency_async.return_value = (
            Decimal("12004000.00"),
            Decimal("0.8"),
            "test"
        )
        
        # Act
        result = await pricing_service.calculate_current_value_async(
            unit_amount, price, quote_unit, price_currency, valuation_date
        )
        
        # Assert
        assert result == Decimal("12004000.00")


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @pytest.mark.unit
    async def test_zero_units(self, pricing_service, mock_currency_service):
        """Test calculation with zero units."""
        # Arrange
        unit_amount = Decimal("0")
        price = Decimal("150.50")
        quote_unit = "GBP"
        price_currency = "GBP"
        valuation_date = date(2025, 12, 4)
        
        # Act
        result = await pricing_service.calculate_current_value_async(
            unit_amount, price, quote_unit, price_currency, valuation_date
        )
        
        # Assert
        assert result == Decimal("0")
    
    @pytest.mark.unit
    async def test_zero_price(self, pricing_service, mock_currency_service):
        """Test calculation with zero price."""
        # Arrange
        unit_amount = Decimal("10")
        price = Decimal("0")
        quote_unit = "GBP"
        price_currency = "GBP"
        valuation_date = date(2025, 12, 4)
        
        # Act
        result = await pricing_service.calculate_current_value_async(
            unit_amount, price, quote_unit, price_currency, valuation_date
        )
        
        # Assert
        assert result == Decimal("0")
    
    @pytest.mark.unit
    async def test_none_quote_unit_defaults(self, pricing_service, mock_currency_service):
        """Test that None quote_unit uses default."""
        # Arrange
        unit_amount = Decimal("10")
        price = Decimal("100.00")
        quote_unit = None  # Should default
        price_currency = "GBP"
        valuation_date = date(2025, 12, 4)
        
        # Act
        result = await pricing_service.calculate_current_value_async(
            unit_amount, price, quote_unit, price_currency, valuation_date
        )
        
        # Assert
        expected = Decimal("1000.00")
        assert result == expected
    
    @pytest.mark.unit
    def test_scaling_with_zero_price(self, pricing_service):
        """Test scaling factor with zero price."""
        # Arrange
        price = Decimal("0")
        ticker = "ISF"
        
        # Act
        result = pricing_service.apply_scaling_factor(price, ticker)
        
        # Assert
        assert result == Decimal("0")
    
    @pytest.mark.unit
    def test_scaling_with_negative_price(self, pricing_service):
        """Test scaling factor with negative price (edge case)."""
        # Arrange
        price = Decimal("-100.00")
        ticker = ExchangeConstants.ISF_TICKER  # "ISF.LSE"
        
        # Act
        result = pricing_service.apply_scaling_factor(price, ticker)
        
        # Assert
        expected = Decimal("-100.00") * Decimal(str(ExchangeConstants.ISF_SCALING_FACTOR))
        assert result == expected


class TestDecimalPrecision:
    """Test that Decimal precision is maintained throughout calculations."""
    
    @pytest.mark.unit
    async def test_precision_maintained_in_calculation(self, pricing_service, mock_currency_service):
        """Test that decimal precision is maintained."""
        # Arrange
        unit_amount = Decimal("10.123456")
        price = Decimal("150.987654")
        quote_unit = "GBP"
        price_currency = "GBP"
        valuation_date = date(2025, 12, 4)
        
        # Act
        result = await pricing_service.calculate_current_value_async(
            unit_amount, price, quote_unit, price_currency, valuation_date
        )
        
        # Assert
        # Exact multiplication
        expected = Decimal("10.123456") * Decimal("150.987654")
        assert result == expected
    
    @pytest.mark.unit
    async def test_gbx_division_precision(self, pricing_service, mock_currency_service):
        """Test that GBX division by 100 maintains precision."""
        # Arrange
        unit_amount = Decimal("10")
        price = Decimal("15055")  # Odd number in pence
        quote_unit = "GBX"
        price_currency = "GBP"
        valuation_date = date(2025, 12, 4)
        
        # Act
        result = await pricing_service.calculate_current_value_async(
            unit_amount, price, quote_unit, price_currency, valuation_date
        )
        
        # Assert
        expected = Decimal("10") * (Decimal("15055") / Decimal("100"))
        assert result == expected
        assert result == Decimal("1505.5")
