"""Conversation thread model for AI chat memory."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship

from src.db.session import Base


class ConversationThread(Base):
    """
    Conversation thread for AI interactions, scoped to a specific account.
    Tracks active conversations and their metadata.
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
    
    # Relationships
    messages = relationship("ChatMessage", back_populates="thread", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ConversationThread(id={self.id}, account_id={self.account_id}, title='{self.thread_title}')>"


class ChatMessage(Base):
    """
    Individual chat message within a conversation thread.
    Stores both user and assistant messages for conversation history.
    """
    __tablename__ = "chat_messages"
    __table_args__ = {'schema': 'app'}
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Foreign Key
    conversation_thread_id = Column(Integer, ForeignKey("app.conversation_threads.id"), nullable=False, index=True)
    
    # Message content
    role = Column(String(50), nullable=False)  # "user", "assistant", "system", "tool"
    content = Column(Text, nullable=False)
    
    # Message metadata
    message_timestamp = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True)
    message_metadata = Column(Text, nullable=True)  # JSON string for additional data
    
    # Relationships
    thread = relationship("ConversationThread", back_populates="messages")
    
    def __repr__(self):
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<ChatMessage(id={self.id}, role='{self.role}', content='{preview}')>"
