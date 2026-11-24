
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
from pydub import AudioSegment


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_LENGTH_MS = 10 * 60 * 1000  # 10 minutes

BASE_TEMP_DIR = Path(tempfile.gettempdir()) / "meetmind_audio"
BASE_TEMP_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def _find_ffmpeg():
    """Find FFmpeg executable."""
    ffmpeg_path = shutil.which("ffmpeg")

    if not ffmpeg_path:
        raise RuntimeError(
            "FFmpeg was not found. Install FFmpeg and ensure it is "
            "available in the system PATH."
        )

    return ffmpeg_path


def _clean_youtube_url(url):
    """
    Clean normal YouTube URLs and Markdown-wrapped URLs.
    Example:
    [https://youtube.com/shorts/abc](https://youtube.com/shorts/abc)
    """

    if not isinstance(url, str):
        raise ValueError("YouTube URL must be a string.")

    url = url.strip()

    # Extract the actual URL from Markdown links.
    match = re.search(
        r"https?://(?:www\.)?(?:youtube\.com|youtu\.be)/[^\s)\]>]+",
        url,
        re.IGNORECASE
    )

    if not match:
        raise ValueError("Please provide a valid YouTube URL.")

    clean_url = match.group(0).rstrip(".,;")

    parsed = urlparse(clean_url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError("Invalid YouTube URL scheme.")

    if not (
        parsed.netloc.endswith("youtube.com")
        or parsed.netloc.endswith("youtu.be")
    ):
        raise ValueError("Only YouTube URLs are supported.")

    return clean_url


def _run_ffmpeg(command):
    """Run FFmpeg and report useful errors."""

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(
            "FFmpeg processing failed:\n" + result.stderr[-3000:]
        )

    return result


# ---------------------------------------------------------
# YOUTUBE AUDIO DOWNLOAD
# ---------------------------------------------------------

def download_youtube_audio(url):
    """
    Download audio from a YouTube URL.
    Returns the downloaded audio file path.
    """

    clean_url = _clean_youtube_url(url)

    print("ORIGINAL YOUTUBE URL:", repr(url))
    print("CLEAN YOUTUBE URL:", clean_url)

    output_dir = Path(
        tempfile.mkdtemp(prefix="youtube_", dir=str(BASE_TEMP_DIR))
    )

    output_template = str(output_dir / "audio.%(ext)s")

    ydl_options = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": False,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
        "overwrites": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_options) as ydl:
            info = ydl.extract_info(clean_url, download=True)

            if not info:
                raise RuntimeError(
                    "YouTube did not return video information."
                )

        downloaded_files = [
            file for file in output_dir.iterdir()
            if file.is_file()
        ]

        if not downloaded_files:
            raise RuntimeError(
                "YouTube audio download completed without producing a file."
            )

        audio_path = max(
            downloaded_files,
            key=lambda file: file.stat().st_size
        )

        if audio_path.stat().st_size == 0:
            raise RuntimeError("Downloaded audio file is empty.")

        print("YOUTUBE AUDIO DOWNLOADED:", audio_path)

        return str(audio_path)

    except Exception as exc:
        shutil.rmtree(output_dir, ignore_errors=True)

        raise RuntimeError(
            f"Unable to download YouTube audio: {exc}"
        ) from exc


# ---------------------------------------------------------
# AUDIO CONVERSION
# ---------------------------------------------------------

def convert_to_wav(input_path):
    """
    Convert uploaded or downloaded audio/video to
    mono, 16 kHz WAV format.

    Supports formats accepted by the installed FFmpeg build,
    including MP3, MP4, WAV, M4A, WEBM and AAC.
    """

    input_path = Path(input_path)

    if not input_path.exists():
        raise FileNotFoundError(
            f"Input audio/video file does not exist: {input_path}"
        )

    if input_path.stat().st_size == 0:
        raise ValueError("Input file is empty.")

    ffmpeg = _find_ffmpeg()

    output_path = input_path.with_name(
        input_path.stem + "_converted.wav"
    )

    command = [
        ffmpeg,
        "-y",
        "-i", str(input_path),
        "-vn",
        "-ac", str(CHANNELS),
        "-ar", str(SAMPLE_RATE),
        "-acodec", "pcm_s16le",
        str(output_path)
    ]

    _run_ffmpeg(command)

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("WAV conversion failed.")

    print("CONVERTED WAV:", output_path)

    return str(output_path)


# ---------------------------------------------------------
# AUDIO CHUNKING
# ---------------------------------------------------------

def chunk_audio(wav_path, chunk_length_ms=CHUNK_LENGTH_MS):
    """
    Split WAV audio into 10-minute chunks by default.
    Returns a list of chunk file paths.
    """

    wav_path = Path(wav_path)

    if not wav_path.exists():
        raise FileNotFoundError(
            f"WAV file does not exist: {wav_path}"
        )

    if chunk_length_ms <= 0:
        raise ValueError("Chunk length must be greater than zero.")

    try:
        audio = AudioSegment.from_wav(str(wav_path))
    except Exception as exc:
        raise RuntimeError(
            f"Unable to read WAV file: {exc}"
        ) from exc

    if len(audio) == 0:
        raise ValueError("Audio contains no sound data.")

    chunk_dir = wav_path.parent / (wav_path.stem + "_chunks")
    chunk_dir.mkdir(parents=True, exist_ok=True)

    chunk_paths = []

    for index, start in enumerate(
        range(0, len(audio), chunk_length_ms)
    ):
        end = min(start + chunk_length_ms, len(audio))

        chunk = audio[start:end]

        chunk_path = chunk_dir / f"chunk_{index + 1}.wav"

        chunk.export(
            str(chunk_path),
            format="wav",
            parameters=[
                "-ac", str(CHANNELS),
                "-ar", str(SAMPLE_RATE)
            ]
        )

        chunk_paths.append(str(chunk_path))

    print("CHUNKS CREATED:", len(chunk_paths))

    return chunk_paths


# ---------------------------------------------------------
# COMPLETE AUDIO PROCESSING
# ---------------------------------------------------------

def process_audio(input_path):
    """
    Process a local audio/video file:
    1. Validate input
    2. Convert to WAV
    3. Split into chunks
    4. Return chunk paths
    """

    print("INPUT TYPE: LOCAL FILE")
    print("SOURCE:", repr(input_path))

    wav_path = convert_to_wav(input_path)

    chunks = chunk_audio(wav_path)

    return chunks


# ---------------------------------------------------------
# YOUTUBE PROCESSING
# ---------------------------------------------------------

def process_youtube_audio(url):
    """
    Download YouTube audio, convert it to WAV,
    split into chunks and return chunk paths.
    """

    print("INPUT TYPE: YOUTUBE URL")

    downloaded_path = download_youtube_audio(url)

    wav_path = convert_to_wav(downloaded_path)

    chunks = chunk_audio(wav_path)

    return chunks
