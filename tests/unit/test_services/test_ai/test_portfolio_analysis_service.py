"""
Unit tests for PortfolioAnalysisService.

Tests cover:
- Portfolio performance analysis
- Performance comparison between dates
- Metric calculations (top/bottom performers)
- Edge cases (empty holdings, missing data)
"""
import pytest
from datetime import datetime, date
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, MagicMock

from src.services.ai.portfolio_analysis_service import PortfolioAnalysisService
from src.services.holding_service import HoldingService
from src.schemas.holding import PortfolioHoldingDto, AccountHoldingsResponse


@pytest.fixture
def mock_holding_service():
    """Mock HoldingService for testing."""
    mock = Mock(spec=HoldingService)
    mock.get_holdings_by_account_and_date_async = AsyncMock()
    return mock


@pytest.fixture
def portfolio_analysis_service(mock_holding_service):
    """Create PortfolioAnalysisService instance with mocked dependencies."""
    return PortfolioAnalysisService(mock_holding_service)


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
        PortfolioHoldingDto(
            holding_id=2,
            portfolio_id=1,
            portfolio_name="Main Portfolio",
            platform_id=1,
            platform_name="Platform A",
            ticker="MSFT",
            instrument_name="Microsoft Corp.",
            units=Decimal("5"),
            bought_value=Decimal("500.00"),
            current_value=Decimal("450.00"),
            current_price=Decimal("90.00"),
            gain_loss=Decimal("-50.00"),
            gain_loss_percentage=Decimal("-10.0"),
            currency_code="USD",
            valuation_date=date(2025, 1, 15)
        ),
    ]
    
    return AccountHoldingsResponse(
        account_id=100,
        valuation_date=date(2025, 1, 15),
        holdings=holdings,
        total_holdings=2,
        total_current_value=Decimal("1950.00"),
        total_bought_value=Decimal("1500.00"),
        total_gain_loss=Decimal("450.00"),
        total_gain_loss_percentage=Decimal("30.0")
    )


class TestPortfolioAnalysisServiceInitialization:
    """Test PortfolioAnalysisService initialization."""
    
    @pytest.mark.unit
    def test_init_with_holding_service(self, mock_holding_service):
        """Test initialization with holding service."""
        service = PortfolioAnalysisService(mock_holding_service)
        assert service.holding_service is mock_holding_service


class TestAnalyzePortfolioPerformance:
    """Test analyze_portfolio_performance_async method."""
    
    @pytest.mark.unit
    async def test_analyze_performance_returns_correct_structure(
        self, portfolio_analysis_service, mock_holding_service, sample_holdings_response
    ):
        """Test that analyze returns correct response structure."""
        mock_holding_service.get_holdings_by_account_and_date_async.return_value = sample_holdings_response
        
        result = await portfolio_analysis_service.analyze_portfolio_performance_async(
            account_id=100,
            analysis_date=datetime(2025, 1, 15)
        )
        
        assert "AccountId" in result
        assert "AnalysisDate" in result
        assert "TotalValue" in result
        assert "HoldingPerformance" in result
        assert "Metrics" in result
    
    @pytest.mark.unit
    async def test_analyze_performance_uses_service_totals(
        self, portfolio_analysis_service, mock_holding_service, sample_holdings_response
    ):
        """Test that service-calculated totals are used."""
        mock_holding_service.get_holdings_by_account_and_date_async.return_value = sample_holdings_response
        
        result = await portfolio_analysis_service.analyze_portfolio_performance_async(
            account_id=100,
            analysis_date=datetime(2025, 1, 15)
        )
        
        # Should use totals from AccountHoldingsResponse
        assert result["TotalValue"] == 1950.00
        assert result["GainLoss"] == 450.00
        assert result["GainLossPercentage"] == 30.0
    
    @pytest.mark.unit
    async def test_analyze_performance_holding_details(
        self, portfolio_analysis_service, mock_holding_service, sample_holdings_response
    ):
        """Test holding performance details."""
        mock_holding_service.get_holdings_by_account_and_date_async.return_value = sample_holdings_response
        
        result = await portfolio_analysis_service.analyze_portfolio_performance_async(
            account_id=100,
            analysis_date=datetime(2025, 1, 15)
        )
        
        holdings = result["HoldingPerformance"]
        assert len(holdings) == 2
        
        # Check AAPL holding
        aapl = next(h for h in holdings if h["Ticker"] == "AAPL")
        assert aapl["CurrentValue"] == 1500.00
        assert aapl["GainLoss"] == 500.00
    
    @pytest.mark.unit
    async def test_analyze_performance_empty_holdings(
        self, portfolio_analysis_service, mock_holding_service
    ):
        """Test analysis with no holdings returns empty analysis."""
        mock_holding_service.get_holdings_by_account_and_date_async.return_value = None
        
        result = await portfolio_analysis_service.analyze_portfolio_performance_async(
            account_id=100,
            analysis_date=datetime(2025, 1, 15)
        )
        
        assert result["TotalValue"] == 0.0
        assert result["HoldingPerformance"] == []
    
    @pytest.mark.unit
    async def test_analyze_performance_calculates_metrics(
        self, portfolio_analysis_service, mock_holding_service, sample_holdings_response
    ):
        """Test that performance metrics are calculated."""
        mock_holding_service.get_holdings_by_account_and_date_async.return_value = sample_holdings_response
        
        result = await portfolio_analysis_service.analyze_portfolio_performance_async(
            account_id=100,
            analysis_date=datetime(2025, 1, 15)
        )
        
        metrics = result["Metrics"]
        assert "TopPerformers" in metrics or "TotalReturn" in metrics


class TestComparePerformance:
    """Test compare_performance_async method."""
    
    @pytest.mark.unit
    async def test_compare_performance_structure(
        self, portfolio_analysis_service, mock_holding_service, sample_holdings_response
    ):
        """Test that comparison returns correct structure."""
        mock_holding_service.get_holdings_by_account_and_date_async.return_value = sample_holdings_response
        
        result = await portfolio_analysis_service.compare_performance_async(
            account_id=100,
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 15)
        )
        
        assert "AccountId" in result
        assert "StartDate" in result
        assert "EndDate" in result
        assert "StartValue" in result
        assert "EndValue" in result
        assert "TotalChange" in result
        assert "TotalChangePercentage" in result
        assert "Insights" in result
    
    @pytest.mark.unit
    async def test_compare_performance_calculates_change(
        self, portfolio_analysis_service, mock_holding_service
    ):
        """Test that value change is correctly calculated."""
        # Create mock responses with holdings (not empty)
        start_holding = PortfolioHoldingDto(
            holding_id=1,
            portfolio_id=1,
            portfolio_name="Main Portfolio",
            platform_id=1,
            platform_name="Platform A",
            ticker="AAPL",
            instrument_name="Apple Inc.",
            units=Decimal("10"),
            bought_value=Decimal("1000.00"),
            current_value=Decimal("1000.00"),
            current_price=Decimal("100.00"),
            gain_loss=Decimal("0"),
            gain_loss_percentage=Decimal("0"),
            currency_code="USD",
            valuation_date=date(2025, 1, 1)
        )
        
        # Start holdings (lower value)
        start_response = AccountHoldingsResponse(
            account_id=100,
            valuation_date=date(2025, 1, 1),
            holdings=[start_holding],
            total_holdings=1,
            total_current_value=Decimal("1000.00"),
            total_bought_value=Decimal("1000.00"),
            total_gain_loss=Decimal("0"),
            total_gain_loss_percentage=Decimal("0")
        )
        
        end_holding = PortfolioHoldingDto(
            holding_id=1,
            portfolio_id=1,
            portfolio_name="Main Portfolio",
            platform_id=1,
            platform_name="Platform A",
            ticker="AAPL",
            instrument_name="Apple Inc.",
            units=Decimal("10"),
            bought_value=Decimal("1000.00"),
            current_value=Decimal("1200.00"),
            current_price=Decimal("120.00"),
            gain_loss=Decimal("200.00"),
            gain_loss_percentage=Decimal("20.0"),
            currency_code="USD",
            valuation_date=date(2025, 1, 15)
        )
        
        # End holdings (higher value)
        end_response = AccountHoldingsResponse(
            account_id=100,
            valuation_date=date(2025, 1, 15),
            holdings=[end_holding],
            total_holdings=1,
            total_current_value=Decimal("1200.00"),
            total_bought_value=Decimal("1000.00"),
            total_gain_loss=Decimal("200.00"),
            total_gain_loss_percentage=Decimal("20.0")
        )
        
        mock_holding_service.get_holdings_by_account_and_date_async.side_effect = [
            start_response, end_response
        ]
        
        result = await portfolio_analysis_service.compare_performance_async(
            account_id=100,
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 15)
        )
        
        assert result["StartValue"] == 1000.00
        assert result["EndValue"] == 1200.00
        assert result["TotalChange"] == 200.00
        assert result["TotalChangePercentage"] == 0.2  # 20%
    
    @pytest.mark.unit
    async def test_compare_performance_empty_holdings(
        self, portfolio_analysis_service, mock_holding_service
    ):
        """Test comparison when no holdings found."""
        empty_response = AccountHoldingsResponse(
            account_id=100,
            valuation_date=date(2025, 1, 1),
            holdings=[],
            total_holdings=0,
            total_current_value=Decimal("0"),
            total_bought_value=Decimal("0"),
            total_gain_loss=Decimal("0"),
            total_gain_loss_percentage=Decimal("0")
        )
        
        mock_holding_service.get_holdings_by_account_and_date_async.return_value = empty_response
        
        result = await portfolio_analysis_service.compare_performance_async(
            account_id=100,
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 15)
        )
        
        assert result["TotalChange"] == 0.0
        assert result["TotalChangePercentage"] == 0.0


class TestPerformanceMetrics:
    """Test performance metric calculations."""
    
    @pytest.mark.unit
    def test_calculate_performance_metrics(self, portfolio_analysis_service):
        """Test performance metrics calculation."""
        # Use the correct keys that the method expects
        holding_performance = [
            {"Ticker": "AAPL", "TotalReturnPercentage": 50.0, "TotalReturn": 500.0, "BoughtValue": 1000.0},
            {"Ticker": "MSFT", "TotalReturnPercentage": -10.0, "TotalReturn": -50.0, "BoughtValue": 500.0},
            {"Ticker": "GOOG", "TotalReturnPercentage": 25.0, "TotalReturn": 250.0, "BoughtValue": 1000.0},
        ]
        
        metrics = portfolio_analysis_service._calculate_performance_metrics(holding_performance)
        
        # Should identify top and bottom performers
        assert "TopPerformers" in metrics
        assert "BottomPerformers" in metrics
        assert "TotalReturn" in metrics
        assert metrics["TotalReturn"] == 700.0  # 500 - 50 + 250
