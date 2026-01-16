"""
LangChain tool for fetching real-time stock prices.
Uses factory pattern to create tools per-request, avoiding global state race conditions.
"""
import logging
from typing import List, Optional

from langchain_core.tools import StructuredTool

from src.services.eod_market_data_tool import EodMarketDataTool

logger = logging.getLogger(__name__)


def create_real_time_prices_tool(eod_tool: Optional[EodMarketDataTool]) -> StructuredTool:
    """
    Factory function to create a real-time prices tool with bound EOD tool.
    Creates a new tool instance per-request to avoid global state race conditions.
    
    Args:
        eod_tool: Configured EodMarketDataTool instance (can be None if not configured)
        
    Returns:
        StructuredTool configured for this specific request context
    """
    
    async def get_real_time_prices(tickers: List[str]) -> dict:
        """Get real-time stock prices for specific ticker symbols.
        
        Fetches current market prices for the requested stock tickers from EOD Historical Data API.
        Returns a dictionary mapping each ticker to its current price in USD.
        
        Args:
            tickers: List of stock ticker symbols (e.g., ["AAPL.US", "MSFT.US", "GOOGL.US"])
        
        Returns:
            Dictionary with:
            - Status: Success or error status
            - Prices: Dictionary mapping ticker symbols to their current prices
            - Message: Informational message about the request
        
        Example:
            >>> await get_real_time_prices(["AAPL.US", "MSFT.US"])
            {
                "Status": "Success",
                "Prices": {
                    "AAPL.US": 178.50,
                    "MSFT.US": 380.25
                },
                "Message": "Retrieved 2 real-time prices"
            }
        """
        if eod_tool is None:
            logger.error("Real-time prices tool not initialized with EodMarketDataTool")
            return {
                "Status": "Error",
                "Prices": {},
                "Message": "Real-time pricing service is not configured. Please contact support."
            }
        
        if not tickers:
            logger.warning("get_real_time_prices called with empty ticker list")
            return {
                "Status": "Error",
                "Prices": {},
                "Message": "No ticker symbols provided. Please specify at least one ticker."
            }
        
        try:
            logger.info(f"Fetching real-time prices for {len(tickers)} tickers: {tickers}")
            
            # Fetch prices using the EOD tool
            prices = await eod_tool.get_real_time_prices_async(tickers)
            
            # Convert Decimal to float for JSON serialization
            prices_dict = {ticker: float(price) for ticker, price in prices.items()}
            
            logger.info(f"Successfully retrieved {len(prices_dict)} prices out of {len(tickers)} requested")
            
            return {
                "Status": "Success",
                "Prices": prices_dict,
                "Message": f"Retrieved {len(prices_dict)} real-time prices out of {len(tickers)} requested tickers"
            }
            
        except Exception as ex:
            logger.error(f"Error fetching real-time prices: {ex}", exc_info=True)
            return {
                "Status": "Error",
                "Prices": {},
                "Message": f"Failed to retrieve real-time prices: {str(ex)}"
            }
    
    return StructuredTool.from_function(
        coroutine=get_real_time_prices,
        name="get_real_time_prices",
        description=(
            "Get real-time stock prices for specific ticker symbols. "
            "Fetches current market prices from EOD Historical Data API. "
            "Pass tickers as a list of stock symbols (e.g., ['AAPL.US', 'MSFT.US'])."
        )
    )
