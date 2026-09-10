"""Video processing service for translation workflows."""
import asyncio
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import yt_dlp
from deep_translator import GoogleTranslator
from fastapi import UploadFile

from app.config import settings
from app.services.ffmpeg_service import adjust_audio_speed, ensure_ffmpeg_available, get_audio_duration, get_ffmpeg_cmd, get_video_duration
from app.services.translation_service import summarize_text, synthesize_speech_safely, translate_text_in_chunks
from app.services.whisper_service import get_summarizer, transcribe_audio
from app.utils.file_utils import unique_filename
from app.utils.subprocess_helper import run_command_async

logger = logging.getLogger(__name__)


async def download_youtube_video(url: str, save_path: str) -> str:
    def download() -> str:
        options = {"format": "bestvideo+bestaudio/best", "outtmpl": os.path.join(save_path, "%(title)s.%(ext)s"), "nocheckcertificate": True, "retries": 10, "fragment_retries": 10, "socket_timeout": 60}
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
    try:
        return await asyncio.to_thread(download)
    except Exception as exc:
        raise Exception(f"Failed to download YouTube video: {exc}") from exc


async def process_video(video_path: str, target_language: str) -> Dict:
    """Original whole-transcript translation and merge workflow."""
    ensure_ffmpeg_available()
    output_id = uuid.uuid4().hex
    audio_path = os.path.join(settings.output_folder, f"extracted_audio_{output_id}.wav")
    translated_audio = os.path.join(settings.output_folder, f"translated_audio_{output_id}.mp3")
    output_video = os.path.join(settings.final_output, f"final_video_{output_id}.mp4")
    temporary_files = [audio_path, translated_audio]
    try:
        ffmpeg = get_ffmpeg_cmd()
        await run_command_async([ffmpeg, "-i", video_path, "-q:a", "0", "-map", "a", "-y", audio_path], check=True)
        result = await transcribe_audio(audio_path)
        transcription = result["text"]
        summary = await summarize_text(transcription, get_summarizer())
        translated_text = await translate_text_in_chunks(transcription, target_language)
        translated_summary = None
        if summary:
            translated_summary = await asyncio.to_thread(GoogleTranslator(source="auto", target=target_language).translate, summary)
        if not await synthesize_speech_safely(translated_text, translated_audio, target_language, str(settings.output_folder), ffmpeg):
            raise Exception("Failed to generate speech from translated text")
        video_duration = await get_video_duration(video_path)
        audio_duration = await get_audio_duration(translated_audio)
        audio_to_use = translated_audio
        if audio_duration and video_duration and abs(audio_duration - video_duration) > 1.0:
            adjusted = os.path.join(settings.output_folder, f"adjusted_{output_id}.mp3")
            temporary_files.append(adjusted)
            if await adjust_audio_speed(translated_audio, video_duration, adjusted):
                audio_to_use = adjusted
        await run_command_async([ffmpeg, "-i", video_path, "-i", audio_to_use, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-shortest", "-y", output_video], check=True)
        return {"original_video_url": f"/static/uploads/{os.path.basename(video_path)}", "translated_video_url": f"/static/processed/{os.path.basename(output_video)}", "original_text": transcription, "translated_text": translated_text, "summary": summary, "translated_summary": translated_summary}
    finally:
        for path in temporary_files:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass


async def process_uploaded_video(video: UploadFile, language: str) -> Dict:
    video_path = os.path.join(settings.upload_folder, unique_filename(video.filename))
    try:
        content = await video.read()
        if not content:
            raise Exception("Uploaded file is empty")
        with open(video_path, "wb") as output:
            output.write(content)
        return await process_video(video_path, language)
    except Exception:
        if os.path.exists(video_path):
            os.remove(video_path)
        raise


async def process_youtube_video(youtube_link: str, language: str) -> Dict:
    return await process_video(await download_youtube_video(youtube_link, str(settings.upload_folder)), language)


async def list_processed_videos() -> List[Dict]:
    try:
        videos = []
        for filename in os.listdir(settings.final_output):
            if filename.endswith(".mp4"):
                path = os.path.join(settings.final_output, filename)
                videos.append({"filename": filename, "date": datetime.fromtimestamp(os.path.getctime(path)).strftime("%Y-%m-%d %H:%M:%S"), "url": f"/static/processed/{filename}"})
        return sorted(videos, key=lambda item: item["date"], reverse=True)
    except Exception:
        return []
