"""Account model representing user accounts in the database."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from src.db.session import Base


class Account(Base):
    """Account model representing user accounts - aligned with C# Account entity."""
    __tablename__ = "accounts"
    __table_args__ = {'schema': 'app'}

    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Azure AD Integration Properties (matching C# schema)
    external_user_id = Column(String(255), nullable=False, unique=True, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    display_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=datetime.utcnow)

    # Relationships
    portfolios = relationship("Portfolio", back_populates="account")

    def record_login(self) -> None:
        """Record login timestamp."""
        self.last_login_at = datetime.utcnow()  # type: ignore[assignment]
        self.updated_at = datetime.utcnow()  # type: ignore[assignment]

    def update_user_info(self, email: str, display_name: str) -> None:
        """Update user info from Azure AD claims."""
        self.email = email  # type: ignore[assignment]
        self.display_name = display_name  # type: ignore[assignment]
        self.updated_at = datetime.utcnow()  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"<Account(id={self.id}, email={self.email})>"
