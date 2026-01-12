"""
Unit tests for DateUtilities.

Tests cover:
- Standard date formats (YYYY-MM-DD, DD/MM/YYYY)
- Relative date terms (today, yesterday, tomorrow)
- Edge cases and error handling
"""
import pytest
from datetime import datetime, date, timedelta
from unittest.mock import patch

from src.services.ai.utils.date_utilities import DateUtilities


class TestParseDateISOFormat:
    """Test ISO format date parsing (YYYY-MM-DD)."""
    
    @pytest.mark.unit
    def test_parse_iso_format(self):
        """Test parsing standard ISO format date."""
        result = DateUtilities.parse_date("2025-01-15")
        assert result == date(2025, 1, 15)
    
    @pytest.mark.unit
    def test_parse_iso_format_end_of_year(self):
        """Test parsing ISO date at end of year."""
        result = DateUtilities.parse_date("2025-12-31")
        assert result == date(2025, 12, 31)
    
    @pytest.mark.unit
    def test_parse_iso_format_beginning_of_year(self):
        """Test parsing ISO date at beginning of year."""
        result = DateUtilities.parse_date("2025-01-01")
        assert result == date(2025, 1, 1)


class TestParseDateRelativeTerms:
    """Test relative date term parsing."""
    
    @pytest.mark.unit
    def test_parse_today(self):
        """Test parsing 'today' keyword."""
        with patch('src.services.ai.utils.date_utilities.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 15, 10, 30, 0)
            result = DateUtilities.parse_date("today")
            assert result == date(2025, 1, 15)
    
    @pytest.mark.unit
    def test_parse_current(self):
        """Test parsing 'current' keyword."""
        with patch('src.services.ai.utils.date_utilities.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 15, 10, 30, 0)
            result = DateUtilities.parse_date("current")
            assert result == date(2025, 1, 15)
    
    @pytest.mark.unit
    def test_parse_now(self):
        """Test parsing 'now' keyword."""
        with patch('src.services.ai.utils.date_utilities.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 15, 10, 30, 0)
            result = DateUtilities.parse_date("now")
            assert result == date(2025, 1, 15)
    
    @pytest.mark.unit
    def test_parse_yesterday(self):
        """Test parsing 'yesterday' keyword."""
        with patch('src.services.ai.utils.date_utilities.datetime') as mock_dt:
            mock_now = datetime(2025, 1, 15, 10, 30, 0)
            mock_dt.now.return_value = mock_now
            # timedelta needs to work normally
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            result = DateUtilities.parse_date("yesterday")
            assert result == date(2025, 1, 14)
    
    @pytest.mark.unit
    def test_parse_tomorrow(self):
        """Test parsing 'tomorrow' keyword."""
        with patch('src.services.ai.utils.date_utilities.datetime') as mock_dt:
            mock_now = datetime(2025, 1, 15, 10, 30, 0)
            mock_dt.now.return_value = mock_now
            result = DateUtilities.parse_date("tomorrow")
            assert result == date(2025, 1, 16)
    
    @pytest.mark.unit
    def test_parse_today_case_insensitive(self):
        """Test that relative terms are case insensitive."""
        with patch('src.services.ai.utils.date_utilities.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 15, 10, 30, 0)
            assert DateUtilities.parse_date("TODAY") == date(2025, 1, 15)
            assert DateUtilities.parse_date("Today") == date(2025, 1, 15)
            assert DateUtilities.parse_date("  today  ") == date(2025, 1, 15)


class TestParseDateOtherFormats:
    """Test parsing other common date formats."""
    
    @pytest.mark.unit
    def test_parse_slash_format_mdy(self):
        """Test parsing MM/DD/YYYY format (US style)."""
        # Note: dayfirst=False means it treats as MM/DD/YYYY
        result = DateUtilities.parse_date("01/15/2025")
        assert result == date(2025, 1, 15)
    
    @pytest.mark.unit
    def test_parse_written_format(self):
        """Test parsing written date format."""
        result = DateUtilities.parse_date("15 January 2025")
        assert result == date(2025, 1, 15)
    
    @pytest.mark.unit
    def test_parse_abbreviated_month(self):
        """Test parsing abbreviated month format."""
        result = DateUtilities.parse_date("15 Jan 2025")
        assert result == date(2025, 1, 15)


class TestParseDateErrors:
    """Test error handling for invalid dates."""
    
    @pytest.mark.unit
    def test_invalid_date_raises_error(self):
        """Test that invalid date format raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            DateUtilities.parse_date("not-a-date")
        assert "Invalid date format" in str(exc_info.value)
    
    @pytest.mark.unit
    def test_empty_string_raises_error(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError):
            DateUtilities.parse_date("")


class TestParseDateTimeRelativeTerms:
    """Test parse_date_time with relative terms."""
    
    @pytest.mark.unit
    def test_parse_datetime_today(self):
        """Test parsing 'today' returns datetime."""
        with patch('src.services.ai.utils.date_utilities.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 15, 10, 30, 0)
            result = DateUtilities.parse_date_time("today")
            assert isinstance(result, datetime)
            assert result.date() == date(2025, 1, 15)
    
    @pytest.mark.unit
    def test_parse_datetime_yesterday(self):
        """Test parsing 'yesterday' returns datetime."""
        with patch('src.services.ai.utils.date_utilities.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 15, 10, 30, 0)
            result = DateUtilities.parse_date_time("yesterday")
            assert result.date() == date(2025, 1, 14)
    
    @pytest.mark.unit
    def test_parse_datetime_with_time(self):
        """Test parsing datetime string with time component."""
        result = DateUtilities.parse_date_time("2025-01-15 14:30:00")
        assert result == datetime(2025, 1, 15, 14, 30, 0)
