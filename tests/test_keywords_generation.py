import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

import streamlit as st
from groq import AuthenticationError, APIConnectionError, RateLimitError, APIStatusError
import httpx

from core.keywords import (
    extract_text_from_transcript,
    parse_keywords_response,
    generate_keywords_from_transcript,
    DEFAULT_KEYWORD_MODEL,
)
from app.ui.state import initialize_session_state, reset_and_clear_all
from app.ui.broll import render_broll_page


class MockSessionState(dict):
    """Mock Streamlit session state object."""
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value


def run_keyword_tests():
    print("==================================================")
    print("STARTING AI KEYWORD GENERATION TEST SUITE")
    print("==================================================")

    # -------------------------------------------------------------
    # TEST 1: Text extraction from transcript segments
    # -------------------------------------------------------------
    print("\n[TEST 1] Testing extract_text_from_transcript...")
    assert extract_text_from_transcript(None) == ""
    assert extract_text_from_transcript([]) == ""
    assert extract_text_from_transcript([{"invalid": "segment"}]) == ""
    assert extract_text_from_transcript([{"text": "   "}]) == ""

    segments = [
        {"start": 0.0, "end": 2.5, "text": "Welcome to our video."},
        {"start": 2.5, "end": 5.0, "text": "Today we discuss technology."},
        {"start": 5.0, "end": 7.0, "text": "Let's dive into the details."},
    ]
    extracted = extract_text_from_transcript(segments)
    expected = "Welcome to our video. Today we discuss technology. Let's dive into the details."
    assert extracted == expected, f"Expected '{expected}', got '{extracted}'"
    print("[PASSED] TEST 1: Transcript text extraction operates accurately.")

    # -------------------------------------------------------------
    # TEST 2: Response parsing (JSON, Markdown code blocks, Bullets, Deduplication)
    # -------------------------------------------------------------
    print("\n[TEST 2] Testing parse_keywords_response across diverse LLM outputs...")
    # Standard JSON array
    json_resp = '["business meeting", "person typing on laptop", "city skyline"]'
    parsed = parse_keywords_response(json_resp)
    assert parsed == ["business meeting", "person typing on laptop", "city skyline"], f"Got: {parsed}"

    # Markdown fenced JSON block
    fence_resp = """```json
[
  "laptop workspace",
  "coffee mug",
  "modern office"
]
```"""
    parsed = parse_keywords_response(fence_resp)
    assert parsed == ["laptop workspace", "coffee mug", "modern office"], f"Got: {parsed}"

    # Bulleted lines
    bullet_resp = """Here are the suggested keywords:
- laptop typing
- Modern Office
- 1. city skyline
* team meeting
"""
    parsed = parse_keywords_response(bullet_resp)
    assert "laptop typing" in parsed
    assert "Modern Office" in parsed
    assert "city skyline" in parsed
    assert "team meeting" in parsed

    # Case-insensitive deduplication
    dedup_resp = '["office", "Office", "OFFICE", "data chart", "DATA CHART"]'
    parsed = parse_keywords_response(dedup_resp)
    assert parsed == ["office", "data chart"], f"Got: {parsed}"

    # Empty / garbage
    assert parse_keywords_response("") == []
    assert parse_keywords_response("   ") == []
    print("[PASSED] TEST 2: Parsing handles JSON, Markdown fences, bullets, and deduplication.")

    # -------------------------------------------------------------
    # TEST 3: Validation on empty transcript
    # -------------------------------------------------------------
    print("\n[TEST 3] Testing validation on empty or silent transcript...")
    try:
        generate_keywords_from_transcript([])
        assert False, "Should have raised ValueError on empty transcript"
    except ValueError as e:
        assert "spoken text" in str(e).lower()
        print(f"  Caught expected error: '{e}'")

    try:
        generate_keywords_from_transcript([{"text": "   "}])
        assert False, "Should have raised ValueError on whitespace transcript"
    except ValueError as e:
        assert "spoken text" in str(e).lower()
        print(f"  Caught expected error: '{e}'")
    print("[PASSED] TEST 3: Empty/silent transcript rejected with clear message.")

    # -------------------------------------------------------------
    # TEST 4: Successful Groq chat completion call
    # -------------------------------------------------------------
    print("\n[TEST 4] Testing Groq chat completion integration with mock...")
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = '["artificial intelligence", "futuristic robot", "data server"]'
    mock_response.choices = [mock_choice]

    with patch("core.keywords.Groq") as mock_groq_cls:
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_response

        keywords = generate_keywords_from_transcript(
            segments,
            api_key="test_mock_key_xyz",
            model="llama-3.3-70b-versatile",
        )

        assert keywords == ["artificial intelligence", "futuristic robot", "data server"]
        mock_groq_cls.assert_called_once_with(api_key="test_mock_key_xyz")
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "llama-3.3-70b-versatile"
        assert "Transcript:" in call_kwargs["messages"][1]["content"]
    print("[PASSED] TEST 4: Mocked Groq chat completion verified.")

    # -------------------------------------------------------------
    # TEST 5: Error handling (Authentication, Rate Limit, Network, API status)
    # -------------------------------------------------------------
    print("\n[TEST 5] Testing error handling wrapping for Groq exceptions...")
    request_dummy = httpx.Request("POST", "https://api.groq.com")
    response_dummy = httpx.Response(401, request=request_dummy)

    # 1. Authentication Error
    with patch("core.keywords.Groq") as mock_groq_cls:
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = AuthenticationError(
            message="Invalid API Key",
            response=response_dummy,
            body=None,
        )
        try:
            generate_keywords_from_transcript(segments, api_key="bad_key")
            assert False, "Should have raised PermissionError"
        except PermissionError as pe:
            assert "GROQ_API_KEY" in str(pe)
            print(f"  Authentication error wrapped: '{pe}'")

    # 2. Rate Limit Error
    response_429 = httpx.Response(429, request=request_dummy)
    with patch("core.keywords.Groq") as mock_groq_cls:
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = RateLimitError(
            message="Rate limit exceeded",
            response=response_429,
            body=None,
        )
        try:
            generate_keywords_from_transcript(segments, api_key="mock_key")
            assert False, "Should have raised RuntimeError"
        except RuntimeError as re_err:
            assert "rate limit" in str(re_err).lower()
            print(f"  Rate limit error wrapped: '{re_err}'")

    # 3. Connection Error
    with patch("core.keywords.Groq") as mock_groq_cls:
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = APIConnectionError(
            request=request_dummy,
        )
        try:
            generate_keywords_from_transcript(segments, api_key="mock_key")
            assert False, "Should have raised ConnectionError"
        except ConnectionError as ce:
            assert "internet connection" in str(ce).lower()
            print(f"  Connection error wrapped: '{ce}'")
    print("[PASSED] TEST 5: API exceptions wrapped with actionable messages.")

    # -------------------------------------------------------------
    # TEST 6: Session state defaults and reset_and_clear_all
    # -------------------------------------------------------------
    print("\n[TEST 6] Testing session state initialization and reset...")
    mock_state = MockSessionState()
    with patch.object(st, "session_state", mock_state):
        initialize_session_state()
        assert "broll_keywords" in mock_state
        assert mock_state["broll_keywords"] is None
        assert "broll_keywords_video_id" in mock_state
        assert "broll_keywords_error" in mock_state

        # Set some values
        mock_state["broll_keywords"] = ["drone shot", "city"]
        mock_state["broll_keywords_video_id"] = "vid_123"
        mock_state["broll_keywords_error"] = "Some error"

        # Test reset
        temp_dir = ROOT_DIR / "temp"
        with patch.object(st, "rerun"), patch.object(st, "success"):
            reset_and_clear_all(temp_dir)
            assert mock_state["broll_keywords"] is None
            assert mock_state["broll_keywords_video_id"] is None
            assert mock_state["broll_keywords_error"] is None
    print("[PASSED] TEST 6: Session state keys initialize and reset properly.")

    # -------------------------------------------------------------
    # TEST 7: Keyword generation button with no transcript
    # -------------------------------------------------------------
    print("\n[TEST 7] Testing Generate Keywords click without transcript...")
    mock_state = MockSessionState()
    with patch.object(st, "session_state", mock_state):
        initialize_session_state()
        mock_state.broll_input_video = None
        mock_state.broll_transcript = None

        def mock_button(label, **kwargs):
            if kwargs.get("key") == "broll_generate_keywords_btn":
                return True
            return False

        with patch.object(st, "button", side_effect=mock_button), \
             patch.object(st, "rerun") as mock_rerun:
            try:
                render_broll_page(temp_dir)
            except Exception:
                pass

            assert mock_state.get("broll_keywords_error") == (
                "Please generate a video transcript before generating keywords."
            )
            assert mock_state.get("broll_keywords") is None
            assert mock_rerun.called
    print("[PASSED] TEST 7: Missing transcript triggers actionable error banner.")

    # -------------------------------------------------------------
    # TEST 8: Successful Generate Keywords click and session state persistence
    # -------------------------------------------------------------
    print("\n[TEST 8] Testing Generate Keywords click with valid transcript...")
    mock_state = MockSessionState()
    temp_dir = ROOT_DIR / "temp"
    dummy_video = temp_dir / "test_with_audio.mp4"
    if not dummy_video.exists():
        dummy_video.write_bytes(b"dummy")
    stat_info = dummy_video.stat()
    current_video_id = f"{dummy_video}_{stat_info.st_size}_{stat_info.st_mtime}"

    with patch.object(st, "session_state", mock_state):
        initialize_session_state()
        mock_state.broll_input_video = str(dummy_video)
        mock_state.broll_transcript = segments
        mock_state.broll_transcript_video_id = current_video_id

        def mock_button(label, **kwargs):
            if kwargs.get("key") == "broll_generate_keywords_btn":
                return True
            return False

        with patch.object(st, "button", side_effect=mock_button), \
             patch.object(st, "rerun") as mock_rerun, \
             patch("app.ui.broll.generate_keywords_from_transcript") as mock_gen:
            mock_gen.return_value = ["workspace typing", "coffee break", "analytics screen"]
            try:
                render_broll_page(temp_dir)
            except Exception:
                pass

            assert mock_gen.called
            assert mock_state.get("broll_keywords") == [
                "workspace typing",
                "coffee break",
                "analytics screen",
            ]
            assert mock_state.get("broll_keywords_error") is None
            assert mock_rerun.called
    print("[PASSED] TEST 8: Keywords generated, saved to session state, and error cleared.")

    # -------------------------------------------------------------
    # TEST 9: Invalidation when video changes
    # -------------------------------------------------------------
    print("\n[TEST 9] Testing keyword invalidation when input video changes...")
    mock_state = MockSessionState()
    with patch.object(st, "session_state", mock_state):
        initialize_session_state()
        mock_state.broll_transcript = segments
        mock_state.broll_transcript_video_id = "video_A"
        mock_state.broll_keywords = ["keyword A", "keyword B"]
        mock_state.broll_keywords_video_id = "video_A"

        # Now simulate video switch: current video id becomes "video_B"
        dummy_video = temp_dir / "test_with_audio.mp4"
        if not dummy_video.exists():
            dummy_video.write_bytes(b"dummy")
        mock_state.broll_input_video = str(dummy_video)

        with patch.object(st, "button", return_value=False):
            try:
                render_broll_page(temp_dir)
            except Exception:
                pass

            # Because cached video ID "video_A" != current video ID, keywords must be None
            assert mock_state.get("broll_keywords") is None, "Keywords must be invalidated on video change"
            assert mock_state.get("broll_keywords_video_id") is None
    print("[PASSED] TEST 9: Invalidation on video switch operates correctly.")

    # -------------------------------------------------------------
    # TEST 10: Markup and Card preservation checks
    # -------------------------------------------------------------
    print("\n[TEST 10] Verifying Card 1 and Card 3, 4 preservation and UI elements...")
    broll_code = (ROOT_DIR / "app" / "ui" / "broll.py").read_text(encoding="utf-8")
    
    # Card 1 must be 100% intact
    assert 'key="broll_transcription_card"' in broll_code
    assert 'key="broll_create_transcript_btn"' in broll_code
    assert "Video Transcription" in broll_code

    # Card 2 has key broll_keywords_card and button broll_generate_keywords_btn
    assert 'key="broll_keywords_card"' in broll_code
    assert 'key="broll_generate_keywords_btn"' in broll_code
    assert "AI Keyword Generation" in broll_code
    assert "keyword-pill" in broll_code

    # Card 3 and 4 remain intact
    assert "Stock Footage Search" in broll_code
    assert "Search Footage" in broll_code
    assert "B-roll Placement & Timeline" in broll_code
    assert "Planned: FFmpeg Overlay" in broll_code
    print("[PASSED] TEST 10: Strict boundaries and UI hierarchy verified.")

    print("\n==================================================")
    print("ALL AI KEYWORD GENERATION TESTS PASSED (10/10)!")
    print("==================================================")


if __name__ == "__main__":
    run_keyword_tests()
