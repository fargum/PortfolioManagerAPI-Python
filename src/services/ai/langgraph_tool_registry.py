"""
Tool composition for the LangGraph portfolio agent.

Assembles the per-request tool list from individual tool factories. Tools are
built fresh for every request (never cached/global) so that `account_id` is
always closed over per authenticated caller, avoiding cross-account data
leakage under concurrent requests.
"""
import logging
from typing import List, Optional

from langchain_core.tools import BaseTool

from src.services.ai.portfolio_analysis_service import PortfolioAnalysisService
from src.services.ai.tools.market_intelligence_tool import create_market_intelligence_tools
from src.services.ai.tools.portfolio_analysis_tool import create_portfolio_analysis_tool
from src.services.ai.tools.portfolio_comparison_tool import create_portfolio_comparison_tool
from src.services.ai.tools.portfolio_holdings_tool import create_portfolio_holdings_tool
from src.services.ai.tools.real_time_prices_tool import create_real_time_prices_tool
from src.services.holding_service import HoldingService
from src.services.tavily_service import TavilyService

logger = logging.getLogger(__name__)


def build_request_tools(
    account_id: int,
    holding_service: HoldingService,
    portfolio_analysis_service: PortfolioAnalysisService,
    tavily_service: Optional[TavilyService],
) -> List[BaseTool]:
    """
    Create tools with account context and database-backed services.

    Security: account_id is injected from authenticated request, not from AI.

    Args:
        account_id: Authenticated user's account ID
        holding_service: Service for accessing holding data (with DB session)
        portfolio_analysis_service: Service for portfolio analysis (with DB session)
        tavily_service: Optional Tavily service for market intelligence tools

    Returns:
        List of tools configured for this specific request context
    """
    tools: List[BaseTool] = []

    # Create portfolio tools with bound account context
    tools.append(create_portfolio_holdings_tool(holding_service, account_id))
    tools.append(create_portfolio_analysis_tool(portfolio_analysis_service, account_id))
    tools.append(create_portfolio_comparison_tool(portfolio_analysis_service, account_id))

    # Create Tavily-powered market intelligence tools
    news_tool, fundamentals_tool, overview_tool, market_tool = (
        create_market_intelligence_tools(tavily_service)
    )
    tools += [news_tool, fundamentals_tool, overview_tool, market_tool]

    # Real-time prices stay on EOD (Tavily is research/news, not tick data)
    eod_tool = holding_service.eod_tool
    tools.append(create_real_time_prices_tool(eod_tool))

    if tavily_service:
        logger.info(
            f"Created {len(tools)} tools (Tavily market intelligence enabled) "
            f"for account {account_id}"
        )
    else:
        logger.warning(
            f"Created {len(tools)} tools for account {account_id} "
            f"(Tavily not configured — market intelligence tools degraded)"
        )

    return tools
