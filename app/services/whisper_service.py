"""Whisper service for speech recognition and model management."""
import logging
import torch
import whisper
from transformers import pipeline, logging as transformers_logging
import asyncio

logger = logging.getLogger(__name__)
transformers_logging.set_verbosity(transformers_logging.ERROR)

whisper_model = None
summarizer = None
device = None


async def initialize_models():
    """Initialize Whisper and summarization models on startup."""
    global whisper_model, summarizer, device
    try:
        logger.info("Checking CUDA availability...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {device}")
        if device == "cuda":
            logger.info(f"CUDA Device: {torch.cuda.get_device_name(0)}")
            logger.info(f"CUDA Version: {torch.version.cuda}")
        logger.info("Loading Whisper model...")
        whisper_model = whisper.load_model("base").to(device)
        logger.info("Whisper model loaded successfully")
        logger.info("Loading summarization model...")
        try:
            summarizer = pipeline("text-generation", model="facebook/bart-large-cnn", device="cpu", truncation=True, task="summarization")
        except Exception:
            logger.warning("Could not load summarization model, summarization will be disabled")
            summarizer = None
        if summarizer:
            logger.info("Summarization model loaded successfully")
    except Exception as exc:
        logger.error(f"Error loading models: {exc}")
        whisper_model = None
        summarizer = None


async def transcribe_audio(audio_path: str) -> dict:
    """Transcribe audio file using Whisper model."""
    if not whisper_model:
        raise Exception("Whisper model not loaded")
    return await asyncio.to_thread(whisper_model.transcribe, audio_path, fp16=torch.cuda.is_available())


def get_whisper_model():
    return whisper_model


def get_summarizer():
    return summarizer


def get_device():
    return device
