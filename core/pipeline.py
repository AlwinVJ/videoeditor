import json
from pathlib import Path
import re
import socket
import subprocess
from typing import Any, Callable, Dict, List, Optional
import urllib.error
import urllib.parse
import urllib.request

import cv2
import imageio_ffmpeg as ffmpeg

from core.utils import generate_safe_filename, safe_unlink
from core.video_io import compute_target_resolution, get_video_metadata

DEFAULT_DOWNLOAD_TIMEOUT = 45


def download_stock_clip(
    clip: Dict[str, Any],
    temp_dir: Path,
    timeout: int = DEFAULT_DOWNLOAD_TIMEOUT,
) -> Path:
    """
    Acquire a stock clip video file on disk:
    1. If a local file path is already present in the clip dict, reuse it.
    2. If the clip was previously downloaded to temp_dir, reuse the cached file.
    3. Otherwise, download from download_url (or preview_url) with streaming chunks.

    Args:
        clip: Standardized stock clip dictionary.
        temp_dir: Directory where downloaded stock clips are cached.
        timeout: Request timeout in seconds.

    Returns:
        Path to the local MP4 video file.

    Raises:
        ValueError: If clip data is invalid or has no accessible URL/path.
        ConnectionError: If network connection fails.
        TimeoutError: If the download times out.
        RuntimeError: If download fails or output file is corrupt/empty.
    """
    if not isinstance(clip, dict):
        raise ValueError("Invalid stock clip: expected a dictionary.")

    clip_id = clip.get("id") or "clip"

    # 1. Check for existing local path in clip dict
    for path_key in ("local_path", "path", "file_path"):
        cand = clip.get(path_key)
        if cand:
            p = Path(cand)
            if p.exists() and p.is_file() and p.stat().st_size > 0:
                return p

    temp_dir = Path(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    # 2. Check for cached file in temp_dir
    cached_path = temp_dir / f"stock_clip_{clip_id}.mp4"
    if cached_path.exists() and cached_path.stat().st_size > 1024:
        return cached_path

    # 3. Resolve remote URL (prefer high-res download_url, fallback to preview_url)
    remote_url = clip.get("download_url") or clip.get("preview_url")
    if not remote_url or not str(remote_url).strip():
        raise ValueError(
            f"Stock clip #{clip_id} does not contain a valid download or preview URL."
        )

    remote_url_str = str(remote_url).strip()

    # Handle local file:// URI if present
    if remote_url_str.startswith("file://"):
        local_cand = Path(urllib.parse.unquote(urllib.parse.urlparse(remote_url_str).path))
        if local_cand.exists() and local_cand.stat().st_size > 0:
            return local_cand
        raise FileNotFoundError(f"Local file URI target not found: {remote_url_str}")

    # Handle direct local path passed as URL
    local_p = Path(remote_url_str)
    if local_p.exists() and local_p.is_file() and local_p.stat().st_size > 0:
        return local_p

    # Download over HTTP / HTTPS
    tmp_download_path = temp_dir / f"stock_clip_{clip_id}_part.tmp"
    req = urllib.request.Request(
        remote_url_str,
        headers={"User-Agent": "Mozilla/5.0 (Streamlit-VideoEditor/1.0; Python-BrollPipeline)"},
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            with open(tmp_download_path, "wb") as out_fh:
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    out_fh.write(chunk)

        if not tmp_download_path.exists() or tmp_download_path.stat().st_size == 0:
            safe_unlink(tmp_download_path)
            raise RuntimeError(f"Downloaded stock clip #{clip_id} is empty.")

        # Atomic rename once completely downloaded
        if cached_path.exists():
            safe_unlink(cached_path)
        tmp_download_path.rename(cached_path)
        return cached_path

    except urllib.error.HTTPError as e:
        safe_unlink(tmp_download_path)
        raise RuntimeError(
            f"Failed to download stock clip #{clip_id} (HTTP {e.code}): {e.reason}"
        ) from e
    except urllib.error.URLError as e:
        safe_unlink(tmp_download_path)
        if isinstance(e.reason, socket.timeout):
            raise TimeoutError(
                f"Download timed out for stock clip #{clip_id}. Please try again."
            ) from e
        raise ConnectionError(
            f"Could not connect to download stock clip #{clip_id}. Please verify your internet connection."
        ) from e
    except (socket.timeout, TimeoutError) as e:
        safe_unlink(tmp_download_path)
        raise TimeoutError(
            f"Download timed out for stock clip #{clip_id}. Please try again."
        ) from e
    except Exception as e:
        safe_unlink(tmp_download_path)
        raise RuntimeError(
            f"Unexpected error while downloading stock clip #{clip_id}: {str(e)}"
        ) from e


def compose_broll_video(
    original_video_path: Path | str,
    broll_placements: List[Dict[str, Any]],
    output_path: Path | str,
    temp_dir: Path | str,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    timeout: int = 180,
) -> Path:
    """
    Integrate selected B-roll clips into the original video at specified timeline intervals.

    - Overlays the B-roll footage during each clip's [start, end] window.
    - Fits B-roll footage to the original video's resolution and aspect ratio (centered with letterboxing).
    - Preserves the original video's audio track continuously.
    - Preserves the original video's resolution, frame rate, and aspect ratio.

    Args:
        original_video_path: Path to the original source video.
        broll_placements: List of placement dicts with 'clip', 'start', and 'end'.
        output_path: Destination path for the generated video file.
        temp_dir: Temporary directory for downloaded stock clips and intermediate files.
        progress_callback: Optional callback receiving (progress_ratio: float, status_message: str).
        timeout: Maximum seconds to wait for FFmpeg to finish rendering.

    Returns:
        Path to the rendered output MP4 file.

    Raises:
        FileNotFoundError: If original video does not exist.
        ValueError: If placements or timestamps are invalid.
        RuntimeError: If FFmpeg encoding fails.
    """
    orig_path = Path(original_video_path)
    if not orig_path.exists() or not orig_path.is_file():
        raise FileNotFoundError(f"Original video file not found: {orig_path}")

    if not broll_placements or not isinstance(broll_placements, list):
        raise ValueError("At least one B-roll clip placement must be provided.")

    temp_dir = Path(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if progress_callback:
        progress_callback(0.05, "Analyzing original video metadata...")

    meta = get_video_metadata(orig_path)
    orig_w = int(meta.get("width") or 1280)
    orig_h = int(meta.get("height") or 720)
    orig_fps = float(meta.get("fps") or 24.0)
    orig_dur = float(meta.get("duration") or 0.0)

    # Ensure dimensions are even for standard H.264 encoding
    target_w = orig_w if orig_w % 2 == 0 else orig_w - 1
    target_h = orig_h if orig_h % 2 == 0 else orig_h - 1
    target_w = max(2, target_w)
    target_h = max(2, target_h)

    # Validate and acquire each B-roll clip file
    prepared_placements = []
    total_clips = len(broll_placements)

    for idx, p in enumerate(broll_placements):
        if not isinstance(p, dict):
            continue

        clip_data = p.get("clip")
        if not clip_data or not isinstance(clip_data, dict):
            raise ValueError(f"Placement #{idx + 1} is missing valid stock clip data.")

        start_time = float(p.get("start", 0.0))
        end_time = float(p.get("end", 0.0))

        start_time = max(0.0, start_time)
        if orig_dur > 0:
            start_time = min(start_time, orig_dur)
            end_time = min(end_time, orig_dur)

        if start_time >= end_time:
            raise ValueError(
                f"Invalid B-roll placement #{idx + 1}: start timestamp ({start_time:.2f}s) "
                f"must be strictly before end timestamp ({end_time:.2f}s)."
            )

        if (end_time - start_time) < 0.1:
            raise ValueError(
                f"B-roll placement #{idx + 1} duration is too short (minimum 0.1s required)."
            )

        if progress_callback:
            dl_progress = 0.10 + (0.25 * ((idx + 1) / total_clips))
            clip_name = clip_data.get("keyword") or f"Clip #{clip_data.get('id', idx + 1)}"
            progress_callback(dl_progress, f"Downloading & preparing {clip_name}...")

        local_clip_file = download_stock_clip(clip_data, temp_dir)
        prepared_placements.append({
            "file": local_clip_file,
            "start": round(start_time, 2),
            "end": round(end_time, 2),
            "clip_id": clip_data.get("id", idx + 1),
        })

    if not prepared_placements:
        raise ValueError("No valid B-roll clip placements could be prepared.")

    # Sort placements chronologically by start timestamp
    prepared_placements.sort(key=lambda x: x["start"])

    if progress_callback:
        progress_callback(0.40, "Building video timeline and FFmpeg filter graph...")

    ffmpeg_exe = ffmpeg.get_ffmpeg_exe()

    # Build FFmpeg command inputs
    cmd = [
        ffmpeg_exe,
        "-y",
        "-loglevel", "error",
        "-i", str(orig_path),  # Input 0: original video
    ]

    for p in prepared_placements:
        cmd.extend(["-stream_loop", "-1", "-i", str(p["file"])])

    # Build filter complex
    filter_parts = []
    for k, p in enumerate(prepared_placements, start=1):
        s = p["start"]
        # Scale & pad B-roll to match original video dimensions, normalized SAR & FPS, shifted PTS
        filter_parts.append(
            f"[{k}:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
            f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={orig_fps},"
            f"setpts=PTS-STARTPTS+{s}/TB[broll{k}]"
        )

    # Chain overlay filters sequentially
    last_v = "[0:v]"
    for k, p in enumerate(prepared_placements, start=1):
        s = p["start"]
        e = p["end"]
        out_v = f"[tmp{k}]" if k < len(prepared_placements) else "[outv]"
        filter_parts.append(
            f"{last_v}[broll{k}]overlay=0:0:enable='between(t,{s},{e})':eof_action=pass{out_v}"
        )
        last_v = out_v

    filter_complex = ";".join(filter_parts)

    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "0:a?",           # Preserve original audio stream if present
        "-c:v", "libx264",
        "-preset", "ultrafast",   # Fast render for interactive web UI
        "-crf", "23",
        "-pix_fmt", "yuv420p",    # Standard web-compatible pixel format
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        "-shortest",
        str(out_path),
    ])

    if progress_callback:
        progress_callback(0.55, "Rendering final video with B-roll cutaways...")

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )

        if proc.returncode != 0:
            stderr_text = proc.stderr if proc.stderr else "Unknown FFmpeg error"
            raise RuntimeError(f"FFmpeg rendering failed ({proc.returncode}): {stderr_text[:400]}")

        if not out_path.exists() or out_path.stat().st_size == 0:
            raise RuntimeError("FFmpeg rendering finished but generated output file is empty.")

        if progress_callback:
            progress_callback(1.0, "Video generation complete! Redirecting to Download...")

        return out_path

    except subprocess.TimeoutExpired as e:
        safe_unlink(out_path)
        raise TimeoutError(f"Video rendering timed out after {timeout} seconds.") from e
    except Exception:
        safe_unlink(out_path)
        raise
