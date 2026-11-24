
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

# Detect system FFmpeg (Linux / Streamlit Cloud / Windows PATH)
SYSTEM_FFMPEG = shutil.which("ffmpeg")
SYSTEM_FFPROBE = shutil.which("ffprobe")

# Local Windows FFmpeg
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
        "FFmpeg or FFprobe not found. "
        "Install FFmpeg and add it to PATH."
    )

# Add FFmpeg directory to PATH
os.environ["PATH"] = (
    FFMPEG_LOCATION
    + os.pathsep
    + os.environ.get("PATH", "")
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

    # Detect Node.js for YouTube JavaScript challenges
    node_path = shutil.which("node")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_path,
        "ffmpeg_location": FFMPEG_LOCATION,
        "noplaylist": True,

        # Logging
        "quiet": True,
        "no_warnings": False,

        # Retry configuration
        "retries": 5,
        "fragment_retries": 5,
        "extractor_retries": 3,
        "socket_timeout": 30,

        # Convert downloaded audio to WAV
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],
    }

    # Configure Node.js runtime explicitly
    if node_path:
        print("yt-dlp JavaScript runtime: Node.js", node_path)

        ydl_opts["js_runtimes"] = {
            "node": {
                "path": node_path
            }
        }

    else:
        print(
            "WARNING: Node.js not found in PATH. "
            "YouTube extraction may fail."
        )

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:

        info = ydl.extract_info(url, download=True)

        filename = os.path.splitext(
            ydl.prepare_filename(info)
        )[0] + ".wav"

    if not os.path.isfile(filename):
        raise FileNotFoundError(
            "yt-dlp finished, but the expected WAV file "
            f"was not created: {filename}"
        )

    print("YouTube audio downloaded:", filename)

    return filename


# ---------------- Convert Audio to WAV ----------------

def convert_to_wav(input_path: str) -> str:

    """Convert audio/video into mono 16kHz WAV."""

    print("Converting audio to WAV...")

    if not os.path.isfile(input_path):
        raise FileNotFoundError(
            f"Input audio/video file not found: {input_path}"
        )

    output_path = (
        os.path.splitext(input_path)[0]
        + "_converted.wav"
    )

    audio = AudioSegment.from_file(input_path)

    # Prepare audio for transcription
    audio = audio.set_channels(1)
    audio = audio.set_frame_rate(16000)

    audio.export(output_path, format="wav")

    print("WAV conversion completed:", output_path)

    return output_path


# ---------------- Chunk Audio ----------------

def chunk_audio(wav_path: str, chunk_minutes: int = 10) -> list:

    """Split WAV audio into smaller chunks."""

    print("Splitting audio into chunks...")

    if chunk_minutes <= 0:
        raise ValueError("chunk_minutes must be greater than zero.")

    if not os.path.isfile(wav_path):
        raise FileNotFoundError(
            f"WAV file not found: {wav_path}"
        )

    audio = AudioSegment.from_wav(wav_path)

    chunk_ms = chunk_minutes * 60 * 1000

    chunks = []

    for i, start in enumerate(range(0, len(audio), chunk_ms)):

        chunk = audio[start:start + chunk_ms]

        chunk_path = f"{wav_path}_chunk_{i}.wav"

        chunk.export(chunk_path, format="wav")

        chunks.append(chunk_path)

    print("Total audio chunks:", len(chunks))

    return chunks


# ---------------- Main Processing Function ----------------

def process_input(source: str) -> list:

    """Process YouTube URLs or locally uploaded audio/video files."""

    print("========== MEETMIND DEBUG ==========")
    print("SOURCE:", repr(source))

    if source.startswith(("http://", "https://")):

        print("INPUT TYPE: URL")

        downloaded_wav = download_youtube_audio(source)

        wav_path = convert_to_wav(downloaded_wav)

    else:

        print("INPUT TYPE: LOCAL FILE")
        print("FILE EXISTS:", os.path.exists(source))

        if not os.path.exists(source):
            raise FileNotFoundError(
                f"Uploaded file not found: {source}"
            )

        wav_path = convert_to_wav(source)

    chunks = chunk_audio(wav_path)

    print("CHUNKS CREATED:", len(chunks))
    print("===================================")

    return chunks
