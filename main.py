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
        cmd = [
            "ffprobe", 
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
        cmd = [
            "ffprobe", 
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
        cmd = [
            "ffmpeg",
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
    """Translate large text by breaking it into smaller chunks to avoid timeouts."""
    if not text:
        return ""
    
    # If text is small enough, translate directly
    if len(text) <= chunk_size:
        try:
            translator = GoogleTranslator(source='auto', target=target_language)
            return translator.translate(text)
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return text  # Return original text on error
    
    # For longer text, split into sentences and translate in chunks
    # Simple sentence splitting by punctuation
    sentences = []
    for end_char in ['. ', '! ', '? ', '.\n', '!\n', '?\n']:
        text = text.replace(end_char, end_char + '<SPLIT>')
    
    raw_sentences = text.split('<SPLIT>')
    
    # Combine sentences into chunks that don't exceed chunk_size
    chunks = []
    current_chunk = ""
    
    for sentence in raw_sentences:
        if len(current_chunk) + len(sentence) > chunk_size:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + " "
        else:
            current_chunk += sentence + " "
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    # Translate each chunk
    translated_chunks = []
    translator = GoogleTranslator(source='auto', target=target_language)
    
    for i, chunk in enumerate(chunks):
        logger.info(f"Translating chunk {i+1}/{len(chunks)} ({len(chunk)} chars)")
        try:
            translated = translator.translate(chunk)
            translated_chunks.append(translated)
            # Short delay to avoid rate limiting
            time.sleep(0.5)
        except Exception as e:
            logger.error(f"Error translating chunk {i+1}: {e}")
            translated_chunks.append(chunk)  # Use original on error
    
    # Combine all translated chunks
    return " ".join(translated_chunks)

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
        concat_cmd = [
            "ffmpeg",
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
        subprocess.run(["ffmpeg", "-i", video_path, "-q:a", "0", "-map", "a", audio_path], check=True)

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
            "ffmpeg",
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
            extract_cmd = [
                "ffmpeg",
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
                silent_cmd = [
                    "ffmpeg",
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
        concat_cmd = [
            "ffmpeg",
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
            "ffmpeg",
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
    """Fetch translated video filenames for frontend."""
    videos = os.listdir(app.config['FINAL_OUTPUT'])
    return jsonify(videos)

if __name__ == '__main__':
    app.run(debug=True)