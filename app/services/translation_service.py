"""Translation and text-to-speech services."""
import asyncio
import logging
import os
import uuid
from typing import Optional

import edge_tts
from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)

MALE_VOICES = {
    "en": "en-IN-PrabhatNeural", "hi": "hi-IN-MadhurNeural", "es": "es-ES-AlvaroNeural",
    "fr": "fr-FR-HenriNeural", "de": "de-DE-ConradNeural", "gu": "gu-IN-NiranjanNeural",
    "ur": "ur-PK-AsadNeural", "bn": "bn-IN-BashkarNeural", "ta": "ta-IN-ValluvarNeural",
    "mr": "mr-IN-ManoharNeural", "kn": "kn-IN-GaganNeural",
}
DEFAULT_MALE_VOICE = "en-IN-PrabhatNeural"


def get_male_voice(language: str) -> str:
    return MALE_VOICES.get(language.lower(), DEFAULT_MALE_VOICE)


async def translate_text_in_chunks(text: str, target_language: str, chunk_size: int = 3000) -> str:
    """Translate text in chunks to avoid provider limits."""
    if not text or text.isspace():
        return ""
    translator = GoogleTranslator(source="auto", target=target_language)
    translated_chunks = []
    for start in range(0, len(text), chunk_size):
        chunk = text[start:start + chunk_size]
        try:
            translated_chunks.append(await asyncio.to_thread(translator.translate, chunk))
        except Exception as exc:
            logger.error("Translation chunk failed: %s", exc)
            translated_chunks.append(chunk)
    return " ".join(chunk for chunk in translated_chunks if chunk)


async def _run_tts_for_chunk(chunk: str, path: str, language: str):
    """Run Edge TTS for a single chunk."""
    try:
        await edge_tts.Communicate(text=chunk, voice=get_male_voice(language)).save(path)
    except Exception as tts_err:
        logger.warning(f"Edge TTS failed for voice {get_male_voice(language)}, retrying with default voice {DEFAULT_MALE_VOICE}: {tts_err}")
        await edge_tts.Communicate(text=chunk, voice=DEFAULT_MALE_VOICE).save(path)
    return path


async def synthesize_speech_safely(text: str, output_path: str, language: str, output_folder: str, ffmpeg_cmd: str) -> bool:
    """Generate the original whole-transcript Edge TTS audio, splitting large input safely."""
    if not text or text.isspace():
        return False
    chunks = [text[index:index + 4000] for index in range(0, len(text), 4000)]
    files = []
    try:
        # Run TTS chunk requests CONCURRENTLY to massively speed up TTS step
        tasks = []
        for index, chunk in enumerate(chunks):
            path = output_path if len(chunks) == 1 else os.path.join(output_folder, f"tts_chunk_{index}_{uuid.uuid4().hex}.mp3")
            files.append(path)
            tasks.append(_run_tts_for_chunk(chunk, path, language))
            
        await asyncio.gather(*tasks)

        if len(files) == 1:
            return True
        concat_file = os.path.join(output_folder, f"concat_{uuid.uuid4().hex}.txt")
        with open(concat_file, "w", encoding="utf-8") as handle:
            for path in files:
                escaped_path = os.path.abspath(path).replace("\\", "/")
                handle.write(f"file '{escaped_path}'\n")
        process = await asyncio.create_subprocess_exec(ffmpeg_cmd, "-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy", "-y", output_path)
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise Exception(f"FFmpeg concat failed with exit code {process.returncode}")
        os.remove(concat_file)
        for path in files:
            os.remove(path)
        return True
    except Exception as exc:
        logger.exception("Speech synthesis failed: %s", exc)
        for path in files:
            if path != output_path and os.path.exists(path):
                os.remove(path)
        return False
