"""EOD Historical Data real-time pricing tool."""
import logging
import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime, date
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
    
    async def get_financial_news_async(
        self, 
        tickers: List[str], 
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        limit: int = 10
    ) -> List[dict]:
        """
        Get real financial news from EOD Historical Data.
        
        Args:
            tickers: Stock tickers to get news for
            from_date: Start date for news search (not used by EOD news API)
            to_date: End date for news search (not used by EOD news API)
            limit: Maximum number of news items to return
            
        Returns:
            List of news items with Title, Summary, Source, PublishedDate, Url, RelatedTickers
        """
        try:
            logger.info(f"Fetching financial news from EOD for tickers: {', '.join(tickers)}")
            
            if not self.api_token:
                logger.warning("EOD API token not configured, returning empty news")
                return []
            
            # Clean ticker symbols - remove exchange suffixes (.LSE, .US, .L, etc.)
            cleaned_tickers = [
                ticker[:dot_index] if (dot_index := ticker.rfind('.')) > 0 else ticker
                for ticker in tickers
            ]
            
            if not cleaned_tickers:
                logger.warning("No valid tickers for news fetch")
                return []
            
            # Use EOD's news API: https://eodhd.com/api/news?s=ticker1,ticker2&offset=0&limit=10&api_token=TOKEN&fmt=json
            ticker_param = ",".join(cleaned_tickers)
            url = f"{self.base_url}/news"
            params: Dict[str, str | int] = {
                "s": ticker_param,
                "offset": 0,
                "limit": limit,
                "api_token": self.api_token,
                "fmt": "json"
            }
            
            logger.info(f"Fetching news from EOD API")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    json_content = response.json()
                    return self._parse_news_response(json_content)
                else:
                    logger.warning(
                        f"HTTP error fetching news: {response.status_code} - {response.reason_phrase}"
                    )
                    return []
                    
        except Exception as ex:
            logger.error(f"Error fetching financial news from EOD: {ex}", exc_info=True)
            return []
    
    def _parse_news_response(self, json_data: Any) -> List[dict]:
        """
        Parse news response from EOD API.
        
        Args:
            json_data: JSON response from EOD news API
            
        Returns:
            List of parsed news items
        """
        try:
            logger.info(f"Parsing EOD news response")
            
            if isinstance(json_data, list):
                news_list = [
                    parsed for item in json_data
                    if (parsed := self._parse_single_news_item(item))
                ]
            elif isinstance(json_data, dict):
                # Single news item
                parsed = self._parse_single_news_item(json_data)
                news_list = [parsed] if parsed else []
            else:
                news_list = []
            
            logger.info(f"Parsed {len(news_list)} news items from EOD response")
            return news_list
            
        except Exception as ex:
            logger.error(f"Error parsing news response: {ex}", exc_info=True)
            return []
    
    def _parse_single_news_item(self, item: dict) -> Optional[dict]:
        """
        Parse a single news item from EOD response.
        
        Args:
            item: Single news item from JSON
            
        Returns:
            Parsed news item dict or None
        """
        try:
            title = item.get("title", "No Title")
            content = item.get("content", "")
            link = item.get("link", "")
            date_str = item.get("date", "")
            
            # Handle symbols as either string or array
            symbols_list = []
            symbols = item.get("symbols")
            if isinstance(symbols, str):
                symbols_list = [s.strip() for s in symbols.split(",") if s.strip()]
            elif isinstance(symbols, list):
                symbols_list = [str(s).strip() for s in symbols if s]
            
            # Parse published date
            published_date = datetime.utcnow()
            if date_str:
                try:
                    published_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except Exception:
                    pass
            
            return {
                "Title": title,
                "Summary": content,
                "Source": "EOD Historical Data",
                "PublishedDate": published_date.isoformat(),
                "Url": link,
                "RelatedTickers": symbols_list,
                "SentimentScore": 0.0,  # EOD doesn't provide sentiment in basic news
                "Category": "Financial News"
            }
            
        except Exception as ex:
            logger.error(f"Error parsing individual news item: {ex}", exc_info=True)
            return None
    
    async def get_market_sentiment_async(
        self, 
        tickers: List[str], 
        target_date: date
    ) -> dict:
        """
        Get market sentiment data from EOD Historical Data.
        
        Args:
            tickers: Stock tickers for sentiment analysis
            target_date: Date for sentiment data
            
        Returns:
            Market sentiment data with OverallSentimentScore, SentimentLabel, FearGreedIndex
        """
        try:
            logger.info(f"Fetching market sentiment from EOD for tickers: {', '.join(tickers)}")
            
            if not self.api_token:
                logger.warning("EOD API token not configured, returning default neutral sentiment")
                return self._create_default_sentiment_response(target_date)
            
            if not tickers:
                logger.warning("No tickers provided for sentiment analysis")
                return self._create_default_sentiment_response(target_date)
            
            # Use the first ticker for sentiment analysis
            ticker = tickers[0]
            from_date = (target_date.replace(day=target_date.day - 7) if target_date.day > 7 
                        else target_date.replace(month=target_date.month - 1 if target_date.month > 1 else 12))
            from_str = from_date.strftime("%Y-%m-%d")
            to_str = target_date.strftime("%Y-%m-%d")
            
            url = "https://eodhd.com/api/sentiments"
            params = {
                "s": ticker,
                "from": from_str,
                "to": to_str,
                "api_token": self.api_token,
                "fmt": "json"
            }
            
            logger.info(f"Fetching sentiment data from EOD API for ticker {ticker}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                
                logger.info(f"EOD API response status: {response.status_code} for ticker {ticker}")
                
                if response.status_code != 200:
                    logger.warning(f"HTTP error fetching sentiment: {response.status_code}")
                    return self._create_default_sentiment_response(target_date)
                
                json_content = response.json()
                
                if not json_content or json_content == []:
                    logger.warning(f"Empty or no sentiment data from EOD API for ticker {ticker}")
                    # Fallback to price-based sentiment
                    return await self._create_price_based_sentiment_async(ticker, target_date)
                
                sentiment_data = self._parse_sentiment_response(json_content, target_date)
                if sentiment_data:
                    logger.info(
                        f"Successfully retrieved sentiment data for ticker {ticker}. "
                        f"Score: {sentiment_data['OverallSentimentScore']}, "
                        f"Label: {sentiment_data['SentimentLabel']}"
                    )
                    return sentiment_data
                else:
                    logger.warning(f"Failed to parse sentiment data for ticker {ticker}")
                    return self._create_default_sentiment_response(target_date)
                    
        except Exception as ex:
            logger.error(f"Error fetching market sentiment from EOD: {ex}", exc_info=True)
            return self._create_default_sentiment_response(target_date)
    
    def _parse_sentiment_response(self, json_data: Any, target_date: date) -> Optional[dict]:
        """
        Parse sentiment response from EOD API.
        EOD returns format: {"TICKER": [{"date": "2022-04-22", "count": 2, "normalized": 0.822}]}
        where normalized is sentiment score from -1 (very negative) to +1 (very positive)
        """
        try:
            if isinstance(json_data, dict):
                # Get the first (and usually only) ticker's sentiment array
                for ticker_key, sentiment_array in json_data.items():
                    if isinstance(sentiment_array, list) and sentiment_array:
                        # Calculate average normalized sentiment score from recent data
                        recent_sentiments = sentiment_array[:10]  # Use last 10 days
                        avg_normalized_score = 0.0
                        valid_count = 0
                        
                        for sentiment in recent_sentiments:
                            normalized = sentiment.get("normalized")
                            if normalized is not None:
                                avg_normalized_score += float(normalized)
                                valid_count += 1
                        
                        if valid_count == 0:
                            return None
                        
                        avg_normalized_score /= valid_count
                        
                        # Convert EOD's -1 to +1 scale to our 0 to 1 scale
                        sentiment_score = (avg_normalized_score + 1.0) / 2.0
                        sentiment_score = max(0.0, min(1.0, sentiment_score))
                        
                        if sentiment_score >= 0.7:
                            sentiment_label = "Very Positive"
                        elif sentiment_score >= 0.6:
                            sentiment_label = "Positive"
                        elif sentiment_score >= 0.4:
                            sentiment_label = "Neutral"
                        elif sentiment_score >= 0.3:
                            sentiment_label = "Negative"
                        else:
                            sentiment_label = "Very Negative"
                        
                        # Calculate Fear & Greed index (0-100) from sentiment
                        fear_greed_index = avg_normalized_score * 50 + 50
                        fear_greed_index = max(0.0, min(100.0, fear_greed_index))
                        
                        return {
                            "Date": target_date.isoformat(),
                            "OverallSentimentScore": Decimal(str(sentiment_score)),
                            "SentimentLabel": sentiment_label,
                            "FearGreedIndex": Decimal(str(fear_greed_index))
                        }
            
            return None
            
        except Exception as ex:
            logger.error(f"Error parsing sentiment response: {ex}", exc_info=True)
            return None
    
    def _create_default_sentiment_response(self, target_date: date) -> dict:
        """Create default neutral sentiment response."""
        return {
            "Date": target_date.isoformat(),
            "OverallSentimentScore": Decimal("0.5"),
            "SentimentLabel": "Neutral - EOD API token not configured or data unavailable",
            "FearGreedIndex": Decimal("50.0")
        }
    
    async def _create_price_based_sentiment_async(self, ticker: str, target_date: date) -> dict:
        """
        Create sentiment analysis based on recent price movements when sentiment data is unavailable.
        """
        try:
            logger.info(f"Creating price-based sentiment for {ticker} using recent price data")
            
            # Get recent price data for the last 10 trading days
            to_date_str = target_date.strftime("%Y-%m-%d")
            from_date = target_date.replace(day=target_date.day - 10) if target_date.day > 10 else target_date
            from_date_str = from_date.strftime("%Y-%m-%d")
            
            url = f"https://eodhd.com/api/eod/{ticker}"
            params = {
                "from": from_date_str,
                "to": to_date_str,
                "api_token": self.api_token,
                "fmt": "json",
                "period": "d"
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                
                if response.status_code != 200:
                    logger.warning(f"Failed to fetch price data for {ticker}, status: {response.status_code}")
                    return self._create_default_sentiment_response(target_date)
                
                price_data = response.json()
                
                if not price_data or price_data == []:
                    logger.warning(f"No price data available for {ticker}")
                    return self._create_default_sentiment_response(target_date)
                
                # Analyze price movement
                return self._analyze_price_movement(price_data, ticker, target_date)
                
        except Exception as ex:
            logger.error(f"Error creating price-based sentiment for {ticker}: {ex}", exc_info=True)
            return self._create_default_sentiment_response(target_date)
    
    def _analyze_price_movement(self, price_data: List[dict], ticker: str, target_date: date) -> dict:
        """Analyze price movement to derive sentiment."""
        try:
            if len(price_data) < 2:
                return self._create_default_sentiment_response(target_date)
            
            # Get the most recent prices (last 5 days)
            recent = price_data[-5:] if len(price_data) >= 5 else price_data
            latest = recent[-1]
            previous = recent[-2]
            
            latest_price = Decimal(str(latest.get("close", 0)))
            previous_price = Decimal(str(previous.get("close", 0)))
            
            if previous_price == 0:
                return self._create_default_sentiment_response(target_date)
            
            # Calculate percentage change
            change_percent = ((latest_price - previous_price) / previous_price) * 100
            
            # Calculate multi-day trend
            first_price = Decimal(str(recent[0].get("close", 0)))
            overall_change_percent = ((latest_price - first_price) / first_price) * 100 if first_price != 0 else Decimal("0")
            
            # Determine sentiment based on price movement
            if change_percent <= -10:
                sentiment_score = Decimal("0.1")
                sentiment_label = "Very Negative (Price-based analysis)"
            elif change_percent <= -5:
                sentiment_score = Decimal("0.25")
                sentiment_label = "Negative (Price-based analysis)"
            elif change_percent <= -2:
                sentiment_score = Decimal("0.4")
                sentiment_label = "Bearish (Price-based analysis)"
            elif change_percent <= 2:
                sentiment_score = Decimal("0.5")
                sentiment_label = "Neutral (Price-based analysis)"
            elif change_percent <= 5:
                sentiment_score = Decimal("0.6")
                sentiment_label = "Bullish (Price-based analysis)"
            elif change_percent <= 10:
                sentiment_score = Decimal("0.75")
                sentiment_label = "Positive (Price-based analysis)"
            else:
                sentiment_score = Decimal("0.9")
                sentiment_label = "Very Positive (Price-based analysis)"
            
            fear_greed_index = sentiment_score * 100
            
            return {
                "Date": target_date.isoformat(),
                "OverallSentimentScore": sentiment_score,
                "SentimentLabel": sentiment_label,
                "FearGreedIndex": fear_greed_index,
                "PriceChange": float(change_percent),
                "MultiDayChange": float(overall_change_percent)
            }
            
        except Exception as ex:
            logger.error(f"Error parsing price data for sentiment analysis: {ex}", exc_info=True)
            return self._create_default_sentiment_response(target_date)
