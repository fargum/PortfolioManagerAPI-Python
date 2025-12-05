"""
LangChain tool for market intelligence (stub implementation).
"""
import logging
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def get_market_context() -> dict:
    """Get current market context and conditions.
    
    Provides overview of current market conditions, major indices, and key economic factors.
    This is a stub implementation that returns placeholder data.
    
    Note: Future enhancements will integrate with real market data APIs.
    """
    logger.info("Getting market context (stub)")
    return {
        "Status": "Stub",
        "Message": "Market intelligence integration is not yet implemented. This is a placeholder for future market data integration.",
        "MarketSummary": "Market intelligence requires external API integration"
    }


@tool
def get_market_sentiment() -> dict:
    """Get current market sentiment analysis.
    
    Provides sentiment analysis of market conditions based on recent trends and indicators.
    This is a stub implementation that returns placeholder data.
    
    Note: Future enhancements will integrate with real sentiment analysis APIs.
    """
    logger.info("Getting market sentiment (stub)")
    return {
        "Status": "Stub",
        "Message": "Market sentiment analysis is not yet implemented. This is a placeholder for future sentiment analysis integration.",
        "OverallScore": 0.0,
        "Label": "Neutral"
    }
