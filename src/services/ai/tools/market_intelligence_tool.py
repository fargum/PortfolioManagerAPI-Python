"""
LangChain tools for market intelligence via Tavily web search.
Uses factory pattern to create tools per-request, avoiding global state race conditions.

Four tools are provided:
- search_recent_news: past-week news for specific tickers
- research_company_fundamentals: P/E, EPS, dividends, analyst ratings
- get_company_overview: business model and competitive position
- get_market_overview: daily market conditions and top financial news
"""
import logging
from typing import List, Optional, Tuple

from langchain_core.tools import StructuredTool

from src.services.tavily_service import TavilyService

logger = logging.getLogger(__name__)

_NOT_CONFIGURED = {
    "Status": "NotConfigured",
    "Message": "Market intelligence service is not configured. Please set TAVILY_API_KEY.",
}


def _format_news_items(results: list[dict]) -> list[str]:
    """Pre-format news results as markdown links, matching C# service output."""
    items = []
    for r in results:
        title = r.get("title", "")
        url = r.get("url", "")
        if title and url:
            items.append(f"[{title}]({url})")
        elif title:
            items.append(title)
    return items


def create_market_intelligence_tools(
    tavily_service: Optional[TavilyService],
) -> Tuple[StructuredTool, StructuredTool, StructuredTool, StructuredTool]:
    """
    Factory function to create market intelligence tools with a bound TavilyService.
    Creates new tool instances per-request to avoid global state race conditions.

    Args:
        tavily_service: Tavily service instance (can be None if not configured)

    Returns:
        Tuple of (search_recent_news, research_company_fundamentals,
                  get_company_overview, get_market_overview)
    """

    async def search_recent_news(
        tickers: List[str], company_names: str = ""
    ) -> dict:
        """Search for recent news articles about specific stock tickers from the past week.

        ALWAYS USE THIS TOOL when the user asks about: news, headlines, updates,
        "what's happening", articles about ANY stock or company.

        Args:
            tickers: List of stock ticker symbols (e.g. ['AAPL', 'MSFT', 'TSLA'])
            company_names: Optional company names to improve search accuracy
                           (e.g. 'Apple Microsoft Tesla')

        Returns:
            Dictionary with Status, answer summary, and results list.
            Each result contains title, url, content, and published_date.
        """
        if not tavily_service:
            return {**_NOT_CONFIGURED, "News": []}
        try:
            data = await tavily_service.search_recent_news(tickers, company_names)
            if not data:
                return {
                    "Status": "Error",
                    "Message": "No data returned from Tavily",
                    "News": [],
                }
            return {
                "Status": "Success",
                "Summary": data.get("answer", ""),
                "News": _format_news_items(data.get("results", [])),
                "INSTRUCTION": "You MUST include these news links in your response using their exact markdown format [Title](URL). Do NOT strip the URLs.",
            }
        except Exception as exc:
            logger.error("Error in search_recent_news: %s", exc, exc_info=True)
            return {"Status": "Error", "Message": str(exc)}

    async def research_company_fundamentals(
        ticker: str, company_name: str = ""
    ) -> dict:
        """Research company fundamentals: P/E ratio, EPS, dividend yield, analyst ratings,
        price targets, earnings history.

        USE THIS TOOL when the user asks about: P/E ratio, earnings per share, dividends,
        analyst ratings, price targets, fundamentals, valuation for a specific company.

        Args:
            ticker: Stock ticker symbol (e.g. 'AAPL')
            company_name: Company name to improve search accuracy (e.g. 'Apple')

        Returns:
            Dictionary with Status, AI-generated fundamentals summary, and source list.
        """
        if not tavily_service:
            return {**_NOT_CONFIGURED, "Sources": []}
        try:
            data = await tavily_service.research_company_fundamentals(
                ticker, company_name
            )
            if not data:
                return {
                    "Status": "Error",
                    "Message": "No data returned from Tavily",
                    "Sources": [],
                }
            return {
                "Status": "Success",
                "Ticker": ticker,
                "Summary": data.get("answer", ""),
                "Sources": _format_news_items(data.get("results", [])),
                "INSTRUCTION": "You MUST include these source links in your response using their exact markdown format [Title](URL). Do NOT strip the URLs.",
            }
        except Exception as exc:
            logger.error(
                "Error in research_company_fundamentals: %s", exc, exc_info=True
            )
            return {"Status": "Error", "Message": str(exc)}

    async def get_company_overview(
        ticker: str, company_name: str = ""
    ) -> dict:
        """Get a company overview including business model, competitive position,
        and recent strategic developments.

        USE THIS TOOL when the user asks about: what a company does, its business model,
        competitive advantages, strategic direction, recent developments.

        Args:
            ticker: Stock ticker symbol (e.g. 'AAPL')
            company_name: Company name to improve search accuracy (e.g. 'Apple')

        Returns:
            Dictionary with Status, AI-generated overview summary, and source list.
        """
        if not tavily_service:
            return {**_NOT_CONFIGURED, "Sources": []}
        try:
            data = await tavily_service.get_company_overview(ticker, company_name)
            if not data:
                return {
                    "Status": "Error",
                    "Message": "No data returned from Tavily",
                    "Sources": [],
                }
            return {
                "Status": "Success",
                "Ticker": ticker,
                "Overview": data.get("answer", ""),
                "Sources": _format_news_items(data.get("results", [])),
                "INSTRUCTION": "You MUST include these source links in your response using their exact markdown format [Title](URL). Do NOT strip the URLs.",
            }
        except Exception as exc:
            logger.error("Error in get_company_overview: %s", exc, exc_info=True)
            return {"Status": "Error", "Message": str(exc)}

    async def get_market_overview(focus: Optional[str] = None) -> dict:
        """Get current market conditions, major index movements, and top financial news.

        USE THIS TOOL when the user asks about: market conditions today, how the market
        is doing, major indices (S&P 500, FTSE, Dow), market sentiment, general market news.

        Args:
            focus: Optional focus area to narrow results
                   (e.g. 'UK markets', 'tech sector', 'emerging markets')

        Returns:
            Dictionary with Status, AI-generated market summary, and news items.
        """
        if not tavily_service:
            return {**_NOT_CONFIGURED, "News": []}
        try:
            data = await tavily_service.get_market_overview(focus)
            if not data:
                return {
                    "Status": "Error",
                    "Message": "No data returned from Tavily",
                    "News": [],
                }
            return {
                "Status": "Success",
                "Summary": data.get("answer", ""),
                "News": _format_news_items(data.get("results", [])),
                "INSTRUCTION": "You MUST include these news links in your response using their exact markdown format [Title](URL). Do NOT strip the URLs.",
            }
        except Exception as exc:
            logger.error("Error in get_market_overview: %s", exc, exc_info=True)
            return {"Status": "Error", "Message": str(exc)}

    search_recent_news_tool = StructuredTool.from_function(
        coroutine=search_recent_news,
        name="search_recent_news",
        description=(
            "Search for recent news articles about specific stock tickers from the past week. "
            "ALWAYS USE THIS TOOL when the user asks about news, headlines, or updates "
            "for any stock or company."
        ),
    )

    research_company_fundamentals_tool = StructuredTool.from_function(
        coroutine=research_company_fundamentals,
        name="research_company_fundamentals",
        description=(
            "Research company fundamentals including P/E ratio, EPS, dividend yield, "
            "analyst ratings, and price targets. Use when asked about valuation or financials."
        ),
    )

    get_company_overview_tool = StructuredTool.from_function(
        coroutine=get_company_overview,
        name="get_company_overview",
        description=(
            "Get a company overview including business model, competitive position, "
            "and recent strategic developments."
        ),
    )

    get_market_overview_tool = StructuredTool.from_function(
        coroutine=get_market_overview,
        name="get_market_overview",
        description=(
            "Get current market conditions, major index movements, and top financial news. "
            "Use when the user asks how the market is doing today or about general market news."
        ),
    )

    return (
        search_recent_news_tool,
        research_company_fundamentals_tool,
        get_company_overview_tool,
        get_market_overview_tool,
    )
