"""Main entry point for the VoiceVista FastAPI application."""
import uvicorn
import logging

logger = logging.getLogger(__name__)


def main():
    """Run the FastAPI application with Uvicorn."""
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=5000,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    main()
