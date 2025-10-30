from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify
import os
import subprocess
import whisper
from deep_translator import GoogleTranslator
from gtts import gTTS
import uuid
from datetime import datetime
import yt_dlp
import logging
import torch
import math
import time
from transformers import pipeline, logging as transformers_logging
import PyPDF2
import pytesseract
from PIL import Image
from docx import Document as DocxDocument
import re
import io
import shutil  # Added for checking if commands exist in PATH
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Suppress transformer warnings
transformers_logging.set_verbosity(transformers_logging.ERROR)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['OUTPUT_FOLDER'] = 'outputs/'
app.config['FINAL_OUTPUT'] = 'static/processed'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
os.makedirs(app.config['FINAL_OUTPUT'], exist_ok=True)

# Resolve ffmpeg/ffprobe binaries (especially important on Windows)
def _resolve_binary(candidate_names):
    """Return full path to the first found binary from candidate names.

    Tries PATH via shutil.which, then common Windows install locations, and a local ffmpeg/bin directory.
    """
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

FFMPEG_CMD = _resolve_binary(["ffmpeg"])  # full path or None
FFPROBE_CMD = _resolve_binary(["ffprobe"])  # full path or None

if FFMPEG_CMD:
    logger.info(f"ffmpeg found at: {FFMPEG_CMD}")
else:
    logger.warning("ffmpeg not found in PATH or common locations")

if FFPROBE_CMD:
    logger.info(f"ffprobe found at: {FFPROBE_CMD}")
else:
    logger.warning("ffprobe not found in PATH or common locations")

def _ensure_ffmpeg_available():
    if not FFMPEG_CMD or not FFPROBE_CMD:
        raise Exception(
            "FFmpeg/FFprobe not found. Install FFmpeg and ensure 'ffmpeg' and 'ffprobe' are in PATH, "
            "or place binaries under 'ffmpeg\\bin' in the project directory."
        )

# Load Whisper model with CUDA support
try:
    logger.info("Checking CUDA availability...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")
    if device == "cuda":
        logger.info(f"CUDA Device: {torch.cuda.get_device_name(0)}")
        logger.info(f"CUDA Version: {torch.version.cuda}")
    
    logger.info("Loading Whisper model...")
    whisper_model = whisper.load_model("base").to(device)
    logger.info("Whisper model loaded successfully and moved to device")
    
    # Load summarization model on CPU to avoid CUDA memory issues
    logger.info("Loading summarization model...")
    summarizer = pipeline("summarization", model="facebook/bart-large-cnn", device="cpu", truncation=True)
    logger.info("Summarization model loaded successfully")
except Exception as e:
    logger.error(f"Error loading models: {e}")
    whisper_model = None
    summarizer = None

def unique_filename(filename):
    """Generate a unique filename by appending a timestamp and UUID."""
    name, ext = os.path.splitext(filename)
    unique_id = datetime.now().strftime('%Y%m%d%H%M%S') + '_' + str(uuid.uuid4())[:8]
    return f"{name}_{unique_id}{ext}"

def download_youtube_video(url, save_path):
    """Download YouTube video using yt-dlp with improved error handling."""
    logger.info(f"Attempting to download YouTube video: {url}")
    
    # Configure yt-dlp with increased timeout and retry options
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': os.path.join(save_path, '%(title)s.%(ext)s'),
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'no_warnings': False,
        'quiet': False,
        'verbose': True,
        'retries': 10,
        'fragment_retries': 10,
        'retry_sleep_functions': {'http': lambda n: 5 * (n + 1)},
        'socket_timeout': 60,
        'extractor_retries': 5
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            logger.info(f"Successfully downloaded YouTube video to: {file_path}")
            return file_path
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"YouTube download error: {e}")
        raise Exception(f"Failed to download YouTube video: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during YouTube download: {e}")
        raise Exception(f"An unexpected error occurred during YouTube download: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/main')
def main():
    languages = {
        'en': 'English',
        'hi': 'Hindi',
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'gu': 'Gujarati',
        'ur': 'Urdu',
        'bn': 'Bengali',
        'ta': 'Tamil',
        'mr': 'Marathi',
        'kn': 'Kannada',
        'mr': 'Marathi',
    
    }
    return render_template('main.html', languages=languages)

@app.route('/process', methods=['POST'])
def process():
    video = request.files['video']
    target_language = request.form['language']
    if video:
        video_filename = unique_filename(video.filename)
        video_path = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)
        video.save(video_path)
        return process_video(video_path, target_language)

@app.route('/process_youtube', methods=['POST'])
def process_youtube():
    try:
        youtube_link = request.form['youtube_link']
        target_language = request.form['language']
        
        logger.info(f"Processing YouTube video: {youtube_link}")
        
        try:
            video_path = download_youtube_video(youtube_link, app.config['UPLOAD_FOLDER'])
            return process_video(video_path, target_language)
        except Exception as e:
            logger.error(f"YouTube processing error: {e}")
            
            # Create a more user-friendly error message
            error_message = str(e)
            if "Read timed out" in error_message:
                error_message = "The YouTube video download timed out. This could be due to a slow internet connection or YouTube's server issues. Please try again later or try with a different video."
            elif "not available" in error_message:
                error_message = "This YouTube video is not available for download. It might be restricted, private, or removed."
            
            return render_template('error.html', error=error_message)
    except Exception as e:
        logger.error(f"Unexpected error in process_youtube: {e}")
        return render_template('error.html', error=f"An unexpected error occurred: {e}")

def process_video(video_path, target_language):
    """Process video: extract audio, translate, synthesize, and merge."""
    try:
        _ensure_ffmpeg_available()
        # Get video duration
        duration = get_video_duration(video_path)
        if duration is None:
            raise Exception("Could not determine video duration")
        
        # For videos longer than 5 minutes, use chunked processing
        if duration > 300:  # 5 minutes in seconds
            return process_long_video(video_path, target_language, duration)
        
        # Process as normal for shorter videos
        return process_short_video(video_path, target_language)
        
    except Exception as e:
        logger.error(f"Error processing video: {e}")
        return render_template('error.html', error=str(e))

def get_video_duration(video_path):
    """Get the duration of a video file in seconds."""
    try:
        if not FFPROBE_CMD:
            raise FileNotFoundError("ffprobe not found")
        cmd = [
            FFPROBE_CMD,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        logger.info(f"Video duration: {duration} seconds")
        return duration
    except Exception as e:
        logger.error(f"Error getting video duration: {e}")
        return None

def get_audio_duration(audio_path):
    """Get the duration of an audio file in seconds."""
    try:
        if not FFPROBE_CMD:
            raise FileNotFoundError("ffprobe not found")
        cmd = [
            FFPROBE_CMD, 
            "-v", "error", 
            "-show_entries", "format=duration", 
            "-of", "default=noprint_wrappers=1:nokey=1", 
            audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        logger.info(f"Audio duration: {duration} seconds")
        return duration
    except Exception as e:
        logger.error(f"Error getting audio duration: {e}")
        return None

def adjust_audio_speed(audio_path, target_duration, output_path):
    """Adjust audio speed to match target duration without changing pitch."""
    try:
        # Get current audio duration
        current_duration = get_audio_duration(audio_path)
        if not current_duration:
            return False
            
        # Calculate the speed factor needed
        speed_factor = current_duration / target_duration
        
        logger.info(f"Adjusting audio speed: current={current_duration}s, target={target_duration}s, factor={speed_factor:.2f}")
        
        # Use atempo filter to adjust speed (1.0 = normal speed)
        # atempo filter only works in range 0.5-2.0, so we may need to chain filters
        if 0.5 <= speed_factor <= 2.0:
            filter_complex = f"atempo={speed_factor}"
        elif speed_factor > 2.0:
            # For speedup > 2.0, need to chain multiple atempo filters
            # Each atempo instance can handle up to 2.0x 
            remaining = speed_factor
            filter_parts = []
            while remaining > 1.0:
                factor = min(2.0, remaining)
                filter_parts.append(f"atempo={factor}")
                remaining /= factor
                if len(filter_parts) >= 5:  # Practical limit to avoid extreme distortion
                    break
            filter_complex = ",".join(filter_parts)
        elif speed_factor < 0.5:
            # For slowdown > 0.5, need to chain multiple atempo filters
            # Each atempo instance can handle down to 0.5x
            remaining = speed_factor
            filter_parts = []
            while remaining < 1.0:
                factor = max(0.5, remaining)
                filter_parts.append(f"atempo={factor}")
                remaining /= factor
                if len(filter_parts) >= 5:  # Practical limit to avoid extreme distortion
                    break
            filter_complex = ",".join(filter_parts)
        
        # Apply the speed adjustment
        if not FFMPEG_CMD:
            raise FileNotFoundError("ffmpeg not found")
        cmd = [
            FFMPEG_CMD,
            "-i", audio_path,
            "-filter:a", filter_complex,
            "-y", output_path
        ]
        subprocess.run(cmd, check=True)
        logger.info(f"Audio speed adjusted to match video duration: {output_path}")
        return True
    except Exception as e:
        logger.error(f"Error adjusting audio speed: {e}")
        return False

def translate_text_in_chunks(text, target_language, chunk_size=3000):
    """Translate text in chunks to avoid API limits."""
    try:
        if not text or text.isspace():
            logger.warning("Empty text provided for translation")
            return ""
        
        # Split text into chunks to avoid API limits
        chunks = []
        for i in range(0, len(text), chunk_size):
            chunks.append(text[i:i + chunk_size])
        
        translated_chunks = []
        translator = GoogleTranslator(source='auto', target=target_language)
        
        # Translate each chunk
        for i, chunk in enumerate(chunks):
            logger.info(f"Translating chunk {i+1}/{len(chunks)}")
            try:
                if chunk and not chunk.isspace():
                    translated = translator.translate(chunk)
                    if translated:
                        translated_chunks.append(translated)
                    else:
                        logger.warning(f"Empty translation returned for chunk {i+1}")
                        translated_chunks.append("")  # Add empty string to maintain ordering
            except Exception as e:
                logger.error(f"Error translating chunk {i+1}: {e}")
                # Add the original chunk to maintain ordering
                translated_chunks.append(chunk)
        
        # Join all translated chunks
        return " ".join(translated_chunks)
    except Exception as e:
        logger.error(f"Error in translate_text_in_chunks: {e}")
        return text  # Return original text if translation fails

def synthesize_speech_safely(text, output_path, language):
    """Safely generate speech from text, handling large text volumes."""
    # gTTS has a character limit (~max 5000 chars to be safe)
    MAX_CHARS = 4000
    
    if len(text) <= MAX_CHARS:
        # Short text can be processed directly
        try:
            tts = gTTS(text=text, lang=language, slow=False)
            tts.save(output_path)
            return True
        except Exception as e:
            logger.error(f"TTS error for short text: {e}")
            return False
    
    # For longer text, split by sentences and generate multiple audio files
    # Simple sentence-based splitting
    for end_char in ['. ', '! ', '? ', '.\n', '!\n', '?\n']:
        text = text.replace(end_char, end_char + '<SPLIT>')
    
    sentences = text.split('<SPLIT>')
    chunks = []
    current_chunk = ""
    
    # Group sentences into chunks under the limit
    for sentence in sentences:
        if len(current_chunk) + len(sentence) > MAX_CHARS:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + " "
        else:
            current_chunk += sentence + " "
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    logger.info(f"Split TTS input into {len(chunks)} chunks")
    
    # Process each chunk and combine audio files
    temp_files = []
    
    try:
        for i, chunk in enumerate(chunks):
            # Skip empty chunks
            if not chunk.strip():
                continue
                
            # Generate temp file for this chunk
            temp_file = os.path.join(app.config['OUTPUT_FOLDER'], f"tts_chunk_{i}_{uuid.uuid4().hex}.mp3")
            logger.info(f"Generating TTS for chunk {i+1}/{len(chunks)} ({len(chunk)} chars)")
            
            try:
                tts = gTTS(text=chunk, lang=language, slow=False)
                tts.save(temp_file)
                temp_files.append(temp_file)
            except Exception as e:
                logger.error(f"Error in TTS for chunk {i+1}: {e}")
                # Continue with other chunks
        
        # If no files were generated, return failure
        if not temp_files:
            return False
            
        # If only one file was generated, just rename it
        if len(temp_files) == 1:
            os.replace(temp_files[0], output_path)
            return True
            
        # Otherwise, combine all audio chunks
        # Create a file list for ffmpeg
        concat_file = os.path.join(app.config['OUTPUT_FOLDER'], f"concat_{uuid.uuid4().hex}.txt")
        with open(concat_file, "w") as f:
            for tmp in temp_files:
                f.write(f"file '{os.path.abspath(tmp)}'\n")
        
        # Use ffmpeg to concatenate
        if not FFMPEG_CMD:
            raise FileNotFoundError("ffmpeg not found")
        concat_cmd = [
            FFMPEG_CMD,
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            "-y", output_path
        ]
        subprocess.run(concat_cmd, check=True)
        
        # Clean up
        os.remove(concat_file)
        for tmp in temp_files:
            os.remove(tmp)
            
        return True
        
    except Exception as e:
        logger.error(f"Error combining TTS chunks: {e}")
        # Clean up any temp files
        for tmp in temp_files:
            if os.path.exists(tmp):
                os.remove(tmp)
        return False

def summarize_text(text):
    """Generate a summary of the given text using the transformer model."""
    try:
        if not summarizer:
            logger.warning("Summarizer model not available, skipping summarization")
            return None
            
        logger.info("Generating summary")
        
        # Truncate the text if it exceeds the model's maximum input length
        max_input_length = summarizer.model.config.max_position_embeddings
        if len(text) > max_input_length:
            logger.info(f"Text exceeds model's maximum input length ({max_input_length}), truncating")
            text = text[:max_input_length]
        
        # Count approximate number of words in the input text
        word_count = len(text.split())
        logger.info(f"Input text word count: {word_count}")
        
        # Set summary length to approximately 25% of the input text
        target_length = max(30, min(int(word_count * 0.60), 500))  # Enforce min/max bounds
        min_length = max(15, int(target_length * 0.5))  # Minimum length is half the target
        
        logger.info(f"Setting summary length to 25% of input: {target_length} tokens (min: {min_length})")
        
        # Generate summary
        summary_result = summarizer(text, max_length=target_length, min_length=min_length, do_sample=False)
        
        if summary_result and len(summary_result) > 0:
            summary = summary_result[0]['summary_text']
            logger.info(f"Summary generated: {summary[:100]}...")
            logger.info(f"Summary length: approximately {len(summary.split())} words")
            return summary
        else:
            logger.warning("Failed to generate summary")
            return None
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        return None

def process_short_video(video_path, target_language):
    """Process shorter videos using the original method, but with improved TTS sequencing."""
    try:
        logger.info("Processing short video")
        output_id = uuid.uuid4().hex
        
        audio_filename = f"extracted_audio_{output_id}.wav"
        audio_path = os.path.join(app.config['OUTPUT_FOLDER'], audio_filename)

        translated_audio_filename = f"translated_audio_{output_id}.mp3"
        translated_audio_path = os.path.join(app.config['OUTPUT_FOLDER'], translated_audio_filename)

        output_video_filename = f"final_video_{output_id}.mp4"
        output_video_path = os.path.join(app.config['FINAL_OUTPUT'], output_video_filename)

        # Extract audio
        logger.info(f"Extracting audio from video: {video_path}")
        if not FFMPEG_CMD:
            raise FileNotFoundError("ffmpeg not found")
        subprocess.run([FFMPEG_CMD, "-i", video_path, "-q:a", "0", "-map", "a", audio_path], check=True)

        # Speech-to-text using Whisper with CUDA support
        logger.info("Transcribing audio with Whisper")
        if whisper_model:
            result = whisper_model.transcribe(audio_path, fp16=torch.cuda.is_available())
            transcription = result["text"]
            logger.info(f"Transcription completed: {transcription[:100]}...")
        else:
            raise Exception("Whisper model failed to load")

        # Generate summary of transcription
        summary = summarize_text(transcription)
            
        # Translate text in chunks
        logger.info(f"Translating text to {target_language}")
        translated_text = translate_text_in_chunks(transcription, target_language)
        logger.info(f"Translation completed: {translated_text[:100]}...")
        
        # Translate summary if available
        translated_summary = None
        if summary:
            translated_summary = GoogleTranslator(source='auto', target=target_language).translate(summary)
            logger.info(f"Summary translation completed: {translated_summary[:100]}...")

        # Synthesize translated text to audio safely
        logger.info("Converting translated text to speech")
        if not synthesize_speech_safely(translated_text, translated_audio_path, target_language):
            raise Exception("Failed to generate speech from translated text")

        # Get video duration to match audio length
        video_duration = get_video_duration(video_path)
        if not video_duration:
            raise Exception("Could not determine video duration")
            
        # Get audio duration
        audio_duration = get_audio_duration(translated_audio_path)
        if not audio_duration:
            raise Exception("Could not determine audio duration")
            
        # Adjust audio speed if necessary to match video duration
        audio_to_use = translated_audio_path
        if abs(audio_duration - video_duration) > 1.0:  # Only adjust if difference > 1 second
            logger.info(f"Audio duration ({audio_duration}s) differs from video duration ({video_duration}s), adjusting...")
            speed_adjusted_audio = os.path.join(app.config['OUTPUT_FOLDER'], f"adjusted_{output_id}.mp3")
            if adjust_audio_speed(translated_audio_path, video_duration, speed_adjusted_audio):
                # Use the speed-adjusted audio
                audio_to_use = speed_adjusted_audio
            else:
                logger.warning("Failed to adjust audio speed, using original audio")

        # Merge audio and video
        logger.info("Merging audio with original video")
        subprocess.run([
            FFMPEG_CMD,
            "-i", video_path,
            "-i", audio_to_use,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            output_video_path
        ], check=True)
        
        # Clean up temporary files
        os.remove(audio_path)
        os.remove(translated_audio_path)
        if audio_to_use != translated_audio_path:
            os.remove(audio_to_use)
        
        logger.info("Processing completed successfully")
        return render_template(
            'result.html',
            original_video_url=url_for('static', filename=f'uploads/{os.path.basename(video_path)}'),
            translated_video_url=url_for('static', filename=f'processed/{os.path.basename(output_video_path)}'),
            original_text=transcription,
            translated_text=translated_text,
            summary=summary,
            translated_summary=translated_summary
        )
    except Exception as e:
        logger.error(f"Error processing short video: {e}")
        return render_template('error.html', error=str(e))

def process_long_video(video_path, target_language, duration):
    """Process longer videos by breaking them into chunks."""
    try:
        logger.info("Processing long video in chunks")
        
        chunk_duration = 180  # 3-minute chunks
        chunk_count = math.ceil(duration / chunk_duration)
        logger.info(f"Processing video in {chunk_count} chunks")
        
        # Create unique IDs for output files
        output_id = uuid.uuid4().hex
        output_video_filename = f"final_video_{output_id}.mp4"
        output_video_path = os.path.join(app.config['FINAL_OUTPUT'], output_video_filename)
        
        # List to store translated audio segments
        translated_audio_segments = []
        
        # Variables to collect full transcription and translation
        full_transcription = ""
        full_translation = ""
        
        # Process each chunk
        for i in range(chunk_count):
            start_time = i * chunk_duration
            # For the last chunk, adjust duration to not exceed total duration
            current_duration = min(chunk_duration, duration - start_time)
            
            logger.info(f"Processing chunk {i+1}/{chunk_count}: {start_time}-{start_time+current_duration}")
            
            # Extract audio for this chunk
            chunk_audio_filename = f"chunk_{i}_{output_id}.wav"
            chunk_audio_path = os.path.join(app.config['OUTPUT_FOLDER'], chunk_audio_filename)
            
            # Extract audio segment
            if not FFMPEG_CMD:
                raise FileNotFoundError("ffmpeg not found")
            extract_cmd = [
                FFMPEG_CMD,
                "-i", video_path,
                "-ss", str(start_time),
                "-t", str(current_duration),
                "-q:a", "0",
                "-map", "a",
                "-y", chunk_audio_path
            ]
            subprocess.run(extract_cmd, check=True)
            
            # Transcribe audio chunk with CUDA support
            if whisper_model:
                result = whisper_model.transcribe(chunk_audio_path, fp16=torch.cuda.is_available())
                transcription = result["text"]
                logger.info(f"Chunk {i+1} transcription completed ({len(transcription)} chars)")
                full_transcription += transcription + " "
            else:
                raise Exception("Whisper model failed to load")
            
            # Translate text in chunks
            translated_text = translate_text_in_chunks(transcription, target_language)
            logger.info(f"Chunk {i+1} translation completed")
            full_translation += translated_text + " "
            
            # Generate audio for this chunk
            chunk_translated_audio = f"translated_chunk_{i}_{output_id}.mp3"
            chunk_translated_path = os.path.join(app.config['OUTPUT_FOLDER'], chunk_translated_audio)
            
            if not synthesize_speech_safely(translated_text, chunk_translated_path, target_language):
                logger.warning(f"Failed to generate speech for chunk {i+1}, using empty audio")
                # Create a silent audio file as a fallback
                if not FFMPEG_CMD:
                    raise FileNotFoundError("ffmpeg not found")
                silent_cmd = [
                    FFMPEG_CMD,
                    "-f", "lavfi",
                    "-i", f"anullsrc=r=44100:cl=stereo:d={current_duration}",
                    "-y", chunk_translated_path
                ]
                subprocess.run(silent_cmd, check=True)
            
            translated_audio_segments.append(chunk_translated_path)
            os.remove(chunk_audio_path)
        
        # Generate summary of the full transcription
        summary = summarize_text(full_transcription)
        
        # Translate summary if available
        translated_summary = None
        if summary:
            translated_summary = GoogleTranslator(source='auto', target=target_language).translate(summary)
            logger.info(f"Summary translation completed: {translated_summary[:100]}...")
        
        # Combine all audio segments
        logger.info("Combining audio segments...")
        combined_audio = os.path.join(app.config['OUTPUT_FOLDER'], f"combined_{output_id}.mp3")
        
        # Create a file list for ffmpeg
        concat_file = os.path.join(app.config['OUTPUT_FOLDER'], f"concat_{output_id}.txt")
        with open(concat_file, "w") as f:
            for audio_file in translated_audio_segments:
                f.write(f"file '{os.path.abspath(audio_file)}'\n")
        
        # Combine audio segments
        if not FFMPEG_CMD:
            raise FileNotFoundError("ffmpeg not found")
        concat_cmd = [
            FFMPEG_CMD,
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            "-y", combined_audio
        ]
        subprocess.run(concat_cmd, check=True)
        
        # Clean up audio segments
        for audio_file in translated_audio_segments:
            os.remove(audio_file)
        os.remove(concat_file)
        
        # Get audio duration
        audio_duration = get_audio_duration(combined_audio)
        if not audio_duration:
            logger.warning("Could not determine audio duration, using original audio")
            audio_to_use = combined_audio
        elif abs(audio_duration - duration) > 1.0:  # Only adjust if difference > 1 second
            logger.info(f"Audio duration ({audio_duration}s) differs from video duration ({duration}s), adjusting...")
            speed_adjusted_audio = os.path.join(app.config['OUTPUT_FOLDER'], f"adjusted_{output_id}.mp3")
            if adjust_audio_speed(combined_audio, duration, speed_adjusted_audio):
                audio_to_use = speed_adjusted_audio
            else:
                logger.warning("Failed to adjust audio speed, using original audio")
                audio_to_use = combined_audio
        else:
            audio_to_use = combined_audio
        
        # Merge final audio with video
        logger.info("Merging final audio with video")
        subprocess.run([
            FFMPEG_CMD,
            "-i", video_path,
            "-i", audio_to_use,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            output_video_path
        ], check=True)
        
        # Clean up
        os.remove(combined_audio)
        if audio_to_use != combined_audio:
            os.remove(audio_to_use)
        
        logger.info("Long video processing completed successfully")
        return render_template(
            'result.html',
            original_video_url=url_for('static', filename=f'uploads/{os.path.basename(video_path)}'),
            translated_video_url=url_for('static', filename=f'processed/{os.path.basename(output_video_path)}'),
            original_text=full_transcription,
            translated_text=full_translation,
            summary=summary,
            translated_summary=translated_summary
        )
    except Exception as e:
        logger.error(f"Error processing long video: {e}")
        return render_template('error.html', error=str(e))

@app.route('/get_translated_videos')
def get_translated_videos():
    try:
        # Get list of all processed videos
        processed_dir = app.config['FINAL_OUTPUT']
        videos = []
        
        for filename in os.listdir(processed_dir):
            if filename.endswith('.mp4'):
                # Get creation time and format it
                file_path = os.path.join(processed_dir, filename)
                creation_time = os.path.getctime(file_path)
                creation_date = datetime.fromtimestamp(creation_time).strftime('%Y-%m-%d %H:%M:%S')
                
                videos.append({
                    'filename': filename,
                    'date': creation_date,
                    'url': url_for('static', filename=f'processed/{filename}')
                })
        
        # Sort by creation date (newest first)
        videos.sort(key=lambda x: x['date'], reverse=True)
        return jsonify(videos)
    except Exception as e:
        logger.error(f"Error in get_translated_videos: {e}")
        return jsonify([])

@app.route('/documents')
def documents():
    languages = {
        'en': 'English',
        'hi': 'Hindi',
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'gu': 'Gujarati',
        'ur': 'Urdu',
        'bn': 'Bengali',
        'ta': 'Tamil',
        'mr': 'Marathi',
        'kn': 'Kannada',
    }
    return render_template('documents.html', languages=languages)

@app.route('/process_document', methods=['POST'])
def process_document_route():
    try:
        document = request.files['document']
        target_language = request.form['language']
        
        if not document:
            return render_template('error.html', error="No document file uploaded")
        
        # Check if the file has an allowed extension
        allowed_extensions = ['.pdf', '.docx', '.doc', '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif']
        file_extension = os.path.splitext(document.filename)[1].lower()
        
        if file_extension not in allowed_extensions:
            return render_template('error.html', 
                                  error=f"Unsupported file type: {file_extension}. Please upload a PDF, Word document, or image file.")
        
        return process_document(document, target_language)
    
    except Exception as e:
        logger.error(f"Error in process_document_route: {e}")
        return render_template('error.html', error=str(e))

@app.route('/download/<filename>')
def download_file(filename):
    try:
        return send_file(os.path.join(app.config['OUTPUT_FOLDER'], filename), as_attachment=True)
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return render_template('error.html', error=f"Error downloading file: {e}")

def is_tesseract_installed():
    """Check if Tesseract OCR is installed and available in the PATH."""
    return shutil.which('tesseract') is not None

def extract_text_from_pdf(pdf_file):
    """Extract text from a PDF file."""
    try:
        logger.info(f"Extracting text from PDF: {pdf_file}")
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n"
            
            # Clean up the text
            text = re.sub(r'\s+', ' ', text).strip()
            logger.info(f"Successfully extracted {len(text)} characters from PDF")
            
            if not text:
                return "ERROR: No text could be extracted from the PDF. The file might be a scanned document or contain only images."
                
            return text
        except Exception as e:
            logger.error(f"Error reading PDF content: {e}")
            return f"ERROR: Could not read PDF content: {e}"
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        return f"ERROR: Could not extract text from PDF: {e}"

def extract_text_from_docx(docx_file):
    """Extract text from a Word document."""
    try:
        logger.info(f"Extracting text from Word document: {docx_file}")
        try:
            doc = DocxDocument(docx_file)
            text = ""
            for para in doc.paragraphs:
                text += para.text + "\n"
            
            # Clean up the text
            text = re.sub(r'\s+', ' ', text).strip()
            logger.info(f"Successfully extracted {len(text)} characters from Word document")
            
            if not text:
                return "ERROR: No text could be extracted from the Word document. The file might contain only images or shapes."
                
            return text
        except Exception as e:
            logger.error(f"Error reading Word document content: {e}")
            return f"ERROR: Could not read Word document content: {e}"
    except Exception as e:
        logger.error(f"Error extracting text from Word document: {e}")
        return f"ERROR: Could not extract text from Word document: {e}"

def extract_text_from_image(image_file):
    """Extract text from an image using OCR."""
    try:
        logger.info(f"Extracting text from image: {image_file}")
        
        # Check if Tesseract is installed
        if not is_tesseract_installed():
            logger.error("Tesseract OCR is not installed or not in PATH")
            return "ERROR: Tesseract OCR is not installed or not in your PATH. Please install Tesseract OCR and add it to your PATH. See README.md for detailed installation instructions."
        
        try:
            image = Image.open(image_file)
            
            # Preprocess image for better OCR results
            # Convert to grayscale
            if image.mode != 'L':
                image = image.convert('L')
            
            # Try to use Tesseract
            try:
                text = pytesseract.image_to_string(image)
                
                # If successful, clean up the text
                text = re.sub(r'\s+', ' ', text).strip()
                logger.info(f"Successfully extracted {len(text)} characters from image")
                
                if not text:
                    return "ERROR: No text could be extracted from the image. The image might not contain readable text or the quality may be too low."
                    
                return text
            except pytesseract.TesseractNotFoundError:
                logger.error("Tesseract OCR executable not found by pytesseract")
                return "ERROR: Tesseract OCR executable not found by pytesseract. Please make sure Tesseract is installed and in your PATH. See README.md for installation instructions."
            
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            return f"ERROR: Could not process image: {e}"
            
    except Exception as e:
        logger.error(f"Error extracting text from image: {e}")
        return f"ERROR: Could not extract text from image: {e}"

def process_document(file, target_language):
    """Process a document (PDF, Word, or image) to extract and translate text."""
    try:
        # Generate unique filename
        original_filename = file.filename
        unique_id = datetime.now().strftime('%Y%m%d%H%M%S') + '_' + str(uuid.uuid4())[:8]
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_id + "_" + original_filename)
        
        # Save the uploaded file
        file.save(file_path)
        logger.info(f"Saved uploaded file to {file_path}")
        
        # Determine file type and extract text
        file_extension = os.path.splitext(original_filename)[1].lower()
        
        if file_extension == '.pdf':
            extracted_text = extract_text_from_pdf(file_path)
        elif file_extension in ['.docx', '.doc']:
            extracted_text = extract_text_from_docx(file_path)
        elif file_extension in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif']:
            extracted_text = extract_text_from_image(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")
        
        # Check if extraction returned an error message
        if extracted_text.startswith("ERROR:"):
            logger.error(f"Text extraction error: {extracted_text}")
            return render_template('error.html', error=extracted_text)
        
        if not extracted_text:
            raise ValueError(f"No text could be extracted from the file")
        
        # Translate the extracted text
        translated_text = translate_text_in_chunks(extracted_text, target_language)
        
        # Create output files for both original and translated text
        output_dir = app.config['OUTPUT_FOLDER']
        original_text_filename = f"{unique_id}_original.txt"
        translated_text_filename = f"{unique_id}_translated.txt"
        original_text_path = os.path.join(output_dir, original_text_filename)
        translated_text_path = os.path.join(output_dir, translated_text_filename)
        
        # Write to files
        with open(original_text_path, 'w', encoding='utf-8') as f:
            f.write(extracted_text)
        
        with open(translated_text_path, 'w', encoding='utf-8') as f:
            f.write(translated_text)
        
        logger.info(f"Saved extracted text to {original_text_path}")
        logger.info(f"Saved translated text to {translated_text_path}")
        
        # Return file paths and metadata for the template
        result = {
            'original_filename': original_filename,
            'original_text_filename': original_text_filename,
            'translated_text_filename': translated_text_filename,
            'original_text': extracted_text[:1000] + "..." if len(extracted_text) > 1000 else extracted_text,
            'translated_text': translated_text[:1000] + "..." if len(translated_text) > 1000 else translated_text,
            'target_language': target_language,
            'file_type': file_extension[1:].upper(),  # Remove the dot and capitalize
        }
        
        return render_template('document_result.html', result=result)
    
    except Exception as e:
        logger.error(f"Error processing document: {e}")
        return render_template('error.html', error=str(e))

if __name__ == '__main__':
    app.run(debug=True)