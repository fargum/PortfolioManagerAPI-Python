"""
LangChain tool for portfolio performance comparison.
"""
import logging
from typing import Annotated

from langchain_core.tools import tool

from src.services.ai.portfolio_analysis_service import PortfolioAnalysisService
from src.services.ai.utils.date_utilities import DateUtilities

logger = logging.getLogger(__name__)

# Global service instance - will be injected
_portfolio_analysis_service: PortfolioAnalysisService = None
_account_id: int = None


def initialize_comparison_tool(portfolio_analysis_service: PortfolioAnalysisService, account_id: int):
    """Initialize the tool with required services and account context."""
    global _portfolio_analysis_service, _account_id
    _portfolio_analysis_service = portfolio_analysis_service
    _account_id = account_id


@tool
async def compare_portfolio_performance(
    start_date: Annotated[str, "Start date in various formats (YYYY-MM-DD, DD/MM/YYYY, DD MMMM YYYY, etc.)"],
    end_date: Annotated[str, "End date in various formats (YYYY-MM-DD, DD/MM/YYYY, DD MMMM YYYY, etc.)"]
) -> dict:
    """Compare portfolio performance for the authenticated user's account between two dates.
    
    Returns a dictionary containing:
    - AccountId: Account identifier
    - StartDate: Start date
    - EndDate: End date
    - StartValue: Portfolio value at start
    - EndValue: Portfolio value at end
    - TotalChange: Absolute change in value
    - TotalChangePercentage: Percentage change in value
    - HoldingComparisons: Per-holding comparison
    - Insights: Analysis insights (trends, drivers, opportunities)
    """
    try:
        # Parse dates
        parsed_start = DateUtilities.parse_date_time(start_date)
        parsed_end = DateUtilities.parse_date_time(end_date)
        
        logger.info(
            f"Comparing portfolio performance for account {_account_id} "
            f"between {parsed_start} and {parsed_end}"
        )
        
        # Get comparison from service
        comparison = await _portfolio_analysis_service.compare_performance_async(
            _account_id, parsed_start, parsed_end
        )
        
        return comparison
        
    except Exception as e:
        logger.error(f"Error comparing portfolio performance: {str(e)}", exc_info=True)
        return {
            "Error": f"Failed to compare portfolio performance: {str(e)}",
            "AccountId": _account_id,
            "StartDate": start_date,
            "EndDate": end_date
        }
