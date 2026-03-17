"""Instruments routes for looking up financial instruments."""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import get_current_account_id
from src.db.models.instrument import Instrument
from src.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/instruments", tags=["instruments"])


@router.get("/check/{ticker}")
async def check_instrument(
    ticker: str,
    _account_id: int = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Check whether a ticker symbol exists in the instruments table.

    Returns exists=True and the instrument details if found,
    or exists=False with instrument=null if not found.
    """
    result = await db.execute(
        select(Instrument).where(Instrument.ticker == ticker.upper())
    )
    instrument = result.scalars().first()

    if instrument is None:
        return {"exists": False, "instrument": None}

    return {
        "exists": True,
        "instrument": {
            "id": instrument.id,
            "ticker": instrument.ticker,
            "name": instrument.name,
            "description": instrument.description,
            "currencyCode": instrument.currency_code,
        },
    }
