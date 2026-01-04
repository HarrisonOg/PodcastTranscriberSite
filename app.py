import os
import logging
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, request, jsonify, render_template
import whisper
import yt_dlp
import validators
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

UPLOAD_FOLDER = 'temp_audio'
WHISPER_MODEL = os.getenv('WHISPER_MODEL', 'base')
PORT = int(os.getenv('PORT', 5000))
DEBUG = os.getenv('DEBUG', 'False') == 'True'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

logger.info(f"Loading Whisper model: {WHISPER_MODEL}")
model = whisper.load_model(WHISPER_MODEL)
logger.info("Whisper model loaded successfully")


def is_safe_url(url):
    """
    Validate URL to prevent injection attacks
    Only allows HTTP and HTTPS schemes
    """
    if not url or not isinstance(url, str):
        logger.warning("URL validation failed: empty or invalid type")
        return False

    if not validators.url(url):
        logger.warning(f"URL validation failed: invalid format - {url}")
        return False

    parsed = urlparse(url)
    if parsed.scheme not in ['http', 'https']:
        logger.warning(f"URL validation failed: invalid scheme '{parsed.scheme}' - {url}")
        return False

    logger.info(f"URL validation passed: {url}")
    return True


def download_audio(url, output_path):
    """
    Download audio from URL using yt-dlp
    Works with direct MP3 links and podcast feeds
    """
    logger.info(f"Starting audio download from: {url}")

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_path,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': False,
        'no_warnings': False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'Unknown Episode')
            logger.info(f"Successfully downloaded: {title}")
            return title
    except Exception as e:
        logger.error(f"Failed to download audio from {url}: {e}", exc_info=True)
        raise


def transcribe_audio(audio_path):
    """
    Transcribe audio file using Whisper
    Returns transcript with timestamps
    """
    logger.info(f"Starting transcription for: {audio_path}")

    try:
        result = model.transcribe(
            audio_path,
            verbose=True,
            language='en',
            task='transcribe'
        )

        logger.info(f"Transcription completed. Segments: {len(result.get('segments', []))}")
        return result
    except Exception as e:
        logger.error(f"Failed to transcribe audio {audio_path}: {e}", exc_info=True)
        raise


def format_transcript(result):
    """
    Format Whisper output into readable transcript
    with timestamps for each segment
    """
    segments = []
    for segment in result['segments']:
        timestamp = format_timestamp(segment['start'])
        text = segment['text'].strip()
        segments.append({
            'timestamp': timestamp,
            'start_seconds': segment['start'],
            'text': text
        })

    logger.info(f"Formatted {len(segments)} transcript segments")
    return segments


def format_timestamp(seconds):
    """Convert seconds to HH:MM:SS format"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def generate_unique_id():
    """Generate unique ID for file naming"""
    return str(uuid.uuid4())[:8]


def find_downloaded_file(file_id):
    """Find the downloaded audio file with dynamic extension"""
    for ext in ['.mp3', '.m4a', '.wav']:
        path = f"{UPLOAD_FOLDER}/{file_id}{ext}"
        if os.path.exists(path):
            return path
    raise FileNotFoundError("Downloaded audio file not found")


@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')


@app.route('/transcribe', methods=['POST'])
def transcribe():
    """
    Main transcription endpoint
    Expects JSON: {"url": "podcast_episode_url"}
    """
    data = request.json
    url = data.get('url') if data else None

    if not url:
        logger.warning("Transcription request failed: No URL provided")
        return jsonify({'error': 'No URL provided'}), 400

    # Validate URL for security
    if not is_safe_url(url):
        logger.warning(f"Transcription request failed: Invalid URL - {url}")
        return jsonify({'error': 'Invalid URL. Please provide a valid HTTP or HTTPS URL.'}), 400

    audio_file = None

    try:
        # Create temp directory
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        # Generate unique filename
        file_id = generate_unique_id()
        audio_path = f"{UPLOAD_FOLDER}/{file_id}"

        logger.info(f"Processing transcription request for URL: {url}")

        # Download audio
        episode_title = download_audio(url, audio_path)

        # Find the downloaded file (yt-dlp adds extension)
        audio_file = find_downloaded_file(file_id)

        # Transcribe
        result = transcribe_audio(audio_file)

        # Format output
        segments = format_transcript(result)

        logger.info(f"Transcription completed successfully for: {episode_title}")

        return jsonify({
            'success': True,
            'title': episode_title,
            'transcript': segments,
            'full_text': result['text']
        })

    except FileNotFoundError as e:
        logger.error(f"File not found during transcription: {e}", exc_info=True)
        return jsonify({'error': 'Failed to process audio file. Please try again.'}), 500

    except Exception as e:
        logger.error(f"Transcription failed for {url}: {e}", exc_info=True)
        return jsonify({'error': 'Transcription failed. Please check the URL and try again.'}), 500

    finally:
        # Clean up audio file
        if audio_file and os.path.exists(audio_file):
            try:
                os.remove(audio_file)
                logger.info(f"Cleaned up temp file: {audio_file}")
            except Exception as e:
                logger.error(f"Failed to clean up temp file {audio_file}: {e}")


@app.route('/health')
def health():
    """Simple health check for monitoring"""
    return jsonify({
        'status': 'healthy',
        'model_loaded': model is not None,
        'whisper_model': WHISPER_MODEL,
        'timestamp': datetime.utcnow().isoformat()
    })


if __name__ == '__main__':
    logger.info(f"Starting Flask app on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=DEBUG)
