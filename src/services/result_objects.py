"""Result objects for service layer operations."""
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import date
from typing import Optional, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.db.models.holding import Holding
    from src.db.models.instrument import Instrument


@dataclass
class ServiceResult:
    """Base result object for service operations."""
    success: bool
    message: str
    errors: list[str] = field(default_factory=list)


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
