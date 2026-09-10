# Voice Vista: Video Translation with Whisper Speech Recognition

This application translates speech in videos to different languages by combining OpenAI's Whisper model for speech recognition with Google Translate and Edge TTS. Built with **FastAPI**, it also provides AI-powered video summarization.

## Features

- FastAPI backend with async processing and automatic API documentation
- OpenAI Whisper speech recognition with CUDA acceleration where available
- Upload video files or process YouTube URLs
- Translate speech to English, Hindi, Spanish, French, German, Gujarati, Urdu, Bengali, Tamil, Marathi, and Kannada
- Generate translated speech and merge it with the source video
- AI-generated video summaries

## Requirements

- Python 3.11+
- FFmpeg

Install the Python dependencies:

```bash
uv sync
```

Or:

```bash
pip install -r requirements.txt
```

## Run

```bash
uv run python main.py
```

Open `http://127.0.0.1:5000`. The video translation page is available at `/main` and API documentation at `/docs`.

## Video workflow

1. FFmpeg extracts audio from the source video.
2. Whisper transcribes the audio.
3. VoiceVista creates an optional summary.
4. Google Translate translates the text and summary.
5. Edge TTS generates translated audio.
6. FFmpeg merges the new audio with the original video.
