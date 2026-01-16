"""
LangChain tool for market intelligence.
Uses factory pattern to create tools per-request, avoiding global state race conditions.
"""
import logging
from datetime import date
from typing import List, Optional, Tuple

from langchain_core.tools import StructuredTool

from src.services.eod_market_data_tool import EodMarketDataTool

logger = logging.getLogger(__name__)


def create_market_intelligence_tools(eod_tool: Optional[EodMarketDataTool]) -> Tuple[StructuredTool, StructuredTool]:
    """
    Factory function to create market intelligence tools with bound EOD tool.
    Creates new tool instances per-request to avoid global state race conditions.
    
    Args:
        eod_tool: EOD market data tool instance (can be None if not configured)
        
    Returns:
        Tuple of (get_market_context_tool, get_market_sentiment_tool)
    """
    
    async def get_market_context(tickers: List[str]) -> dict:
        """Get financial news, headlines, and market updates for specific stocks.
        
        ALWAYS USE THIS TOOL when user mentions: news, headlines, updates, "what's happening", articles about ANY stock or company.
        
        Args:
            tickers: Stock ticker symbols OR company names (e.g., ['AAPL', 'Microsoft', 'GOOGL', 'Tesla'])
                     You can use either ticker symbols (AAPL, MSFT, GOOGL, TSLA) or company names (Apple, Microsoft, Google, Tesla).
                     The API will understand both formats.
        
        Returns:
            Dictionary with Status, Message, and Articles list. Each article contains:
            - Title: Article headline
            - Summary: Article content/description
            - URL: Link to full article
            - PublishedDate: When the article was published
            - RelatedTickers: Tickers mentioned in the article
        """
        if not eod_tool:
            logger.warning("EOD tool not initialized, cannot fetch market news")
            return {
                "Status": "NotConfigured",
                "Message": "Market news service is not configured. Please configure EOD API token.",
                "Articles": []
            }
        
        try:
            logger.info(f"Getting market news for tickers: {', '.join(tickers)}")
            
            news_items = await eod_tool.get_financial_news_async(tickers, limit=10)
            
            return {
                "Status": "Success",
                "Message": f"Retrieved {len(news_items)} news articles",
                "Articles": news_items
            }
            
        except Exception as ex:
            logger.error(f"Error getting market context: {ex}", exc_info=True)
            return {
                "Status": "Error",
                "Message": f"Failed to retrieve market news: {str(ex)}",
                "Articles": []
            }

    async def get_market_sentiment(tickers: List[str]) -> dict:
        """Get market sentiment and investor mood analysis for specific stocks.
        
        ALWAYS USE THIS TOOL when user mentions: sentiment, mood, feeling, opinion, investor confidence about ANY stock or company.
        
        Args:
            tickers: Stock ticker symbols OR company names (e.g., ['AAPL', 'Microsoft', 'Tesla'])
        
        USE THIS TOOL when the user asks about:
        - Sentiment (e.g., "What's the sentiment on Apple?", "How do investors feel about Tesla?")
        - Mood (e.g., "What's the market mood for Microsoft?")
        - Fear/greed (e.g., "Is there fear or greed around this stock?")
        - Investor feelings (e.g., "Are people bullish or bearish on Amazon?")
        
        Returns:
            Dictionary with:
            - Status: Success/Error/NotConfigured
            - Message: Description of results
            - OverallSentimentScore: Decimal 0.0 to 1.0 (0=very negative, 1=very positive)
            - SentimentLabel: Text description (e.g., "Positive", "Neutral")
            - FearGreedIndex: Decimal 0 to 100 (0=extreme fear, 100=extreme greed)
        """
        if not eod_tool:
            logger.warning("EOD tool not initialized, cannot fetch market sentiment")
            return {
                "Status": "NotConfigured",
                "Message": "Market sentiment service is not configured. Please configure EOD API token.",
                "OverallSentimentScore": 0.5,
                "SentimentLabel": "Neutral - Not Configured",
                "FearGreedIndex": 50.0
            }
        
        try:
            if not tickers:
                logger.warning("No tickers provided for sentiment analysis")
                return {
                    "Status": "Error",
                    "Message": "No tickers provided for sentiment analysis",
                    "OverallSentimentScore": 0.5,
                    "SentimentLabel": "Neutral",
                    "FearGreedIndex": 50.0
                }
            
            logger.info(f"Getting market sentiment for tickers: {', '.join(tickers)}")
            
            target_date = date.today()
            sentiment_data = await eod_tool.get_market_sentiment_async(tickers, target_date)
            
            return {
                "Status": "Success",
                "Message": "Sentiment analysis complete",
                **sentiment_data
            }
            
        except Exception as ex:
            logger.error(f"Error getting market sentiment: {ex}", exc_info=True)
            return {
                "Status": "Error",
                "Message": f"Failed to retrieve market sentiment: {str(ex)}",
                "OverallSentimentScore": 0.5,
                "SentimentLabel": "Neutral - Error",
                "FearGreedIndex": 50.0
            }
    
    market_context_tool = StructuredTool.from_function(
        coroutine=get_market_context,
        name="get_market_context",
        description=(
            "Get financial news, headlines, and market updates for specific stocks. "
            "ALWAYS USE THIS TOOL when user mentions: news, headlines, updates, 'what's happening', articles about ANY stock or company. "
            "Pass tickers as a list of stock symbols or company names."
        )
    )
    
    market_sentiment_tool = StructuredTool.from_function(
        coroutine=get_market_sentiment,
        name="get_market_sentiment",
        description=(
            "Get market sentiment and investor mood analysis for specific stocks. "
            "ALWAYS USE THIS TOOL when user mentions: sentiment, mood, feeling, opinion, investor confidence about ANY stock or company. "
            "Returns sentiment score (0-1), label, and Fear & Greed Index (0-100)."
        )
    )
    
    return market_context_tool, market_sentiment_tool
