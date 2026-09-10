"""FastAPI application initialization."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
import logging

from app.config import settings
from app.services.whisper_service import initialize_models

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Startup
    logger.info("Starting VoiceVista application...")
    logger.info("Loading AI models...")
    await initialize_models()
    logger.info("Application started successfully")

    yield

    # Shutdown
    logger.info("Shutting down VoiceVista application...")


# Create FastAPI app
app = FastAPI(
    title="VoiceVista API",
    description="Video Dubbing and Speech-to-Speech Translation with AI-powered speech recognition",
    version="2.0.0",
    lifespan=lifespan
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Include routers
from app.routes import pages, video

app.include_router(pages.router, tags=["Pages"])
app.include_router(video.router, tags=["Video"])

# Debug routes (only in development)
try:
    from app.routes import debug
    app.include_router(debug.router, prefix="/debug", tags=["Debug"])
except ImportError:
    pass


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": "VoiceVista",
        "version": "2.0.0"
    }
