"""Speech recognition service with Groq Whisper API (primary) and Web Speech / local fallback."""
import asyncio
import logging
import os
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)

groq_client = None
local_whisper_model = None
device = None


async def initialize_models():
    """Initialize lightweight services on startup without downloading heavy models."""
    global groq_client, device
    try:
        api_key = settings.groq_api_key or os.getenv("GROQ_API_KEY")
        if api_key:
            try:
                from groq import Groq
                groq_client = Groq(api_key=api_key)
                logger.info(f"Groq API initialized as primary speech-to-text service (model: {settings.groq_model})")
            except Exception as exc:
                logger.warning(f"Failed to initialize Groq client: {exc}")
                groq_client = None
        else:
            logger.info("GROQ_API_KEY not found in environment. Groq API will check per request or use Web Speech API fallback.")
    except Exception as exc:
        logger.error(f"Error during model initialization: {exc}")


def _transcribe_with_groq(audio_path: str) -> str:
    """Transcribe audio file via Groq Whisper API."""
    global groq_client
    api_key = settings.groq_api_key or os.getenv("GROQ_API_KEY")
    if not groq_client:
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set in environment or .env file.")
        from groq import Groq
        groq_client = Groq(api_key=api_key)

    model_name = settings.groq_model or "whisper-large-v3"
    logger.info(f"Transcribing audio with Groq Whisper API ({model_name})...")
    with open(audio_path, "rb") as file:
        transcription = groq_client.audio.transcriptions.create(
            file=(os.path.basename(audio_path), file.read()),
            model=model_name,
            response_format="json"
        )
    return transcription.text


def _get_local_whisper():
    """Lazy load local whisper model only as secondary fallback if installed and available."""
    global local_whisper_model, device
    if local_whisper_model is None:
        import torch
        import whisper
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("Loading local Whisper model on demand...")
        local_whisper_model = whisper.load_model("base").to(device)
    return local_whisper_model


async def transcribe_audio(audio_path: str, fallback_text: Optional[str] = None) -> dict:
    """
    Transcribe audio file using Groq Whisper API (primary).
    Falls back to Web Speech API text (fallback_text) or local model if primary fails.
    """
    clean_fallback = (fallback_text or "").strip()

    # 1. Try Groq Whisper API (Primary Service)
    try:
        text = await asyncio.to_thread(_transcribe_with_groq, audio_path)
        if text and text.strip():
            logger.info("Transcription completed successfully via Groq Whisper API.")
            return {"text": text.strip(), "provider": "groq"}
    except Exception as groq_err:
        logger.warning(f"Groq Whisper API transcription unavailable/failed: {groq_err}")

    # 2. Try Browser Web Speech API Fallback text if user provided one
    if clean_fallback:
        logger.info("Using Web Speech API fallback transcript provided by client.")
        return {"text": clean_fallback, "provider": "web_speech_fallback"}

    # 3. Try Local Whisper on demand if installed
    try:
        model = _get_local_whisper()
        import torch
        logger.info("Transcribing using local Whisper fallback...")
        res = await asyncio.to_thread(model.transcribe, audio_path, fp16=torch.cuda.is_available())
        return {"text": res["text"].strip(), "provider": "local_whisper"}
    except Exception as local_err:
        logger.error(f"Local Whisper fallback also failed: {local_err}")

    raise Exception(
        "Transcription failed. Groq API key is not configured (GROQ_API_KEY), and no Web Speech fallback text was provided. "
        "Please set GROQ_API_KEY in your .env file or use Web Speech transcription."
    )


def get_whisper_model():
    return local_whisper_model


def get_device():
    return device
