# Local Setup Instructions

## Prerequisites

Before running the Podcast Transcriber locally, ensure you have:

- **Python 3.11+** installed (3.12 recommended)
- **FFmpeg** installed (required for audio processing)

### Installing FFmpeg

**macOS (using Homebrew):**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

**Windows (using Chocolatey):**
```bash
choco install ffmpeg
```

Or download from [ffmpeg.org](https://ffmpeg.org/download.html)

---

## Setup Steps

### 1. Clone or Navigate to the Project Directory

```bash
cd /path/to/PodcastTranscriberSite
```

### 2. Create a Virtual Environment

```bash
python3 -m venv venv
```

### 3. Activate the Virtual Environment

**macOS/Linux:**
```bash
source venv/bin/activate
```

**Windows:**
```bash
venv\Scripts\activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- Flask (web framework)
- openai-whisper (transcription)
- yt-dlp (audio download)
- validators (URL validation)
- python-dotenv (environment variables)

**Note:** The first time Whisper runs, it will download the model (~140MB for 'base' model). This happens automatically on first use.

### 5. (Optional) Create Environment Variables

Create a `.env` file in the project root if you want to customize settings:

```bash
# .env file (optional)
WHISPER_MODEL=base          # Options: tiny, base, small, medium, large
PORT=5000                    # Default port
DEBUG=True                   # Enable debug mode for development
```

**Model sizes:**
- `tiny` - Fastest, least accurate (~75MB)
- `base` - Good balance (~140MB) - **Recommended for local testing**
- `small` - Better accuracy (~460MB)
- `medium` - High accuracy (~1.5GB)
- `large` - Best accuracy (~3GB)

---

## Running the Application

### Start the Flask Server

```bash
python app.py
```

You should see output like:
```
2026-01-04 14:00:00 - __main__ - INFO - Loading Whisper model: base
2026-01-04 14:00:05 - __main__ - INFO - Whisper model loaded successfully
 * Serving Flask app 'app'
 * Debug mode: on
 * Running on http://127.0.0.1:5000
```

### Access the Application

Open your web browser and navigate to:
```
http://localhost:5000
```

---

## Testing the Transcriber

### Test with a Sample Podcast URL

Try one of these test URLs:

**Direct MP3 (quick test):**
```
https://ia802508.us.archive.org/5/items/testmp3testfile/mpthreetest.mp3
```

**YouTube podcast episode:**
```
https://www.youtube.com/watch?v=VALID_VIDEO_ID
```

**Public RSS feed:**
```
https://feeds.example.com/podcast-feed.xml
```

### What to Expect

1. **First run:** The Whisper model will download (~140MB for base model). This takes 1-2 minutes.
2. **Transcription time:** Roughly 1/10th the length of the audio
   - 10-minute episode ≈ 1 minute to transcribe
   - 60-minute episode ≈ 6 minutes to transcribe
3. **Memory usage:** ~500MB-1GB depending on model size

---

## Troubleshooting

### Issue: "FFmpeg not found"
**Solution:** Install FFmpeg (see Prerequisites section above)

### Issue: "Model download stuck"
**Solution:** Check internet connection. Whisper downloads from Hugging Face. First download takes a few minutes.

### Issue: "Port 5000 already in use"
**Solution:** Either:
- Kill the process using port 5000: `lsof -ti:5000 | xargs kill`
- Or change the port in `.env` file: `PORT=5001`

### Issue: "Out of memory"
**Solution:** Use a smaller Whisper model. Set in `.env`:
```
WHISPER_MODEL=tiny
```

### Issue: "yt-dlp can't download URL"
**Solution:** Some platforms require authentication:
- Spotify requires Premium + cookies
- Private RSS feeds need authentication
- Try a direct MP3 link for testing

### Issue: Transcription is slow
**Solution:**
- Use a smaller model (`tiny` or `base`)
- Try shorter episodes first (< 10 minutes)
- Consider using GPU acceleration (requires PyTorch with CUDA)

---

## Stopping the Server

Press `Ctrl+C` in the terminal where Flask is running.

To deactivate the virtual environment:
```bash
deactivate
```

---

## Project Structure

```
PodcastTranscriberSite/
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── templates/
│   └── index.html         # Frontend UI
├── temp_audio/            # Temporary audio files (auto-created)
├── venv/                  # Virtual environment (gitignored)
└── .env                   # Environment variables (optional)
```

---

## Development Tips

### Enable Debug Mode

Set `DEBUG=True` in `.env` for:
- Auto-reload on code changes
- Detailed error messages
- Interactive debugger in browser

### Check Logs

The app logs useful information:
```python
INFO - Starting transcription for: https://example.com/podcast.mp3
INFO - Transcription completed in 45.2 seconds
ERROR - Failed to download: Invalid URL
```

### Clean Up Temp Files

Temp audio files are automatically deleted after transcription. If they accumulate during testing:

```bash
rm -rf temp_audio/*
```

---

## Next Steps

Once you've verified it works locally:

1. **Deploy to Render** - See deployment guide in `podcast_transcriber_plan.md`
2. **Add features** - Audio player, more export formats, etc.
3. **Configure rate limiting** - Prevent abuse in production

---

## Support

For issues or questions:
- Check the project plan: `podcast_transcriber_plan.md`
- Review Flask logs for error messages
- Verify all dependencies are installed: `pip list`
