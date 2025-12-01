"""Instrument model representing financial instruments in the database."""
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime

from src.db.session import Base


class Instrument(Base):
    """Instrument model representing stocks, bonds, ETFs, etc."""
    __tablename__ = "instruments"
    __table_args__ = {'schema': 'app'}
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Instrument Details
    ticker = Column(String, nullable=False, index=True)
    name = Column(String, nullable=True)
    description = Column(String, nullable=True)
    instrument_type_id = Column(Integer, nullable=True)
    currency_code = Column(String, nullable=True, default="USD")
    quote_unit = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<Instrument(id={self.id}, ticker={self.ticker}, name={self.name})>"
