
import os
import shutil
import yt_dlp

# ---------------- Project Configuration ----------------

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DOWNLOAD_DIR = os.path.join(PROJECT_ROOT, "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ---------------- FFmpeg Configuration ----------------

LOCAL_FFMPEG_BIN = os.path.join(
    PROJECT_ROOT,
    "ffmpeg-9.1-essentials_build",
    "bin"
)

# Use local Windows FFmpeg if available; otherwise use system FFmpeg
SYSTEM_FFMPEG = shutil.which("ffmpeg")
SYSTEM_FFPROBE = shutil.which("ffprobe")

LOCAL_FFMPEG = os.path.join(LOCAL_FFMPEG_BIN, "ffmpeg.exe")
LOCAL_FFPROBE = os.path.join(LOCAL_FFMPEG_BIN, "ffprobe.exe")

if os.path.exists(LOCAL_FFMPEG) and os.path.exists(LOCAL_FFPROBE):
    FFMPEG_PATH = LOCAL_FFMPEG
    FFPROBE_PATH = LOCAL_FFPROBE
    FFMPEG_LOCATION = LOCAL_FFMPEG_BIN
elif SYSTEM_FFMPEG and SYSTEM_FFPROBE:
    FFMPEG_PATH = SYSTEM_FFMPEG
    FFPROBE_PATH = SYSTEM_FFPROBE
    FFMPEG_LOCATION = os.path.dirname(SYSTEM_FFMPEG)
else:
    raise RuntimeError(
        "FFmpeg or FFprobe not found. Install FFmpeg and add it to PATH."
    )

# Add FFmpeg to PATH
os.environ["PATH"] = (
    FFMPEG_LOCATION + os.pathsep + os.environ.get("PATH", "")
)

from pydub import AudioSegment

AudioSegment.converter = FFMPEG_PATH
AudioSegment.ffmpeg = FFMPEG_PATH
AudioSegment.ffprobe = FFPROBE_PATH


# ---------------- YouTube Audio Download ----------------

def download_youtube_audio(url: str) -> str:

    print("Downloading YouTube audio...")

    output_path = os.path.join(
        DOWNLOAD_DIR,
        "%(title)s.%(ext)s"
    )

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_path,
        "ffmpeg_location": FFMPEG_LOCATION,
        "js_runtimes": {"node": {}},
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],
        "quiet": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

        filename = os.path.splitext(
            ydl.prepare_filename(info)
        )[0] + ".wav"

    return filename


# ---------------- Convert Audio to WAV ----------------

def convert_to_wav(input_path: str) -> str:

    """Convert audio/video to mono 16kHz WAV."""

    print("Converting audio to WAV...")

    output_path = os.path.splitext(input_path)[0] + "_converted.wav"

    audio = AudioSegment.from_file(input_path)
    audio = audio.set_channels(1)
    audio = audio.set_frame_rate(16000)

    audio.export(output_path, format="wav")

    return output_path


# ---------------- Chunk Audio ----------------

def chunk_audio(wav_path: str, chunk_minutes: int = 10) -> list:

    print("Splitting audio into chunks...")

    audio = AudioSegment.from_wav(wav_path)

    chunk_ms = chunk_minutes * 60 * 1000

    chunks = []

    for i, start in enumerate(range(0, len(audio), chunk_ms)):

        chunk = audio[start:start + chunk_ms]

        chunk_path = f"{wav_path}_chunk_{i}.wav"

        chunk.export(chunk_path, format="wav")

        chunks.append(chunk_path)

    return chunks


# ---------------- Main Processing Function ----------------

def process_input(source: str) -> list:

    if source.startswith(("http://", "https://")):

        print("Detected YouTube URL.")

        downloaded_wav = download_youtube_audio(source)
        wav_path = convert_to_wav(downloaded_wav)

    else:

        print("Detected local file.")

        wav_path = convert_to_wav(source)

    chunks = chunk_audio(wav_path)

    print(f"Audio ready — {len(chunks)} chunk(s) created.")

    return chunks
