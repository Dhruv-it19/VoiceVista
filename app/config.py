"""Application configuration using Pydantic Settings."""
from pathlib import Path
from typing import Optional
import os


class Settings:
    """Application settings."""

    app_name: str = "VoiceVista"
    upload_folder: Path = Path("static/uploads")
    output_folder: Path = Path("outputs")
    final_output: Path = Path("static/processed")

    # Model settings
    whisper_model: str = "base"
    device: str = "cuda"  # or "cpu"

    # File size limits (500MB)
    max_file_size: int = 500 * 1024 * 1024

    def __init__(self):
        """Initialize settings and create directories."""
        self.upload_folder.mkdir(parents=True, exist_ok=True)
        self.output_folder.mkdir(parents=True, exist_ok=True)
        self.final_output.mkdir(parents=True, exist_ok=True)


settings = Settings()
