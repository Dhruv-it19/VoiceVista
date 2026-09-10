"""FFmpeg operations and utilities with Windows compatibility."""
import os
import subprocess
import logging
import shutil
import asyncio

logger = logging.getLogger(__name__)


def _resolve_binary(candidate_names: list) -> str:
    """Return full path to the first found binary from candidate names."""
    # Try PATH first
    for name in candidate_names:
        path = shutil.which(name)
        if path:
            return path

    # Try common locations (Windows focused)
    common_dirs = [
        os.path.join(os.getcwd(), 'ffmpeg', 'bin'),
        r"C:\\ffmpeg\\bin",
        r"C:\\Program Files\\ffmpeg\\bin",
        r"C:\\Program Files (x86)\\ffmpeg\\bin",
    ]
    exe_suffix = '.exe' if os.name == 'nt' else ''
    for base in common_dirs:
        for name in candidate_names:
            candidate = os.path.join(base, name + exe_suffix)
            if os.path.exists(candidate):
                return candidate
    return None


# Initialize FFmpeg binaries
FFMPEG_CMD = _resolve_binary(["ffmpeg"])
FFPROBE_CMD = _resolve_binary(["ffprobe"])

if FFMPEG_CMD:
    logger.info(f"ffmpeg found at: {FFMPEG_CMD}")
else:
    logger.warning("ffmpeg not found in PATH or common locations")

if FFPROBE_CMD:
    logger.info(f"ffprobe found at: {FFPROBE_CMD}")
else:
    logger.warning("ffprobe not found in PATH or common locations")


def ensure_ffmpeg_available():
    """Check if FFmpeg/FFprobe are available."""
    if not FFMPEG_CMD or not FFPROBE_CMD:
        raise Exception(
            "FFmpeg/FFprobe not found. Install FFmpeg and ensure 'ffmpeg' and 'ffprobe' are in PATH, "
            "or place binaries under 'ffmpeg\\bin' in the project directory."
        )


async def get_video_duration(video_path: str) -> float:
    """Get the duration of a video file in seconds."""
    try:
        if not FFPROBE_CMD:
            raise FileNotFoundError("ffprobe not found")

        # Check if file exists
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        cmd = [
            FFPROBE_CMD,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]

        logger.info(f"Getting duration for: {video_path}")

        # Use subprocess.run in a thread for Windows compatibility
        def run_ffprobe():
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )

        result = await asyncio.to_thread(run_ffprobe)

        if result.returncode != 0:
            error_msg = result.stderr if result.stderr else "Unknown error"
            logger.error(f"ffprobe failed with return code {result.returncode}: {error_msg}")
            raise Exception(f"ffprobe error: {error_msg}")

        output = result.stdout.strip()
        if not output:
            raise Exception("ffprobe returned empty output - file may not have video stream")

        duration = float(output)
        logger.info(f"Video duration: {duration} seconds")
        return duration
    except ValueError as e:
        logger.error(f"Could not parse duration from ffprobe output: {e}")
        raise Exception(f"Invalid duration format from ffprobe: {e}")
    except Exception as e:
        logger.error(f"Error getting video duration: {e}")
        raise


async def get_audio_duration(audio_path: str) -> float:
    """Get the duration of an audio file in seconds."""
    try:
        if not FFPROBE_CMD:
            raise FileNotFoundError("ffprobe not found")

        # Check if file exists
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        cmd = [
            FFPROBE_CMD,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ]

        logger.info(f"Getting duration for: {audio_path}")

        # Use subprocess.run in a thread for Windows compatibility
        def run_ffprobe():
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )

        result = await asyncio.to_thread(run_ffprobe)

        if result.returncode != 0:
            error_msg = result.stderr if result.stderr else "Unknown error"
            logger.error(f"ffprobe failed with return code {result.returncode}: {error_msg}")
            raise Exception(f"ffprobe error: {error_msg}")

        output = result.stdout.strip()
        if not output:
            raise Exception("ffprobe returned empty output - file may not have audio stream")

        duration = float(output)
        logger.info(f"Audio duration: {duration} seconds")
        return duration
    except ValueError as e:
        logger.error(f"Could not parse duration from ffprobe output: {e}")
        raise Exception(f"Invalid duration format from ffprobe: {e}")
    except Exception as e:
        logger.error(f"Error getting audio duration: {e}")
        raise


async def adjust_audio_speed(audio_path: str, target_duration: float, output_path: str) -> bool:
    """Adjust audio speed to match target duration without changing pitch."""
    try:
        current_duration = await get_audio_duration(audio_path)
        if not current_duration:
            return False

        speed_factor = current_duration / target_duration
        logger.info(f"Adjusting audio speed: current={current_duration}s, target={target_duration}s, factor={speed_factor:.2f}")

        # Build atempo filter
        if 0.5 <= speed_factor <= 2.0:
            filter_complex = f"atempo={speed_factor}"
        elif speed_factor > 2.0:
            remaining = speed_factor
            filter_parts = []
            while remaining > 1.0:
                factor = min(2.0, remaining)
                filter_parts.append(f"atempo={factor}")
                remaining /= factor
                if len(filter_parts) >= 5:
                    break
            filter_complex = ",".join(filter_parts)
        elif speed_factor < 0.5:
            remaining = speed_factor
            filter_parts = []
            while remaining < 1.0:
                factor = max(0.5, remaining)
                filter_parts.append(f"atempo={factor}")
                remaining /= factor
                if len(filter_parts) >= 5:
                    break
            filter_complex = ",".join(filter_parts)

        if not FFMPEG_CMD:
            raise FileNotFoundError("ffmpeg not found")

        cmd = [
            FFMPEG_CMD,
            "-i", audio_path,
            "-filter:a", filter_complex,
            "-y", output_path
        ]

        # Use subprocess.run in a thread for Windows compatibility
        def run_ffmpeg():
            return subprocess.run(
                cmd,
                capture_output=True,
                check=False
            )

        result = await asyncio.to_thread(run_ffmpeg)

        if result.returncode != 0:
            return False

        logger.info(f"Audio speed adjusted to match video duration: {output_path}")
        return True
    except Exception as e:
        logger.error(f"Error adjusting audio speed: {e}")
        return False


def get_ffmpeg_cmd():
    """Get FFmpeg command path."""
    return FFMPEG_CMD


def get_ffprobe_cmd():
    """Get FFprobe command path."""
    return FFPROBE_CMD
