# Pricing Calculation Service Implementation

## Overview
This document describes the implementation of the PricingCalculationService that handles quote unit conversions, scaling factors, and currency conversions for real-time pricing in the Portfolio Manager API.

## Architecture

### Components Created

1. **src/core/constants.py**
   - `CurrencyConstants`: Currency codes (GBP, GBX, USD, EUR)
   - `ExchangeConstants`: Exchange suffixes (.L, .US, .PA, .DE), special tickers (CASH, ISF), scaling factors

2. **src/services/currency_conversion_service.py**
   - Handles currency conversions between different currencies
   - Currently supports GBX/GBP quote unit conversion (divide by 100)
   - Placeholder for full foreign exchange rate lookups (USD/EUR to GBP)
   - Returns tuple of (converted_amount, exchange_rate, rate_source)

3. **src/services/pricing_calculation_service.py**
   - Core pricing logic that mirrors C# PricingCalculationService
   - Three main methods:
     * `calculate_current_value_async()`: Calculates holding value with quote unit and currency conversion
     * `apply_scaling_factor()`: Handles special ticker scaling (ISF = 1000x multiplier)
     * `get_currency_from_ticker()`: Infers currency from ticker exchange suffix

4. **src/services/holding_service.py** (Modified)
   - Added `pricing_calculation_service` parameter to constructor
   - Updated query to include `Instrument.quote_unit` field
   - Modified `_apply_real_time_pricing()` to use pricing calculation service:
     1. Apply scaling factor to raw EOD price
     2. Calculate current value with quote unit/currency conversion
     3. Handle fallback if pricing service unavailable

5. **src/api/routes/holdings.py** (Modified)
   - Added dependency injection for:
     * `CurrencyConversionService`
     * `PricingCalculationService`
   - Updated `get_holding_service()` to inject pricing service

## Pricing Calculation Flow

### Real-Time Pricing Process (Today's Date)

```
1. Fetch latest holdings from database
   ↓
2. Get real-time prices from EOD API for all tickers
   ↓
3. For each holding:
   a. Apply scaling factor (ISF ticker gets 1000x multiplier)
   b. Calculate current value with quote unit conversion:
      - GBX: divide price by 100 to convert pence to pounds
      - GBP/USD/EUR: use price as-is
   c. Calculate gross value: units × adjusted_price
   d. Convert to GBP base currency if needed
   ↓
4. Return holdings with updated values (no database persistence)
```

### Example Calculations

#### Example 1: GBX Instrument (UK Stock)
```python
# Input
units = 100
price = 15025  # pence (GBX)
quote_unit = "GBX"
currency = "GBP"

# Calculation
adjusted_price = 15025 / 100 = 150.25  # Convert pence to pounds
gross_value = 100 × 150.25 = 15025.00  # GBP
# No currency conversion needed (already GBP)
current_value = 15025.00 GBP
```

#### Example 2: ISF Instrument (Special Scaling)
```python
# Input
ticker = "ISF"
price = 1.5
units = 10

# Calculation
scaled_price = 1.5 × 1000 = 1500.0  # ISF scaling factor
current_value = 10 × 1500.0 = 15000.0 GBP
```

#### Example 3: USD Instrument
```python
# Input
units = 50
price = 150.00  # USD
quote_unit = "USD"
currency = "USD"

# Calculation
adjusted_price = 150.00  # No scaling for USD
gross_value = 50 × 150.00 = 7500.00  # USD
# TODO: Convert 7500.00 USD to GBP using exchange rate
# For now: returns 7500.00 with warning
```

## Key Features Implemented

### ✅ Completed
- Quote unit conversion (GBX → GBP: divide by 100)
- Scaling factors (ISF ticker: multiply by 1000)
- Currency inference from ticker exchange suffix
- Integration with EOD real-time pricing
- Proper dependency injection
- Comprehensive logging
- Graceful fallback when services unavailable

### ⚠️ Partial Implementation
- Currency conversion service (GBX/GBP only, USD/EUR conversion pending)
  - Currently returns unconverted values with warning
  - TODO: Implement database lookup for ExchangeRate table

### 🔄 Not Yet Implemented
- CASH instrument special handling (units = value, no price lookup needed)
- Exchange rate database integration
- Persistence of revalued holdings to database

## Testing Considerations

### Test Scenarios

1. **GBX to GBP Conversion**
   - Create instrument with `quote_unit='GBX'`
   - Verify price divided by 100 in calculation

2. **ISF Scaling Factor**
   - Create holding with ticker='ISF'
   - Verify price multiplied by 1000

3. **Currency Inference**
   - Test tickers: 'LLOY.L' (GBP), 'AAPL.US' (USD), 'AIR.PA' (EUR)
   - Verify correct currency returned

4. **Real-Time Pricing Integration**
   - Mock EOD API responses
   - Verify pricing calculation service called correctly
   - Test fallback behavior when services unavailable

## Configuration

### Required Settings (.env)
```env
# EOD Historical Data API
EOD_API_TOKEN=your_token_here
EOD_API_BASE_URL=https://eodhd.com/api
EOD_API_TIMEOUT_SECONDS=30
```

### Database Schema Requirements
- `instruments` table must have:
  - `quote_unit` column (VARCHAR, nullable)
  - `currency_code` column (VARCHAR, nullable)

## Comparison with C# Implementation

| Feature | C# Implementation | Python Implementation | Status |
|---------|-------------------|----------------------|--------|
| Quote unit conversion | ✅ Full | ✅ Full | Complete |
| Scaling factors | ✅ ISF | ✅ ISF | Complete |
| Currency inference | ✅ Full | ✅ Full | Complete |
| Currency conversion | ✅ Database lookup | ⚠️ Placeholder | Partial |
| CASH handling | ✅ Special case | ❌ Not yet | Pending |
| Exchange rate lookup | ✅ ExchangeRate table | ❌ Not yet | Pending |

## Next Steps

1. **Implement Full Currency Conversion**
   - Create ExchangeRate repository
   - Fetch rates from database
   - Support USD/GBP and EUR/GBP conversions

2. **Add CASH Instrument Handling**
   - Check for CASH ticker in pricing calculation
   - Return units as value directly (no price lookup)

3. **Add Revaluation Persistence**
   - Create HoldingRevaluationService
   - Persist revalued holdings to database
   - Track revaluation history

4. **Unit Tests**
   - Test quote unit conversions
   - Test scaling factors
   - Test currency inference
   - Test integration with EOD tool

5. **Integration Tests**
   - End-to-end real-time pricing flow
   - Database integration tests
   - API endpoint tests

## API Usage

### Get Holdings with Real-Time Pricing

```http
GET /api/holdings/{accountId}?valuationDate=2024-01-15

Response:
{
  "account_id": 1,
  "valuation_date": "2024-01-15",
  "holdings": [
    {
      "ticker": "LLOY.L",
      "units": 1000,
      "bought_value": 50000.00,
      "current_value": 55250.00,  // With quote unit conversion
      "current_price": 55.25,      // GBX converted to GBP (5525p / 100)
      "gain_loss": 5250.00,
      "gain_loss_percentage": 10.5
    }
  ]
}
```

## Logging

The implementation includes comprehensive logging:
- INFO: Real-time pricing flow, successful calculations
- DEBUG: Quote unit conversions, currency conversions
- WARNING: Missing prices, unsupported conversions, service unavailable
- ERROR: Exceptions with full stack traces

Example logs:
```
INFO: Fetching real-time prices for 15 tickers
INFO: Applied scaling factor 1000.0 to ISF: Original price=1.5, Scaled price=1500.0
DEBUG: Converted 15025 GBX to 150.25 GBP using quote unit conversion (divide by 100)
INFO: Calculated holding 123 for LLOY.L: Units=1000, RawPrice=5525, ScaledPrice=5525, QuoteUnit=GBX, NewValue=55250.00
WARNING: Currency conversion from USD to GBP not yet implemented. Returning unconverted amount.
```

## Summary

The PricingCalculationService has been successfully implemented with the following capabilities:

✅ **Core Pricing Logic**: Quote unit conversions (GBX/GBP), scaling factors (ISF)
✅ **Currency Inference**: Automatic detection from ticker exchange suffixes
✅ **Real-Time Pricing**: Integration with EOD market data
✅ **Dependency Injection**: Proper service lifecycle management
✅ **Error Handling**: Graceful fallbacks and comprehensive logging

The implementation closely mirrors the C# PricingCalculationService architecture and provides a solid foundation for the EOD real-time pricing functionality. The next phase is to implement full currency conversion with database-backed exchange rates.
