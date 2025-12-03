"""Platform model representing trading platforms in the database."""
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from src.db.session import Base


class Platform(Base):
    """Platform model representing trading/investment platforms."""
    __tablename__ = "platforms"
    __table_args__ = {'schema': 'app'}
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Platform Details
    name = Column(String, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=datetime.utcnow)
    
    # Relationships
    holdings = relationship("Holding", back_populates="platform")
    
    def __repr__(self) -> str:
        return f"<Platform(id={self.id}, name={self.name})>"
