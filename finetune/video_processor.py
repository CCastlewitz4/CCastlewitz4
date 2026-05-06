# finetune/video_processor.py
# ─────────────────────────────────────────────────────────────────────────────
# PURPOSE: Extracts spoken audio from video files and transcribes it to text
#          using OpenAI Whisper (runs 100% locally — no API key or internet
#          required for transcription).
#
# SUPPORTED SOURCES:
#   - YouTube URLs (downloaded automatically via yt-dlp)
#   - Local video files (.mp4, .mkv, .avi, .mov)
#   - Local audio files (.wav, .mp3, .m4a)
#
# OUTPUT:
#   - A JSON file containing timestamped transcript segments
#   - Each segment: {'start': float, 'end': float, 'text': str}
#
# LOCATION: dnd_ai_dm/finetune/video_processor.py
# ─────────────────────────────────────────────────────────────────────────────

import json
import os

import whisper
import yt_dlp

import config


# ── Whisper Model Size ─────────────────────────────────────────────────────
# Controls the trade-off between speed/RAM and transcription accuracy.
#
# Size options and approximate VRAM/RAM requirements:
#   'tiny'   — ~75MB,  fastest, least accurate
#   'base'   — ~140MB, fast, good for clear audio       ← recommended start
#   'small'  — ~460MB, balanced accuracy
#   'medium' — ~1.5GB, high accuracy
#   'large'  — ~2.9GB, highest accuracy, slowest
#
# Override with environment variable: WHISPER_SIZE=small python ...
WHISPER_MODEL_SIZE = os.getenv('WHISPER_SIZE', 'base')

# ── Output directories ─────────────────────────────────────────────────────
AUDIO_DIR      = os.path.join(config.TRAINING_DIR, 'audio')
TRANSCRIPT_DIR = os.path.join(config.TRAINING_DIR, 'transcripts')


def _ensure_dirs():
    """Creates the audio and transcript output directories if needed."""
    os.makedirs(AUDIO_DIR, exist_ok=True)
    os.makedirs(TRANSCRIPT_DIR, exist_ok=True)


def download_youtube_audio(url: str) -> str:
    """
    Downloads the audio track from a YouTube video as a .wav file.

    Uses yt-dlp to download and FFmpeg to convert to WAV format.
    FFmpeg must be installed on your system (included with most Linux distros;
    on Windows, download from https://ffmpeg.org and add to PATH).

    Parameters:
      url — A valid YouTube video URL

    Returns:
      The full file path of the downloaded .wav file.
    """
    _ensure_dirs()

    # yt-dlp options dictionary
    ydl_opts = {
        # Only download the best available audio track (no video)
        'format': 'bestaudio/best',

        # Output file path template — uses the video's unique ID as filename
        'outtmpl': os.path.join(AUDIO_DIR, '%(id)s.%(ext)s'),

        # Post-processor: convert whatever format is downloaded to .wav
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
        }],

        # Suppress yt-dlp's verbose output to keep the terminal clean
        'quiet': True,
        'no_warnings': True,
    }

    print(f'Downloading audio from YouTube: {url}')
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # extract_info() downloads the video and returns its metadata
        info = ydl.extract_info(url, download=True)
        # The video ID is used as the filename
        video_id = info.get('id', 'unknown_video')

    audio_path = os.path.join(AUDIO_DIR, f'{video_id}.wav')
    print(f'Audio saved to: {audio_path}')
    return audio_path


def transcribe_audio(audio_path: str) -> list[dict]:
    """
    Transcribes an audio file to text using the Whisper model.

    On first call, Whisper downloads the model weights (~140MB for 'base').
    Subsequent calls use the cached model.

    Parameters:
      audio_path — Full path to a .wav, .mp3, or .m4a audio file

    Returns:
      A list of segment dicts, each containing:
        - 'start' : float — start time in seconds
        - 'end'   : float — end time in seconds
        - 'text'  : str   — the transcribed speech for this segment
    """
    print(f'Loading Whisper model ({WHISPER_MODEL_SIZE})...')
    # load_model() downloads on first use, then uses local cache
    model = whisper.load_model(WHISPER_MODEL_SIZE)

    print(f'Transcribing: {audio_path}')
    # transcribe() processes the entire audio file
    # verbose=False suppresses per-segment output to keep terminal clean
    result = model.transcribe(audio_path, verbose=False)

    # Return the segments list (each segment = a spoken chunk with timestamps)
    segments = result.get('segments', [])
    print(f'Transcription complete: {len(segments)} segments extracted.')
    return segments


def save_transcript(segments: list[dict], source_name: str) -> str:
    """
    Saves the transcribed segments to a JSON file in the transcripts directory.

    Parameters:
      segments    — List of segment dicts from transcribe_audio()
      source_name — A base name for the output file (e.g., video ID or filename)

    Returns:
      Full path of the saved transcript JSON file.
    """
    _ensure_dirs()
    # Clean the source_name for use as a filename
    safe_name = ''.join(c if c.isalnum() or c in ('_', '-') else '_' for c in source_name)
    out_path = os.path.join(TRANSCRIPT_DIR, f'{safe_name}_transcript.json')

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(segments, f, indent=2, ensure_ascii=False)

    print(f'Transcript saved: {out_path}')
    return out_path


def process_video_source(source: str) -> str:
    """
    Main entry point for processing a video/audio source.
    Handles both YouTube URLs and local file paths automatically.

    Workflow:
      1. If source is a YouTube URL → download audio → transcribe → save
      2. If source is a local file  → transcribe directly → save

    Parameters:
      source — Either a YouTube URL (starts with 'http') or a local file path

    Returns:
      Full path of the saved transcript JSON file.
    """
    # Determine if source is a URL or a local file path
    if source.startswith('http://') or source.startswith('https://'):
        # YouTube or other web video URL
        audio_path = download_youtube_audio(source)
        # Use the filename (video ID) as the transcript name
        source_name = os.path.splitext(os.path.basename(audio_path))[0]
    else:
        # Local file — use directly
        if not os.path.exists(source):
            raise FileNotFoundError(f'Local file not found: {source}')
        audio_path = source
        source_name = os.path.splitext(os.path.basename(source))[0]

    # Transcribe the audio
    segments = transcribe_audio(audio_path)

    # Save and return the transcript path
    return save_transcript(segments, source_name)


def process_multiple_sources(sources: list[str]) -> list[str]:
    """
    Processes a list of video/audio sources one by one.
    Useful for batch processing an entire playlist or folder of videos.

    Parameters:
      sources — List of YouTube URLs and/or local file paths

    Returns:
      List of transcript file paths that were successfully created.
    """
    transcript_paths = []
    for i, source in enumerate(sources, start=1):
        print(f'\n[{i}/{len(sources)}] Processing: {source}')
        try:
            path = process_video_source(source)
            transcript_paths.append(path)
        except Exception as e:
            # Log the error but continue processing remaining sources
            print(f'  ERROR processing {source}: {e}')
    return transcript_paths

# ─────────────────────────────────────────────────────────────────────────────
# ADD YOUR VIDEO SOURCES HERE
# This block runs when you execute: python finetune/video_processor.py
#
# For YouTube URLs:    paste the full URL in quotes
# For local files:     paste the full file path in quotes
#                      Example: r'C:\Users\colin\Videos\dnd_session.mp4'
#                      The r before the quote means "raw string" — it stops
#                      Python from misreading backslashes as escape characters
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':

    # ── ADD YOUR SOURCES BELOW ────────────────────────────────────────────
    # Delete the example entries and replace with your own.
    # You can mix YouTube URLs and local file paths in the same list.

    sources = [

        # ── YouTube URLs ──────────────────────────────────────────────────
        # Paste the full YouTube URL for each DnD session video you want
        # Example (delete this and add your own):
        # 'https://www.youtube.com/watch?v=XXXXXXXXXXX',
        'https://youtu.be/_zZxCVBi7-k?si=oLcNDKTYClVrdM9I'

        # ── Local video/audio files ───────────────────────────────────────
        # Use r'path' (note the r) to handle Windows backslashes correctly
        # Example (delete this and add your own):
        # r'C:\Users\colin\Videos\dnd_session_1.mp4',
        # r'C:\Users\colin\Videos\dnd_session_2.mp4',

    ]
    # ── END OF SOURCES LIST ───────────────────────────────────────────────

    if not sources:
        print("No sources added yet.")
        print("Open finetune/video_processor.py and add your YouTube URLs")
        print("or local file paths to the 'sources' list above.")
    else:
        print(f"Processing {len(sources)} source(s)...")
        completed = process_multiple_sources(sources)
        print(f"\nDone! {len(completed)} transcript(s) saved to:")
        print(f"  {os.path.join(config.TRAINING_DIR, 'transcripts')}")
        print(f"\nNext step: run python finetune/dataset_builder.py")