import subprocess
from pathlib import Path
import imageio_ffmpeg as ffmpeg


def create_ffmpeg_pipe_process(
    original_video: Path,
    final_output: Path,
    width: int,
    height: int,
    fps: float,
):
    """
    Launch an FFmpeg process that accepts raw BGR frames from stdin and multiplexes
    audio directly from the original video in a single pass.
    Configured with ultrafast preset, fastdecode tuning, faststart index,
    and a 2-thread ceiling to minimize CPU usage on Streamlit Cloud.
    """
    ffmpeg_path = ffmpeg.get_ffmpeg_exe()
    final_output = Path(final_output)
    final_output.parent.mkdir(parents=True, exist_ok=True)

    command = [
        ffmpeg_path,
        "-y",
        "-loglevel", "error",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{width}x{height}",
        "-pix_fmt", "bgr24",
        "-r", str(fps),
        "-i", "pipe:0",
        "-i", str(original_video),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "fastdecode",
        "-crf", "23",
        "-threads", "2",
        "-c:a", "aac",
        "-b:a", "192k",
        "-map", "0:v:0",
        "-map", "1:a:0?",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(final_output),
    ]

    return subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def merge_audio(original_video, processed_video, final_output, timeout=180):
    """
    Fallback helper to multiplex original audio onto a processed video file.
    """
    ffmpeg_path = ffmpeg.get_ffmpeg_exe()
    final_output = Path(final_output)
    final_output.parent.mkdir(parents=True, exist_ok=True)

    command = [
        ffmpeg_path,
        "-y",
        "-loglevel", "error",
        "-i", str(processed_video),
        "-i", str(original_video),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "fastdecode",
        "-crf", "23",
        "-threads", "2",
        "-c:a", "aac",
        "-b:a", "192k",
        "-map", "0:v:0",
        "-map", "1:a:0?",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(final_output),
    ]

    try:
        subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=True,
        )
        return final_output
    except subprocess.TimeoutExpired as e:
        print(f"FFmpeg process timed out after {timeout} seconds.")
        raise TimeoutError(f"Video encoding timed out after {timeout} seconds.") from e
    except subprocess.CalledProcessError as e:
        stderr_output = e.stderr if e.stderr else "Unknown FFmpeg error"
        print(f"FFmpeg failed with exit code {e.returncode}: {stderr_output}")
        raise RuntimeError(f"FFmpeg encoding failed: {stderr_output[:300]}") from e


def has_audio_stream(video_path: Path) -> bool:
    """
    Check if a video file has at least one audio stream using an FFmpeg probe.
    Returns True if an audio stream is detected, False otherwise.
    """
    ffmpeg_path = ffmpeg.get_ffmpeg_exe()
    try:
        proc = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-i", str(video_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
        )
        return "Audio:" in proc.stderr
    except Exception as e:
        print(f"Audio stream probe failed for {video_path}: {e}")
        return False


def extract_audio_for_transcription(
    video_path: Path,
    output_audio_path: Path,
    timeout: int = 120,
) -> Path:
    """
    Extract speech-optimized mono MP3 audio (16kHz, 64kbps) from a video file.
    Whisper natively operates on 16kHz audio; mono 16kHz 64k maximizes compression
    to comfortably remain well below Groq's 25 MB upload limit without degrading speech clarity.
    """
    video_path = Path(video_path)
    output_audio_path = Path(output_audio_path)
    output_audio_path.parent.mkdir(parents=True, exist_ok=True)

    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    if not has_audio_stream(video_path):
        raise ValueError("The selected video does not contain an audio track to transcribe.")

    ffmpeg_path = ffmpeg.get_ffmpeg_exe()
    command = [
        ffmpeg_path,
        "-y",
        "-loglevel", "error",
        "-i", str(video_path),
        "-vn",                   # Omit video stream
        "-acodec", "libmp3lame", # MP3 audio encoding
        "-ar", "16000",          # 16kHz sampling rate
        "-ac", "1",              # Mono channel
        "-b:a", "64k",           # 64kbps bitrate
        str(output_audio_path),
    ]

    try:
        subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=True,
        )
    except subprocess.TimeoutExpired as e:
        raise TimeoutError(f"Audio extraction timed out after {timeout} seconds.") from e
    except subprocess.CalledProcessError as e:
        stderr_output = e.stderr.strip() if e.stderr else "Unknown FFmpeg error"
        raise RuntimeError(f"Audio extraction failed: {stderr_output[:300]}") from e

    if not output_audio_path.exists() or output_audio_path.stat().st_size == 0:
        raise RuntimeError("Extracted audio file is empty or was not created.")

    return output_audio_path

