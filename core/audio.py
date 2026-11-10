import subprocess
from pathlib import Path
import imageio_ffmpeg as ffmpeg


def merge_audio(original_video, processed_video, final_output, timeout=180):
    """
    Merge the original audio stream onto the processed video.
    Uses an optimized preset and thread ceiling to control CPU load,
    and applies faststart for instant web preview.
    """
    ffmpeg_path = ffmpeg.get_ffmpeg_exe()

    final_output = Path(final_output)
    final_output.parent.mkdir(parents=True, exist_ok=True)

    command = [
        ffmpeg_path,
        "-y",
        "-i", str(processed_video),
        "-i", str(original_video),
        "-c:v", "libx264",
        "-preset", "veryfast",
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
        result = subprocess.run(
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
