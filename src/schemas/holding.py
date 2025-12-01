"""Pydantic schemas for Holdings API requests and responses."""
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, date
from decimal import Decimal
from typing import Optional


class InstrumentInfo(BaseModel):
    id: int
    ticker: str
    name: str
    description: Optional[str] = None
    currency_code: str = Field(alias="currencyCode")
    quote_unit: Optional[str] = Field(None, alias="quoteUnit")
    instrument_type_id: Optional[int] = Field(None, alias="instrumentTypeId")
    
    model_config = ConfigDict(populate_by_name=True)


class PortfolioHoldingDto(BaseModel):
    holding_id: int = Field(alias="holdingId")
    portfolio_id: int = Field(alias="portfolioId")
    portfolio_name: str = Field(alias="portfolioName")
    platform_id: int = Field(alias="platformId")
    platform_name: str = Field(alias="platformName")
    ticker: str
    instrument_name: str = Field(alias="instrumentName")
    units: Decimal
    bought_value: Decimal = Field(alias="boughtValue")
    current_value: Decimal = Field(alias="currentValue")
    current_price: Optional[Decimal] = Field(None, alias="currentPrice")
    gain_loss: Decimal = Field(alias="gainLoss")
    gain_loss_percentage: Decimal = Field(alias="gainLossPercentage")
    currency_code: str = Field(alias="currencyCode")
    valuation_date: date = Field(alias="valuationDate")
    
    model_config = ConfigDict(populate_by_name=True)


class AccountHoldingsResponse(BaseModel):
    account_id: int = Field(alias="accountId")
    valuation_date: date = Field(alias="valuationDate")
    holdings: list[PortfolioHoldingDto]
    total_holdings: int = Field(alias="totalHoldings")
    total_current_value: Decimal = Field(alias="totalCurrentValue")
    total_bought_value: Decimal = Field(alias="totalBoughtValue")
    total_gain_loss: Decimal = Field(alias="totalGainLoss")
    total_gain_loss_percentage: Decimal = Field(alias="totalGainLossPercentage")
    
    model_config = ConfigDict(populate_by_name=True)


class AddHoldingApiRequest(BaseModel):
    platform_id: int = Field(alias="platformId")
    ticker: str = Field(max_length=20)
    units: Decimal = Field(gt=0)
    bought_value: Decimal = Field(ge=0, alias="boughtValue")
    instrument_name: Optional[str] = Field(None, alias="instrumentName")
    description: Optional[str] = None
    instrument_type_id: Optional[int] = Field(None, alias="instrumentTypeId")
    currency_code: str = Field(default="USD", alias="currencyCode")
    quote_unit: Optional[str] = Field(None, alias="quoteUnit")
    
    model_config = ConfigDict(populate_by_name=True)


class AddHoldingApiResponse(BaseModel):
    success: bool
    message: str
    errors: Optional[list[str]] = None
    holding_id: Optional[int] = Field(None, alias="holdingId")
    instrument_created: bool = Field(alias="instrumentCreated")
    instrument: Optional[InstrumentInfo] = None
    current_price: Optional[Decimal] = Field(None, alias="currentPrice")
    current_value: Optional[Decimal] = Field(None, alias="currentValue")
    
    model_config = ConfigDict(populate_by_name=True)


class UpdateHoldingUnitsApiRequest(BaseModel):
    units: Decimal = Field(gt=0)


class UpdateHoldingApiResponse(BaseModel):
    success: bool
    message: str
    errors: Optional[list[str]] = None
    holding_id: int = Field(alias="holdingId")
    previous_units: Decimal = Field(alias="previousUnits")
    new_units: Decimal = Field(alias="newUnits")
    previous_current_value: Decimal = Field(alias="previousCurrentValue")
    new_current_value: Decimal = Field(alias="newCurrentValue")
    ticker: Optional[str] = None
    
    model_config = ConfigDict(populate_by_name=True)


class DeleteHoldingApiResponse(BaseModel):
    success: bool
    message: str
    errors: Optional[list[str]] = None
    deleted_holding_id: Optional[int] = Field(None, alias="deletedHoldingId")
    deleted_ticker: Optional[str] = Field(None, alias="deletedTicker")
    portfolio_id: Optional[int] = Field(None, alias="portfolioId")
    
    model_config = ConfigDict(populate_by_name=True)

