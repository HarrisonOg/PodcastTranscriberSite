import os
import logging
import uuid
import time
import threading
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, request, jsonify, render_template, Response, stream_with_context
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

# Job tracking for background transcription
jobs = {}
jobs_lock = threading.Lock()


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


def update_job_progress(job_id, progress, message, status='processing'):
    """Update job progress in thread-safe manner"""
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id]['progress'] = progress
            jobs[job_id]['message'] = message
            jobs[job_id]['status'] = status
            logger.info(f"Job {job_id}: {progress}% - {message}")


def transcribe_job_worker(job_id, url):
    """Background worker that handles the full transcription process"""
    audio_file = None

    try:
        # Stage 1: Download audio (0-20%)
        update_job_progress(job_id, 0, 'Starting download...', 'downloading')

        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        file_id = generate_unique_id()
        audio_path = f"{UPLOAD_FOLDER}/{file_id}"

        update_job_progress(job_id, 5, 'Downloading audio...', 'downloading')

        # Download with duration tracking
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': audio_path,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': False,
            'no_warnings': False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            episode_title = info.get('title', 'Unknown Episode')
            audio_duration = info.get('duration', 300)  # Default 5 min if unknown

        update_job_progress(job_id, 20, 'Audio downloaded successfully', 'downloading')

        # Find the downloaded file
        audio_file = find_downloaded_file(file_id)

        # Stage 2: Load audio for transcription (20-30%)
        update_job_progress(job_id, 25, 'Preparing audio for transcription...', 'processing')
        time.sleep(0.5)  # Brief pause for UX

        # Stage 3: Transcription (30-90%)
        update_job_progress(job_id, 30, 'Starting transcription...', 'transcribing')

        # Start transcription with progress estimation
        transcription_start = time.time()

        # Run transcription in separate thread to allow progress updates
        result_container = {'result': None, 'error': None}

        def run_transcription():
            try:
                result_container['result'] = model.transcribe(
                    audio_file,
                    verbose=True,
                    language='en',
                    task='transcribe'
                )
            except Exception as e:
                result_container['error'] = e

        transcription_thread = threading.Thread(target=run_transcription)
        transcription_thread.start()

        # Estimate progress based on audio duration and elapsed time
        # Assume Whisper processes at ~1x real-time for base model
        while transcription_thread.is_alive():
            elapsed = time.time() - transcription_start
            estimated_total = audio_duration * 1.2  # Add 20% buffer

            if estimated_total > 0:
                # Progress from 30% to 90% based on elapsed time
                estimated_progress = 30 + min(60, (elapsed / estimated_total) * 60)
            else:
                estimated_progress = 50

            update_job_progress(
                job_id,
                int(estimated_progress),
                f'Transcribing audio... ({int(elapsed)}s elapsed)',
                'transcribing'
            )

            time.sleep(2)  # Update every 2 seconds

        transcription_thread.join()

        # Check for transcription errors
        if result_container['error']:
            raise result_container['error']

        result = result_container['result']

        # Stage 4: Format results (90-100%)
        update_job_progress(job_id, 90, 'Formatting transcript...', 'formatting')

        segments = format_transcript(result)

        update_job_progress(job_id, 95, 'Finalizing...', 'formatting')

        # Store result in job
        with jobs_lock:
            jobs[job_id]['result'] = {
                'success': True,
                'title': episode_title,
                'transcript': segments,
                'full_text': result['text']
            }

        update_job_progress(job_id, 100, 'Transcription complete!', 'completed')

        logger.info(f"Job {job_id} completed successfully")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        with jobs_lock:
            jobs[job_id]['status'] = 'failed'
            jobs[job_id]['error'] = str(e)
            jobs[job_id]['message'] = f'Transcription failed: {str(e)}'

    finally:
        # Clean up audio file
        if audio_file and os.path.exists(audio_file):
            try:
                os.remove(audio_file)
                logger.info(f"Cleaned up temp file: {audio_file}")
            except Exception as e:
                logger.error(f"Failed to clean up temp file {audio_file}: {e}")


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
    Main transcription endpoint - starts background job
    Expects JSON: {"url": "podcast_episode_url"}
    Returns: {"job_id": "unique_id"}
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

    # Generate unique job ID
    job_id = generate_unique_id()

    # Initialize job in tracking dictionary
    with jobs_lock:
        jobs[job_id] = {
            'status': 'pending',
            'progress': 0,
            'message': 'Initializing...',
            'result': None,
            'error': None,
            'created_at': datetime.utcnow().isoformat()
        }

    # Start background transcription thread
    worker_thread = threading.Thread(
        target=transcribe_job_worker,
        args=(job_id, url),
        daemon=True
    )
    worker_thread.start()

    logger.info(f"Started transcription job {job_id} for URL: {url}")

    return jsonify({
        'success': True,
        'job_id': job_id
    })


@app.route('/progress/<job_id>')
def progress(job_id):
    """
    Server-Sent Events endpoint for progress updates
    Streams progress updates for a specific job
    """
    def generate():
        # Validate job exists
        if job_id not in jobs:
            yield f"data: {jsonify({'error': 'Job not found'}).get_data(as_text=True)}\n\n"
            return

        last_progress = -1
        last_status = None

        # Stream progress updates
        while True:
            with jobs_lock:
                if job_id not in jobs:
                    break

                job = jobs[job_id]
                status = job['status']
                progress = job['progress']
                message = job['message']

            # Only send update if progress or status changed
            if progress != last_progress or status != last_status:
                event_data = {
                    'progress': progress,
                    'message': message,
                    'status': status
                }

                # Send SSE formatted message
                yield f"data: {jsonify(event_data).get_data(as_text=True)}\n\n"

                last_progress = progress
                last_status = status

            # Check if job is complete or failed
            if status in ['completed', 'failed']:
                # Send final result
                with jobs_lock:
                    if status == 'completed':
                        result_data = {
                            'status': 'completed',
                            'result': job['result']
                        }
                    else:
                        result_data = {
                            'status': 'failed',
                            'error': job.get('error', 'Unknown error')
                        }

                yield f"data: {jsonify(result_data).get_data(as_text=True)}\n\n"
                break

            time.sleep(0.5)  # Check for updates every 500ms

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


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
