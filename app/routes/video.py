"""Video processing routes."""
import logging
from typing import Optional
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.services.video_processor import process_uploaded_video, process_youtube_video, list_processed_videos

router = APIRouter()
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)


def url_for(endpoint: str, **values):
    routes = {"static": "/static", "main": "/main", "index": "/", "process": "/process", "process_youtube": "/process_youtube", "get_translated_videos": "/get_translated_videos"}
    if endpoint == "static" and "filename" in values:
        return f"/static/{values['filename']}"
    if endpoint == "download_file" and "filename" in values:
        return f"/download/{values['filename']}"
    return routes.get(endpoint, "/")


templates.env.globals["url_for"] = url_for


@router.post("/process", response_class=HTMLResponse)
async def process_video(
    request: Request,
    video: UploadFile = File(...),
    language: str = Form(...),
    fallback_text: Optional[str] = Form(None)
):
    try:
        result = await process_uploaded_video(video, language, fallback_text=fallback_text)
        return templates.TemplateResponse(request=request, name="result.html", context=result)
    except Exception as exc:
        logger.exception("Video processing failed")
        return templates.TemplateResponse(request=request, name="error.html", context={"error": str(exc) or "An unknown error occurred during video processing"})


@router.post("/process_youtube", response_class=HTMLResponse)
async def process_youtube(
    request: Request,
    youtube_link: str = Form(...),
    language: str = Form(...),
    fallback_text: Optional[str] = Form(None)
):
    try:
        result = await process_youtube_video(youtube_link, language, fallback_text=fallback_text)
        return templates.TemplateResponse(request=request, name="result.html", context=result)
    except Exception as exc:
        logger.error("YouTube processing failed: %s", exc)
        return templates.TemplateResponse(request=request, name="error.html", context={"error": str(exc)})


@router.get("/get_translated_videos")
async def get_translated_videos():
    try:
        return JSONResponse(content=await list_processed_videos())
    except Exception:
        return JSONResponse(content=[])
