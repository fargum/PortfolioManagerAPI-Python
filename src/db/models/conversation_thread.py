"""Conversation thread model for AI chat memory."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean

from src.db.session import Base


class ConversationThread(Base):
    """
    Conversation thread for AI interactions, scoped to a specific account.
    Tracks active conversations and their metadata.
    
    Note: The chat_messages table exists in the database but is managed by the C# service.
    LangGraph checkpointer handles message persistence for the Python implementation.
    """
    __tablename__ = "conversation_threads"
    __table_args__ = {'schema': 'app'}
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Account association
    account_id = Column(Integer, nullable=False, index=True)
    
    # Thread metadata
    thread_title = Column(String(500), nullable=False)
    last_activity = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<ConversationThread(id={self.id}, account_id={self.account_id}, title='{self.thread_title}')>"
