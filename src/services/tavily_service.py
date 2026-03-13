"""Async client for the Tavily web-search API."""
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class TavilyService:
    """
    Async HTTP wrapper around the Tavily /search endpoint.

    Provides four focused search methods for market intelligence:
    - search_recent_news: past-week news for specific tickers
    - research_company_fundamentals: P/E, EPS, dividends, analyst data
    - get_company_overview: business model and competitive position
    - get_market_overview: daily market conditions and top financial news
    """

    FINANCIAL_DOMAINS = [
        "stockanalysis.com",
        "macrotrends.net",
        "dividendmax.com",
        "hl.co.uk",
        "marketwatch.com",
        "finviz.com",
        "finance.yahoo.com",
    ]

    NEWS_DOMAINS = [
        "reuters.com",
        "finance.yahoo.com",
        "marketwatch.com",
        "cnbc.com",
        "ft.com",
        "bloomberg.com",
        "investing.com",
    ]

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.tavily.com",
        timeout_seconds: int = 30,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def _search(self, payload: dict) -> dict | None:
        """POST /search with Bearer auth. Returns parsed JSON or None on error."""
        url = f"{self._base_url}/search"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload, headers=headers)

            if not response.is_success:
                logger.warning(
                    "Tavily returned %s: %s",
                    response.status_code,
                    response.text[:200],
                )
                return None

            return response.json()

        except Exception as exc:
            logger.error("Tavily request failed: %s", exc, exc_info=True)
            return None

    async def search_recent_news(
        self, tickers: list[str], company_names: str = ""
    ) -> dict | None:
        """Search for recent news articles about the given tickers from the past week."""
        query_parts = " ".join(tickers)
        if company_names:
            query_parts = f"{query_parts} {company_names}"
        query = f"{query_parts} stock news"

        return await self._search(
            {
                "query": query,
                "topic": "news",
                "time_range": "week",
                "max_results": 10,
            }
        )

    async def research_company_fundamentals(
        self, ticker: str, company_name: str = ""
    ) -> dict | None:
        """Research company fundamentals: P/E, EPS, dividends, analyst ratings."""
        name = company_name or ticker
        query = (
            f"{name} {ticker} P/E ratio EPS earnings per share analyst price target "
            f"dividend yield payout ratio ex-dividend date dividend cover 2026"
        )
        return await self._search(
            {
                "query": query,
                "search_depth": "advanced",
                "include_answer": "advanced",
                "max_results": 8,
                "include_domains": self.FINANCIAL_DOMAINS,
            }
        )

    async def get_company_overview(
        self, ticker: str, company_name: str = ""
    ) -> dict | None:
        """Get company overview: business model, competitive position, recent developments."""
        name = company_name or ticker
        query = (
            f"{name} {ticker} company overview business model "
            f"competitive position recent developments 2025"
        )
        return await self._search(
            {
                "query": query,
                "search_depth": "advanced",
                "include_answer": "advanced",
                "max_results": 5,
            }
        )

    async def get_market_overview(self, focus: Optional[str] = None) -> dict | None:
        """Get market conditions, major indices, and top financial news."""
        query = "stock market news today major indices"
        if focus:
            query = f"{query} {focus}"

        return await self._search(
            {
                "query": query,
                "topic": "news",
                "time_range": "day",
                "search_depth": "advanced",
                "include_answer": "advanced",
                "max_results": 10,
                "include_domains": self.NEWS_DOMAINS,
            }
        )
