"""
LangChain tool for market intelligence.
"""
import logging
from datetime import datetime, date
from typing import List, Optional
from langchain_core.tools import tool
from src.services.eod_market_data_tool import EodMarketDataTool

logger = logging.getLogger(__name__)

# Module-level storage for EOD tool
_eod_tool: Optional[EodMarketDataTool] = None


def initialize_market_intelligence_tool(eod_tool: EodMarketDataTool):
    """
    Initialize market intelligence tools with EOD market data tool.
    
    Args:
        eod_tool: EOD market data tool instance
    """
    global _eod_tool
    _eod_tool = eod_tool
    logger.info("Market intelligence tool initialized with EodMarketDataTool")


@tool
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
    
    Example:
        >>> get_market_context(['AAPL', 'MSFT'])
        {
            "Status": "Success",
            "Message": "Retrieved 5 news articles",
            "Articles": [
                {
                    "Title": "Apple Announces New Product",
                    "Summary": "...",
                    "URL": "https://...",
                    "PublishedDate": "2025-12-10T...",
                    "RelatedTickers": ["AAPL"]
                }
            ]
        }
    """
    if not _eod_tool:
        logger.warning("EOD tool not initialized, cannot fetch market news")
        return {
            "Status": "NotConfigured",
            "Message": "Market news service is not configured. Please configure EOD API token.",
            "Articles": []
        }
    
    try:
        logger.info(f"Getting market news for tickers: {', '.join(tickers)}")
        
        news_items = await _eod_tool.get_financial_news_async(tickers, limit=10)
        
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


@tool
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
    
    Analyzes market sentiment using EOD Historical Data sentiment API or price-based analysis.
    Returns sentiment score (0-1), label (Very Negative to Very Positive), and Fear & Greed Index (0-100).
    
    Args:
        tickers: List of stock tickers to analyze sentiment for (uses first ticker)
    
    Returns:
        Dictionary with:
        - Status: Success/Error/NotConfigured
        - Message: Description of results
        - OverallSentimentScore: Decimal 0.0 to 1.0 (0=very negative, 1=very positive)
        - SentimentLabel: Text description (e.g., "Positive", "Neutral")
        - FearGreedIndex: Decimal 0 to 100 (0=extreme fear, 100=extreme greed)
    
    Example:
        >>> get_market_sentiment(['AAPL'])
        {
            "Status": "Success",
            "Message": "Sentiment analysis complete",
            "OverallSentimentScore": 0.65,
            "SentimentLabel": "Positive",
            "FearGreedIndex": 65.0
        }
    """
    if not _eod_tool:
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
        sentiment_data = await _eod_tool.get_market_sentiment_async(tickers, target_date)
        
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
