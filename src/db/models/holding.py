"""Holding model representing portfolio holdings in the database."""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, Integer, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from src.db.session import Base


class Holding(Base):
    """
    Holding model representing a portfolio holding.
    
    Matches the actual database schema in the 'app' schema.
    """
    __tablename__ = "holdings"
    __table_args__ = {'schema': 'app'}
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Valuation Date
    valuation_date = Column(DateTime(timezone=True), nullable=False)
    
    # Foreign Keys
    instrument_id = Column(Integer, ForeignKey("app.instruments.id"), nullable=False, index=True)
    platform_id = Column(Integer, ForeignKey("app.platforms.id"), nullable=False, index=True)
    portfolio_id = Column(Integer, ForeignKey("app.portfolios.id"), nullable=False, index=True)
    
    # Holding Values
    unit_amount = Column(Numeric, nullable=False)
    bought_value = Column(Numeric, nullable=False)
    current_value = Column(Numeric, nullable=False)
    daily_profit_loss = Column(Numeric, nullable=False)
    daily_profit_loss_percentage = Column(Numeric, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=datetime.utcnow)
    
    # Relationships (uncomment when other models are created)
    # instrument = relationship("Instrument", back_populates="holdings")
    # platform = relationship("Platform", back_populates="holdings")
    # portfolio = relationship("Portfolio", back_populates="holdings")
    
    def __repr__(self) -> str:
        return f"<Holding(id={self.id}, symbol={self.symbol}, quantity={self.quantity})>"
