"""ExchangeRate model representing currency exchange rates in the database."""
from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, Index
from datetime import datetime

from src.db.session import Base


class ExchangeRate(Base):
    """ExchangeRate model representing currency exchange rates for conversions."""
    __tablename__ = "exchange_rates"
    __table_args__ = (
        Index('ix_exchange_rates_currency_pair', 'base_currency', 'target_currency'),
        {'schema': 'app'}
    )
    
    # Primary Key - Database has "Id" (capital I) instead of "id"
    id = Column("Id", Integer, primary_key=True, index=True, autoincrement=True)
    
    # Currency Pair - Everything else is snake_case in database
    base_currency = Column(String(3), nullable=False)  # e.g., "USD"
    target_currency = Column(String(3), nullable=False)  # e.g., "GBP"
    
    # Exchange Rate
    rate = Column(Numeric(18, 8), nullable=False)  # 1 BaseCurrency = Rate TargetCurrency
    
    # Date
    rate_date = Column(Date, nullable=False)
    
    # Source
    source = Column(String(50), nullable=False)  # "EOD", "MANUAL", "ROLLED_FORWARD"
    
    # Timestamps
    fetched_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<ExchangeRate(id={self.id}, {self.base_currency}/{self.target_currency}={self.rate}, date={self.rate_date})>"
