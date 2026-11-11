import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from groq import Groq, AuthenticationError, APIConnectionError, RateLimitError, APIStatusError

from core.audio import extract_audio_for_transcription, has_audio_stream
from core.config import get_groq_api_key
from core.utils import safe_unlink, get_file_fingerprint

# Maximum audio upload size supported by Groq Whisper (25 MB)
MAX_GROQ_AUDIO_SIZE_BYTES = 25 * 1024 * 1024


def load_groq_api_key() -> str:
    """Load and validate the Groq API key from environment (.env) or Streamlit Secrets."""
    return get_groq_api_key()


def format_timestamp(seconds: float) -> str:
    """Format seconds into MM:SS or HH:MM:SS format."""
    if not seconds or seconds < 0:
        return "00:00"
    total_seconds = int(round(seconds))
    m, s = divmod(total_seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def format_segment_time(start: float, end: float) -> str:
    """Format start and end timestamps into '00:00 - 00:05' display string."""
    return f"{format_timestamp(start)} - {format_timestamp(end)}"


def transcribe_audio_with_groq(
    audio_path: Path,
    api_key: Optional[str] = None,
    model: str = "whisper-large-v3",
) -> List[Dict[str, Any]]:
    """
    Send an audio file to Groq Whisper for speech transcription with segment timestamps.

    Args:
        audio_path: Path to the local MP3/M4A/WAV audio file.
        api_key: Optional explicit Groq API key. If omitted, loaded from .env.
        model: Groq Whisper model ID ('whisper-large-v3' or 'whisper-large-v3-turbo').

    Returns:
        List of segment dictionaries:
        [
            {"start": float, "end": float, "text": str},
            ...
        ]
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file does not exist: {audio_path}")

    file_size = audio_path.stat().st_size
    if file_size == 0:
        raise ValueError("Audio file is empty.")

    if file_size > MAX_GROQ_AUDIO_SIZE_BYTES:
        raise ValueError(
            f"Audio file ({file_size / (1024 * 1024):.1f} MB) exceeds Groq's 25 MB limit."
        )

    resolved_key = api_key or load_groq_api_key()
    client = Groq(api_key=resolved_key)

    try:
        with open(audio_path, "rb") as fh:
            response = client.audio.transcriptions.create(
                file=(audio_path.name, fh),
                model=model,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )
    except AuthenticationError as e:
        raise PermissionError(
            "Groq authentication failed. Please check that your GROQ_API_KEY in .env or Streamlit Secrets is valid."
        ) from e
    except RateLimitError as e:
        raise RuntimeError(
            "Groq API rate limit exceeded. Please wait a moment before trying again."
        ) from e
    except APIConnectionError as e:
        raise ConnectionError(
            "Could not connect to Groq API. Please verify your internet connection."
        ) from e
    except APIStatusError as e:
        raise RuntimeError(
            f"Groq API error ({e.status_code}): {e.message}"
        ) from e
    except Exception as e:
        raise RuntimeError(f"Transcription failed: {str(e)}") from e

    # Extract segment-level timestamps from the response
    segments_data = getattr(response, "segments", None)
    if not segments_data and hasattr(response, "model_dump"):
        segments_data = response.model_dump().get("segments")

    parsed_segments: List[Dict[str, Any]] = []

    if segments_data:
        for seg in segments_data:
            if isinstance(seg, dict):
                start = round(float(seg.get("start", 0.0) or 0.0), 2)
                end = round(float(seg.get("end", 0.0) or 0.0), 2)
                text = str(seg.get("text", "")).strip()
            else:
                start = round(float(getattr(seg, "start", 0.0) or 0.0), 2)
                end = round(float(getattr(seg, "end", 0.0) or 0.0), 2)
                text = str(getattr(seg, "text", "")).strip()

            if text:
                parsed_segments.append({
                    "start": start,
                    "end": end,
                    "text": text,
                })

    # If segments was empty but full text was returned:
    if not parsed_segments:
        full_text = getattr(response, "text", "")
        if isinstance(full_text, str) and full_text.strip():
            duration = getattr(response, "duration", 0.0) or 0.0
            parsed_segments.append({
                "start": 0.0,
                "end": round(float(duration), 2),
                "text": full_text.strip(),
            })

    return parsed_segments


def transcribe_video(
    video_path: Path,
    temp_dir: Path,
    api_key: Optional[str] = None,
    model: str = "whisper-large-v3",
) -> List[Dict[str, Any]]:
    """
    High-level orchestrator: extracts audio from a video and transcribes it with Groq Whisper.
    Automatically manages and cleans up intermediate temporary audio files.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Validate audio stream exists before extracting
    if not has_audio_stream(video_path):
        raise ValueError("The selected video does not contain an audio track to transcribe.")

    # Generate unique temp audio filename
    fingerprint = get_file_fingerprint(video_path.name, video_path.stat().st_size)
    temp_audio_path = temp_dir / f"extracted_{fingerprint}.mp3"

    try:
        extract_audio_for_transcription(video_path, temp_audio_path)
        segments = transcribe_audio_with_groq(temp_audio_path, api_key=api_key, model=model)
        return segments
    finally:
        safe_unlink(temp_audio_path)
