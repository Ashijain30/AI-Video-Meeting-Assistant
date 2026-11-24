
import os
import re
import uuid
import yt_dlp
from pydub import AudioSegment


DOWNLOAD_DIR = "downloades"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def clean_youtube_url(url: str) -> str:
    """
    Extract a clean YouTube URL, including from Markdown links.
    """

    url = str(url).strip()

    match = re.search(
        r"https?://(?:www\.|m\.)?(?:youtube\.com|youtu\.be)/[^\s)\]>]+",
        url,
        re.IGNORECASE
    )

    if not match:
        raise ValueError("Invalid YouTube URL.")

    return match.group(0).rstrip(".,;")


def download_youtube_audio(url: str) -> str:
    """
    Download YouTube audio and convert it to WAV.
    """

    url = clean_youtube_url(url)

    print("CLEAN YOUTUBE URL:", repr(url))

    unique_id = uuid.uuid4().hex

    output_path = os.path.join(
        DOWNLOAD_DIR,
        f"{unique_id}.%(ext)s"
    )

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_path,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": False,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)

        filename = os.path.join(
            DOWNLOAD_DIR,
            f"{unique_id}.wav"
        )

        if not os.path.isfile(filename):
            raise FileNotFoundError(
                f"Downloaded WAV file not found: {filename}"
            )

        print("YOUTUBE AUDIO READY:", filename)

        return filename

    except Exception as e:
        print("YOUTUBE DOWNLOAD ERROR:", repr(e))
        raise RuntimeError(
            f"YouTube audio download failed: {e}"
        ) from e


def convert_to_wav(input_path: str) -> str:
    """
    Convert local audio/video files to mono 16 kHz WAV.
    Supports MP4, MP3, WAV and other FFmpeg formats.
    """

    if not os.path.isfile(input_path):
        raise FileNotFoundError(
            f"Input file not found: {input_path}"
        )

    output_path = (
        os.path.splitext(input_path)[0] + "_converted.wav"
    )

    print("Converting audio to WAV...")

    audio = AudioSegment.from_file(input_path)

    audio = audio.set_channels(1).set_frame_rate(16000)

    audio.export(output_path, format="wav")

    print("WAV FILE CREATED:", output_path)

    return output_path


def chunk_audio(wav_path: str, chunk_minutes: int = 10) -> list:
    """
    Split WAV audio into chunks.
    Default chunk duration: 10 minutes.
    """

    if chunk_minutes <= 0:
        raise ValueError("chunk_minutes must be positive.")

    audio = AudioSegment.from_wav(wav_path)

    chunk_ms = chunk_minutes * 60 * 1000

    chunks = []

    for i, start in enumerate(range(0, len(audio), chunk_ms)):

        chunk = audio[start:start + chunk_ms]

        chunk_path = f"{wav_path}_chunk_{i}.wav"

        chunk.export(chunk_path, format="wav")

        chunks.append(chunk_path)

    print("CHUNKS CREATED:", len(chunks))

    return chunks


def process_input(source: str) -> list:
    """
    Main entry point called by app.py.

    Handles:
    - YouTube URLs
    - Local MP4 files
    - Local MP3 files
    - Local WAV files
    """

    source = str(source).strip()

    print("SOURCE:", repr(source))

    youtube_match = re.search(
        r"https?://(?:www\.|m\.)?(?:youtube\.com|youtu\.be)/",
        source,
        re.IGNORECASE
    )

    if youtube_match:

        print("INPUT TYPE: YOUTUBE URL")

        wav_path = download_youtube_audio(source)

    else:

        print("INPUT TYPE: LOCAL FILE")

        if not os.path.isfile(source):
            raise FileNotFoundError(
                f"Local file not found: {source}"
            )

        wav_path = convert_to_wav(source)

    print("Splitting audio into chunks...")

    chunks = chunk_audio(wav_path)

    print(
        f"Audio ready — {len(chunks)} chunk(s) created."
    )

    return chunks

