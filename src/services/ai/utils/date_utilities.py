"""
Date parsing utilities for AI tools.
"""
from datetime import datetime, date, timedelta
from dateutil import parser
import logging

logger = logging.getLogger(__name__)


class DateUtilities:
    """
    Utility class for parsing dates from various formats.
    Supports flexible date parsing for AI tool parameters.
    """
    
    @staticmethod
    def parse_date(date_string: str) -> date:
        """
        Parse a date string in various formats to a date object.
        
        Supports formats:
        - YYYY-MM-DD
        - DD/MM/YYYY
        - DD MMMM YYYY
        - Relative terms: today, yesterday, tomorrow
        
        Args:
            date_string: Date string to parse
        
        Returns:
            date object
        
        Raises:
            ValueError: If date cannot be parsed
        """
        try:
            # Handle relative terms using pattern matching
            match date_string.lower().strip():
                case 'today' | 'current' | 'now':
                    return datetime.now().date()
                case 'yesterday':
                    return (datetime.now() - timedelta(days=1)).date()
                case 'tomorrow':
                    return (datetime.now() + timedelta(days=1)).date()
                case _:
                    # Try parsing with dateutil (handles many formats)
                    # Note: dayfirst=False for ISO format (YYYY-MM-DD) compatibility
                    # ISO format should be preferred, but this handles DD/MM/YYYY too
                    parsed = parser.parse(date_string, dayfirst=False)
                    return parsed.date()
            
        except Exception as e:
            logger.error(f"Failed to parse date '{date_string}': {str(e)}")
            raise ValueError(f"Invalid date format: {date_string}")
    
    @staticmethod
    def parse_date_time(date_string: str) -> datetime:
        """
        Parse a date string in various formats to a datetime object.
        
        Args:
            date_string: Date string to parse
        
        Returns:
            datetime object
        
        Raises:
            ValueError: If date cannot be parsed
        """
        try:
            # Handle relative terms using pattern matching
            match date_string.lower().strip():
                case 'today' | 'current' | 'now':
                    return datetime.now()
                case 'yesterday':
                    return datetime.now() - timedelta(days=1)
                case 'tomorrow':
                    return datetime.now() + timedelta(days=1)
                case _:
                    # Try parsing with dateutil (handles many formats)
                    parsed = parser.parse(date_string, dayfirst=True)
                    return parsed
            
        except Exception as e:
            logger.error(f"Failed to parse datetime '{date_string}': {str(e)}")
            raise ValueError(f"Invalid date format: {date_string}")
