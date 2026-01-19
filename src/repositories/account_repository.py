"""Account repository for Azure AD user management - mirrors C# IAccountRepository."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.account import Account


class AccountRepository:
    """Repository for Account entity operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_external_user_id_async(self, external_user_id: str) -> Optional[Account]:
        """Get account by Azure AD external user ID (oid claim)."""
        result = await self.db.execute(
            select(Account).where(Account.external_user_id == external_user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email_async(self, email: str) -> Optional[Account]:
        """Get account by email address."""
        result = await self.db.execute(
            select(Account).where(Account.email == email)
        )
        return result.scalar_one_or_none()

    async def create_or_update_external_user_async(
        self,
        external_user_id: str,
        email: str,
        display_name: str
    ) -> Account:
        """
        Create new account or update existing one for external user.

        Mirrors C# IAccountRepository.CreateOrUpdateExternalUserAsync().

        Lookup order:
        1. By external_user_id (Azure AD oid)
        2. By email (fallback for existing accounts)
        3. Create new if not found
        """
        # Try find by external_user_id first
        account = await self.get_by_external_user_id_async(external_user_id)

        if account is None:
            # Fallback to email lookup (for accounts created before Azure AD integration)
            account = await self.get_by_email_async(email)

        if account:
            # Update existing account
            account.update_user_info(email, display_name)
            account.record_login()
        else:
            # Create new account
            account = Account(
                external_user_id=external_user_id,
                email=email,
                display_name=display_name,
                is_active=True,
                last_login_at=datetime.now(timezone.utc)
            )
            self.db.add(account)

        await self.db.flush()
        return account
