"""Result objects for service layer operations."""
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import date
from enum import Enum
from typing import Optional, TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from src.db.models.holding import Holding
    from src.db.models.instrument import Instrument


class HoldingDict(TypedDict):
    """Typed dictionary for holding data returned from service methods."""
    holding_id: int
    portfolio_id: int
    portfolio_name: str
    platform_id: int
    platform_name: str
    ticker: str
    instrument_name: str
    units: Decimal
    bought_value: Decimal
    current_value: Decimal
    current_price: Optional[Decimal]
    gain_loss: Decimal
    gain_loss_percentage: Decimal
    currency_code: str
    valuation_date: date


class ErrorCode(str, Enum):
    """Standardized error codes for service operations."""
    NONE = "none"
    NOT_FOUND = "not_found"
    NOT_ACCESSIBLE = "not_accessible"
    DUPLICATE = "duplicate"
    VALIDATION_ERROR = "validation_error"
    INTERNAL_ERROR = "internal_error"


@dataclass
class ServiceResult:
    """Base result object for service operations."""
    success: bool
    message: str
    errors: list[str] = field(default_factory=list)
    error_code: ErrorCode = ErrorCode.NONE


@dataclass
class AddHoldingResult(ServiceResult):
    """Result for AddHoldingAsync operation."""
    created_holding: Optional[Any] = None  # Holding model
    instrument: Optional[Any] = None  # Instrument model
    instrument_created: bool = False
    current_price: Optional[Decimal] = None
    current_value: Optional[Decimal] = None


@dataclass
class UpdateHoldingResult(ServiceResult):
    """Result for UpdateHoldingUnitsAsync operation."""
    updated_holding: Optional[Any] = None  # Holding model
    previous_units: Decimal = Decimal("0")
    new_units: Decimal = Decimal("0")
    previous_current_value: Decimal = Decimal("0")
    new_current_value: Decimal = Decimal("0")


@dataclass
class DeleteHoldingResult(ServiceResult):
    """Result for DeleteHoldingAsync operation."""
    deleted_holding_id: Optional[int] = None
    deleted_ticker: Optional[str] = None
    portfolio_id: Optional[int] = None
