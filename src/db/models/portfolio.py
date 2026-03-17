"""Portfolio model representing investment portfolios in the database."""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from src.db.session import Base


class Portfolio(Base):
    """Portfolio model representing investment portfolios."""
    __tablename__ = "portfolios"
    __table_args__ = {'schema': 'app'}

    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Foreign Keys
    account_id = Column(Integer, ForeignKey("app.accounts.id"), nullable=False, index=True)

    # Portfolio Details
    name = Column(String, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=datetime.utcnow)

    # Relationships
    account = relationship("Account", back_populates="portfolios")
    holdings = relationship("Holding", back_populates="portfolio")

    def __repr__(self) -> str:
        return f"<Portfolio(id={self.id}, name={self.name})>"
