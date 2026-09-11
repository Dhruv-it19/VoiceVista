# Voice Vista: AI Video Translation & Dubbing

This application translates speech in videos into different languages by combining Groq Cloud Whisper API for ultra-fast, zero-download speech recognition with Google Translate and Edge TTS. Built with **FastAPI**, it delivers realistic, synchronized dubbed videos.

---

## Features

- **FastAPI Backend**: Async request handling, clean modular architecture, and automatic `/docs` Swagger API documentation.
- **Zero-Download Cloud STT**: Powered by Groq Whisper API (`whisper-large-v3`) running on LPUs for instant, high-accuracy transcription without heavy local model downloads.
- **Flexible Video Sources**: Upload local video files (MP4, AVI, MOV, WEBM) or process YouTube URLs directly via `yt_dlp`.
- **Multi-Language Support**: Dub speech into English, Hindi, Spanish, French, German, Gujarati, Urdu, Bengali, Tamil, Marathi, and Kannada.
- **Parallelized TTS Synthesis**: Concurrent Edge TTS generation for multi-chunk transcriptions, cutting processing times by up to 5x.
- **Automated Video Sync & Dubbing**: Merges translated audio back into the source video with dynamic speed adjustment via FFmpeg.

---

## Prerequisites

Before running Voice Vista, ensure you have the following installed:

1. **Python 3.11 or higher**
2. **FFmpeg** (Required for audio extraction and video dubbing):
   - **Windows**: Install via `winget install Gyan.FFmpeg` or download from [ffmpeg.org](https://ffmpeg.org/download.html) and add `ffmpeg/bin` to your System PATH.
   - **macOS**: `brew install ffmpeg`
   - **Linux**: `sudo apt update && sudo apt install ffmpeg`

---

## Step-by-Step Installation & Setup

### Step 1: Clone the Repository
```bash
git clone https://github.com/your-username/VoiceVista.git
cd VoiceVista
```

### Step 2: Install Dependencies

#### Option A: Using `uv` (Recommended - Super Fast)
```bash
# Install uv package manager if you haven't already
pip install uv

# Install all project dependencies
uv sync
```

#### Option B: Using standard `pip` & Virtual Environment
```bash
# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -r pyproject.toml
```

### Step 3: Configure Environment Variables

1. Get a **free Groq API Key** at [console.groq.com](https://console.groq.com).
2. Create a `.env` file in the root project directory:

```bash
# Copy from example template
cp .env.example .env
```

3. Open `.env` and paste your API key:

```env
GROQ_API_KEY=gsk_your_actual_groq_api_key_here
GROQ_MODEL=whisper-large-v3
```

---

## How to Run the Project

### Step 1: Start the Server

Using `uv`:
```bash
uv run python main.py
```

Or with active virtual environment:
```bash
python main.py
```

The server will start at `http://localhost:5000` (with hot-reload enabled).

---

## How to Use the Application

1. Open your browser and go to `http://localhost:5000`.
2. Click **"Get Started"** or navigate to `http://localhost:5000/main`.
3. Choose your input mode:
   - **Upload Video**: Drag & drop or browse a video file (MP4, AVI, MOV, WEBM).
   - **YouTube Link**: Paste any valid YouTube video URL.
4. Select your **Target Language** from the dropdown menu (e.g., Hindi, Gujarati, French, Spanish, etc.).
5. Click **"Translate Video"** / **"Translate YouTube Video"**.
6. Once processing is complete, you will be redirected to the **Result Page**:
   - Play the original and translated videos side-by-side.
   - View the full original transcription and translated text.
   - Click **"Download Translated Video"** to save your dubbed video.

---

## End-to-End Video Processing Pipeline

```text
[ Source Video / YouTube ] 
           │
           ▼
 [ 1. FFmpeg Audio Extract ] ───► 16kHz Mono MP3
           │
           ▼
 [ 2. Groq Whisper Cloud ]   ───► Rapid Speech-to-Text Transcription
           │
           ▼
 [ 3. Google Translator ]    ───► Chunked Text Translation
           │
           ▼
 [ 4. Concurrent Edge TTS ]  ───► Parallel Neural Speech Synthesis
           │
           ▼
 [ 5. FFmpeg Speed Sync ]    ───► Match Video Duration & Render Dubbed MP4
```

---

## API & Documentation Endpoints

- **Landing Page**: `http://localhost:5000/`
- **Dubbing Application**: `http://localhost:5000/main`
- **Swagger Interactive API Docs**: `http://localhost:5000/docs`
- **Health Check**: `http://localhost:5000/health`
