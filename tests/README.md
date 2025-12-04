# Test Suite Documentation

## Overview

This test suite provides comprehensive testing for the Portfolio Manager API using pytest and related testing tools.

## Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── test_example.py          # Example tests (can be deleted)
├── unit/                    # Unit tests - fast, isolated
│   ├── test_services/       # Service layer tests
│   └── test_models/         # Model tests
├── integration/             # Integration tests - multiple components
└── api/                     # API/E2E tests - full request/response
```

## Running Tests

### Run All Tests
```bash
pytest
```

### Run Specific Test Categories
```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# API tests only
pytest -m api
```

### Run Tests with Coverage
```bash
pytest --cov=src --cov-report=html
# View coverage report: htmlcov/index.html
```

### Run Specific Test File
```bash
pytest tests/unit/test_services/test_holding_service.py
```

### Run Tests in Verbose Mode
```bash
pytest -v
```

## Test Fixtures

### Database Fixtures
- `async_db_session` - Async database session for testing
- `async_db_engine` - Async database engine

**Note:** Due to PostgreSQL schema usage (`app.` schema), SQLite in-memory database has limitations. For full database integration tests, use a real PostgreSQL test database.

### Service Mocks
- `mock_eod_tool` - Mocked EOD Market Data Tool
- `mock_currency_service` - Mocked Currency Conversion Service
- `mock_pricing_service` - Mocked Pricing Calculation Service

### Sample Data
- `sample_instrument_data` - Sample instrument dictionary
- `sample_platform_data` - Sample platform dictionary
- `sample_portfolio_data` - Sample portfolio dictionary
- `sample_holding_data` - Sample holding dictionary

### FastAPI Client
- `client` - Synchronous test client
- `async_client` - Asynchronous test client

## Writing Tests

### Unit Test Example
```python
import pytest
from decimal import Decimal

@pytest.mark.unit
async def test_pricing_calculation(pricing_service, mock_currency_service):
    """Test pricing calculation logic."""
    result = await pricing_service.calculate_value(
        units=Decimal("10"),
        price=Decimal("150.50")
    )
    assert result == Decimal("1505.00")
```

### API Test Example
```python
import pytest

@pytest.mark.api
async def test_get_holdings_endpoint(async_client):
    """Test GET /api/holdings endpoint."""
    response = await async_client.get("/api/holdings/date/2025-12-04")
    assert response.status_code == 200
    data = response.json()
    assert "holdings" in data
```

### Using Mocks
```python
@pytest.mark.unit
async def test_with_mock_eod_tool(mock_eod_tool):
    """Test using mocked external service."""
    # Configure mock return value
    mock_eod_tool.get_latest_price.return_value = Decimal("100.50")
    
    # Test your code that uses the EOD tool
    price = await mock_eod_tool.get_latest_price("AAPL")
    assert price == Decimal("100.50")
    
    # Verify the mock was called
    mock_eod_tool.get_latest_price.assert_called_once_with("AAPL")
```

## Test Markers

Use markers to categorize tests:

- `@pytest.mark.unit` - Unit tests (fast, isolated)
- `@pytest.mark.integration` - Integration tests (multiple components)
- `@pytest.mark.api` - API/E2E tests (full request/response)
- `@pytest.mark.slow` - Tests that take longer to run
- `@pytest.mark.external` - Tests requiring external services

## Dependencies

All test dependencies are in `requirements-dev.txt`:

- `pytest` - Testing framework
- `pytest-asyncio` - Async test support
- `pytest-cov` - Coverage reporting
- `pytest-mock` - Mocking utilities
- `httpx` - HTTP client for testing
- `faker` - Test data generation
- `aiosqlite` - Async SQLite driver for testing

## Best Practices

1. **Keep tests fast** - Use mocks for external dependencies
2. **Test one thing** - Each test should verify one behavior
3. **Use descriptive names** - Test names should describe what they test
4. **Arrange-Act-Assert** - Structure tests clearly
5. **Don't test implementation** - Test behavior, not internals
6. **Use fixtures** - Reuse common setup code
7. **Mark appropriately** - Use markers for test organization

## CI/CD Integration

Tests are configured to run in CI/CD pipelines. The `pytest.ini` file contains all necessary configuration.

### GitHub Actions Example
```yaml
- name: Run tests
  run: |
    pytest --cov=src --cov-report=xml
    
- name: Upload coverage
  uses: codecov/codecov-action@v3
```

## Troubleshooting

### SQLite Schema Issues
If you encounter `unknown database app` errors, this is because SQLite doesn't support PostgreSQL schemas. Options:
1. Use mocks instead of database fixtures
2. Use PostgreSQL test database for integration tests
3. Skip database-dependent tests for unit testing

### Async Issues
Make sure to:
- Use `async def` for async tests
- `await` async function calls
- Use `AsyncMock` for async mocked methods

### Coverage Not Working
Run with coverage explicitly:
```bash
pytest --cov=src --cov-report=term-missing
```

## Next Steps

1. Write unit tests for service layer (`PricingCalculationService`, `CurrencyConversionService`)
2. Write API tests for endpoints
3. Set up integration tests with PostgreSQL test database
4. Implement CI/CD pipeline with automated testing
5. Aim for >80% code coverage
