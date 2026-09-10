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


async def summarize_text(text: str, summarizer) -> Optional[str]:
    if not summarizer:
        return None
    try:
        maximum = summarizer.model.config.max_position_embeddings
        text = text[:maximum]
        words = len(text.split())
        target = max(30, min(int(words * 0.60), 500))
        result = await asyncio.to_thread(summarizer, text, max_length=target, min_length=max(15, int(target * 0.5)), do_sample=False)
        return result[0]["summary_text"] if result else None
    except Exception as exc:
        logger.error("Summary generation failed: %s", exc)
        return None


async def synthesize_speech_safely(text: str, output_path: str, language: str, output_folder: str, ffmpeg_cmd: str) -> bool:
    """Generate the original whole-transcript Edge TTS audio, splitting large input safely."""
    if not text or text.isspace():
        return False
    chunks = [text[index:index + 4000] for index in range(0, len(text), 4000)]
    files = []
    try:
        for index, chunk in enumerate(chunks):
            path = output_path if len(chunks) == 1 else os.path.join(output_folder, f"tts_chunk_{index}_{uuid.uuid4().hex}.mp3")
            await edge_tts.Communicate(text=chunk, voice=get_male_voice(language)).save(path)
            files.append(path)
        if len(files) == 1:
            return True
        concat_file = os.path.join(output_folder, f"concat_{uuid.uuid4().hex}.txt")
        with open(concat_file, "w", encoding="utf-8") as handle:
            for path in files:
                handle.write(f"file '{os.path.abspath(path)}'\n")
        process = await asyncio.create_subprocess_exec(ffmpeg_cmd, "-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy", "-y", output_path)
        await process.communicate()
        os.remove(concat_file)
        for path in files:
            os.remove(path)
        return True
    except Exception as exc:
        logger.error("Speech synthesis failed: %s", exc)
        for path in files:
            if path != output_path and os.path.exists(path):
                os.remove(path)
        return False
