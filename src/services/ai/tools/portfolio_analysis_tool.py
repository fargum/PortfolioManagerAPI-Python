"""
LangChain tool for portfolio performance analysis.
Uses factory pattern to create tools per-request, avoiding global state race conditions.
"""
import logging
from datetime import datetime
from typing import Annotated

from langchain_core.tools import StructuredTool

from src.services.ai.portfolio_analysis_service import PortfolioAnalysisService
from src.services.ai.utils.date_utilities import DateUtilities

logger = logging.getLogger(__name__)


def create_portfolio_analysis_tool(portfolio_analysis_service: PortfolioAnalysisService, account_id: int) -> StructuredTool:
    """
    Factory function to create a portfolio analysis tool with bound context.
    Creates a new tool instance per-request to avoid global state race conditions.
    
    Args:
        portfolio_analysis_service: Service for portfolio analysis
        account_id: Authenticated user's account ID
        
    Returns:
        StructuredTool configured for this specific request context
    """
    
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
            # Smart date handling
            effective_date = analysis_date
            if not analysis_date or analysis_date.lower() in ['today', 'current', 'now']:
                effective_date = datetime.now().strftime("%Y-%m-%d")
                logger.info(f"Interpreted '{analysis_date}' as today: {effective_date}")
            
            # Parse the date
            parsed_date = DateUtilities.parse_date_time(effective_date)
            
            logger.info(f"Analyzing portfolio performance for account {account_id} on {parsed_date}")
            
            # Get analysis from service
            analysis = await portfolio_analysis_service.analyze_portfolio_performance_async(
                account_id, parsed_date
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing portfolio performance: {str(e)}", exc_info=True)
            return {
                "Error": f"Failed to analyze portfolio performance: {str(e)}",
                "AccountId": account_id,
                "AnalysisDate": analysis_date
            }
    
    return StructuredTool.from_function(
        coroutine=analyze_portfolio_performance,
        name="analyze_portfolio_performance",
        description=(
            "Analyze portfolio performance and generate insights for the authenticated user's account on a specific date. "
            "For current/today performance, use today's date to get real-time analysis. "
            "Returns AccountId, AnalysisDate, TotalValue, DayChange, DayChangePercentage, HoldingPerformance, and Metrics."
        )
    )
