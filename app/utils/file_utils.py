"""Utility functions for file operations."""
import os
import re
from datetime import datetime
import uuid


def sanitize_filename(filename: str) -> str:
    """Remove special characters and emojis from filename."""
    # Get file extension
    name, ext = os.path.splitext(filename)

    # Remove emojis and special characters, keep only alphanumeric, spaces, hyphens, underscores
    name = re.sub(r'[^\w\s\-.]', '', name)

    # Replace multiple spaces with single space
    name = re.sub(r'\s+', '_', name)

    # Remove leading/trailing spaces and dots
    name = name.strip('._')

    # If name is empty after sanitization, use a default
    if not name:
        name = "file"

    return name + ext


def unique_filename(filename: str) -> str:
    """Generate a unique filename by appending a timestamp and UUID."""
    # First sanitize the filename
    filename = sanitize_filename(filename)

    name, ext = os.path.splitext(filename)
    unique_id = datetime.now().strftime('%Y%m%d%H%M%S') + '_' + str(uuid.uuid4())[:8]
    return f"{name}_{unique_id}{ext}"


def is_tesseract_installed() -> bool:
    """Check if Tesseract OCR is installed and available in the PATH."""
    import shutil
    return shutil.which('tesseract') is not None
