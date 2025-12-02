"""EOD Historical Data real-time pricing tool."""
import logging
import asyncio
from typing import Dict, List
import httpx
from decimal import Decimal

logger = logging.getLogger(__name__)


class EodMarketDataTool:
    """Tool for fetching real-time market data from EOD Historical Data API."""
    
    def __init__(self, api_token: str, base_url: str = "https://eodhd.com/api", timeout_seconds: int = 30):
        """
        Initialize EOD Market Data Tool.
        
        Args:
            api_token: EOD Historical Data API token
            base_url: Base URL for EOD API (default: https://eodhd.com/api)
            timeout_seconds: Request timeout in seconds (default: 30)
        """
        self.api_token = api_token
        self.base_url = base_url
        self.timeout = timeout_seconds
        self._semaphore = asyncio.Semaphore(10)  # Limit concurrent requests
        
    async def get_real_time_prices_async(self, tickers: List[str]) -> Dict[str, Decimal]:
        """
        Get real-time prices for specific tickers from EOD Historical Data.
        
        Args:
            tickers: List of stock tickers to get prices for
            
        Returns:
            Dictionary mapping ticker to price
        """
        if not self.api_token:
            logger.warning("EOD API token not configured, returning empty prices")
            return {}
            
        if not tickers:
            logger.warning("No tickers provided for real-time pricing")
            return {}
        
        logger.info(f"Fetching real-time prices from EOD for {len(tickers)} tickers: {', '.join(tickers)}")
        
        price_dict: Dict[str, Decimal] = {}
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            tasks = [self._fetch_ticker_price(client, ticker, price_dict) for ticker in tickers]
            await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info(f"Successfully fetched {len(price_dict)} real-time prices out of {len(tickers)} requested")
        return price_dict
    
    async def _fetch_ticker_price(
        self, 
        client: httpx.AsyncClient, 
        ticker: str, 
        price_dict: Dict[str, Decimal]
    ) -> None:
        """
        Fetch price for a single ticker.
        
        Args:
            client: HTTP client
            ticker: Stock ticker
            price_dict: Dictionary to store results (thread-safe with asyncio)
        """
        async with self._semaphore:
            try:
                # Use ticker as provided without formatting
                url = f"{self.base_url}/real-time/{ticker}"
                params = {
                    "api_token": self.api_token,
                    "fmt": "json"
                }
                
                logger.info(f"Fetching real-time price for ticker: {ticker}")
                
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    json_content = response.json()
                    price = self._extract_price_from_response(json_content, ticker)
                    
                    if price is not None:
                        price_dict[ticker] = price
                        logger.info(f"Successfully fetched real-time price for {ticker}: {price}")
                    else:
                        logger.warning(f"No valid price found in response for ticker: {ticker}")
                else:
                    logger.warning(
                        f"HTTP error fetching price for {ticker}: {response.status_code} - {response.reason_phrase}"
                    )
                    
            except Exception as ex:
                logger.error(f"Error fetching real-time price for ticker {ticker}: {ex}", exc_info=True)
    
    def _extract_price_from_response(self, json_data: dict, ticker: str) -> Decimal | None:
        """
        Extract price value from EOD API JSON response.
        
        Args:
            json_data: JSON response from EOD API
            ticker: Ticker symbol for logging
            
        Returns:
            Price as Decimal or None if not found
        """
        try:
            logger.info(f"Parsing EOD response for {ticker}")
            
            # Try different possible price field names
            price_fields = ["close", "price", "last", "current_price", "value"]
            
            for field in price_fields:
                if field in json_data:
                    value = json_data[field]
                    
                    # Handle numeric values
                    if isinstance(value, (int, float)):
                        price = Decimal(str(value))
                        logger.info(f"Extracted price for {ticker} from field '{field}': {price}")
                        return price
                    
                    # Handle string values
                    if isinstance(value, str):
                        try:
                            price = Decimal(value)
                            logger.info(f"Parsed price for {ticker} from string field '{field}': {price}")
                            return price
                        except (ValueError, Exception):
                            continue
            
            logger.warning(
                f"No recognized price field found for ticker: {ticker}. "
                f"Available fields: {', '.join(json_data.keys())}"
            )
            
        except Exception as ex:
            logger.error(f"Error extracting price from element for ticker {ticker}: {ex}", exc_info=True)
        
        return None
