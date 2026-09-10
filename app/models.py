"""Pydantic models for request/response validation."""
from pydantic import BaseModel, Field
from typing import Optional


class VideoTranslationRequest(BaseModel):
    """Request model for video translation."""
    language: str = Field(..., description="Target language code")


class YouTubeTranslationRequest(BaseModel):
    """Request model for YouTube video translation."""
    youtube_link: str = Field(..., description="YouTube video URL")
    language: str = Field(..., description="Target language code")


class TranslationResponse(BaseModel):
    """Response model for translation results."""
    original_text: str
    translated_text: str
    summary: Optional[str] = None
    translated_summary: Optional[str] = None
    original_video_url: Optional[str] = None
    translated_video_url: Optional[str] = None


class VideoListItem(BaseModel):
    """Model for video list items."""
    filename: str
    date: str
    url: str
