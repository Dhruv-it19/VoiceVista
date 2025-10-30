# Voice Vista: Video Translation with Whisper Speech Recognition

This application translates speech in videos to different languages by combining OpenAI's Whisper model for speech recognition with Google Translate and gTTS. It also provides AI-powered summarization of video content and text extraction from documents with translation.

## Features

- Highly accurate speech recognition using OpenAI's Whisper model
- Upload video files for translation
- Process YouTube videos by URL
- Translate speech to multiple languages
- Merge translated audio with original video
- AI-powered content summarization (25% of original length)
- GPU acceleration support for faster processing
- Extract and translate text from PDF documents
- Extract and translate text from Word documents (.docx)
- Optical Character Recognition (OCR) to extract text from images
- Download both original and translated text from documents

## Supported Languages

- English
- Hindi
- Spanish
- French
- German
- Gujarati
- Urdu
- Bengali
- Tamil
- Marathi
- Kannada

## Requirements

- Python 3.12+
- Flask
- FFmpeg
- OpenAI Whisper
- Googletrans
- gTTS
- yt-dlp
- Transformers (for summarization)
- PyTorch (with CUDA support for GPU acceleration)
- PyPDF2 (for PDF text extraction)
- python-docx (for Word document text extraction)
- pytesseract (for OCR image text extraction)
- Tesseract OCR engine

## Installation

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Install FFmpeg from [ffmpeg.org](https://ffmpeg.org/download.html)
4. Install Tesseract OCR:
   - Windows: 
     1. Download the installer from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)
     2. Run the installer and remember the installation path (e.g., `C:\Program Files\Tesseract-OCR`)
     3. Add Tesseract to your PATH environment variable:
        - Right-click on 'This PC' or 'My Computer' and select 'Properties'
        - Click on 'Advanced system settings'
        - Click on 'Environment Variables'
        - Under 'System variables', find and select 'Path', then click 'Edit'
        - Click 'New' and add the Tesseract installation path (e.g., `C:\Program Files\Tesseract-OCR`)
        - Click 'OK' on all dialogs to save
   - macOS: `brew install tesseract`
   - Linux: `sudo apt install tesseract-ocr`

## Known Issues and Solutions

### AttributeError: module 'httpcore' has no attribute 'SyncHTTPTransport'

If you encounter this error, it's due to incompatible versions of httpx and httpcore. Fix it with:
```
pip install --force-reinstall httpx==0.13.3 httpcore==0.9.1
```

### ImportError: cannot import name 'create_task' from 'sniffio'

This can be fixed by reinstalling the correct version of sniffio:
```
pip install --force-reinstall sniffio==1.2.0
```

### YouTube Download Timeouts

If you encounter timeout errors when downloading YouTube videos:

1. **Network Issues**: Ensure you have a stable internet connection
2. **Video Length**: Try shorter videos (less than 5 minutes)
3. **Restricted Content**: Some videos may be region-restricted or not available for download
4. **Alternative Sources**: If a particular video consistently fails, try a different video
5. **Timeout Settings**: The app has increased timeout settings, but very large videos may still time out

### Package Conflicts

The application may conflict with newer versions of some packages like elevenlabs. If you're using elevenlabs in other projects, consider using a virtual environment for this application.

## Usage

1. Run the application:
   ```
   python main.py
   ```
2. Open your browser and navigate to `http://127.0.0.1:5000`

### Video Translation
1. Click on "Video Translation" or navigate to the main page
2. Upload a video file or provide a YouTube URL
3. Select the target language for translation
4. Click "Translate Video" to start translation
5. View the result with the translated audio

### Document Processing
1. Click on "Document Processing" or navigate to "/documents"
2. Upload a supported document (PDF, Word, or image)
3. Select the target language for translation
4. Click "Process Document" to extract and translate text
5. View the extracted and translated text
6. Download the original or translated text using the provided buttons

## How It Works

### Video Translation
1. The application extracts audio from the uploaded video using FFmpeg
2. Whisper model transcribes the audio to text with high accuracy
3. AI summarization generates a concise summary (25% of original length)
4. Google Translate translates both the full transcription and summary to the target language
5. gTTS converts the translated text to speech
6. FFmpeg merges the new audio with the original video

### Document Processing
1. For PDF files: PyPDF2 extracts text from all pages
2. For Word documents: python-docx extracts text from all paragraphs
3. For images: Tesseract OCR engine extracts text from the image
4. The extracted text is cleaned and processed
5. Google Translate translates the text to the target language
6. Both original and translated texts are saved and presented to the user

## Troubleshooting

### Video Processing Issues
- If you encounter errors related to missing directories, make sure the application has permission to create folders
- For Whisper-related errors, check that your CUDA/GPU setup is correctly configured if using GPU acceleration
- Long videos may require more memory for Whisper transcription
- If translation fails, try with shorter content first to ensure all components are working correctly
- For summarization errors, ensure you have enough RAM available (at least 4GB recommended)
- For YouTube download issues, refer to the "YouTube Download Timeouts" section above

### Document Processing Issues
- If OCR results are poor quality, ensure the image is clear and has good contrast
- For PDF extraction issues, check if the PDF contains actual text rather than scanned images
- If document processing fails with large files, try splitting them into smaller segments
- For OCR issues, make sure Tesseract OCR is installed correctly and available in the system PATH
- Incorrect text encoding may occur with certain languages - try using Unicode-compatible documents
- If Word documents don't extract properly, check for complex formatting that might not be supported

## Notes

- Processing long videos may take time, especially for the Whisper transcription
- Whisper works with many languages and accents with high accuracy
- For best results, use videos with clear speech 
- OCR quality depends on the image quality and clarity of the text
- PDF extraction works best with digitally created PDFs rather than scanned documents 
