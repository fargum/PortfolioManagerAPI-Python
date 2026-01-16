"""
LangChain tool for retrieving portfolio holdings.
Uses factory pattern to create tools per-request, avoiding global state race conditions.
"""
import logging
from datetime import datetime
from typing import Annotated

from langchain_core.tools import StructuredTool

from src.services.holding_service import HoldingService
from src.services.ai.utils.date_utilities import DateUtilities

logger = logging.getLogger(__name__)


def create_portfolio_holdings_tool(holding_service: HoldingService, account_id: int) -> StructuredTool:
    """
    Factory function to create a portfolio holdings tool with bound context.
    Creates a new tool instance per-request to avoid global state race conditions.
    
    Args:
        holding_service: Service for accessing holding data (with DB session)
        account_id: Authenticated user's account ID
        
    Returns:
        StructuredTool configured for this specific request context
    """
    
    async def get_portfolio_holdings(
        date: Annotated[str, "Date for holdings analysis. Use 'today' or current date (YYYY-MM-DD) for real-time data, or specify historical date in various formats (YYYY-MM-DD, DD/MM/YYYY, DD MMMM YYYY, etc.)"]
    ) -> dict:
        """Retrieve portfolio holdings for the authenticated user's account and a specific date.
        
        For current/today performance, use today's date to get real-time data.
        For historical analysis, specify the desired date.
        
        Returns a dictionary containing:
        - AccountId: Account identifier
        - Date: Requested date
        - Holdings: List of holdings with ticker, name, platform, units, prices, values
        - TotalValue: Total portfolio value
        """
        try:
            # Smart date handling: if asking for 'today', 'current', or similar, use today's date
            effective_date = date
            if not date or date.lower() in ['today', 'current', 'now']:
                effective_date = datetime.now().strftime("%Y-%m-%d")
                logger.info(f"Interpreted '{date}' as today: {effective_date}")
            
            # Parse the date
            parsed_date = DateUtilities.parse_date(effective_date)
            
            logger.info(f"Getting portfolio holdings for account {account_id} on {parsed_date}")
            
            # Get holdings with aggregated totals from service
            response = await holding_service.get_holdings_by_account_and_date_async(
                account_id, parsed_date
            )
            
            if not response:
                return {
                    "Error": "No holdings found for the specified date",
                    "AccountId": account_id,
                    "Date": effective_date
                }
            
            # Format response using service-calculated totals
            return {
                "AccountId": response.account_id,
                "Date": effective_date,
                "TotalValue": float(response.total_current_value),
                "TotalBoughtValue": float(response.total_bought_value),
                "TotalGainLoss": float(response.total_gain_loss),
                "TotalGainLossPercentage": float(response.total_gain_loss_percentage),
                "TotalHoldings": response.total_holdings,
                "Holdings": [
                    {
                        "Ticker": h.ticker,
                        "InstrumentName": h.instrument_name,
                        "Platform": h.platform_name,
                        "UnitAmount": float(h.units),
                        "CurrentPrice": float(h.current_price) if h.current_price else 0.0,
                        "CurrentValue": float(h.current_value),
                        "BoughtValue": float(h.bought_value),
                        "UnrealizedGainLoss": float(h.gain_loss),
                        "GainLoss": float(h.gain_loss),
                        "GainLossPercentage": float(h.gain_loss_percentage),
                    }
                    for h in response.holdings
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting portfolio holdings: {str(e)}", exc_info=True)
            return {
                "Error": f"Failed to retrieve portfolio holdings: {str(e)}",
                "AccountId": account_id,
                "Date": date
            }
    
    return StructuredTool.from_function(
        coroutine=get_portfolio_holdings,
        name="get_portfolio_holdings",
        description=(
            "Retrieve portfolio holdings for the authenticated user's account and a specific date. "
            "For current/today performance, use today's date to get real-time data. "
            "For historical analysis, specify the desired date. "
            "Returns AccountId, Date, Holdings list with ticker, name, platform, units, prices, values, and TotalValue."
        )
    )
