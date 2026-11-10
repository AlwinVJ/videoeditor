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
