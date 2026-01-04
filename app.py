import os
import logging
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, render_template
import whisper
import yt_dlp
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
    pass


def format_transcript(result):
    """
    Format Whisper output into readable transcript
    with timestamps for each segment
    """
    pass


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
    pass


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
