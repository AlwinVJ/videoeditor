import io
import json
import os
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

import streamlit as st

from core.stock import (
    format_duration,
    search_pixabay_videos,
    search_stock_footage,
    match_clip_to_transcript,
    get_segment_color,
    calculate_timeline_percentages,
    PIXABAY_VIDEO_API_URL,
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


def make_mock_http_response(payload_dict: dict, status: int = 200):
    """Create a mock HTTP response object for urllib.request.urlopen."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(payload_dict).encode("utf-8")
    mock_resp.status = status
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None
    return mock_resp


SAMPLE_PIXABAY_HIT = {
    "id": 1001,
    "tags": "business, meeting, team, office",
    "duration": 25,
    "pageURL": "https://pixabay.com/videos/1001/",
    "user": "creator_jane",
    "videos": {
        "large": {
            "url": "https://cdn.pixabay.com/video/1001_large.mp4",
            "width": 3840,
            "height": 2160,
            "size": 50000000,
            "thumbnail": "https://cdn.pixabay.com/video/1001_large.jpg",
        },
        "medium": {
            "url": "https://cdn.pixabay.com/video/1001_medium.mp4",
            "width": 1920,
            "height": 1080,
            "size": 20000000,
            "thumbnail": "https://cdn.pixabay.com/video/1001_medium.jpg",
        },
        "tiny": {
            "url": "https://cdn.pixabay.com/video/1001_tiny.mp4",
            "width": 640,
            "height": 360,
            "size": 5000000,
            "thumbnail": "https://cdn.pixabay.com/video/1001_tiny.jpg",
        },
    },
}


def run_stock_search_tests():
    print("==================================================")
    print("STARTING STOCK FOOTAGE SEARCH TEST SUITE")
    print("==================================================")

    # -------------------------------------------------------------
    # TEST 1: Duration formatting helper
    # -------------------------------------------------------------
    print("\n[TEST 1] Testing format_duration...")
    assert format_duration(0) == "00:00"
    assert format_duration(-5) == "00:00"
    assert format_duration(15) == "00:15"
    assert format_duration(65) == "01:05"
    assert format_duration(3665) == "01:01:05"
    print("[PASSED] TEST 1: Duration formatting accurate.")

    # -------------------------------------------------------------
    # TEST 2: Query sanitization & empty input handling
    # -------------------------------------------------------------
    print("\n[TEST 2] Testing query sanitization and empty query handling...")
    assert search_pixabay_videos("", api_key="dummy_key") == []
    assert search_pixabay_videos("   ", api_key="dummy_key") == []
    print("[PASSED] TEST 2: Empty/whitespace query handled gracefully without network calls.")

    # -------------------------------------------------------------
    # TEST 3: Missing API Key validation
    # -------------------------------------------------------------
    print("\n[TEST 3] Testing missing API key rejection...")
    with patch("core.stock.get_pixabay_api_key", return_value=None):
        try:
            search_pixabay_videos("office", api_key=None)
            assert False, "Should have raised ValueError on missing API key"
        except ValueError as ve:
            assert "PIXABAY_API_KEY" in str(ve)
            print(f"  Caught expected error: '{ve}'")
    print("[PASSED] TEST 3: Missing API key caught with actionable instruction.")

    # -------------------------------------------------------------
    # TEST 4: Successful Pixabay video search and data mapping
    # -------------------------------------------------------------
    print("\n[TEST 4] Testing Pixabay API parsing and standardized clip data...")
    mock_payload = {"total": 1, "totalHits": 1, "hits": [SAMPLE_PIXABAY_HIT]}
    with patch("urllib.request.urlopen", return_value=make_mock_http_response(mock_payload)):
        clips = search_pixabay_videos("office meeting", api_key="valid_key", per_page=5)
        assert len(clips) == 1
        clip = clips[0]
        assert clip["id"] == 1001
        assert clip["tags"] == "business, meeting, team, office"
        assert clip["duration"] == 25
        assert clip["duration_formatted"] == "00:25"
        assert clip["width"] == 3840
        assert clip["height"] == 2160
        assert clip["resolution"] == "3840×2160"
        assert clip["thumbnail_url"] == "https://cdn.pixabay.com/video/1001_medium.jpg"
        assert clip["preview_url"] == "https://cdn.pixabay.com/video/1001_tiny.mp4"
        assert clip["download_url"] == "https://cdn.pixabay.com/video/1001_large.mp4"
        assert clip["keyword"] == "office meeting"
    print("[PASSED] TEST 4: Clip response parsed into complete standardized dictionary.")

    # -------------------------------------------------------------
    # TEST 5: Error handling (Authentication, Rate Limit, Network failure)
    # -------------------------------------------------------------
    print("\n[TEST 5] Testing error mapping for Pixabay API failures...")

    # 1. Invalid API key (HTTP 400 with "invalid or missing API key")
    err_body = b"[ERROR 400] Invalid or missing API key"
    http_err_400 = urllib.error.HTTPError(
        url=PIXABAY_VIDEO_API_URL,
        code=400,
        msg="Bad Request",
        hdrs={},
        fp=io.BytesIO(err_body),
    )
    with patch("urllib.request.urlopen", side_effect=http_err_400):
        try:
            search_pixabay_videos("test", api_key="bad_key")
            assert False, "Should have raised PermissionError"
        except PermissionError as pe:
            assert "PIXABAY_API_KEY" in str(pe)
            print(f"  Authentication error wrapped: '{pe}'")

    # 2. Rate limit (HTTP 429)
    http_err_429 = urllib.error.HTTPError(
        url=PIXABAY_VIDEO_API_URL,
        code=429,
        msg="Too Many Requests",
        hdrs={},
        fp=io.BytesIO(b"Rate limit exceeded"),
    )
    with patch("urllib.request.urlopen", side_effect=http_err_429):
        try:
            search_pixabay_videos("test", api_key="key")
            assert False, "Should have raised RuntimeError"
        except RuntimeError as re_err:
            assert "rate limit" in str(re_err).lower()
            print(f"  Rate limit error wrapped: '{re_err}'")

    # 3. Network connection error (URLError)
    url_err = urllib.error.URLError(reason="getaddrinfo failed")
    with patch("urllib.request.urlopen", side_effect=url_err):
        try:
            search_pixabay_videos("test", api_key="key")
            assert False, "Should have raised ConnectionError"
        except ConnectionError as ce:
            assert "internet connection" in str(ce).lower()
            print(f"  Connection error wrapped: '{ce}'")
    print("[PASSED] TEST 5: API errors wrapped with user-friendly messages.")

    # -------------------------------------------------------------
    # TEST 6: Multi-keyword search and deduplication
    # -------------------------------------------------------------
    print("\n[TEST 6] Testing multi-keyword aggregation and clip deduplication...")
    hit_1 = {**SAMPLE_PIXABAY_HIT, "id": 1001}
    hit_2 = {**SAMPLE_PIXABAY_HIT, "id": 1002}
    # hit_1 appears in both searches to verify deduplication
    resp_kw1 = {"hits": [hit_1, hit_2]}
    resp_kw2 = {"hits": [hit_1]}

    call_count = 0
    def mock_urlopen(req, timeout=12):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return make_mock_http_response(resp_kw1)
        return make_mock_http_response(resp_kw2)

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        results = search_stock_footage(["laptop typing", "modern office"], api_key="valid_key")
        # Should contain hit 1001 and 1002, with 1001 not duplicated
        clip_ids = [c["id"] for c in results]
        assert clip_ids == [1001, 1002], f"Expected [1001, 1002], got {clip_ids}"
    print("[PASSED] TEST 6: Multi-keyword results aggregated and deduplicated by clip ID.")

    # -------------------------------------------------------------
    # TEST 7: Session state initialization and reset
    # -------------------------------------------------------------
    print("\n[TEST 7] Testing session state defaults and reset...")
    mock_state = MockSessionState()
    with patch.object(st, "session_state", mock_state):
        initialize_session_state()
        assert "broll_stock_results" in mock_state
        assert mock_state["broll_stock_results"] is None
        assert "broll_stock_video_id" in mock_state
        assert "broll_stock_error" in mock_state
        assert "broll_selected_clip" in mock_state

        mock_state["broll_stock_results"] = [SAMPLE_PIXABAY_HIT]
        mock_state["broll_stock_video_id"] = "vid_1"
        mock_state["broll_stock_error"] = "Error"
        mock_state["broll_selected_clip"] = SAMPLE_PIXABAY_HIT

        temp_dir = ROOT_DIR / "temp"
        with patch.object(st, "rerun"), patch.object(st, "success"):
            reset_and_clear_all(temp_dir)
            assert mock_state["broll_stock_results"] is None
            assert mock_state["broll_stock_video_id"] is None
            assert mock_state["broll_stock_error"] is None
            assert mock_state["broll_selected_clip"] is None
    print("[PASSED] TEST 7: Stock session state keys initialize and wipe cleanly.")

    # -------------------------------------------------------------
    # TEST 8: Card 3 Search Footage click without keywords
    # -------------------------------------------------------------
    print("\n[TEST 8] Testing Search Footage click with no keywords...")
    mock_state = MockSessionState()
    with patch.object(st, "session_state", mock_state):
        initialize_session_state()
        mock_state.broll_keywords = None

        def mock_button(label, **kwargs):
            if kwargs.get("key") == "broll_search_footage_btn":
                return True
            return False

        with patch.object(st, "button", side_effect=mock_button), \
             patch.object(st, "rerun") as mock_rerun:
            try:
                render_broll_page(temp_dir)
            except Exception:
                pass

            assert mock_state.get("broll_stock_error") == (
                "Please generate AI keywords in Step 2 before searching for stock footage."
            )
            assert mock_state.get("broll_stock_results") is None
            assert mock_rerun.called
    print("[PASSED] TEST 8: Missing keywords sets actionable error banner.")

    # -------------------------------------------------------------
    # TEST 9: Card 3 Search Footage click with keywords and selection
    # -------------------------------------------------------------
    print("\n[TEST 9] Testing Search Footage click with keywords and clip selection...")
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
        mock_state.broll_transcript = [{"start": 0.0, "end": 2.0, "text": "demo"}]
        mock_state.broll_transcript_video_id = current_video_id
        mock_state.broll_keywords = ["technology", "coding"]
        mock_state.broll_keywords_video_id = current_video_id

        def mock_button(label, **kwargs):
            if kwargs.get("key") == "broll_search_footage_btn":
                return True
            return False

        sample_clip = {
            "id": 999,
            "tags": "tech, screen",
            "duration": 15,
            "duration_formatted": "00:15",
            "width": 1920,
            "height": 1080,
            "resolution": "1920×1080",
            "thumbnail_url": "https://example.com/thumb.jpg",
            "preview_url": "https://example.com/preview.mp4",
            "download_url": "https://example.com/full.mp4",
            "keyword": "technology",
        }

        with patch.object(st, "button", side_effect=mock_button), \
             patch.object(st, "rerun") as mock_rerun, \
             patch("app.ui.broll.search_stock_footage") as mock_search:
            mock_search.return_value = [sample_clip]
            try:
                render_broll_page(temp_dir)
            except Exception:
                pass

            assert mock_search.called
            assert mock_state.get("broll_stock_results") == [sample_clip]
            assert mock_state.get("broll_stock_error") is None
            assert mock_rerun.called

        # Test clip selection on subsequent interaction
        def mock_select_button(label, **kwargs):
            if "broll_select_clip_999" in kwargs.get("key", ""):
                return True
            return False

        with patch.object(st, "button", side_effect=mock_select_button), \
             patch.object(st, "rerun") as mock_rerun, \
             patch("app.ui.broll.search_stock_footage") as mock_search_2:
            try:
                render_broll_page(temp_dir)
            except Exception:
                pass

            # Search should NOT be called again on select rerun!
            assert not mock_search_2.called, "Selecting a clip must not re-trigger API search"
            assert mock_state.get("broll_selected_clip") == sample_clip
            assert mock_rerun.called
    print("[PASSED] TEST 9: Search executed, results stored, and clip selection works without re-searching.")

    # -------------------------------------------------------------
    # TEST 10: Automatic invalidation when video changes
    # -------------------------------------------------------------
    print("\n[TEST 10] Testing invalidation when video changes...")
    mock_state = MockSessionState()
    with patch.object(st, "session_state", mock_state):
        initialize_session_state()
        mock_state.broll_stock_results = [sample_clip]
        mock_state.broll_stock_video_id = "old_video_id_1"
        mock_state.broll_selected_clip = sample_clip
        mock_state.broll_input_video = str(dummy_video)  # Has new video ID

        with patch.object(st, "button", return_value=False):
            try:
                render_broll_page(temp_dir)
            except Exception:
                pass

            assert mock_state.get("broll_stock_results") is None, "Results must be invalidated when video changes"
            assert mock_state.get("broll_selected_clip") is None, "Selected clip must be invalidated when video changes"
    print("[PASSED] TEST 10: Automatic invalidation verified.")

    # -------------------------------------------------------------
    # TEST 11: Preservation of Cards 1, 2, 4
    # -------------------------------------------------------------
    print("\n[TEST 11] Verifying preservation of Cards 1, 2, 4...")
    broll_code = (ROOT_DIR / "app" / "ui" / "broll.py").read_text(encoding="utf-8")
    assert 'key="broll_transcription_card"' in broll_code
    assert 'key="broll_create_transcript_btn"' in broll_code
    assert 'key="broll_keywords_card"' in broll_code
    assert 'key="broll_generate_keywords_btn"' in broll_code
    assert 'key="broll_stock_search_card"' in broll_code
    assert 'key="broll_search_footage_btn"' in broll_code
    assert "B-roll Placement & Timeline" in broll_code
    assert "Planned: FFmpeg Overlay" in broll_code
    print("[PASSED] TEST 11: Cards 1, 2, and 4 preserved with strict boundaries.")

    # -------------------------------------------------------------
    # TEST 12: Clip to transcript segment matching & fallback
    # -------------------------------------------------------------
    print("\n[TEST 12] Testing match_clip_to_transcript...")
    transcript_sample = [
        {"start": 0.0, "end": 4.5, "text": "Welcome to our video on modern workspace productivity."},
        {"start": 4.5, "end": 9.2, "text": "Here our team is collaborating in an open office."},
        {"start": 9.2, "end": 15.0, "text": "We review real-time charts on an interactive dashboard."},
    ]

    # Exact keyword match
    match1 = match_clip_to_transcript("open office", transcript_sample)
    assert match1 is not None
    assert match1["segment_index"] == 1
    assert match1["start"] == 4.5
    assert match1["end"] == 9.2
    assert "collaborating in an open office" in match1["text"]

    # Token overlap match
    match2 = match_clip_to_transcript("workspace productivity", transcript_sample)
    assert match2 is not None
    assert match2["segment_index"] == 0
    assert match2["start"] == 0.0

    # No match -> returns None (does not invent arbitrary placement)
    match_none = match_clip_to_transcript("flying airplane sunset", transcript_sample)
    assert match_none is None, "Non-matching keyword must return None"

    # Missing transcript -> returns None
    assert match_clip_to_transcript("open office", None) is None
    assert match_clip_to_transcript("open office", []) is None
    print("[PASSED] TEST 12: Clip to transcript matching operates accurately with fallbacks.")

    # -------------------------------------------------------------
    # TEST 13: Timeline percentage calculations and color palette
    # -------------------------------------------------------------
    print("\n[TEST 13] Testing calculate_timeline_percentages and color palette...")
    l_pct, w_pct = calculate_timeline_percentages(10.0, 20.0, 100.0)
    assert l_pct == 10.0
    assert w_pct == 10.0

    # Minimum width guard for very short segments
    l_pct, w_pct = calculate_timeline_percentages(0.0, 0.5, 100.0)
    assert l_pct == 0.0
    assert w_pct >= 2.5, "Short segments must have a minimum perceptible width"

    # Zero total duration guard
    assert calculate_timeline_percentages(0.0, 5.0, 0.0) == (0.0, 0.0)

    # Color distinction for different segments
    c0 = get_segment_color(0)
    c1 = get_segment_color(1)
    assert c0["primary"] != c1["primary"], "Different segment indices must have distinguishable colors"
    assert "light" in c0 and "bg" in c0 and "border" in c0
    print("[PASSED] TEST 13: Timeline percentages and segment colors verified.")

    # -------------------------------------------------------------
    # TEST 14: Card 3 Timeline UI rendering and fallback states
    # -------------------------------------------------------------
    print("\n[TEST 14] Testing timeline HTML elements in Card 3 rendering...")
    mock_state = MockSessionState()
    stat_info = dummy_video.stat()
    vid_id = f"{dummy_video}_{stat_info.st_size}_{stat_info.st_mtime}"

    with patch.object(st, "session_state", mock_state):
        initialize_session_state()
        mock_state.broll_input_video = str(dummy_video)
        mock_state.broll_transcript = transcript_sample
        mock_state.broll_transcript_video_id = vid_id
        mock_state.broll_keywords = ["open office", "outer galaxy"]
        mock_state.broll_keywords_video_id = vid_id

        # Clip A: matches transcript segment 1 ("open office")
        clip_matched = {
            "id": 101,
            "tags": "office, work",
            "duration": 10,
            "duration_formatted": "00:10",
            "resolution": "1920×1080",
            "thumbnail_url": "https://example.com/thumb1.jpg",
            "preview_url": "https://example.com/prev1.mp4",
            "keyword": "open office",
        }
        # Clip B: unmapped keyword
        clip_unmapped = {
            "id": 102,
            "tags": "space, stars",
            "duration": 8,
            "duration_formatted": "00:08",
            "resolution": "1920×1080",
            "thumbnail_url": "https://example.com/thumb2.jpg",
            "preview_url": "https://example.com/prev2.mp4",
            "keyword": "outer galaxy deep space",
        }
        mock_state.broll_stock_results = [clip_matched, clip_unmapped]
        mock_state.broll_stock_video_id = vid_id

        rendered_markdowns = []
        def mock_markdown(text, **kwargs):
            rendered_markdowns.append(str(text))

        with patch.object(st, "markdown", side_effect=mock_markdown), \
             patch.object(st, "button", return_value=False), \
             patch.object(st, "expander"):
            try:
                render_broll_page(temp_dir)
            except Exception:
                pass

        full_output = "\n".join(rendered_markdowns)
        # Master overview timeline must be present
        assert "Original Video Timeline & B-roll Placements" in full_output
        # Matched placement must be present with range
        assert "Suggested Placement" in full_output
        assert "00:04 - 00:09" in full_output
        assert "collaborating in an open office" in full_output
        # Fallback state must be present for unmapped clip
        assert "Timeline placement: No direct transcript timestamp match" in full_output
    print("[PASSED] TEST 14: Master timeline and per-clip placement render with fallbacks.")

    print("\n==================================================")
    print("ALL STOCK FOOTAGE SEARCH TESTS PASSED (14/14)!")
    print("==================================================")


if __name__ == "__main__":
    run_stock_search_tests()
