"""
LangChain tool for portfolio performance analysis.
"""
import logging
from datetime import datetime
from typing import Annotated, Optional

from langchain_core.tools import tool

from src.services.ai.portfolio_analysis_service import PortfolioAnalysisService
from src.services.ai.utils.date_utilities import DateUtilities

logger = logging.getLogger(__name__)

# Global service instance - will be injected
_portfolio_analysis_service: Optional[PortfolioAnalysisService] = None
_account_id: Optional[int] = None


def initialize_analysis_tool(portfolio_analysis_service: PortfolioAnalysisService, account_id: int):
    """Initialize the tool with required services and account context."""
    global _portfolio_analysis_service, _account_id
    _portfolio_analysis_service = portfolio_analysis_service
    _account_id = account_id


@tool
async def analyze_portfolio_performance(
    analysis_date: Annotated[str, "Analysis date. Use 'today' or current date (YYYY-MM-DD) for real-time analysis, or specify historical date in various formats (YYYY-MM-DD, DD/MM/YYYY, DD MMMM YYYY, etc.)"]
) -> dict:
    """Analyze portfolio performance and generate insights for the authenticated user's account on a specific date.
    
    For current/today performance, use today's date to get real-time analysis.
    
    Returns a dictionary containing:
    - AccountId: Account identifier
    - AnalysisDate: Date of analysis
    - TotalValue: Total portfolio value
    - DayChange: Day-over-day change in value
    - DayChangePercentage: Day-over-day change percentage
    - HoldingPerformance: Per-holding performance breakdown
    - Metrics: Performance metrics (top/bottom performers)
    """
    try:
        # Validate service is initialized
        if _portfolio_analysis_service is None or _account_id is None:
            return {"Error": "Analysis tool not initialized. Please call initialize_analysis_tool first."}
        
        # Smart date handling
        effective_date = analysis_date
        if not analysis_date or analysis_date.lower() in ['today', 'current', 'now']:
            effective_date = datetime.now().strftime("%Y-%m-%d")
            logger.info(f"Interpreted '{analysis_date}' as today: {effective_date}")
        
        # Parse the date
        parsed_date = DateUtilities.parse_date_time(effective_date)
        
        logger.info(f"Analyzing portfolio performance for account {_account_id} on {parsed_date}")
        
        # Get analysis from service
        analysis = await _portfolio_analysis_service.analyze_portfolio_performance_async(
            _account_id, parsed_date
        )
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error analyzing portfolio performance: {str(e)}", exc_info=True)
        return {
            "Error": f"Failed to analyze portfolio performance: {str(e)}",
            "AccountId": _account_id,
            "AnalysisDate": analysis_date
        }
