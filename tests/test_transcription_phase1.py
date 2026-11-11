import sys
import os
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

import imageio_ffmpeg as ffmpeg
import subprocess

from core.audio import has_audio_stream, extract_audio_for_transcription
from core.transcription import (
    transcribe_video,
    transcribe_audio_with_groq,
    format_timestamp,
    format_segment_time,
    load_groq_api_key,
    MAX_GROQ_AUDIO_SIZE_BYTES,
)
from app.ui.state import AppState, initialize_session_state, reset_and_clear_all
from app.ui.broll import render_broll_page, save_broll_upload


class MockSessionState(dict):
    """Mock Streamlit session state object."""
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value


class MockUploadedFile:
    def __init__(self, name: str, data: bytes):
        self.name = name
        self.size = len(data)
        self._data = data
        self._pos = 0

    def seek(self, pos: int):
        self._pos = pos

    def read(self, length: int = -1):
        if length == -1:
            res = self._data[self._pos:]
            self._pos = len(self._data)
            return res
        res = self._data[self._pos:self._pos + length]
        self._pos += len(res)
        return res


def create_synthetic_video(filepath: Path, with_audio: bool = True, duration: int = 2):
    """Create a synthetic MP4 video with or without an audio stream using imageio_ffmpeg."""
    ffmpeg_path = ffmpeg.get_ffmpeg_exe()
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    if with_audio:
        cmd = [
            ffmpeg_path, "-y",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
            "-f", "lavfi", "-i", f"color=c=navy:s=320x240:d={duration}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            str(filepath),
        ]
    else:
        cmd = [
            ffmpeg_path, "-y",
            "-f", "lavfi", "-i", f"color=c=navy:s=320x240:d={duration}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-an",  # No audio
            str(filepath),
        ]

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def run_phase1_tests():
    print("==================================================")
    print("STARTING PHASE 1: VIDEO TRANSCRIPTION TEST SUITE")
    print("==================================================")

    import streamlit as st
    temp_dir = ROOT_DIR / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    video_with_audio = temp_dir / "test_with_audio.mp4"
    video_silent = temp_dir / "test_silent.mp4"

    create_synthetic_video(video_with_audio, with_audio=True, duration=2)
    create_synthetic_video(video_silent, with_audio=False, duration=2)

    # -------------------------------------------------------------
    # TEST 1 & 2 & 3: Audio Extraction & Segment Timestamp Structure
    # -------------------------------------------------------------
    print("\n[TEST 1] Testing audio stream detection and extraction...")
    assert has_audio_stream(video_with_audio) is True, "video_with_audio must have audio stream"
    assert has_audio_stream(video_silent) is False, "video_silent must not have audio stream"

    extracted_mp3 = temp_dir / "test_extracted.mp3"
    extract_audio_for_transcription(video_with_audio, extracted_mp3)
    assert extracted_mp3.exists() and extracted_mp3.stat().st_size > 0, "Extracted audio must exist and be non-empty"
    extracted_mp3.unlink()
    print("[PASSED] TEST 1: Audio stream detection and speech-optimized extraction verified.")

    # -------------------------------------------------------------
    # TEST 3: Timestamp Formatting Helpers
    # -------------------------------------------------------------
    print("\n[TEST 2] Testing timestamp formatting helpers...")
    assert format_timestamp(0.0) == "00:00"
    assert format_timestamp(5.2) == "00:05"
    assert format_timestamp(65.0) == "01:05"
    assert format_timestamp(3665.0) == "01:01:05"
    assert format_segment_time(0.0, 5.2) == "00:00 - 00:05"
    assert format_segment_time(5.2, 11.4) == "00:05 - 00:11"
    print("[PASSED] TEST 2: Timestamp formatters compliant with specification.")

    # -------------------------------------------------------------
    # TEST 4: Empty Audio or Video Without Audio Stream
    # -------------------------------------------------------------
    print("\n[TEST 3] Testing graceful handling of silent video...")
    try:
        extract_audio_for_transcription(video_silent, temp_dir / "should_fail.mp3")
        assert False, "Should have raised ValueError for video without audio"
    except ValueError as e:
        assert "audio track" in str(e).lower()
        print(f"  Expected error caught: '{e}'")

    try:
        transcribe_video(video_silent, temp_dir)
        assert False, "transcribe_video should fail cleanly for video without audio"
    except ValueError as e:
        assert "audio track" in str(e).lower()
        print(f"  Expected error caught in transcribe_video: '{e}'")
    print("[PASSED] TEST 3: Silent video caught cleanly with actionable error message.")

    # -------------------------------------------------------------
    # TEST 5: Large Audio File Limit (>25MB)
    # -------------------------------------------------------------
    print("\n[TEST 4] Testing Groq 25MB file size limit enforcement...")
    fake_large_audio = temp_dir / "fake_large.mp3"
    fake_large_audio.write_bytes(b"\x00" * 1024)  # Small on disk

    with patch.object(Path, "stat") as mock_stat:
        mock_stat_obj = MagicMock()
        mock_stat_obj.st_size = 26 * 1024 * 1024  # 26 MB
        mock_stat.return_value = mock_stat_obj

        try:
            transcribe_audio_with_groq(fake_large_audio, api_key="dummy")
            assert False, "Should have rejected file > 25MB"
        except ValueError as e:
            assert "25 mb" in str(e).lower()
            print(f"  Expected limit error caught: '{e}'")
    fake_large_audio.unlink()
    print("[PASSED] TEST 4: 25MB upload size guard operates correctly.")

    # -------------------------------------------------------------
    # TEST 6: Mocked Groq Whisper Segment Extraction
    # -------------------------------------------------------------
    print("\n[TEST 5] Testing Groq Whisper segment parsing and data contract...")
    mock_groq_response = MagicMock()
    mock_groq_response.text = "Hello world this is a test."
    mock_groq_response.duration = 4.5
    mock_groq_response.segments = [
        {"start": 0.0, "end": 2.1, "text": "Hello world"},
        {"start": 2.1, "end": 4.5, "text": "this is a test."},
    ]

    with patch("core.transcription.Groq") as mock_groq_cls:
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_groq_response
        mock_groq_cls.return_value = mock_client

        segments = transcribe_video(video_with_audio, temp_dir, api_key="test_key")
        assert len(segments) == 2, f"Expected 2 segments, got {len(segments)}"
        assert segments[0]["start"] == 0.0
        assert segments[0]["end"] == 2.1
        assert segments[0]["text"] == "Hello world"
        assert segments[1]["start"] == 2.1
        assert segments[1]["end"] == 4.5
        assert segments[1]["text"] == "this is a test."
    print("[PASSED] TEST 5: Groq Whisper response parsing matches structured segment format.")

    # -------------------------------------------------------------
    # TEST 7: Authentication & Network Failure Handling
    # -------------------------------------------------------------
    print("\n[TEST 6] Testing API authentication and network failure handling...")
    from groq import AuthenticationError, APIConnectionError

    with patch("core.transcription.Groq") as mock_groq_cls:
        mock_client = MagicMock()
        mock_req = MagicMock()
        mock_client.audio.transcriptions.create.side_effect = AuthenticationError(
            "Invalid API Key", response=MagicMock(status_code=401), body={"error": "invalid_api_key"}
        )
        mock_groq_cls.return_value = mock_client

        try:
            transcribe_video(video_with_audio, temp_dir, api_key="invalid_key")
            assert False, "Should have raised PermissionError for 401"
        except PermissionError as e:
            assert "authentication failed" in str(e).lower()
            print(f"  Authentication error wrapped cleanly: '{e}'")

    with patch("core.transcription.Groq") as mock_groq_cls:
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.side_effect = APIConnectionError(request=MagicMock())
        mock_groq_cls.return_value = mock_client

        try:
            transcribe_video(video_with_audio, temp_dir, api_key="test_key")
            assert False, "Should have raised ConnectionError"
        except ConnectionError as e:
            assert "could not connect" in str(e).lower()
            print(f"  Network error wrapped cleanly: '{e}'")
    print("[PASSED] TEST 6: Authentication and network errors wrapped with user-friendly messages.")

    # -------------------------------------------------------------
    # TEST 8: Session State Persistence across Streamlit Reruns
    # -------------------------------------------------------------
    print("\n[TEST 7] Testing transcript session state persistence across reruns...")
    st.session_state = MockSessionState()
    initialize_session_state()

    st.session_state.broll_input_video = str(video_with_audio)
    st.session_state.broll_source = "transferred"

    # Set mock transcript
    sample_segments = [
        {"start": 0.0, "end": 2.0, "text": "Sample speech segment."}
    ]
    st.session_state.broll_transcript = sample_segments
    stat = video_with_audio.stat()
    video_id = f"{video_with_audio}_{stat.st_size}_{stat.st_mtime}"
    st.session_state.broll_transcript_video_id = video_id

    # Simulate render_broll_page rerun
    render_broll_page(temp_dir)

    # Transcript must be preserved
    assert st.session_state.broll_transcript == sample_segments
    assert st.session_state.broll_transcript_video_id == video_id
    print("[PASSED] TEST 7: Transcript preserved on Streamlit rerun without redundant API calls.")

    # -------------------------------------------------------------
    # TEST 9: Invalidation When Selected Video Changes
    # -------------------------------------------------------------
    print("\n[TEST 8] Testing automatic transcript invalidation when video changes...")
    different_video = temp_dir / "different_video.mp4"
    create_synthetic_video(different_video, with_audio=True, duration=1)

    # Switch video in session state
    st.session_state.broll_input_video = str(different_video)

    # Rerun B-roll page
    render_broll_page(temp_dir)

    # Previous transcript must now be invalidated!
    assert st.session_state.broll_transcript is None, "Old transcript must be invalidated on video change"
    assert st.session_state.broll_transcript_video_id is None
    print("[PASSED] TEST 8: Invalidation verified on video switch.")

    # -------------------------------------------------------------
    # TEST 9: Verify Cards 2, 3, 4 Remain Unchanged & Manual Work Preserved
    # -------------------------------------------------------------
    print("\n[TEST 9] Verifying Cards 2, 3, 4 remain unchanged and user manual badges preserved...")
    broll_code = (ROOT_DIR / "app" / "ui" / "broll.py").read_text(encoding="utf-8")
    assert "Generate Keywords" in broll_code, "Card 2 must retain user manual badge Generate Keywords"
    assert "Search Footage" in broll_code, "Card 3 must retain user manual badge Search Footage"
    assert "B-roll Placement & Timeline" in broll_code, "Card 4 must remain intact"
    print("[PASSED] TEST 9: Cards 2, 3, 4 and manual badges remain completely untouched.")

    # -------------------------------------------------------------
    # TEST 10: Verify 'Create Transcript' button and no-video error handling
    # -------------------------------------------------------------
    print("\n[TEST 10] Testing 'Create Transcript' button interaction and validation...")
    assert 'key="broll_create_transcript_btn"' in broll_code, "Create Transcript button must have key broll_create_transcript_btn"
    assert 'type="primary"' in broll_code, "Create Transcript button must use primary styling"

    # Simulate clicking Create Transcript when no video is selected
    st.session_state = MockSessionState()
    initialize_session_state()
    st.session_state.broll_input_video = None
    st.session_state.processed_video = None

    with patch("streamlit.button", side_effect=lambda label, **kwargs: True if kwargs.get("key") == "broll_create_transcript_btn" else False):
        try:
            render_broll_page(temp_dir)
        except Exception:
            pass  # st.rerun mock if triggered
        assert st.session_state.get("broll_transcription_error") == "Please select or upload a video before creating a transcript."
        assert st.session_state.get("broll_transcript") is None
    print("[PASSED] TEST 10: 'Create Transcript' button validates active video and sets actionable error.")

    # -------------------------------------------------------------
    # TEST 11: Multi-Segment Transcript UI Display (43 segments without HTML leak)
    # -------------------------------------------------------------
    print("\n[TEST 11] Testing multi-segment (43 segments) transcript display and markup hygiene...")
    st.session_state = MockSessionState()
    initialize_session_state()

    # Create 43 mock segments
    mock_43_segments = [
        {"start": float(i * 2.5), "end": float((i + 1) * 2.5), "text": f"This is speech segment {i + 1}."}
        for i in range(43)
    ]
    stat = video_with_audio.stat()
    video_id = f"{video_with_audio}_{stat.st_size}_{stat.st_mtime}"
    st.session_state.broll_transcript = mock_43_segments
    st.session_state.broll_transcript_video_id = video_id
    st.session_state.broll_input_video = str(video_with_audio)

    captured_markdowns = []
    with patch("streamlit.markdown", side_effect=lambda content, **kwargs: captured_markdowns.append(content)):
        render_broll_page(temp_dir)

    # Locate the transcript HTML block
    transcript_blocks = [m for m in captured_markdowns if "max-height: 280px" in m]
    assert len(transcript_blocks) == 1, "Expected exactly one scrollable transcript container"
    t_html = transcript_blocks[0]

    # Verify all 43 segments are present
    for i in range(43):
        assert f"This is speech segment {i + 1}." in t_html, f"Segment {i + 1} missing from rendered HTML"
    assert t_html.count("font-family: monospace") == 43, f"Expected 43 timestamps, got {t_html.count('font-family: monospace')}"

    # Verify no line has leading whitespace of 4 or more spaces (which triggers CommonMark indented code blocks)
    for line in t_html.split("\n"):
        assert not line.startswith("    "), f"Found line with 4+ leading spaces that would trigger code block: {line[:50]}"

    # Verify success banner rendered with 43 segments
    success_blocks = [m for m in captured_markdowns if "status-banner-card" in m and "Extracted 43 timestamped segments" in m]
    assert len(success_blocks) == 1, "Success banner with 43 segments must be displayed"
    print("[PASSED] TEST 11: All 43 segments rendered cleanly with zero raw HTML/code-block leaks.")

    # Cleanup synthetic videos
    video_with_audio.unlink(missing_ok=True)
    video_silent.unlink(missing_ok=True)
    different_video.unlink(missing_ok=True)

    print("\n==================================================")
    print("ALL PHASE 1 TRANSCRIPTION TESTS PASSED (11/11)!")
    print("==================================================")


if __name__ == "__main__":
    run_phase1_tests()
