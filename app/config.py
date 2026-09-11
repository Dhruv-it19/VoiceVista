"""Application configuration using Pydantic Settings."""
from pathlib import Path
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings."""

    app_name: str = "VoiceVista"
    upload_folder: Path = Path("static/uploads")
    output_folder: Path = Path("outputs")
    final_output: Path = Path("static/processed")

    # API Keys & Services
    groq_api_key: Optional[str] = os.getenv("GROQ_API_KEY")
    groq_model: str = os.getenv("GROQ_MODEL", "whisper-large-v3")

    # Model settings (optional local fallback)
    whisper_model: str = "base"
    device: str = "cuda"  # or "cpu"

    # File size limits (500MB)
    max_file_size: int = 500 * 1024 * 1024

    # Comma-separated origins for the separate frontend application.
    frontend_origins: list[str] = [
        origin.strip()
        for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if origin.strip()
    ]

    def __init__(self):
        """Initialize settings and create directories."""
        self.upload_folder.mkdir(parents=True, exist_ok=True)
        self.output_folder.mkdir(parents=True, exist_ok=True)
        self.final_output.mkdir(parents=True, exist_ok=True)


settings = Settings()
