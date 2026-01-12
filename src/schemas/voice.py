"""Pydantic schemas for voice mode responses."""
import re
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Source(BaseModel):
    """Article/news source reference for voice response."""

    title: str = Field(..., description="Article headline")
    publisher: Optional[str] = Field(None, description="Source publisher name")
    url: str = Field(..., description="URL to full article")
    published_at: Optional[datetime] = Field(
        None, alias="publishedAt", description="Publication timestamp"
    )

    model_config = ConfigDict(populate_by_name=True)


class Action(BaseModel):
    """Suggested follow-up action for voice response."""

    id: str = Field(..., description="Unique action identifier")
    label: str = Field(..., description="Human-readable action label for UI/voice")
    args: Optional[dict[str, Any]] = Field(
        default=None, description="Action arguments"
    )

    model_config = ConfigDict(populate_by_name=True)


class Telemetry(BaseModel):
    """Debug/performance telemetry for voice responses."""

    latency_ms: int = Field(
        ..., alias="latencyMs", description="Total response latency in milliseconds"
    )
    mode: Literal["voice"] = Field(..., description="Response mode")
    tools: list[str] = Field(
        default_factory=list, description="Tools invoked during processing"
    )
    model: Optional[str] = Field(None, description="AI model used for response generation")

    model_config = ConfigDict(populate_by_name=True)


def enforce_word_limit(text: str, max_words: int = 45) -> str:
    """
    Trim text to respect max word count, ending at sentence boundary if possible.

    Args:
        text: Input text to trim
        max_words: Maximum number of words allowed

    Returns:
        Text trimmed to max_words, preferring sentence boundaries
    """
    words = text.split()
    if len(words) <= max_words:
        return text

    # Try to find sentence boundary within limit
    trimmed = " ".join(words[:max_words])

    # Look for last sentence-ending punctuation
    for punct in [". ", "! ", "? "]:
        last_sentence_end = trimmed.rfind(punct)
        if last_sentence_end > len(trimmed) // 2:  # At least half the content
            return trimmed[: last_sentence_end + 1].strip()

    # No good sentence boundary, just add ellipsis
    return trimmed.rstrip(".,!?;:") + "..."


def sanitize_for_tts(text: str) -> str:
    """
    Sanitize text for text-to-speech by removing non-speakable content.

    Removes:
    - URLs (http/https)
    - Markdown links (keeps link text)
    - Markdown tables
    - Code blocks (fenced and inline)
    - Markdown headers
    - Bullet points and list markers
    - Bold/italic markers
    - Extra whitespace

    Args:
        text: Input text to sanitize

    Returns:
        Text suitable for TTS with no URLs, markdown, or code
    """
    if not text:
        return text

    # Remove code blocks (fenced)
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Remove inline code
    text = re.sub(r"`[^`]+`", "", text)

    # Remove markdown headers but keep text
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)

    # Remove bullet points and list markers
    text = re.sub(r"^[\*\-\+]\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\d+\.\s*", "", text, flags=re.MULTILINE)

    # Remove bold/italic markers but keep text
    text = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text)
    text = re.sub(r"_{1,2}([^_]+)_{1,2}", r"\1", text)

    # Remove markdown links but keep text: [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Remove standalone URLs (http/https)
    text = re.sub(r"https?://\S+", "", text)

    # Remove markdown tables (lines with pipes)
    text = re.sub(r"\|[^\n]+\|", "", text)
    text = re.sub(r"[-|]+\n", "", text)

    # Clean up extra whitespace
    text = re.sub(r"\n{2,}", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


class VoiceResponse(BaseModel):
    """Complete voice mode response with spoken text, sources, and actions."""

    speak_text: str = Field(
        ...,
        alias="speakText",
        description="Concise text optimized for TTS (no URLs, no tables)",
    )
    answer_text: str = Field(
        ..., alias="answerText", description="Full markdown answer for display"
    )
    sources: list[Source] = Field(
        default_factory=list, description="News/article sources referenced"
    )
    actions: list[Action] = Field(
        default_factory=list,
        max_length=3,
        description="Suggested follow-up actions (0-3)",
    )
    telemetry: Optional[Telemetry] = Field(
        None, description="Debug telemetry (when enabled)"
    )

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("speak_text", mode="before")
    @classmethod
    def sanitize_speak_text(cls, v: str) -> str:
        """Remove URLs and other non-speakable content from speak_text."""
        if not isinstance(v, str):
            return v
        return sanitize_for_tts(v)

    @model_validator(mode="after")
    def validate_speak_text_no_urls(self) -> "VoiceResponse":
        """Final validation that speak_text contains no URLs."""
        if "http://" in self.speak_text or "https://" in self.speak_text:
            raise ValueError("speak_text must not contain URLs")
        return self


class UIResponse(BaseModel):
    """UI mode response with markdown answer."""

    answer: str = Field(..., description="Markdown-formatted answer")
