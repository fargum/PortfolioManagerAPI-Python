"""
Unit tests for voice mode functionality.

Tests cover:
- VoiceResponse speak_text sanitization (no URLs)
- Word limit enforcement
- Sources extraction from tool_events
- VoiceResponseAdapter behavior
- Endpoint contract validation
"""
import pytest
from datetime import datetime

from src.schemas.voice import (
    VoiceResponse,
    Source,
    Action,
    Telemetry,
    UIResponse,
    enforce_word_limit,
)
from src.services.ai.voice_adapter import VoiceResponseAdapter


class TestSpeakTextSanitization:
    """Test speak_text URL and content sanitization."""

    @pytest.mark.unit
    def test_removes_https_urls(self) -> None:
        """speak_text should not contain https URLs."""
        response = VoiceResponse(
            speak_text="Check this link https://example.com for details.",
            answer_text="Full answer here.",
        )
        assert "https://" not in response.speak_text
        assert "example.com" not in response.speak_text

    @pytest.mark.unit
    def test_removes_http_urls(self) -> None:
        """speak_text should not contain http URLs."""
        response = VoiceResponse(
            speak_text="Check http://test.com for info.",
            answer_text="Full answer.",
        )
        assert "http://" not in response.speak_text

    @pytest.mark.unit
    def test_preserves_markdown_link_text(self) -> None:
        """Markdown link text should be preserved, URL removed."""
        response = VoiceResponse(
            speak_text="Read [this article](https://example.com/article) for more.",
            answer_text="Full answer.",
        )
        assert "this article" in response.speak_text
        assert "https://" not in response.speak_text

    @pytest.mark.unit
    def test_removes_markdown_tables(self) -> None:
        """Markdown tables should be removed from speak_text."""
        text_with_table = "Here is data:\n| Col1 | Col2 |\n|------|------|\n| A | B |"
        response = VoiceResponse(
            speak_text=text_with_table,
            answer_text="Full answer.",
        )
        assert "|" not in response.speak_text

    @pytest.mark.unit
    def test_cleans_extra_whitespace(self) -> None:
        """Extra whitespace should be cleaned up."""
        response = VoiceResponse(
            speak_text="Too    many   spaces   here.",
            answer_text="Full answer.",
        )
        assert "  " not in response.speak_text


class TestWordLimitEnforcement:
    """Test max_speak_words enforcement."""

    @pytest.mark.unit
    def test_short_text_unchanged(self) -> None:
        """Text under limit should not be modified."""
        text = "This is a short sentence."
        result = enforce_word_limit(text, max_words=10)
        assert result == text

    @pytest.mark.unit
    def test_long_text_trimmed(self) -> None:
        """Text over limit should be trimmed."""
        text = "Word " * 50  # 50 words
        result = enforce_word_limit(text, max_words=10)
        words = result.split()
        assert len(words) <= 11  # 10 + possible ellipsis

    @pytest.mark.unit
    def test_respects_sentence_boundary(self) -> None:
        """Should end at sentence boundary if possible."""
        text = "First sentence here. Second sentence continues. Third goes on and on and on."
        result = enforce_word_limit(text, max_words=8)
        # Should end at first sentence since it's within limit
        assert result.endswith(".")

    @pytest.mark.unit
    def test_adds_ellipsis_when_no_boundary(self) -> None:
        """Should add ellipsis when no sentence boundary found."""
        text = "One two three four five six seven eight nine ten eleven twelve"
        result = enforce_word_limit(text, max_words=5)
        assert result.endswith("...")

    @pytest.mark.unit
    def test_empty_text_returns_empty(self) -> None:
        """Empty text should return empty."""
        result = enforce_word_limit("", max_words=10)
        assert result == ""


class TestSourcesExtraction:
    """Test extraction of sources from tool_events."""

    @pytest.fixture
    def market_context_tool_event(self) -> dict:
        """Sample get_market_context tool event."""
        return {
            "name": "get_market_context",
            "input": {"tickers": ["AAPL"]},
            "output": {
                "Status": "Success",
                "Message": "Retrieved 2 news articles",
                "Articles": [
                    {
                        "Title": "Apple Reports Strong Q4",
                        "Summary": "Apple Inc reported...",
                        "Source": "Reuters",
                        "PublishedDate": "2025-12-10T14:30:00+00:00",
                        "Url": "https://reuters.com/article/123",
                        "RelatedTickers": ["AAPL"],
                        "SentimentScore": 0.75,
                        "Category": "Financial News",
                    },
                    {
                        "Title": "Tech Stocks Rally",
                        "Summary": "Tech sector sees gains...",
                        "Source": "Bloomberg",
                        "PublishedDate": "2025-12-10T15:00:00+00:00",
                        "Url": "https://bloomberg.com/news/456",
                        "RelatedTickers": ["AAPL", "MSFT"],
                        "SentimentScore": 0.65,
                        "Category": "Market Analysis",
                    },
                ],
            },
        }

    @pytest.mark.unit
    def test_extracts_sources_from_market_context(
        self, market_context_tool_event: dict
    ) -> None:
        """Should extract Source objects from get_market_context output."""
        adapter = VoiceResponseAdapter(
            final_text="The news shows positive sentiment.",
            tool_events=[market_context_tool_event],
            query="What's the news on Apple?",
        )

        sources = adapter._extract_sources()

        assert len(sources) == 2
        assert sources[0].title == "Apple Reports Strong Q4"
        assert sources[0].publisher == "Reuters"
        assert sources[0].url == "https://reuters.com/article/123"

    @pytest.mark.unit
    def test_ignores_non_market_context_tools(self) -> None:
        """Should only extract from get_market_context, not other tools."""
        adapter = VoiceResponseAdapter(
            final_text="Your holdings show good performance.",
            tool_events=[
                {
                    "name": "get_portfolio_holdings",
                    "input": {"date": "today"},
                    "output": {"Holdings": []},
                }
            ],
            query="Show my holdings",
        )

        sources = adapter._extract_sources()
        assert len(sources) == 0

    @pytest.mark.unit
    def test_handles_missing_articles(self) -> None:
        """Should handle missing or empty Articles gracefully."""
        adapter = VoiceResponseAdapter(
            final_text="No news found.",
            tool_events=[
                {
                    "name": "get_market_context",
                    "input": {"tickers": ["XYZ"]},
                    "output": {"Status": "Success", "Articles": []},
                }
            ],
            query="News for XYZ?",
        )

        sources = adapter._extract_sources()
        assert len(sources) == 0

    @pytest.mark.unit
    def test_handles_articles_without_urls(self) -> None:
        """Should skip articles without URLs."""
        adapter = VoiceResponseAdapter(
            final_text="News found.",
            tool_events=[
                {
                    "name": "get_market_context",
                    "input": {"tickers": ["AAPL"]},
                    "output": {
                        "Status": "Success",
                        "Articles": [
                            {
                                "Title": "Article without URL",
                                "Source": "Unknown",
                            }
                        ],
                    },
                }
            ],
            query="News?",
        )

        sources = adapter._extract_sources()
        assert len(sources) == 0

    @pytest.mark.unit
    def test_limits_sources_to_five(self) -> None:
        """Should limit sources to 5 articles."""
        articles = [
            {
                "Title": f"Article {i}",
                "Source": "Test",
                "Url": f"https://test.com/{i}",
            }
            for i in range(10)
        ]
        adapter = VoiceResponseAdapter(
            final_text="Many articles.",
            tool_events=[
                {
                    "name": "get_market_context",
                    "input": {},
                    "output": {"Articles": articles},
                }
            ],
            query="News?",
        )

        sources = adapter._extract_sources()
        assert len(sources) == 5


class TestVoiceResponseAdapter:
    """Test VoiceResponseAdapter full behavior."""

    @pytest.mark.unit
    def test_build_returns_voice_response(self) -> None:
        """build() should return a valid VoiceResponse."""
        adapter = VoiceResponseAdapter(
            final_text="Your portfolio is performing well today.",
            tool_events=[],
            query="How is my portfolio?",
        )

        response = adapter.build()

        assert isinstance(response, VoiceResponse)
        assert response.speak_text
        assert response.answer_text

    @pytest.mark.unit
    def test_speak_text_respects_max_words(self) -> None:
        """speak_text should not exceed max_speak_words."""
        long_text = "This is a test " * 20  # 80 words
        adapter = VoiceResponseAdapter(
            final_text=long_text,
            tool_events=[],
            query="test",
            max_speak_words=20,
        )

        response = adapter.build()
        words = response.speak_text.split()
        assert len(words) <= 21  # max + possible ellipsis word

    @pytest.mark.unit
    def test_actions_limited_to_three(self) -> None:
        """Should return at most 3 actions."""
        adapter = VoiceResponseAdapter(
            final_text="Result",
            tool_events=[],
            query="holdings portfolio performance news price buy sell",  # Many keywords
        )

        response = adapter.build()
        assert len(response.actions) <= 3

    @pytest.mark.unit
    def test_telemetry_included_when_enabled(self) -> None:
        """Telemetry should be included when include_telemetry=True."""
        adapter = VoiceResponseAdapter(
            final_text="Result",
            tool_events=[{"name": "test_tool", "input": {}, "output": {}}],
            query="test",
            model_name="gpt-4",
            latency_ms=500,
            include_telemetry=True,
        )

        response = adapter.build()

        assert response.telemetry is not None
        assert response.telemetry.latency_ms == 500
        assert response.telemetry.model == "gpt-4"
        assert "test_tool" in response.telemetry.tools

    @pytest.mark.unit
    def test_telemetry_excluded_when_disabled(self) -> None:
        """Telemetry should be None when include_telemetry=False."""
        adapter = VoiceResponseAdapter(
            final_text="Result",
            tool_events=[],
            query="test",
            include_telemetry=False,
        )

        response = adapter.build()
        assert response.telemetry is None

    @pytest.mark.unit
    def test_removes_tool_status_messages(self) -> None:
        """Should remove tool status emoji lines from speak_text."""
        text_with_status = (
            "📊 Fetching your portfolio holdings...\n\n"
            "✓ Portfolio data retrieved\n\n"
            "Your portfolio value is $10,000."
        )
        adapter = VoiceResponseAdapter(
            final_text=text_with_status,
            tool_events=[],
            query="test",
        )

        response = adapter.build()
        assert "📊" not in response.speak_text
        assert "✓" not in response.speak_text
        assert "portfolio" in response.speak_text.lower()

    @pytest.mark.unit
    def test_actions_based_on_query_keywords(self) -> None:
        """Should suggest actions based on query keywords."""
        adapter = VoiceResponseAdapter(
            final_text="Result",
            tool_events=[],
            query="What news is affecting my portfolio?",
        )

        response = adapter.build()
        action_ids = [a.id for a in response.actions]
        # "news" keyword should trigger headlines action
        assert "headlines" in action_ids or "portfolio_impact" in action_ids

    @pytest.mark.unit
    def test_fallback_on_empty_speak_text(self) -> None:
        """Should provide fallback when speak_text would be empty."""
        adapter = VoiceResponseAdapter(
            final_text="",
            tool_events=[],
            query="test",
        )

        response = adapter.build()
        assert response.speak_text  # Should not be empty
        assert "trouble" in response.speak_text.lower()


class TestEndpointContract:
    """Test /respond endpoint response contract."""

    @pytest.mark.unit
    def test_voice_response_has_required_fields(self) -> None:
        """VoiceResponse should have all required fields."""
        response = VoiceResponse(
            speak_text="Spoken text here",
            answer_text="Full markdown answer",
        )

        assert hasattr(response, "speak_text")
        assert hasattr(response, "answer_text")
        assert hasattr(response, "sources")
        assert hasattr(response, "actions")
        assert hasattr(response, "telemetry")

    @pytest.mark.unit
    def test_source_model_structure(self) -> None:
        """Source model should have correct structure."""
        source = Source(
            title="Test Article",
            publisher="Test Publisher",
            url="https://test.com/article",
            published_at=datetime.now(),
        )

        # Check camelCase aliases work
        data = source.model_dump(by_alias=True)
        assert "publishedAt" in data

    @pytest.mark.unit
    def test_action_model_structure(self) -> None:
        """Action model should have correct structure."""
        action = Action(
            id="test_action",
            label="Test Action Label",
            args={"key": "value"},
        )

        assert action.id == "test_action"
        assert action.label == "Test Action Label"
        assert action.args == {"key": "value"}

    @pytest.mark.unit
    def test_telemetry_model_structure(self) -> None:
        """Telemetry model should have correct structure."""
        telemetry = Telemetry(
            latency_ms=100,
            mode="voice",
            tools=["get_portfolio_holdings"],
            model="gpt-4o-mini",
        )

        # Check camelCase aliases work
        data = telemetry.model_dump(by_alias=True)
        assert "latencyMs" in data
        assert data["latencyMs"] == 100

    @pytest.mark.unit
    def test_ui_response_model_structure(self) -> None:
        """UIResponse model should have correct structure."""
        response = UIResponse(answer="Test answer in markdown format.")

        assert response.answer == "Test answer in markdown format."

    @pytest.mark.unit
    def test_voice_response_camel_case_serialization(self) -> None:
        """VoiceResponse should serialize with camelCase aliases."""
        response = VoiceResponse(
            speak_text="Test speak",
            answer_text="Test answer",
        )

        data = response.model_dump(by_alias=True)
        assert "speakText" in data
        assert "answerText" in data


class TestActionSelection:
    """Test action selection logic."""

    @pytest.mark.unit
    def test_today_query_suggests_movers_and_breakdown(self) -> None:
        """Query with 'today' should suggest top_movers or breakdown."""
        adapter = VoiceResponseAdapter(
            final_text="Result",
            tool_events=[],
            query="How is my portfolio doing today?",
        )

        response = adapter.build()
        action_ids = [a.id for a in response.actions]
        assert "top_movers" in action_ids or "breakdown" in action_ids

    @pytest.mark.unit
    def test_performance_query_suggests_compare(self) -> None:
        """Query with 'performance' should suggest compare_performance."""
        adapter = VoiceResponseAdapter(
            final_text="Result",
            tool_events=[],
            query="How is my portfolio performance?",
        )

        response = adapter.build()
        action_ids = [a.id for a in response.actions]
        assert "compare_performance" in action_ids or "analyze_portfolio" in action_ids

    @pytest.mark.unit
    def test_tool_based_suggestions_when_no_keywords(self) -> None:
        """Should suggest actions based on tools used when no keywords match."""
        adapter = VoiceResponseAdapter(
            final_text="Result",
            tool_events=[
                {"name": "get_market_context", "input": {}, "output": {}}
            ],
            query="xyz",  # No matching keywords
        )

        response = adapter.build()
        action_ids = [a.id for a in response.actions]
        # Should suggest check_prices based on get_market_context tool
        assert "check_prices" in action_ids
