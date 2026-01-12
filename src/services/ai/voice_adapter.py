"""
Voice response adapter for transforming AI responses to voice-optimized format.
"""
import logging
import re
from datetime import datetime
from typing import Any, Optional

from src.schemas.voice import (
    Action,
    Source,
    Telemetry,
    VoiceResponse,
    enforce_word_limit,
    sanitize_for_tts,
)

logger = logging.getLogger(__name__)


# Action definitions for suggested follow-ups
AVAILABLE_ACTIONS = {
    "top_movers": Action(id="top_movers", label="Show top movers"),
    "breakdown": Action(id="breakdown", label="Show portfolio breakdown"),
    "headlines": Action(id="headlines", label="Get latest headlines"),
    "portfolio_impact": Action(id="portfolio_impact", label="Check portfolio impact"),
    "risk_exposure": Action(id="risk_exposure", label="View risk exposure"),
    "view_holdings": Action(id="view_holdings", label="View all holdings"),
    "analyze_portfolio": Action(id="analyze_portfolio", label="Analyze portfolio"),
    "compare_performance": Action(id="compare_performance", label="Compare performance"),
    "check_prices": Action(id="check_prices", label="Check current prices"),
}

# Keyword to action mappings
KEYWORD_ACTION_MAP = {
    "today": ["top_movers", "breakdown"],
    "doing": ["top_movers", "breakdown"],
    "performance": ["compare_performance", "analyze_portfolio"],
    "why": ["headlines", "portfolio_impact"],
    "news": ["headlines", "portfolio_impact"],
    "exposure": ["risk_exposure", "breakdown"],
    "holdings": ["view_holdings", "analyze_portfolio"],
    "portfolio": ["analyze_portfolio", "breakdown"],
    "price": ["check_prices", "top_movers"],
    "prices": ["check_prices", "top_movers"],
}


class VoiceResponseAdapter:
    """
    Adapter to transform LangGraph agent output into VoiceResponse.

    Extracts sources from tool outputs, generates speak_text,
    and suggests relevant follow-up actions.
    """

    # Fallback message when processing fails
    FALLBACK_SPEAK_TEXT = (
        "I had trouble formatting that response for voice. "
        "Please check the on-screen summary."
    )

    def __init__(
        self,
        final_text: str,
        tool_events: list[dict[str, Any]],
        query: str,
        max_speak_words: int = 100,
        model_name: Optional[str] = None,
        latency_ms: int = 0,
        include_telemetry: bool = False,
    ):
        """
        Initialize the voice response adapter.

        Args:
            final_text: Complete AI response text
            tool_events: List of tool event dicts with name, input, output
            query: Original user query
            max_speak_words: Maximum words for speak_text
            model_name: AI model name for telemetry
            latency_ms: Response latency for telemetry
            include_telemetry: Whether to include telemetry in response
        """
        self.final_text = final_text
        self.tool_events = tool_events
        self.query = query.lower()
        self.max_speak_words = max_speak_words
        self.model_name = model_name
        self.latency_ms = latency_ms
        self.include_telemetry = include_telemetry

    def _extract_sources(self) -> list[Source]:
        """Extract Source objects from get_market_context tool outputs."""
        sources: list[Source] = []

        for event in self.tool_events:
            if event.get("name") != "get_market_context":
                continue

            output = event.get("output")
            if not output or not isinstance(output, dict):
                continue

            articles = output.get("Articles", [])
            for article in articles[:5]:  # Limit to first 5 articles
                try:
                    # Parse published date
                    published_at = None
                    pub_date_str = article.get("PublishedDate")
                    if pub_date_str:
                        try:
                            # Handle ISO format with timezone
                            published_at = datetime.fromisoformat(
                                pub_date_str.replace("Z", "+00:00")
                            )
                        except (ValueError, TypeError):
                            logger.debug(f"Could not parse date: {pub_date_str}")

                    url = article.get("Url", "")
                    if not url:
                        continue  # Skip articles without URLs

                    source = Source(
                        title=article.get("Title", "Untitled"),
                        publisher=article.get("Source"),
                        url=url,
                        published_at=published_at,
                    )
                    sources.append(source)
                except Exception as e:
                    logger.warning(f"Failed to parse article source: {e}")
                    continue

        return sources

    def _extract_voice_summary(self) -> Optional[str]:
        """
        Extract the VOICE_SUMMARY section from the AI response.
        
        The agent is instructed to format responses with:
        **VOICE_SUMMARY**
        <summary text>
        
        **DETAILED**
        <full response>
        
        Returns:
            Extracted voice summary text, or None if not found
        """
        # Look for **VOICE_SUMMARY** section - flexible pattern allowing for variations
        # Handles: **VOICE_SUMMARY**, **VOICE SUMMARY**, **Voice Summary**, etc.
        pattern = r"\*\*\s*VOICE[_\s]?SUMMARY\s*\*\*\s*[:\n]?(.+?)(?=\*\*\s*DETAILED|$)"
        match = re.search(pattern, self.final_text, re.DOTALL | re.IGNORECASE)
        
        if match:
            summary = match.group(1).strip()
            # Clean up any residual markdown
            summary = sanitize_for_tts(summary)
            logger.info(f"Extracted VOICE_SUMMARY ({len(summary.split())} words)")
            return summary if summary else None
        
        logger.info("No VOICE_SUMMARY section found in AI response, using fallback")
        return None
    
    def _extract_detailed_section(self) -> str:
        """
        Extract the DETAILED section from the AI response.
        
        Returns:
            The detailed section, or the full response if no sections found
        """
        # Look for **DETAILED** section
        pattern = r"\*\*DETAILED\*\*\s*\n(.+)"
        match = re.search(pattern, self.final_text, re.DOTALL | re.IGNORECASE)
        
        if match:
            return match.group(1).strip()
        
        # If no DETAILED section, check if there's a VOICE_SUMMARY to remove
        voice_pattern = r"\*\*VOICE_SUMMARY\*\*\s*\n.+?(?=\n\*\*|$)"
        cleaned = re.sub(voice_pattern, "", self.final_text, flags=re.DOTALL | re.IGNORECASE)
        return cleaned.strip() if cleaned.strip() else self.final_text

    def _generate_speak_text(self) -> str:
        """
        Generate TTS-optimized speak_text from final_text.

        First tries to extract the VOICE_SUMMARY section from the AI response.
        Falls back to heuristic extraction if no summary section found.
        """
        # Try to extract AI-generated voice summary first
        voice_summary = self._extract_voice_summary()
        if voice_summary:
            logger.info(f"Using AI-generated voice summary ({len(voice_summary)} chars)")
            return voice_summary
        
        # Fallback: heuristic extraction from full response
        logger.info("Using heuristic extraction for speak_text (fallback)")
        text = self.final_text

        # Remove tool status messages (✓ ... lines) - app-specific
        text = re.sub(r"[✓📊📈🌍💭💰🔧].*?\n", "", text)

        # Use shared sanitization for markdown/URL cleanup
        text = sanitize_for_tts(text)

        # Apply word limit
        text = enforce_word_limit(text, self.max_speak_words)

        return text if text else self.FALLBACK_SPEAK_TEXT

    def _generate_answer_text(self, sources: list[Source]) -> str:
        """
        Generate answer_text with markdown and source references.

        Uses the DETAILED section if present, otherwise the full response.
        If sources exist, append a "Sources:" section at the end.
        """
        # Use detailed section if available, otherwise full response
        answer = self._extract_detailed_section()

        if sources:
            answer += "\n\n---\n\n**Sources:**\n"
            for i, source in enumerate(sources[:5], 1):  # Limit to 5 sources
                answer += f"{i}. [{source.title}]({source.url})"
                if source.publisher:
                    answer += f" - {source.publisher}"
                answer += "\n"

        return answer

    def _choose_actions(self) -> list[Action]:
        """
        Choose 0-3 relevant actions based on query keywords.

        Returns actions that match keywords in the user's query.
        """
        suggested_action_ids: list[str] = []

        # Check query for keywords
        for keyword, action_ids in KEYWORD_ACTION_MAP.items():
            if keyword in self.query:
                for action_id in action_ids:
                    if action_id not in suggested_action_ids:
                        suggested_action_ids.append(action_id)
                        if len(suggested_action_ids) >= 3:
                            break
            if len(suggested_action_ids) >= 3:
                break

        # If no keyword matches, suggest based on tools used
        if not suggested_action_ids:
            tool_names = [e.get("name", "") for e in self.tool_events]
            if "get_market_context" in tool_names:
                suggested_action_ids.append("check_prices")
            if "get_portfolio_holdings" in tool_names:
                suggested_action_ids.append("compare_performance")
            if "analyze_portfolio_performance" in tool_names:
                suggested_action_ids.append("headlines")

        # Convert IDs to Action objects
        actions = []
        for action_id in suggested_action_ids[:3]:
            if action_id in AVAILABLE_ACTIONS:
                actions.append(AVAILABLE_ACTIONS[action_id])

        return actions

    def _build_telemetry(self) -> Optional[Telemetry]:
        """Build telemetry object if enabled."""
        if not self.include_telemetry:
            return None

        tool_names = list(set(e.get("name", "unknown") for e in self.tool_events))

        return Telemetry(
            latency_ms=self.latency_ms,
            mode="voice",
            tools=tool_names,
            model=self.model_name,
        )

    def build(self) -> VoiceResponse:
        """
        Build the complete VoiceResponse.

        Returns:
            VoiceResponse with speak_text, answer_text, sources, actions,
            and optional telemetry. Falls back to safe defaults on error.
        """
        try:
            sources = self._extract_sources()
            speak_text = self._generate_speak_text()
            answer_text = self._generate_answer_text(sources)
            actions = self._choose_actions()
            telemetry = self._build_telemetry()

            return VoiceResponse(
                speak_text=speak_text,
                answer_text=answer_text,
                sources=sources,
                actions=actions,
                telemetry=telemetry,
            )
        except Exception as e:
            logger.error(f"Error building voice response: {e}", exc_info=True)
            # Return safe fallback response
            return VoiceResponse(
                speak_text=self.FALLBACK_SPEAK_TEXT,
                answer_text=self.final_text,
                sources=[],
                actions=[],
                telemetry=self._build_telemetry() if self.include_telemetry else None,
            )
