"""
API-level tests for holdings routes (src/api/routes/holdings.py).

These tests exercise the route handlers through the FastAPI TestClient,
overriding the service/auth dependencies so no real database or auth
provider is required.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from src.api.main import app
from src.api.routes.holdings import get_holding_service
from src.core.auth import get_current_account_id
from src.schemas.holding import AccountHoldingsResponse, PortfolioHoldingDto
from src.services.holding_service import HoldingService
from src.services.metrics_service import MetricsService, get_metrics_service
from src.services.result_objects import DeleteHoldingResult, ErrorCode

ACCOUNT_ID = 100
HOLDING_ID = 1


@pytest.fixture
def mock_holding_service():
    """AsyncMock for HoldingService, spec'd so unknown attrs raise."""
    return AsyncMock(spec=HoldingService)


@pytest.fixture(autouse=True)
def override_dependencies(mock_holding_service):
    """Override auth + service dependencies for every test in this module."""
    app.dependency_overrides[get_current_account_id] = lambda: ACCOUNT_ID
    app.dependency_overrides[get_holding_service] = lambda: mock_holding_service
    app.dependency_overrides[get_metrics_service] = lambda: MetricsService()
    yield
    app.dependency_overrides.clear()


class TestDeleteHolding:
    def test_delete_holding_success_returns_200(self, client, mock_holding_service):
        mock_holding_service.delete_holding_async.return_value = DeleteHoldingResult(
            success=True,
            message="Holding deleted",
            deleted_holding_id=HOLDING_ID,
            deleted_ticker="AAPL",
            portfolio_id=5,
        )

        response = client.delete(f"/api/holdings/{HOLDING_ID}")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["deletedHoldingId"] == HOLDING_ID
        assert body["deletedTicker"] == "AAPL"
        assert body["portfolioId"] == 5
        mock_holding_service.delete_holding_async.assert_awaited_once_with(HOLDING_ID, ACCOUNT_ID)

    @pytest.mark.parametrize(
        "error_code, expected_status",
        [
            (ErrorCode.NOT_FOUND, 404),
            (ErrorCode.NOT_ACCESSIBLE, 404),
            (ErrorCode.VALIDATION_ERROR, 400),
        ],
    )
    def test_delete_holding_error_returns_expected_status(
        self, client, mock_holding_service, error_code, expected_status
    ):
        mock_holding_service.delete_holding_async.return_value = DeleteHoldingResult(
            success=False,
            message="Something went wrong",
            error_code=error_code,
        )

        response = client.delete(f"/api/holdings/{HOLDING_ID}")

        assert response.status_code == expected_status
        assert response.json()["success"] is False


class TestGetHoldingsByDate:
    def test_get_holdings_by_date_success_returns_200(self, client, mock_holding_service):
        valuation_date = date(2024, 1, 15)
        holding = PortfolioHoldingDto(
            holdingId=HOLDING_ID,
            portfolioId=5,
            portfolioName="Test Portfolio",
            platformId=1,
            platformName="Test Platform",
            ticker="AAPL",
            instrumentName="Apple Inc.",
            unitAmount=Decimal("10"),
            boughtValue=Decimal("1000.00"),
            currentValue=Decimal("1500.00"),
            gainLoss=Decimal("500.00"),
            gainLossPercentage=Decimal("50.0"),
            currencyCode="USD",
            valuationDate=valuation_date,
        )
        mock_holding_service.get_holdings_by_account_and_date_async.return_value = AccountHoldingsResponse(
            accountId=ACCOUNT_ID,
            valuationDate=valuation_date,
            holdings=[holding],
            totalHoldings=1,
            totalCurrentValue=Decimal("1500.00"),
            totalBoughtValue=Decimal("1000.00"),
            totalGainLoss=Decimal("500.00"),
            totalGainLossPercentage=Decimal("50.0"),
        )

        response = client.get(f"/api/holdings/date/{valuation_date.isoformat()}")

        assert response.status_code == 200
        body = response.json()
        assert body["totalHoldings"] == 1
        assert body["holdings"][0]["ticker"] == "AAPL"
        assert body["holdings"][0]["currentValue"] == 1500.00
        mock_holding_service.get_holdings_by_account_and_date_async.assert_awaited_once_with(
            ACCOUNT_ID, valuation_date
        )

    def test_get_holdings_by_date_invalid_format_returns_400(self, client, mock_holding_service):
        response = client.get("/api/holdings/date/not-a-date")

        assert response.status_code == 400
        mock_holding_service.get_holdings_by_account_and_date_async.assert_not_awaited()

    def test_get_holdings_by_date_no_holdings_returns_404(self, client, mock_holding_service):
        mock_holding_service.get_holdings_by_account_and_date_async.return_value = None

        response = client.get("/api/holdings/date/2024-01-15")

        assert response.status_code == 404
