"""Account model representing user accounts in the database."""
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from src.db.session import Base


class Account(Base):
    """Account model representing user accounts."""
    __tablename__ = "accounts"
    __table_args__ = {'schema': 'app'}
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Account Details
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=datetime.utcnow)
    
    # Relationships
    portfolios = relationship("Portfolio", back_populates="account")
    
    def __repr__(self) -> str:
        return f"<Account(id={self.id}, name={self.name})>"
