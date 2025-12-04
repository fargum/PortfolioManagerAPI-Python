"""
Pytest configuration and shared fixtures for unit tests.

This module provides common fixtures for unit testing:
- Mock services and dependencies (no real database)
- Sample test data
- FastAPI test client (for future API tests)

Note: Database fixtures are not included because SQLite doesn't support 
PostgreSQL schemas. For integration tests with database, use a real 
PostgreSQL test database.
"""
from datetime import datetime, date
from decimal import Decimal
from unittest.mock import Mock, AsyncMock

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.services.currency_conversion_service import CurrencyConversionService
from src.services.eod_market_data_tool import EodMarketDataTool
from src.services.pricing_calculation_service import PricingCalculationService


# ==================== FastAPI App & Client Fixtures ====================

@pytest.fixture
def test_app():
    """Get the FastAPI application instance."""
    return app


@pytest.fixture
def client(test_app):
    """
    Create a synchronous test client for API endpoint testing.
    Use this for simple endpoint tests that don't require async.
    """
    with TestClient(test_app) as test_client:
        yield test_client


# ==================== Mock Service Fixtures ====================

@pytest.fixture
def mock_eod_tool():
    """
    Mock EOD Market Data Tool for testing without external API calls.
    Returns a mock with common methods pre-configured.
    """
    mock = Mock(spec=EodMarketDataTool)
    mock.get_latest_price = AsyncMock(return_value=150.50)
    mock.get_instrument_info = AsyncMock(return_value={
        "Code": "AAPL",
        "Name": "Apple Inc.",
        "Exchange": "NASDAQ",
        "Currency": "USD"
    })
    return mock


@pytest.fixture
def mock_currency_service():
    """
    Mock Currency Conversion Service for testing without database calls.
    Returns USD to GBP conversion rate of 0.8 by default.
    """
    mock = Mock(spec=CurrencyConversionService)
    mock.get_exchange_rate = AsyncMock(return_value=Decimal("0.8"))
    mock.convert_amount = AsyncMock(return_value=Decimal("80.00"))
    return mock


@pytest.fixture
def mock_pricing_service():
    """Mock Pricing Calculation Service."""
    mock = Mock(spec=PricingCalculationService)
    mock.calculate_current_value = AsyncMock(return_value=Decimal("1500.00"))
    mock.calculate_profit_loss = AsyncMock(return_value={
        "profit_loss": Decimal("100.00"),
        "profit_loss_percentage": Decimal("7.14")
    })
    return mock


# ==================== Sample Test Data Fixtures ====================

@pytest.fixture
def sample_instrument_data():
    """Sample instrument data dictionary for testing."""
    return {
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "description": "Technology company",
        "instrument_type_id": 1,
        "currency_code": "USD",
        "quote_unit": "USD"
    }


@pytest.fixture
def sample_holding_data():
    """Sample holding data dictionary for testing."""
    return {
        "valuation_date": datetime(2025, 12, 4, 0, 0, 0),
        "unit_amount": Decimal("10.0"),
        "bought_value": Decimal("1000.00"),
        "current_value": Decimal("1500.00"),
        "daily_profit_loss": Decimal("50.00"),
        "daily_profit_loss_percentage": Decimal("3.45")
    }
