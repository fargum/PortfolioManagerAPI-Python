"""
Unit tests for AI tools (portfolio_holdings_tool, portfolio_analysis_tool, etc.).

Tests cover:
- Tool initialization
- Tool execution with mock services
- Error handling when tools not initialized
- Response formatting
"""
import pytest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch

from src.schemas.holding import PortfolioHoldingDto, AccountHoldingsResponse
from src.services.ai.tools import portfolio_holdings_tool, portfolio_analysis_tool
from src.services.holding_service import HoldingService
from src.services.ai.portfolio_analysis_service import PortfolioAnalysisService


@pytest.fixture
def mock_holding_service():
    """Mock HoldingService for testing."""
    mock = Mock(spec=HoldingService)
    mock.get_holdings_by_account_and_date_async = AsyncMock()
    return mock


@pytest.fixture
def mock_portfolio_analysis_service():
    """Mock PortfolioAnalysisService for testing."""
    mock = Mock(spec=PortfolioAnalysisService)
    mock.analyze_portfolio_performance_async = AsyncMock()
    mock.compare_performance_async = AsyncMock()
    return mock


@pytest.fixture
def sample_holdings_response():
    """Sample AccountHoldingsResponse for testing."""
    holdings = [
        PortfolioHoldingDto(
            holding_id=1,
            portfolio_id=1,
            portfolio_name="Main Portfolio",
            platform_id=1,
            platform_name="Platform A",
            ticker="AAPL",
            instrument_name="Apple Inc.",
            units=Decimal("10"),
            bought_value=Decimal("1000.00"),
            current_value=Decimal("1500.00"),
            current_price=Decimal("150.00"),
            gain_loss=Decimal("500.00"),
            gain_loss_percentage=Decimal("50.0"),
            currency_code="USD",
            valuation_date=date(2025, 1, 15)
        ),
    ]
    
    return AccountHoldingsResponse(
        account_id=100,
        valuation_date=date(2025, 1, 15),
        holdings=holdings,
        total_holdings=1,
        total_current_value=Decimal("1500.00"),
        total_bought_value=Decimal("1000.00"),
        total_gain_loss=Decimal("500.00"),
        total_gain_loss_percentage=Decimal("50.0")
    )


class TestPortfolioHoldingsToolInitialization:
    """Test portfolio holdings tool initialization."""
    
    @pytest.mark.unit
    def test_initialize_holdings_tool(self, mock_holding_service):
        """Test that holdings tool can be initialized."""
        portfolio_holdings_tool.initialize_holdings_tool(mock_holding_service, 100)
        
        assert portfolio_holdings_tool._holding_service is mock_holding_service
        assert portfolio_holdings_tool._account_id == 100
    
    @pytest.mark.unit
    def test_initialize_with_different_account_ids(self, mock_holding_service):
        """Test tool can be reinitialized with different account."""
        portfolio_holdings_tool.initialize_holdings_tool(mock_holding_service, 100)
        assert portfolio_holdings_tool._account_id == 100
        
        portfolio_holdings_tool.initialize_holdings_tool(mock_holding_service, 200)
        assert portfolio_holdings_tool._account_id == 200


class TestPortfolioHoldingsToolExecution:
    """Test portfolio holdings tool execution."""
    
    @pytest.mark.unit
    async def test_get_holdings_returns_formatted_response(
        self, mock_holding_service, sample_holdings_response
    ):
        """Test that get_portfolio_holdings returns properly formatted response."""
        mock_holding_service.get_holdings_by_account_and_date_async.return_value = sample_holdings_response
        portfolio_holdings_tool.initialize_holdings_tool(mock_holding_service, 100)
        
        result = await portfolio_holdings_tool.get_portfolio_holdings.ainvoke(
            {"date": "2025-01-15"}
        )
        
        assert result["AccountId"] == 100
        assert result["TotalValue"] == 1500.00
        assert result["TotalHoldings"] == 1
        assert len(result["Holdings"]) == 1
    
    @pytest.mark.unit
    async def test_get_holdings_handles_today_keyword(
        self, mock_holding_service, sample_holdings_response
    ):
        """Test that 'today' keyword is handled correctly."""
        mock_holding_service.get_holdings_by_account_and_date_async.return_value = sample_holdings_response
        portfolio_holdings_tool.initialize_holdings_tool(mock_holding_service, 100)
        
        result = await portfolio_holdings_tool.get_portfolio_holdings.ainvoke(
            {"date": "today"}
        )
        
        # Should not raise error and return valid response
        assert "AccountId" in result
        assert "Error" not in result
    
    @pytest.mark.unit
    async def test_get_holdings_not_initialized_returns_error(self):
        """Test error when tool not initialized."""
        # Reset global state
        portfolio_holdings_tool._holding_service = None
        portfolio_holdings_tool._account_id = None
        
        result = await portfolio_holdings_tool.get_portfolio_holdings.ainvoke(
            {"date": "2025-01-15"}
        )
        
        assert "Error" in result
        assert "not initialized" in result["Error"]
    
    @pytest.mark.unit
    async def test_get_holdings_formats_holding_details(
        self, mock_holding_service, sample_holdings_response
    ):
        """Test that individual holding details are properly formatted."""
        mock_holding_service.get_holdings_by_account_and_date_async.return_value = sample_holdings_response
        portfolio_holdings_tool.initialize_holdings_tool(mock_holding_service, 100)
        
        result = await portfolio_holdings_tool.get_portfolio_holdings.ainvoke(
            {"date": "2025-01-15"}
        )
        
        holding = result["Holdings"][0]
        assert holding["Ticker"] == "AAPL"
        assert holding["InstrumentName"] == "Apple Inc."
        assert holding["CurrentValue"] == 1500.00
        assert holding["GainLoss"] == 500.00


class TestPortfolioAnalysisToolInitialization:
    """Test portfolio analysis tool initialization."""
    
    @pytest.mark.unit
    def test_initialize_analysis_tool(self, mock_portfolio_analysis_service):
        """Test that analysis tool can be initialized."""
        portfolio_analysis_tool.initialize_analysis_tool(mock_portfolio_analysis_service, 100)
        
        assert portfolio_analysis_tool._portfolio_analysis_service is mock_portfolio_analysis_service
        assert portfolio_analysis_tool._account_id == 100


class TestPortfolioAnalysisToolExecution:
    """Test portfolio analysis tool execution."""
    
    @pytest.mark.unit
    async def test_analyze_performance_returns_service_response(
        self, mock_portfolio_analysis_service
    ):
        """Test that analyze_portfolio_performance returns service response."""
        expected_analysis = {
            "AccountId": 100,
            "AnalysisDate": "2025-01-15T00:00:00",
            "TotalValue": 1500.00,
            "GainLoss": 500.00,
            "HoldingPerformance": [],
            "Metrics": {}
        }
        mock_portfolio_analysis_service.analyze_portfolio_performance_async.return_value = expected_analysis
        portfolio_analysis_tool.initialize_analysis_tool(mock_portfolio_analysis_service, 100)
        
        result = await portfolio_analysis_tool.analyze_portfolio_performance.ainvoke(
            {"analysis_date": "2025-01-15"}
        )
        
        assert result == expected_analysis
    
    @pytest.mark.unit
    async def test_analyze_performance_not_initialized_returns_error(self):
        """Test error when tool not initialized."""
        # Reset global state
        portfolio_analysis_tool._portfolio_analysis_service = None
        portfolio_analysis_tool._account_id = None
        
        result = await portfolio_analysis_tool.analyze_portfolio_performance.ainvoke(
            {"analysis_date": "2025-01-15"}
        )
        
        assert "Error" in result
        assert "not initialized" in result["Error"]
    
    @pytest.mark.unit
    async def test_analyze_performance_handles_today_keyword(
        self, mock_portfolio_analysis_service
    ):
        """Test that 'today' keyword is handled correctly."""
        mock_portfolio_analysis_service.analyze_portfolio_performance_async.return_value = {
            "AccountId": 100,
            "TotalValue": 1500.00
        }
        portfolio_analysis_tool.initialize_analysis_tool(mock_portfolio_analysis_service, 100)
        
        result = await portfolio_analysis_tool.analyze_portfolio_performance.ainvoke(
            {"analysis_date": "today"}
        )
        
        assert "Error" not in result
        mock_portfolio_analysis_service.analyze_portfolio_performance_async.assert_called_once()
