"""Main entry point for the VoiceVista FastAPI application."""
import os
import uvicorn
import logging

logger = logging.getLogger(__name__)


def main():
    """Run the FastAPI application with Uvicorn."""
    port = int(os.getenv("PORT", 5000))
    reload = os.getenv("ENVIRONMENT", "development").lower() == "development"
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        reload=reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()
