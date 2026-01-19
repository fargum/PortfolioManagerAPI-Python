"""Service for managing conversation threads and memory operations."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import selectinload

from src.db.models.conversation_thread import ConversationThread, ChatMessage

logger = logging.getLogger(__name__)


class ConversationThreadService:
    """
    Service for managing conversation threads and memory operations.
    Handles thread lifecycle: creation, activation, deactivation, and cleanup.
    """
    
    # Thread is considered inactive after 30 minutes of no activity
    INACTIVITY_THRESHOLD = timedelta(minutes=30)
    
    def __init__(self, db_session: AsyncSession):
        """
        Initialize the conversation thread service.
        
        Args:
            db_session: SQLAlchemy async database session
        """
        self.db = db_session
    
    async def get_or_create_active_thread(
        self, 
        account_id: int,
        thread_id: Optional[int] = None
    ) -> ConversationThread:
        """
        Get or create an active conversation thread for the account.
        
        If thread_id is provided, retrieves that specific thread (if active and belongs to account).
        Otherwise, gets the most recent active thread or creates a new one if none exists
        or if the existing thread is inactive.
        
        Args:
            account_id: Account ID to get/create thread for
            thread_id: Optional specific thread ID to retrieve
        
        Returns:
            ConversationThread: Active conversation thread
        """
        if thread_id:
            # Get specific thread
            thread = await self._get_thread_by_id(thread_id, account_id)
            if thread and thread.is_active:
                # Update last activity
                await self._update_last_activity(thread)
                return thread
            else:
                logger.warning(
                    f"Thread {thread_id} not found or inactive for account {account_id}, creating new thread"
                )
        
        # Get most recent active thread
        active_thread = await self._get_most_recent_active_thread(account_id)
        
        if active_thread:
            # Check if thread should be closed due to inactivity
            time_since_activity = datetime.now(timezone.utc) - active_thread.last_activity.replace(tzinfo=None)
            
            if time_since_activity > self.INACTIVITY_THRESHOLD:
                logger.info(
                    f"Closing inactive thread {active_thread.id} for account {account_id} "
                    f"(inactive for {time_since_activity})"
                )
                await self._deactivate_thread(active_thread)
                # Create new thread
                return await self._create_new_thread(account_id)
            else:
                # Update last activity and return
                await self._update_last_activity(active_thread)
                return active_thread
        else:
            # No active thread, create new one
            return await self._create_new_thread(account_id)
    
    async def _get_thread_by_id(
        self, 
        thread_id: int, 
        account_id: int
    ) -> Optional[ConversationThread]:
        """
        Get a specific thread by ID, ensuring it belongs to the account.
        
        Args:
            thread_id: Thread ID to retrieve
            account_id: Account ID that should own the thread
        
        Returns:
            ConversationThread or None if not found
        """
        result = await self.db.execute(
            select(ConversationThread)
            .where(
                and_(
                    ConversationThread.id == thread_id,
                    ConversationThread.account_id == account_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def _get_most_recent_active_thread(
        self, 
        account_id: int
    ) -> Optional[ConversationThread]:
        """
        Get the most recent active thread for an account.
        
        Args:
            account_id: Account ID to search for
        
        Returns:
            ConversationThread or None if no active threads exist
        """
        result = await self.db.execute(
            select(ConversationThread)
            .where(
                and_(
                    ConversationThread.account_id == account_id,
                    ConversationThread.is_active == True
                )
            )
            .order_by(desc(ConversationThread.last_activity))
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def _create_new_thread(self, account_id: int) -> ConversationThread:
        """
        Create a new conversation thread for the account.
        
        Args:
            account_id: Account ID to create thread for
        
        Returns:
            ConversationThread: Newly created thread
        """
        now = datetime.now(timezone.utc)
        thread = ConversationThread(
            account_id=account_id,
            thread_title=f"Conversation {now.strftime('%Y-%m-%d %H:%M')}",
            last_activity=now,
            is_active=True,
            created_at=now,
            updated_at=now
        )
        
        self.db.add(thread)
        await self.db.commit()
        await self.db.refresh(thread)
        
        logger.info(f"Created new conversation thread {thread.id} for account {account_id}")
        return thread
    
    async def _update_last_activity(self, thread: ConversationThread) -> None:
        """
        Update the last activity timestamp for a thread.
        
        Args:
            thread: Thread to update
        """
        thread.last_activity = datetime.now(timezone.utc)
        thread.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
    
    async def _deactivate_thread(self, thread: ConversationThread) -> None:
        """
        Deactivate a conversation thread.
        
        Args:
            thread: Thread to deactivate
        """
        thread.is_active = False
        thread.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        logger.info(f"Deactivated thread {thread.id}")
    
    async def get_active_threads_for_account(
        self, 
        account_id: int, 
        limit: int = 20
    ) -> List[ConversationThread]:
        """
        Get all active threads for an account.
        
        Args:
            account_id: Account ID to get threads for
            limit: Maximum number of threads to return
        
        Returns:
            List of active ConversationThread objects
        """
        result = await self.db.execute(
            select(ConversationThread)
            .where(
                and_(
                    ConversationThread.account_id == account_id,
                    ConversationThread.is_active == True
                )
            )
            .order_by(desc(ConversationThread.last_activity))
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def close_thread(self, thread_id: int, account_id: int) -> bool:
        """
        Manually close a conversation thread.
        
        Args:
            thread_id: Thread ID to close
            account_id: Account ID that owns the thread
        
        Returns:
            bool: True if thread was closed, False if not found
        """
        thread = await self._get_thread_by_id(thread_id, account_id)
        if thread:
            await self._deactivate_thread(thread)
            return True
        else:
            logger.warning(f"Thread {thread_id} not found for account {account_id}")
            return False
