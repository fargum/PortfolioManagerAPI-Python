"""
Service for analyzing portfolio performance and generating insights.
Provides business logic for portfolio analysis calculations.
"""
import logging
from datetime import datetime
from typing import List, Dict, Any
from decimal import Decimal

from src.services.holding_service import HoldingService
from src.schemas.holding import PortfolioHoldingDto

logger = logging.getLogger(__name__)


class PortfolioAnalysisService:
    """
    Implementation of portfolio analysis service for AI-powered insights.
    """
    
    def __init__(self, holding_service: HoldingService):
        """
        Initialize the portfolio analysis service.
        
        Args:
            holding_service: Service for accessing holding data
        """
        self.holding_service = holding_service
    
    async def analyze_portfolio_performance_async(
        self,
        account_id: int,
        analysis_date: datetime
    ) -> dict:
        """
        Analyze portfolio performance for a specific account and date.
        
        Args:
            account_id: The account ID to analyze
            analysis_date: The date to analyze
        
        Returns:
            Dictionary containing:
            - AccountId: Account identifier
            - AnalysisDate: Date of analysis
            - TotalValue: Total portfolio value
            - DayChange: Day-over-day change in value
            - DayChangePercentage: Day-over-day change percentage
            - HoldingPerformance: List of holding performance details
            - Metrics: Performance metrics (top/bottom performers)
        """
        try:
            logger.info(f"Analyzing portfolio performance for account {account_id} on {analysis_date}")
            
            # Get holdings with aggregated totals from service
            response = await self.holding_service.get_holdings_by_account_and_date_async(
                account_id, analysis_date.date()
            )
            
            if not response or not response.holdings:
                logger.warning(f"No holdings found for account {account_id} on {analysis_date}")
                return self._create_empty_analysis(account_id, analysis_date)
            
            # Convert holdings to performance DTOs
            holding_performance = []
            for h in response.holdings:
                holding_performance.append({
                    "Ticker": h.ticker,
                    "InstrumentName": h.instrument_name,
                    "UnitAmount": float(h.units),
                    "CurrentValue": float(h.current_value),
                    "BoughtValue": float(h.bought_value),
                    "GainLoss": float(h.gain_loss),
                    "GainLossPercentage": float(h.gain_loss_percentage),
                    "TotalReturn": float(h.gain_loss),
                    "TotalReturnPercentage": float((h.current_value - h.bought_value) / h.bought_value) if h.bought_value > 0 else 0.0
                })
            
            # Use service-calculated totals instead of recalculating
            total_value = float(response.total_current_value)
            total_gain_loss = float(response.total_gain_loss)
            total_gain_loss_percentage = float(response.total_gain_loss_percentage)
            
            # Generate performance metrics
            metrics = self._calculate_performance_metrics(holding_performance)
            
            return {
                "AccountId": account_id,
                "AnalysisDate": analysis_date.isoformat(),
                "TotalValue": total_value,
                "GainLoss": total_gain_loss,
                "GainLossPercentage": total_gain_loss_percentage,
                "HoldingPerformance": holding_performance,
                "Metrics": metrics
            }
            
        except Exception as e:
            logger.error(f"Error analyzing portfolio performance: {str(e)}", exc_info=True)
            raise
    
    async def compare_performance_async(
        self,
        account_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> dict:
        """
        Compare portfolio performance between two dates.
        
        Args:
            account_id: The account ID to analyze
            start_date: Start date for comparison
            end_date: End date for comparison
        
        Returns:
            Dictionary containing:
            - AccountId: Account identifier
            - StartDate: Start date
            - EndDate: End date
            - StartValue: Portfolio value at start
            - EndValue: Portfolio value at end
            - TotalChange: Absolute change in value
            - TotalChangePercentage: Percentage change in value
            - HoldingComparisons: List of per-holding comparisons
            - Insights: Analysis insights
        """
        try:
            logger.info(
                f"Comparing portfolio performance for account {account_id} "
                f"between {start_date} and {end_date}"
            )
            
            # Get holdings with aggregated totals from service
            start_response = await self.holding_service.get_holdings_by_account_and_date_async(
                account_id, start_date.date()
            )
            end_response = await self.holding_service.get_holdings_by_account_and_date_async(
                account_id, end_date.date()
            )
            
            start_holdings = start_response.holdings if start_response else []
            end_holdings = end_response.holdings if end_response else []
            
            if not start_holdings and not end_holdings:
                logger.warning(
                    f"No holdings found for account {account_id} on either {start_date} or {end_date}"
                )
                return {
                    "AccountId": account_id,
                    "StartDate": start_date.isoformat(),
                    "EndDate": end_date.isoformat(),
                    "StartValue": 0.0,
                    "EndValue": 0.0,
                    "TotalChange": 0.0,
                    "TotalChangePercentage": 0.0,
                    "HoldingComparisons": [],
                    "Insights": self._generate_comparison_insights([], 0.0)
                }
            
            # Use service-calculated totals
            start_value = float(start_response.total_current_value) if start_response else 0.0
            end_value = float(end_response.total_current_value) if end_response else 0.0
            total_change = end_value - start_value
            total_change_percentage = float(total_change / start_value) if start_value > 0 else 0.0
            
            # Compare individual holdings
            holding_comparisons = self._compare_holdings(start_holdings, end_holdings)
            
            # Generate insights
            insights = self._generate_comparison_insights(holding_comparisons, total_change_percentage)
            
            return {
                "AccountId": account_id,
                "StartDate": start_date.isoformat(),
                "EndDate": end_date.isoformat(),
                "StartValue": float(start_value),
                "EndValue": float(end_value),
                "TotalChange": float(total_change),
                "TotalChangePercentage": total_change_percentage,
                "HoldingComparisons": holding_comparisons,
                "Insights": insights
            }
            
        except Exception as e:
            logger.error(f"Error comparing portfolio performance: {str(e)}", exc_info=True)
            raise
    
    def _create_empty_analysis(self, account_id: int, analysis_date: datetime) -> dict:
        """Create an empty analysis result when no holdings found."""
        return {
            "AccountId": account_id,
            "AnalysisDate": analysis_date.isoformat(),
            "TotalValue": 0.0,
            "DayChange": 0.0,
            "DayChangePercentage": 0.0,
            "HoldingPerformance": [],
            "Metrics": {
                "TotalReturn": 0.0,
                "TotalReturnPercentage": 0.0,
                "TopPerformers": [],
                "BottomPerformers": []
            }
        }
    
    def _calculate_performance_metrics(self, holdings: List[dict]) -> dict:
        """Calculate performance metrics from holdings."""
        if not holdings:
            return {
                "TotalReturn": 0.0,
                "TotalReturnPercentage": 0.0,
                "TopPerformers": [],
                "BottomPerformers": []
            }
        
        # Calculate total returns
        total_return = sum(h["TotalReturn"] for h in holdings)
        total_bought = sum(h["BoughtValue"] for h in holdings)
        total_return_percentage = (total_return / total_bought) if total_bought > 0 else 0.0
        
        # Sort by total return percentage
        sorted_holdings = sorted(holdings, key=lambda h: h["TotalReturnPercentage"], reverse=True)
        
        # Top 3 performers
        top_performers = [h["Ticker"] for h in sorted_holdings[:3]]
        
        # Bottom 3 performers
        bottom_performers = [h["Ticker"] for h in sorted_holdings[-3:]]
        
        return {
            "TotalReturn": total_return,
            "TotalReturnPercentage": total_return_percentage,
            "TopPerformers": top_performers,
            "BottomPerformers": bottom_performers
        }
    
    def _compare_holdings(self, start_holdings: List, end_holdings: List) -> List[dict]:
        """Compare holdings between two dates."""
        # Create dictionaries keyed by composite key (ticker|platform)
        start_dict = {}
        for h in start_holdings:
            key = f"{h.ticker}|{h.platform_name}"
            start_dict[key] = h
        
        end_dict = {}
        for h in end_holdings:
            key = f"{h.ticker}|{h.platform_name}"
            end_dict[key] = h
        
        # Get all unique keys
        all_keys = set(start_dict.keys()) | set(end_dict.keys())
        
        comparisons = []
        for key in all_keys:
            start_holding = start_dict.get(key)
            end_holding = end_dict.get(key)
            
            ticker, platform = key.split('|')
            
            start_value = float(start_holding.current_value) if start_holding else 0.0
            end_value = float(end_holding.current_value) if end_holding else 0.0
            change = end_value - start_value
            change_percentage = (change / start_value) if start_value > 0 else 0.0
            
            instrument_name = (
                end_holding.instrument_name if end_holding
                else start_holding.instrument_name if start_holding
                else "Unknown"
            )
            
            comparisons.append({
                "Ticker": f"{ticker} ({platform})" if platform != "UNKNOWN" else ticker,
                "InstrumentName": instrument_name,
                "StartValue": start_value,
                "EndValue": end_value,
                "Change": change,
                "ChangePercentage": change_percentage
            })
        
        return comparisons
    
    def _generate_comparison_insights(
        self,
        holding_comparisons: List[dict],
        total_change_percentage: float
    ) -> dict:
        """Generate insights from portfolio comparison."""
        if not holding_comparisons:
            return {
                "OverallTrend": "No holdings to compare",
                "KeyDrivers": [],
                "RiskFactors": [],
                "Opportunities": []
            }
        
        # Determine overall trend
        if total_change_percentage > 0.05:
            overall_trend = "Strong Positive Growth"
        elif total_change_percentage > 0:
            overall_trend = "Modest Growth"
        elif total_change_percentage > -0.05:
            overall_trend = "Slight Decline"
        else:
            overall_trend = "Significant Decline"
        
        # Find key drivers (top 3 by absolute change)
        sorted_by_change = sorted(
            holding_comparisons,
            key=lambda h: abs(h["Change"]),
            reverse=True
        )
        key_drivers = [
            f"{h['Ticker']}: {h['Change']:+.2f} ({h['ChangePercentage']:+.2%})"
            for h in sorted_by_change[:3]
        ]
        
        # Identify risk factors (holdings with significant declines)
        risk_factors = [
            f"{h['Ticker']}: {h['ChangePercentage']:.2%} decline"
            for h in holding_comparisons
            if h["ChangePercentage"] < -0.10  # More than 10% decline
        ]
        
        # Identify opportunities (holdings with strong growth)
        opportunities = [
            f"{h['Ticker']}: {h['ChangePercentage']:.2%} growth"
            for h in holding_comparisons
            if h["ChangePercentage"] > 0.10  # More than 10% growth
        ]
        
        return {
            "OverallTrend": overall_trend,
            "KeyDrivers": key_drivers if key_drivers else ["No significant drivers"],
            "RiskFactors": risk_factors if risk_factors else ["No major risk factors identified"],
            "Opportunities": opportunities if opportunities else ["No significant opportunities identified"]
        }
