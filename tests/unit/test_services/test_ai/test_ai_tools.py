"""
Unit tests for AI tools (portfolio_holdings_tool, portfolio_analysis_tool, etc.).

Tests cover:
- Tool factory function creation
- Tool execution with mock services
- Response formatting
- Error handling

Note: Tools use factory pattern - each call to create_*_tool() returns a new
StructuredTool instance with bound context, avoiding global state.
"""
import pytest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch

from src.schemas.holding import PortfolioHoldingDto, AccountHoldingsResponse
from src.services.ai.tools import (
    create_portfolio_holdings_tool,
    create_portfolio_analysis_tool,
    create_market_intelligence_tools,
)
from src.services.holding_service import HoldingService
from src.services.ai.portfolio_analysis_service import PortfolioAnalysisService
from src.services.tavily_service import TavilyService


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


class TestPortfolioHoldingsToolFactory:
    """Test portfolio holdings tool factory creation."""
    
    @pytest.mark.unit
    def test_create_holdings_tool_returns_structured_tool(self, mock_holding_service):
        """Test that factory returns a StructuredTool."""
        tool = create_portfolio_holdings_tool(mock_holding_service, 100)
        
        assert tool is not None
        assert tool.name == "get_portfolio_holdings"
        assert "portfolio holdings" in tool.description.lower()
    
    @pytest.mark.unit
    def test_create_holdings_tool_with_different_accounts(self, mock_holding_service):
        """Test factory creates separate tools for different accounts."""
        tool1 = create_portfolio_holdings_tool(mock_holding_service, 100)
        tool2 = create_portfolio_holdings_tool(mock_holding_service, 200)
        
        # Each call creates a new independent tool instance
        assert tool1 is not tool2


class TestPortfolioHoldingsToolExecution:
    """Test portfolio holdings tool execution."""
    
    @pytest.mark.unit
    async def test_get_holdings_returns_formatted_response(
        self, mock_holding_service, sample_holdings_response
    ):
        """Test that get_portfolio_holdings returns properly formatted response."""
        mock_holding_service.get_holdings_by_account_and_date_async.return_value = sample_holdings_response
        tool = create_portfolio_holdings_tool(mock_holding_service, 100)
        
        result = await tool.ainvoke({"date": "2025-01-15"})
        
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
        tool = create_portfolio_holdings_tool(mock_holding_service, 100)
        
        result = await tool.ainvoke({"date": "today"})
        
        # Should not raise error and return valid response
        assert "AccountId" in result
        assert "Error" not in result
    
    @pytest.mark.unit
    async def test_get_holdings_formats_holding_details(
        self, mock_holding_service, sample_holdings_response
    ):
        """Test that individual holding details are properly formatted."""
        mock_holding_service.get_holdings_by_account_and_date_async.return_value = sample_holdings_response
        tool = create_portfolio_holdings_tool(mock_holding_service, 100)
        
        result = await tool.ainvoke({"date": "2025-01-15"})
        
        holding = result["Holdings"][0]
        assert holding["Ticker"] == "AAPL"
        assert holding["InstrumentName"] == "Apple Inc."
        assert holding["CurrentValue"] == 1500.00
        assert holding["GainLoss"] == 500.00
    
    @pytest.mark.unit
    async def test_get_holdings_no_holdings_returns_error(self, mock_holding_service):
        """Test response when no holdings found."""
        mock_holding_service.get_holdings_by_account_and_date_async.return_value = None
        tool = create_portfolio_holdings_tool(mock_holding_service, 100)
        
        result = await tool.ainvoke({"date": "2025-01-15"})
        
        assert "Error" in result


class TestPortfolioAnalysisToolFactory:
    """Test portfolio analysis tool factory creation."""
    
    @pytest.mark.unit
    def test_create_analysis_tool_returns_structured_tool(self, mock_portfolio_analysis_service):
        """Test that factory returns a StructuredTool."""
        tool = create_portfolio_analysis_tool(mock_portfolio_analysis_service, 100)
        
        assert tool is not None
        assert tool.name == "analyze_portfolio_performance"
        assert "portfolio" in tool.description.lower()


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
        tool = create_portfolio_analysis_tool(mock_portfolio_analysis_service, 100)
        
        result = await tool.ainvoke({"analysis_date": "2025-01-15"})
        
        assert result == expected_analysis
    
    @pytest.mark.unit
    async def test_analyze_performance_handles_today_keyword(
        self, mock_portfolio_analysis_service
    ):
        """Test that 'today' keyword is handled correctly."""
        mock_portfolio_analysis_service.analyze_portfolio_performance_async.return_value = {
            "AccountId": 100,
            "TotalValue": 1500.00
        }
        tool = create_portfolio_analysis_tool(mock_portfolio_analysis_service, 100)
        
        result = await tool.ainvoke({"analysis_date": "today"})
        
        assert "Error" not in result
        mock_portfolio_analysis_service.analyze_portfolio_performance_async.assert_called_once()


# ---------------------------------------------------------------------------
# Tavily market intelligence tools
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_tavily_service():
    """Mock TavilyService for testing."""
    mock = Mock(spec=TavilyService)
    mock.search_recent_news = AsyncMock()
    mock.research_company_fundamentals = AsyncMock()
    mock.get_company_overview = AsyncMock()
    mock.get_market_overview = AsyncMock()
    return mock


class TestMarketIntelligenceToolFactory:
    """Test market intelligence tool factory creation."""

    @pytest.mark.unit
    def test_creates_four_structured_tools(self, mock_tavily_service):
        news, fundamentals, overview, market = create_market_intelligence_tools(
            mock_tavily_service
        )
        assert news.name == "search_recent_news"
        assert fundamentals.name == "research_company_fundamentals"
        assert overview.name == "get_company_overview"
        assert market.name == "get_market_overview"

    @pytest.mark.unit
    def test_two_instances_are_independent(self, mock_tavily_service):
        tools_a = create_market_intelligence_tools(mock_tavily_service)
        tools_b = create_market_intelligence_tools(mock_tavily_service)
        assert tools_a[0] is not tools_b[0]

    @pytest.mark.unit
    def test_accepts_none_service(self):
        tools = create_market_intelligence_tools(None)
        assert len(tools) == 4


class TestSearchRecentNewsTool:
    """Test search_recent_news tool execution."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_successful_execution(self, mock_tavily_service):
        mock_tavily_service.search_recent_news.return_value = {
            "answer": "Apple news summary",
            "results": [{"title": "Apple Q1", "url": "http://example.com", "content": "...", "published_date": "2025-01-01"}],
        }
        news_tool, _, _, _ = create_market_intelligence_tools(mock_tavily_service)
        result = await news_tool.ainvoke({"tickers": ["AAPL"]})

        assert result["Status"] == "Success"
        assert result["Answer"] == "Apple news summary"
        assert len(result["Results"]) == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_not_configured_when_service_is_none(self):
        news_tool, _, _, _ = create_market_intelligence_tools(None)
        result = await news_tool.ainvoke({"tickers": ["AAPL"]})

        assert result["Status"] == "NotConfigured"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_error_when_tavily_returns_none(self, mock_tavily_service):
        mock_tavily_service.search_recent_news.return_value = None
        news_tool, _, _, _ = create_market_intelligence_tools(mock_tavily_service)
        result = await news_tool.ainvoke({"tickers": ["AAPL"]})

        assert result["Status"] == "Error"


class TestResearchCompanyFundamentalsTool:
    """Test research_company_fundamentals tool execution."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_successful_execution(self, mock_tavily_service):
        mock_tavily_service.research_company_fundamentals.return_value = {
            "answer": "P/E is 28, dividend yield 0.5%",
            "results": [{"title": "AAPL Fundamentals", "url": "http://stockanalysis.com"}],
        }
        _, fundamentals_tool, _, _ = create_market_intelligence_tools(mock_tavily_service)
        result = await fundamentals_tool.ainvoke({"ticker": "AAPL", "company_name": "Apple"})

        assert result["Status"] == "Success"
        assert result["Ticker"] == "AAPL"
        assert "P/E" in result["Summary"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_not_configured_when_service_is_none(self):
        _, fundamentals_tool, _, _ = create_market_intelligence_tools(None)
        result = await fundamentals_tool.ainvoke({"ticker": "AAPL"})

        assert result["Status"] == "NotConfigured"


class TestGetCompanyOverviewTool:
    """Test get_company_overview tool execution."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_successful_execution(self, mock_tavily_service):
        mock_tavily_service.get_company_overview.return_value = {
            "answer": "Apple designs consumer electronics",
            "results": [],
        }
        _, _, overview_tool, _ = create_market_intelligence_tools(mock_tavily_service)
        result = await overview_tool.ainvoke({"ticker": "AAPL", "company_name": "Apple"})

        assert result["Status"] == "Success"
        assert result["Overview"] == "Apple designs consumer electronics"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_not_configured_when_service_is_none(self):
        _, _, overview_tool, _ = create_market_intelligence_tools(None)
        result = await overview_tool.ainvoke({"ticker": "AAPL"})

        assert result["Status"] == "NotConfigured"


class TestGetMarketOverviewTool:
    """Test get_market_overview tool execution."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_successful_execution(self, mock_tavily_service):
        mock_tavily_service.get_market_overview.return_value = {
            "answer": "Markets up today",
            "results": [{"title": "Markets rally", "url": "http://reuters.com", "content": "...", "published_date": "2025-01-01"}],
        }
        _, _, _, market_tool = create_market_intelligence_tools(mock_tavily_service)
        result = await market_tool.ainvoke({})

        assert result["Status"] == "Success"
        assert result["MarketSummary"] == "Markets up today"
        assert len(result["NewsItems"]) == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_accepts_optional_focus(self, mock_tavily_service):
        mock_tavily_service.get_market_overview.return_value = {"answer": "UK up", "results": []}
        _, _, _, market_tool = create_market_intelligence_tools(mock_tavily_service)
        result = await market_tool.ainvoke({"focus": "UK markets"})

        assert result["Status"] == "Success"
        mock_tavily_service.get_market_overview.assert_called_once_with("UK markets")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_not_configured_when_service_is_none(self):
        _, _, _, market_tool = create_market_intelligence_tools(None)
        result = await market_tool.ainvoke({})

        assert result["Status"] == "NotConfigured"
