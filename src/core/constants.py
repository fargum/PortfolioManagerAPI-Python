"""
Constants for currencies, exchanges, and portfolio calculations.
"""

class CurrencyConstants:
    """Currency codes and quote units."""
    
    # British Pound Sterling
    GBP = "GBP"
    
    # British Pence (1/100th of a pound)
    GBX = "GBX"
    
    # United States Dollar
    USD = "USD"
    
    # Euro
    EUR = "EUR"
    
    # Default base currency for portfolio calculations
    DEFAULT_BASE_CURRENCY = GBP
    
    # Default quote unit when not specified
    DEFAULT_QUOTE_UNIT = GBP


class ExchangeConstants:
    """Exchange suffixes and special ticker constants."""
    
    # Exchange suffixes
    LSE_SUFFIX = ".L"          # London Stock Exchange
    LONDON_SUFFIX = ".LSE"     # London Stock Exchange (alternate)
    US_SUFFIX = ".US"          # US Markets
    PARIS_SUFFIX = ".PA"       # Euronext Paris
    DEUTSCHE_SUFFIX = ".DE"    # Deutsche Börse
    
    # Special tickers
    CASH_TICKER = "CASH"
    ISF_TICKER = "ISF.LSE"
    
    # Scaling factors for proxy instruments. I have a proxy instrument ISF.LSE because EOF does not track
    # the actual instrument of this holding. I use this scaling factor to adjust the valuation accordingly.
    ISF_SCALING_FACTOR = 3.362  # ISF requires 3.362x scaling
