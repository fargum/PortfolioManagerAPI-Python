"""
Unit tests for HoldingService.

Tests cover:
- Getting holdings by account and date (historical vs real-time)
- Building holdings response from database rows
- Applying real-time pricing with EOD tool
- Adding new holdings (with validation)
- Updating holding units
- Deleting holdings
- Edge cases and error handling
"""
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from src.services.holding_service import HoldingService
from src.schemas.holding import AddHoldingApiRequest
from src.core.constants import ExchangeConstants


# ==================== Local Service Fixtures ====================
# All mock objects come from conftest.py. Only service-specific fixtures here.

@pytest.fixture
def holding_service(mock_db_session, mock_eod_tool, mock_pricing_service):
    """Create a HoldingService with all mocked dependencies."""
    return HoldingService(
        db=mock_db_session,
        eod_tool=mock_eod_tool,
        pricing_calculation_service=mock_pricing_service
    )


@pytest.fixture
def holding_service_no_tools(mock_db_session):
    """Create a HoldingService without EOD tool or pricing service."""
    return HoldingService(db=mock_db_session, eod_tool=None, pricing_calculation_service=None)


class TestGetHoldingsByAccountAndDate:
    """Test getting holdings for an account on a specific date."""
    
    @pytest.mark.asyncio
    async def test_no_portfolios_returns_none(self, holding_service, mock_db_session):
        """Test that no portfolios for account returns None."""
        account_id = 100
        valuation_date = date(2024, 1, 15)
        
        # Mock empty portfolio result
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db_session.execute.return_value = mock_result
        
        result = await holding_service.get_holdings_by_account_and_date_async(
            account_id, valuation_date
        )
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_no_holdings_returns_none(self, holding_service, mock_db_session):
        """Test that no holdings for date returns None."""
        account_id = 100
        valuation_date = date(2024, 1, 15)
        
        # Mock portfolio result with IDs
        mock_portfolio_result = MagicMock()
        mock_portfolio_result.all.return_value = [(1,), (2,)]
        
        # Mock empty holdings result
        mock_holdings_result = MagicMock()
        mock_holdings_result.all.return_value = []
        
        mock_db_session.execute.side_effect = [
            mock_portfolio_result,
            mock_holdings_result
        ]
        
        result = await holding_service.get_holdings_by_account_and_date_async(
            account_id, valuation_date
        )
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_historical_date_uses_database_values(
        self, 
        holding_service, 
        mock_db_session,
        sample_holding,
        sample_instrument,
        sample_portfolio
    ):
        """Test that historical dates use database values without real-time pricing."""
        account_id = 100
        valuation_date = date(2024, 1, 15)  # Historical date
        
        # Mock portfolio result
        mock_portfolio_result = MagicMock()
        mock_portfolio_result.all.return_value = [(1,)]
        
        # Mock holdings result with row data
        mock_holdings_result = MagicMock()
        mock_holdings_result.all.return_value = [
            (
                sample_holding,
                sample_instrument.ticker,
                sample_instrument.name,
                sample_instrument.description,
                sample_instrument.currency_code,
                sample_instrument.quote_unit,
                sample_portfolio.name,
                sample_portfolio.id
            )
        ]
        
        mock_db_session.execute.side_effect = [
            mock_portfolio_result,
            mock_holdings_result
        ]
        
        result = await holding_service.get_holdings_by_account_and_date_async(
            account_id, valuation_date
        )
        
        assert result is not None
        assert result.total_holdings == 1
        assert result.holdings[0].ticker == "AAPL"
        assert result.holdings[0].current_value == Decimal("1500.00")
        assert result.holdings[0].units == Decimal("10.0")


class TestBuildHoldingsResponse:
    """Test building holdings response from database rows."""
    
    def test_single_holding_response(
        self,
        holding_service,
        sample_holding,
        sample_instrument,
        sample_portfolio
    ):
        """Test building response for a single holding."""
        valuation_date = date(2024, 1, 15)
        holdings_rows = [
            (
                sample_holding,
                sample_instrument.ticker,
                sample_instrument.name,
                sample_instrument.description,
                sample_instrument.currency_code,
                sample_instrument.quote_unit,
                sample_portfolio.name,
                sample_portfolio.id
            )
        ]
        
        result = holding_service._build_holdings_response(holdings_rows, valuation_date)
        
        assert len(result) == 1
        assert result[0]['ticker'] == "AAPL"
        assert result[0]['instrument_name'] == "Apple Inc."
        assert result[0]['units'] == Decimal("10.0")
        assert result[0]['current_value'] == Decimal("1500.00")
        assert result[0]['bought_value'] == Decimal("1000.00")
        assert result[0]['gain_loss'] == Decimal("500.00")
        assert result[0]['currency_code'] == "USD"
    
    def test_gain_loss_percentage_calculation(
        self,
        holding_service,
        sample_holding,
        sample_instrument,
        sample_portfolio
    ):
        """Test that gain/loss percentage is calculated correctly."""
        valuation_date = date(2024, 1, 15)
        sample_holding.bought_value = Decimal("1000.00")
        sample_holding.current_value = Decimal("1200.00")
        
        holdings_rows = [
            (
                sample_holding,
                sample_instrument.ticker,
                sample_instrument.name,
                sample_instrument.description,
                sample_instrument.currency_code,
                sample_instrument.quote_unit,
                sample_portfolio.name,
                sample_portfolio.id
            )
        ]
        
        result = holding_service._build_holdings_response(holdings_rows, valuation_date)
        
        expected_percentage = Decimal("20.0")  # (1200-1000)/1000 * 100
        assert result[0]['gain_loss_percentage'] == expected_percentage
    
    def test_zero_bought_value_handling(
        self,
        holding_service,
        sample_holding,
        sample_instrument,
        sample_portfolio
    ):
        """Test handling of zero bought value to avoid division by zero."""
        valuation_date = date(2024, 1, 15)
        sample_holding.bought_value = Decimal("0")
        sample_holding.current_value = Decimal("100.00")
        
        holdings_rows = [
            (
                sample_holding,
                sample_instrument.ticker,
                sample_instrument.name,
                sample_instrument.description,
                sample_instrument.currency_code,
                sample_instrument.quote_unit,
                sample_portfolio.name,
                sample_portfolio.id
            )
        ]
        
        result = holding_service._build_holdings_response(holdings_rows, valuation_date)
        
        assert result[0]['gain_loss_percentage'] == Decimal('0')


class TestApplyRealTimePricing:
    """Test applying real-time pricing to holdings."""
    
    @pytest.mark.asyncio
    async def test_no_eod_tool_falls_back_to_database_values(
        self,
        holding_service_no_tools,
        sample_holding,
        sample_instrument,
        sample_portfolio
    ):
        """Test that missing EOD tool falls back to database values."""
        valuation_date = date.today()
        holdings_rows = [
            (
                sample_holding,
                sample_instrument.ticker,
                sample_instrument.name,
                sample_instrument.description,
                sample_instrument.currency_code,
                sample_instrument.quote_unit,
                sample_portfolio.name,
                sample_portfolio.id
            )
        ]
        
        result = await holding_service_no_tools._apply_real_time_pricing(
            holdings_rows, valuation_date
        )
        
        assert len(result) == 1
        assert result[0]['current_value'] == sample_holding.current_value
    
    @pytest.mark.asyncio
    async def test_cash_ticker_special_handling(
        self,
        holding_service,
        mock_eod_tool,
        sample_holding,
        sample_portfolio
    ):
        """Test that CASH ticker is handled specially (units = value)."""
        valuation_date = date.today()
        sample_holding.unit_amount = Decimal("5000.00")
        sample_holding.bought_value = Decimal("5000.00")
        
        holdings_rows = [
            (
                sample_holding,
                ExchangeConstants.CASH_TICKER,
                "Cash",
                "Cash holdings",
                "GBP",
                "GBP",
                sample_portfolio.name,
                sample_portfolio.id
            )
        ]
        
        # CASH is filtered out from ticker list, so no prices fetched
        # Mock returns prices for other tickers but not CASH
        mock_eod_tool.get_real_time_prices_async.return_value = {}
        
        result = await holding_service._apply_real_time_pricing(
            holdings_rows, valuation_date
        )
        
        # CASH is filtered before price fetch, so result falls back to database response
        # which uses historical values since no pricing needed
        assert len(result) == 1
        assert result[0]['ticker'] == ExchangeConstants.CASH_TICKER
        # When tickers list is empty, it falls back to _build_holdings_response
        assert result[0]['current_value'] == sample_holding.current_value
    
    @pytest.mark.asyncio
    async def test_real_time_price_with_pricing_service(
        self,
        holding_service,
        mock_eod_tool,
        mock_pricing_service,
        sample_holding,
        sample_instrument,
        sample_portfolio
    ):
        """Test real-time pricing with full pricing calculation service."""
        valuation_date = date.today()
        
        holdings_rows = [
            (
                sample_holding,
                sample_instrument.ticker,
                sample_instrument.name,
                sample_instrument.description,
                sample_instrument.currency_code,
                sample_instrument.quote_unit,
                sample_portfolio.name,
                sample_portfolio.id
            )
        ]
        
        # Mock real-time price
        mock_eod_tool.get_real_time_prices_async.return_value = {
            "AAPL": 175.50
        }
        
        # Mock pricing service calculations
        mock_pricing_service.apply_scaling_factor.return_value = Decimal("175.50")
        mock_pricing_service.calculate_current_value_async.return_value = Decimal("1755.00")
        
        result = await holding_service._apply_real_time_pricing(
            holdings_rows, valuation_date
        )
        
        assert len(result) == 1
        assert result[0]['current_value'] == Decimal("1755.00")
        assert result[0]['current_price'] == Decimal("175.50")
        
        # Verify pricing service was called correctly
        mock_pricing_service.apply_scaling_factor.assert_called_once()
        mock_pricing_service.calculate_current_value_async.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_no_real_time_price_uses_database_value(
        self,
        holding_service,
        mock_eod_tool,
        sample_holding,
        sample_instrument,
        sample_portfolio
    ):
        """Test that missing real-time price falls back to database value."""
        valuation_date = date.today()
        
        holdings_rows = [
            (
                sample_holding,
                sample_instrument.ticker,
                sample_instrument.name,
                sample_instrument.description,
                sample_instrument.currency_code,
                sample_instrument.quote_unit,
                sample_portfolio.name,
                sample_portfolio.id
            )
        ]
        
        # Mock no price available
        mock_eod_tool.get_real_time_prices_async.return_value = {}
        
        result = await holding_service._apply_real_time_pricing(
            holdings_rows, valuation_date
        )
        
        assert len(result) == 1
        assert result[0]['current_value'] == sample_holding.current_value
    
    @pytest.mark.asyncio
    async def test_exception_falls_back_to_database_values(
        self,
        holding_service,
        mock_eod_tool,
        sample_holding,
        sample_instrument,
        sample_portfolio
    ):
        """Test that exceptions during pricing fall back to database values."""
        valuation_date = date.today()
        
        holdings_rows = [
            (
                sample_holding,
                sample_instrument.ticker,
                sample_instrument.name,
                sample_instrument.description,
                sample_instrument.currency_code,
                sample_instrument.quote_unit,
                sample_portfolio.name,
                sample_portfolio.id
            )
        ]
        
        # Mock exception during price fetch
        mock_eod_tool.get_real_time_prices_async.side_effect = Exception("API error")
        
        result = await holding_service._apply_real_time_pricing(
            holdings_rows, valuation_date
        )
        
        assert len(result) == 1
        assert result[0]['current_value'] == sample_holding.current_value


class TestAddHolding:
    """Test adding new holdings."""
    
    @pytest.mark.asyncio
    async def test_portfolio_not_found(
        self,
        holding_service,
        mock_db_session
    ):
        """Test that non-existent portfolio returns error."""
        portfolio_id = 1
        account_id = 100
        request = AddHoldingApiRequest(
            ticker="AAPL",
            units=Decimal("10"),
            bought_value=Decimal("1000"),
            platform_id=1,
            instrument_type_id=1
        )
        
        # Mock portfolio not found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        result = await holding_service.add_holding_async(portfolio_id, request, account_id)
        
        assert result.success is False
        assert "not found" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_duplicate_holding_returns_error(
        self,
        holding_service,
        mock_db_session,
        sample_portfolio,
        sample_instrument,
        sample_holding
    ):
        """Test that duplicate holding for same date returns error."""
        portfolio_id = 1
        account_id = 100
        request = AddHoldingApiRequest(
            ticker="AAPL",
            units=Decimal("10"),
            bought_value=Decimal("1000"),
            platform_id=1,
            instrument_type_id=1
        )
        
        # Mock portfolio found
        mock_portfolio_result = MagicMock()
        mock_portfolio_result.scalar_one_or_none.return_value = sample_portfolio
        
        # Mock instrument found
        mock_instrument_result = MagicMock()
        mock_instrument_result.scalar_one_or_none.return_value = sample_instrument
        
        # Mock duplicate found
        mock_duplicate_result = MagicMock()
        mock_duplicate_result.scalar_one_or_none.return_value = sample_holding
        
        mock_db_session.execute.side_effect = [
            mock_portfolio_result,
            mock_instrument_result,
            mock_duplicate_result
        ]
        
        result = await holding_service.add_holding_async(portfolio_id, request, account_id)
        
        assert result.success is False
        assert "already exists" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_exception_triggers_rollback(
        self,
        holding_service,
        mock_db_session
    ):
        """Test that exceptions trigger database rollback."""
        portfolio_id = 1
        account_id = 100
        request = AddHoldingApiRequest(
            ticker="AAPL",
            units=Decimal("10"),
            bought_value=Decimal("1000"),
            platform_id=1,
            instrument_type_id=1
        )
        
        # Mock exception
        mock_db_session.execute.side_effect = Exception("Database error")
        
        result = await holding_service.add_holding_async(portfolio_id, request, account_id)
        
        assert result.success is False
        mock_db_session.rollback.assert_called_once()


class TestUpdateHoldingUnits:
    """Test updating holding units."""
    
    @pytest.mark.asyncio
    async def test_holding_not_found(
        self,
        holding_service,
        mock_db_session
    ):
        """Test that non-existent holding returns error."""
        holding_id = 999
        new_units = Decimal("20")
        account_id = 100
        
        # Mock holding not found
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        result = await holding_service.update_holding_units_async(
            holding_id, new_units, account_id
        )
        
        assert result.success is False
        assert "not found" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_successful_units_update(
        self,
        holding_service,
        mock_db_session,
        sample_holding,
        sample_portfolio,
        sample_instrument
    ):
        """Test successful update of holding units."""
        holding_id = 1
        new_units = Decimal("20")
        account_id = 100
        
        # Mock holding found
        mock_result = MagicMock()
        mock_result.first.return_value = (sample_holding, sample_portfolio, sample_instrument)
        mock_db_session.execute.return_value = mock_result
        
        result = await holding_service.update_holding_units_async(
            holding_id, new_units, account_id
        )
        
        assert result.success is True
        assert result.new_units == new_units
        assert result.previous_units == Decimal("10.0")
        mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_exception_triggers_rollback(
        self,
        holding_service,
        mock_db_session
    ):
        """Test that exceptions trigger database rollback."""
        holding_id = 1
        new_units = Decimal("20")
        account_id = 100
        
        # Mock exception
        mock_db_session.execute.side_effect = Exception("Database error")
        
        result = await holding_service.update_holding_units_async(
            holding_id, new_units, account_id
        )
        
        assert result.success is False
        mock_db_session.rollback.assert_called_once()


class TestDeleteHolding:
    """Test deleting holdings."""
    
    @pytest.mark.asyncio
    async def test_holding_not_found(
        self,
        holding_service,
        mock_db_session
    ):
        """Test that non-existent holding returns error."""
        holding_id = 999
        account_id = 100
        
        # Mock holding not found
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        result = await holding_service.delete_holding_async(holding_id, account_id)
        
        assert result.success is False
        assert "not found" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_successful_deletion(
        self,
        holding_service,
        mock_db_session,
        sample_holding,
        sample_portfolio,
        sample_instrument
    ):
        """Test successful deletion of holding."""
        holding_id = 1
        account_id = 100
        
        # Mock holding found
        mock_result = MagicMock()
        mock_result.first.return_value = (sample_holding, sample_portfolio, sample_instrument)
        mock_db_session.execute.return_value = mock_result
        
        result = await holding_service.delete_holding_async(holding_id, account_id)
        
        assert result.success is True
        assert result.deleted_holding_id == holding_id
        assert result.deleted_ticker == sample_instrument.ticker
        mock_db_session.delete.assert_called_once()
        mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_exception_triggers_rollback(
        self,
        holding_service,
        mock_db_session
    ):
        """Test that exceptions trigger database rollback."""
        holding_id = 1
        account_id = 100
        
        # Mock exception
        mock_db_session.execute.side_effect = Exception("Database error")
        
        result = await holding_service.delete_holding_async(holding_id, account_id)
        
        assert result.success is False
        mock_db_session.rollback.assert_called_once()
