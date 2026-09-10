"""Debug endpoint to test video processing."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import os
from app.services.ffmpeg_service import get_video_duration, FFMPEG_CMD, FFPROBE_CMD

router = APIRouter()

@router.get("/debug/ffmpeg")
async def debug_ffmpeg():
    """Debug FFmpeg configuration."""
    return JSONResponse({
        "ffmpeg_cmd": FFMPEG_CMD,
        "ffprobe_cmd": FFPROBE_CMD,
        "ffmpeg_exists": os.path.exists(FFMPEG_CMD) if FFMPEG_CMD else False,
        "ffprobe_exists": os.path.exists(FFPROBE_CMD) if FFPROBE_CMD else False,
    })

@router.get("/debug/test-video/{filename}")
async def debug_test_video(filename: str):
    """Test video duration detection."""
    try:
        video_path = os.path.join("static/uploads", filename)

        if not os.path.exists(video_path):
            return JSONResponse({
                "error": f"File not found: {video_path}",
                "exists": False
            })

        duration = await get_video_duration(video_path)

        return JSONResponse({
            "success": True,
            "video_path": video_path,
            "duration": duration,
            "file_size": os.path.getsize(video_path)
        })
    except Exception as e:
        return JSONResponse({
            "error": str(e),
            "traceback": str(e.__class__.__name__)
        })
