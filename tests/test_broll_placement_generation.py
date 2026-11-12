import copy
import html
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

import cv2
import streamlit as st

from app.ui.state import AppState, initialize_session_state, reset_and_clear_all
from app.ui.broll import render_broll_page
from app.ui.export import render_export_page
from core.pipeline import compose_broll_video, download_stock_clip
from core.video_io import get_video_metadata


class MockSessionState(dict):
    """Mock Streamlit session state object for deterministic unit testing."""
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value


SAMPLE_CLIP = {
    "id": 8881,
    "tags": "technology, coding, computer",
    "duration": 10,
    "duration_formatted": "00:10",
    "width": 1280,
    "height": 720,
    "resolution": "1280×720",
    "thumbnail_url": "https://cdn.pixabay.com/test_thumb.jpg",
    "preview_url": "https://cdn.pixabay.com/test_preview.mp4",
    "download_url": "https://cdn.pixabay.com/test_download.mp4",
    "page_url": "https://pixabay.com/videos/8881/",
    "user": "videomaker",
    "keyword": "modern technology",
}

SAMPLE_TRANSCRIPT = [
    {
        "segment_index": 0,
        "start": 0.0,
        "end": 0.8,
        "duration": 0.8,
        "text": "Welcome to our introductory overview.",
    },
    {
        "segment_index": 1,
        "start": 0.8,
        "end": 1.7,
        "duration": 0.9,
        "text": "Today we explore modern technology and future innovations.",
    },
]


def run_broll_placement_tests():
    print("==================================================")
    print("STARTING B-ROLL PLACEMENT & GENERATION TEST SUITE")
    print("==================================================")

    sample_video = Path("sample.mp4")
    assert sample_video.exists(), "sample.mp4 must exist in workspace for tests"

    # -------------------------------------------------------------------------
    # TEST 1: download_stock_clip local file and caching
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Testing download_stock_clip local resolution and caching...")
    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)

        # 1A: Existing local_path
        clip_local = copy.deepcopy(SAMPLE_CLIP)
        clip_local["local_path"] = str(sample_video)
        res_path = download_stock_clip(clip_local, temp_dir)
        assert res_path == sample_video, "Should return existing local_path"

        # 1B: Cached file in temp_dir
        cached_file = temp_dir / "stock_clip_8881.mp4"
        shutil.copy(str(sample_video), str(cached_file))
        res_cached = download_stock_clip(SAMPLE_CLIP, temp_dir)
        assert res_cached == cached_file, "Should return cached file"

        # 1C: Missing URL rejection
        clip_empty = {"id": 123}
        try:
            download_stock_clip(clip_empty, temp_dir)
            assert False, "Should have raised ValueError for missing URL"
        except ValueError as e:
            assert "does not contain a valid download or preview URL" in str(e)

    print("[PASSED] TEST 1: Local file resolution, caching, and validation verified.")

    # -------------------------------------------------------------------------
    # TEST 2: download_stock_clip error handling
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Testing download_stock_clip error mapping...")
    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)
        clip_remote = copy.deepcopy(SAMPLE_CLIP)

        # 2A: Connection Error
        with patch("urllib.request.urlopen") as mock_open:
            import urllib.error
            mock_open.side_effect = urllib.error.URLError("No route to host")
            try:
                download_stock_clip(clip_remote, temp_dir)
                assert False, "Should have raised ConnectionError"
            except ConnectionError as e:
                assert "Could not connect to download stock clip" in str(e)

        # 2B: Timeout
        with patch("urllib.request.urlopen") as mock_open:
            import socket
            mock_open.side_effect = socket.timeout("Timed out")
            try:
                download_stock_clip(clip_remote, temp_dir)
                assert False, "Should have raised TimeoutError"
            except TimeoutError as e:
                assert "timed out" in str(e).lower()

    print("[PASSED] TEST 2: Network failure and timeout error mapping verified.")

    # -------------------------------------------------------------------------
    # TEST 3: compose_broll_video parameter validation
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Testing compose_broll_video validation...")
    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)
        out_vid = temp_dir / "out.mp4"

        # Missing original video
        try:
            compose_broll_video(temp_dir / "nonexistent.mp4", [{"clip": SAMPLE_CLIP, "start": 0, "end": 1}], out_vid, temp_dir)
            assert False, "Should fail on missing video"
        except FileNotFoundError:
            pass

        # Empty placements
        try:
            compose_broll_video(sample_video, [], out_vid, temp_dir)
            assert False, "Should fail on empty placements"
        except ValueError as e:
            assert "At least one B-roll clip" in str(e)

        # Invalid timestamps (start >= end)
        clip_with_local = copy.deepcopy(SAMPLE_CLIP)
        clip_with_local["local_path"] = str(sample_video)
        try:
            compose_broll_video(sample_video, [{"clip": clip_with_local, "start": 1.5, "end": 0.5}], out_vid, temp_dir)
            assert False, "Should fail when start >= end"
        except ValueError as e:
            assert "strictly before" in str(e)

        # Too short duration
        try:
            compose_broll_video(sample_video, [{"clip": clip_with_local, "start": 1.0, "end": 1.02}], out_vid, temp_dir)
            assert False, "Should fail when duration < 0.1s"
        except ValueError as e:
            assert "too short" in str(e)

    print("[PASSED] TEST 3: Parameter and timestamp boundary validation verified.")

    # -------------------------------------------------------------------------
    # TEST 4: compose_broll_video rendering with single placement
    # -------------------------------------------------------------------------
    print("\n[TEST 4] Testing end-to-end compose_broll_video rendering...")
    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)
        out_vid = temp_dir / "rendered_broll.mp4"
        clip_local = copy.deepcopy(SAMPLE_CLIP)
        clip_local["local_path"] = str(sample_video)

        progress_log = []
        def on_prog(frac, msg):
            progress_log.append((round(frac, 2), msg))

        result = compose_broll_video(
            original_video_path=sample_video,
            broll_placements=[{"clip": clip_local, "start": 0.4, "end": 1.4}],
            output_path=out_vid,
            temp_dir=temp_dir,
            progress_callback=on_prog,
        )

        assert result.exists(), "Output video must exist"
        assert result.stat().st_size > 5000, "Output video must not be empty"

        # Verify output video metadata
        meta = get_video_metadata(result)
        orig_meta = get_video_metadata(sample_video)

        assert meta["width"] == orig_meta["width"], f"Width mismatch: {meta['width']} vs {orig_meta['width']}"
        assert meta["height"] == orig_meta["height"], f"Height mismatch: {meta['height']} vs {orig_meta['height']}"
        assert abs(meta["fps"] - orig_meta["fps"]) < 0.1, f"FPS mismatch: {meta['fps']} vs {orig_meta['fps']}"
        assert meta["total_frames"] == orig_meta["total_frames"], "Frame count should match original video"
        assert len(progress_log) >= 4, "Progress callback should have reported multiple stages"

    print("[PASSED] TEST 4: End-to-end B-roll video compositing verified with matching dimensions and fps.")

    # -------------------------------------------------------------------------
    # TEST 5: compose_broll_video with multiple placements
    # -------------------------------------------------------------------------
    print("\n[TEST 5] Testing compose_broll_video with multiple placements...")
    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)
        out_vid = temp_dir / "multi_rendered.mp4"
        clip1 = copy.deepcopy(SAMPLE_CLIP)
        clip1["local_path"] = str(sample_video)
        clip1["id"] = 101

        clip2 = copy.deepcopy(SAMPLE_CLIP)
        clip2["local_path"] = str(sample_video)
        clip2["id"] = 102

        result = compose_broll_video(
            original_video_path=sample_video,
            broll_placements=[
                {"clip": clip1, "start": 0.2, "end": 0.7},
                {"clip": clip2, "start": 1.1, "end": 1.6},
            ],
            output_path=out_vid,
            temp_dir=temp_dir,
        )
        assert result.exists() and result.stat().st_size > 5000

    print("[PASSED] TEST 5: Multiple B-roll cutaway placement rendering verified.")

    # -------------------------------------------------------------------------
    # TEST 6: Card 4 empty state when no clip is selected
    # -------------------------------------------------------------------------
    print("\n[TEST 6] Testing Card 4 UI empty state...")
    mock_state = MockSessionState()
    mock_state.update({
        "current_page": "broll",
        "app_state": AppState.IDLE,
        "processed_video": None,
        "broll_input_video": str(sample_video),
        "broll_source": "uploaded",
        "broll_preview_active": False,
        "broll_transcript": SAMPLE_TRANSCRIPT,
        "broll_transcript_video_id": f"{sample_video}_{sample_video.stat().st_size}_{sample_video.stat().st_mtime}",
        "broll_keywords": ["technology"],
        "broll_keywords_video_id": f"{sample_video}_{sample_video.stat().st_size}_{sample_video.stat().st_mtime}",
        "broll_stock_results": [SAMPLE_CLIP],
        "broll_stock_video_id": f"{sample_video}_{sample_video.stat().st_size}_{sample_video.stat().st_mtime}",
        "broll_selected_clip": None,
        "broll_is_generating": False,
        "broll_generation_error": None,
        "broll_generation_success": False,
    })

    rendered_html = []
    button_calls = {}

    def mock_markdown(content, unsafe_allow_html=False):
        rendered_html.append(content)

    def mock_button(label, key=None, type=None, use_container_width=False, disabled=False, **kwargs):
        button_calls[key] = {"label": label, "disabled": disabled}
        return False

    with patch.object(st, "session_state", mock_state):
        with patch.object(st, "markdown", side_effect=mock_markdown):
            with patch.object(st, "button", side_effect=mock_button):
                render_broll_page(Path("temp"))

    all_html = "\n".join(rendered_html)
    assert "No Stock Footage Selected" in all_html, "Should display guidance when no clip is selected"
    assert "broll_generate_video_btn" in button_calls, "Generate Video button must exist"
    assert button_calls["broll_generate_video_btn"]["disabled"] is True, "Generate Video must be disabled when no clip selected"

    print("[PASSED] TEST 6: Card 4 empty state and disabled Generate Video button verified.")

    # -------------------------------------------------------------------------
    # TEST 7: Card 4 review state with selected clip & transcript match
    # -------------------------------------------------------------------------
    print("\n[TEST 7] Testing Card 4 UI review state when clip is selected...")
    mock_state["broll_selected_clip"] = copy.deepcopy(SAMPLE_CLIP)
    rendered_html.clear()
    button_calls.clear()

    with patch.object(st, "session_state", mock_state):
        with patch.object(st, "markdown", side_effect=mock_markdown):
            with patch.object(st, "button", side_effect=mock_button):
                render_broll_page(Path("temp"))

    all_html = "\n".join(rendered_html)
    assert "Proposed Timeline Placement" in all_html, "Timeline placement bar must render"
    assert "Target Transcript Context" in all_html, "Transcript context card must render"
    assert "modern technology and future innovations" in all_html, "Matching transcript text must be displayed"
    assert button_calls["broll_generate_video_btn"]["disabled"] is False, "Generate Video must be enabled when clip is selected"

    print("[PASSED] TEST 7: Selected footage review, transcript match, and timeline bar verified.")

    # -------------------------------------------------------------------------
    # TEST 8: Card 4 error banner rendering
    # -------------------------------------------------------------------------
    print("\n[TEST 8] Testing Card 4 error banner rendering...")
    mock_state["broll_generation_error"] = "Test rendering failure message"
    rendered_html.clear()

    with patch.object(st, "session_state", mock_state):
        with patch.object(st, "markdown", side_effect=mock_markdown):
            with patch.object(st, "button", side_effect=mock_button):
                render_broll_page(Path("temp"))

    all_html = "\n".join(rendered_html)
    assert "Video Generation Error" in all_html
    assert "Test rendering failure message" in all_html

    print("[PASSED] TEST 8: Card 4 error banner verified.")

    # -------------------------------------------------------------------------
    # TEST 9: Generate Video click simulation and redirect to export
    # -------------------------------------------------------------------------
    print("\n[TEST 9] Testing Generate Video click and export redirect...")
    mock_state["broll_generation_error"] = None
    mock_state["broll_selected_clip"]["local_path"] = str(sample_video)
    clip_id = mock_state["broll_selected_clip"]["id"]
    mock_state[f"broll_time_start_{clip_id}"] = 0.5
    mock_state[f"broll_time_end_{clip_id}"] = 1.5

    rerun_called = []
    def mock_rerun():
        rerun_called.append(True)

    def mock_button_click(label, key=None, **kwargs):
        if key == "broll_generate_video_btn":
            return True
        return False

    with patch.object(st, "session_state", mock_state):
        with patch.object(st, "rerun", side_effect=mock_rerun):
            with patch.object(st, "button", side_effect=mock_button_click):
                with patch.object(st, "progress"):
                    render_broll_page(Path("temp"))

    assert len(rerun_called) > 0, "st.rerun() must be called after generation"
    assert mock_state.get("current_page") == "export", "User must be redirected to export page"
    assert mock_state.get("app_state") == AppState.COMPLETED, "AppState must be COMPLETED"
    assert mock_state.get("broll_generation_success") is True, "broll_generation_success must be True"
    assert mock_state.get("processed_video") is not None, "processed_video must be populated"
    proc_file = Path(mock_state["processed_video"])
    assert proc_file.exists() and proc_file.stat().st_size > 0, "Generated video file must exist on disk"
    assert "video_metadata" in mock_state and mock_state["video_metadata"]["width"] == 640

    print("[PASSED] TEST 9: Generate Video completes, sets state, and redirects to export page.")

    # -------------------------------------------------------------------------
    # TEST 10: Export page verification for B-roll generated video
    # -------------------------------------------------------------------------
    print("\n[TEST 10] Testing Export page preview and download button...")
    export_html = []
    video_calls = []
    download_btn_params = {}

    def mock_exp_markdown(content, unsafe_allow_html=False):
        export_html.append(content)

    def mock_st_video(path):
        video_calls.append(str(path))

    def mock_download_button(label, data, file_name, mime, **kwargs):
        download_btn_params["label"] = label
        download_btn_params["data"] = data() if callable(data) else data
        download_btn_params["file_name"] = file_name
        download_btn_params["mime"] = mime
        return False

    with patch.object(st, "session_state", mock_state):
        with patch.object(st, "markdown", side_effect=mock_exp_markdown):
            with patch.object(st, "video", side_effect=mock_st_video):
                with patch.object(st, "download_button", side_effect=mock_download_button):
                    with patch.object(st, "button", return_value=False):
                        render_export_page()

    all_exp_html = "\n".join(export_html)
    assert "B-roll Video Generated Successfully!" in all_exp_html, "Success banner must display"
    assert len(video_calls) == 1, "st.video must be called exactly once to preview rendered output"
    assert video_calls[0] == str(proc_file), "Preview player must play newly generated video"
    assert "Download Processed Video" in download_btn_params["label"], "Download button must be present"
    assert download_btn_params["file_name"].startswith("exported_broll_"), "File name must reflect newly generated video"
    assert len(download_btn_params["data"]) == proc_file.stat().st_size, "Download button data must match generated video bytes"

    print("[PASSED] TEST 10: Export page preview and download button verified.")

    # -------------------------------------------------------------------------
    # TEST 11: Application reset and cleanup
    # -------------------------------------------------------------------------
    print("\n[TEST 11] Testing reset_and_clear_all state wipe...")
    with patch.object(st, "session_state", mock_state):
        with patch.object(st, "rerun"):
            with patch.object(st, "success"):
                reset_and_clear_all(Path("temp"))

    assert mock_state.get("broll_selected_clip") is None
    assert mock_state.get("broll_is_generating") is False
    assert mock_state.get("broll_generation_error") is None
    assert mock_state.get("broll_generation_success") is False
    assert mock_state.get("processed_video") is None

    print("[PASSED] TEST 11: Complete reset and state cleanup verified.")

    # Clean up generated video
    if proc_file.exists():
        proc_file.unlink()

    print("\n==================================================")
    print("ALL B-ROLL PLACEMENT & GENERATION TESTS PASSED (11/11)!")
    print("==================================================")


if __name__ == "__main__":
    run_broll_placement_tests()
