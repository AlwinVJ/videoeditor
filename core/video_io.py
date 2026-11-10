import os
from pathlib import Path
import shutil
import time
import cv2

# Clamp OpenCV internal thread pool to 1 thread to avoid host oversubscription on cloud containers
cv2.setNumThreads(1)

from core.audio import create_ffmpeg_pipe_process, merge_audio
from core.worker import VideoFrameSegmenter
from core.utils import safe_unlink


def get_video_metadata(video_path: Path) -> dict:
    """Extract metadata from a video file quickly from stream headers."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Could not open video file: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    fps = fps if fps > 0 else 24.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_seconds = (total_frames / fps) if fps > 0 else 0.0

    cap.release()

    return {
        "width": width,
        "height": height,
        "fps": round(fps, 2),
        "total_frames": total_frames,
        "duration": round(duration_seconds, 2),
    }


def compute_target_resolution(width: int, height: int, max_dimension: int = 1920) -> tuple[int, int]:
    """
    Scale resolution down if it exceeds max_dimension, ensuring both dimensions are even.
    Preserves exact aspect ratio.
    """
    max_side = max(width, height)
    if max_side > max_dimension:
        scale = max_dimension / float(max_side)
        width = int(width * scale)
        height = int(height * scale)

    # Both dimensions must be even for standard video codecs (libx264/yuv420p)
    width = width if width % 2 == 0 else width - 1
    height = height if height % 2 == 0 else height - 1

    return max(width, 2), max(height, 2)


def process_video(
    input_path: Path,
    output_path: Path,
    effect="blur",
    bg_image=None,
    blur_strength=51,
    progress_callback=None,
    max_duration_seconds: float = 600.0,
    frame_stride: int = None,
):
    """
    Process video with single-pass direct FFmpeg pipe streaming, adaptive frame stride,
    zero-copy memoryview writes, and single-thread clamping to prevent CPU throttling.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        raise ValueError(f"Error opening video file: {input_path}")

    ffmpeg_proc = None
    segmenter = None

    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        fps = fps if fps > 0 else 24.0

        orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        duration = (total_frames / fps) if fps > 0 else 0.0
        if duration > max_duration_seconds:
            raise ValueError(
                f"Video duration ({duration:.1f}s) exceeds the maximum allowed limit "
                f"of {max_duration_seconds:.0f} seconds."
            )

        # Scale down 4K or excessive resolutions to ensure low memory and CPU footprint
        target_w, target_h = compute_target_resolution(orig_w, orig_h, max_dimension=1920)
        needs_resize = (target_w != orig_w) or (target_h != orig_h)

        # Compute adaptive frame stride if not explicitly specified (targets 8-10 inferences/s)
        if frame_stride is None:
            frame_stride = max(1, int(round(fps / 10.0)))

        # Initialize segmenter with target resolution and frame stride
        segmenter = VideoFrameSegmenter(
            effect=effect,
            bg_image=bg_image,
            blur_strength=blur_strength,
            target_size=(target_w, target_h),
            frame_stride=frame_stride,
        )

        # Launch single-pass FFmpeg streaming pipe
        ffmpeg_proc = create_ffmpeg_pipe_process(
            original_video=input_path,
            final_output=output_path,
            width=target_w,
            height=target_h,
            fps=fps,
        )

        frame_count = 0
        update_interval = max(1, total_frames // 100) if total_frames > 0 else 5

        # Stream processed frames directly into FFmpeg stdin with zero-copy memoryview
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            if needs_resize:
                frame = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_LINEAR)

            processed_frame = segmenter.process_frame(frame)

            try:
                # Zero-copy memoryview write avoids allocating large temporary Python byte buffers
                ffmpeg_proc.stdin.write(memoryview(processed_frame))
            except (BrokenPipeError, IOError) as e:
                raise RuntimeError("FFmpeg pipe closed unexpectedly during frame encoding.") from e

            frame_count += 1

            if progress_callback and total_frames > 0:
                if frame_count % update_interval == 0 or frame_count == total_frames:
                    progress_callback(min(frame_count / total_frames, 1.0))

        # Close stdin to signal EOF to FFmpeg
        if ffmpeg_proc and ffmpeg_proc.stdin:
            ffmpeg_proc.stdin.close()

        # Wait for FFmpeg to finish multiplexing and writing the final file
        stderr_bytes = ffmpeg_proc.stderr.read() if ffmpeg_proc.stderr else b""
        ffmpeg_proc.stderr.close()
        ffmpeg_proc.wait(timeout=120)

        if ffmpeg_proc.returncode != 0:
            stderr_text = stderr_bytes.decode("utf-8", errors="replace")
            raise RuntimeError(f"FFmpeg streaming encoding failed ({ffmpeg_proc.returncode}): {stderr_text[:300]}")

    finally:
        if cap is not None and cap.isOpened():
            cap.release()
        if segmenter is not None:
            segmenter.close()
        if ffmpeg_proc is not None and ffmpeg_proc.poll() is None:
            try:
                ffmpeg_proc.kill()
            except Exception:
                pass

    return output_path
