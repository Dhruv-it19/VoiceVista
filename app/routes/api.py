"""JSON API routes for the separate VoiceVista frontend."""
import logging
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.models import TranslationResponse
from app.routes.pages import LANGUAGES
from app.services.video_processor import process_uploaded_video, process_youtube_video

router = APIRouter(prefix="/api", tags=["Translation API"])
logger = logging.getLogger(__name__)


@router.get("/languages")
async def get_languages() -> dict[str, str]:
    """Return the languages supported by the translation pipeline."""
    return LANGUAGES


@router.post("/translate/upload", response_model=TranslationResponse)
async def translate_upload(
    video: UploadFile = File(...),
    language: str = Form(...),
    fallback_text: Optional[str] = Form(None),
):
    """Translate an uploaded video and return media URLs plus transcripts."""
    if language not in LANGUAGES:
        raise HTTPException(status_code=422, detail="Unsupported target language")
    if not video.filename:
        raise HTTPException(status_code=422, detail="A video file is required")

    try:
        return await process_uploaded_video(video, language, fallback_text=fallback_text)
    except Exception as exc:
        logger.exception("API upload translation failed")
        raise HTTPException(status_code=500, detail=str(exc) or "Translation failed") from exc


@router.post("/translate/youtube", response_model=TranslationResponse)
async def translate_youtube(
    youtube_link: str = Form(...),
    language: str = Form(...),
    fallback_text: Optional[str] = Form(None),
):
    """Translate a YouTube video and return media URLs plus transcripts."""
    if language not in LANGUAGES:
        raise HTTPException(status_code=422, detail="Unsupported target language")
    if not youtube_link.strip():
        raise HTTPException(status_code=422, detail="A YouTube URL is required")

    try:
        return await process_youtube_video(youtube_link, language, fallback_text=fallback_text)
    except Exception as exc:
        logger.exception("API YouTube translation failed")
        raise HTTPException(status_code=500, detail=str(exc) or "Translation failed") from exc
