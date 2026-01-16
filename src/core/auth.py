"""Azure AD authentication module - mirrors C# CurrentUserService pattern."""
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.db.session import get_db
from src.repositories.account_repository import AccountRepository

if TYPE_CHECKING:
    from fastapi_azure_auth import SingleTenantAzureAuthorizationCodeBearer

logger = logging.getLogger(__name__)

# Lazy-initialized Azure AD scheme
_azure_scheme: Optional["SingleTenantAzureAuthorizationCodeBearer"] = None


@dataclass
class CurrentUser:
    """Current authenticated user data extracted from Azure AD token."""
    user_id: str       # oid claim (Azure AD Object ID)
    email: str         # email or preferred_username claim
    display_name: str  # name claim


def get_azure_scheme() -> Optional[Any]:
    """
    Lazily initialize Azure AD authentication scheme.

    Returns None if Azure AD is not configured (development mode).
    """
    global _azure_scheme

    if _azure_scheme is None:
        if not settings.is_azure_ad_configured:
            logger.warning("Azure AD not configured - authentication disabled")
            return None

        from fastapi_azure_auth import SingleTenantAzureAuthorizationCodeBearer

        _azure_scheme = SingleTenantAzureAuthorizationCodeBearer(
            app_client_id=settings.azure_ad_client_id,
            tenant_id=settings.azure_ad_tenant_id,
            scopes={
                f"api://{settings.azure_ad_client_id}/Portfolio.ReadWrite": "Portfolio access"
            }
        )

    return _azure_scheme


async def get_current_user_from_token(
    token: Optional[dict] = None
) -> CurrentUser:
    """
    Extract current user from Azure AD token.

    Mirrors C# ICurrentUserService.GetCurrentUserId() and GetCurrentUserEmail().

    Claims extraction order (matching C# implementation):
    - User ID: oid -> sub -> objectidentifier
    - Email: email -> preferred_username -> upn
    - Display Name: name -> given_name -> preferred_username
    """
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Extract user_id (try multiple claim names matching C# order)
    user_id = (
        token.get("oid") or
        token.get("sub") or
        token.get("http://schemas.microsoft.com/identity/claims/objectidentifier")
    )

    if not user_id:
        logger.warning(f"Unable to determine user ID from claims: {list(token.keys())}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to determine user ID from token"
        )

    # Extract email
    email = (
        token.get("email") or
        token.get("preferred_username") or
        token.get("upn")
    )

    if not email:
        logger.warning(f"Unable to determine email from claims: {list(token.keys())}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to determine user email from token"
        )

    # Extract display name
    display_name = (
        token.get("name") or
        token.get("given_name") or
        token.get("preferred_username") or
        email
    )

    return CurrentUser(
        user_id=user_id,
        email=email,
        display_name=display_name
    )


async def get_current_user(
    token: Optional[dict] = Depends(get_azure_scheme)
) -> CurrentUser:
    """
    FastAPI dependency to get current user from Azure AD token.

    This is the main entry point used by routes.
    """
    return await get_current_user_from_token(token)


async def get_current_account_id(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> int:
    """
    Get or create internal Account ID for current user.

    Mirrors C# ICurrentUserService.GetCurrentUserAccountIdAsync().

    Flow:
    1. Look up account by external_user_id (Azure AD oid)
    2. Fallback to lookup by email
    3. Auto-create account if not found
    4. Record login timestamp
    5. Verify account is active
    6. Return internal Account ID
    """
    repo = AccountRepository(db)

    logger.info(f"Getting account for user {current_user.user_id} ({current_user.email})")

    # Get or create account (mirrors C# pattern exactly)
    account = await repo.create_or_update_external_user_async(
        external_user_id=current_user.user_id,
        email=current_user.email,
        display_name=current_user.display_name
    )

    # Verify account is active
    if not account.is_active:
        logger.warning(f"Account {account.id} is deactivated for user {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account {account.id} is deactivated"
        )

    logger.info(f"Using account {account.id} for user {current_user.email}")
    return int(account.id)  # type: ignore[arg-type]
