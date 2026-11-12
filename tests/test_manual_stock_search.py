import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from app.ui.broll import render_broll_page
from app.ui.state import AppState, initialize_session_state, reset_and_clear_all


class MockSessionState(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value


SAMPLE_SUGGESTED_CLIP = {
    "id": 1001,
    "tags": "technology, coding, computer",
    "duration": 12,
    "duration_formatted": "00:12",
    "width": 1920,
    "height": 1080,
    "resolution": "1920×1080",
    "thumbnail_url": "https://cdn.pixabay.com/suggested_thumb.jpg",
    "preview_url": "https://cdn.pixabay.com/suggested_preview.mp4",
    "download_url": "https://cdn.pixabay.com/suggested_download.mp4",
    "page_url": "https://pixabay.com/videos/1001/",
    "user": "ai_cameraman",
    "keyword": "modern technology",
    "source_type": "suggested",
}

SAMPLE_MANUAL_CLIP = {
    "id": 2002,
    "tags": "coffee, morning, cafe",
    "duration": 15,
    "duration_formatted": "00:15",
    "width": 1920,
    "height": 1080,
    "resolution": "1920×1080",
    "thumbnail_url": "https://cdn.pixabay.com/manual_thumb.jpg",
    "preview_url": "https://cdn.pixabay.com/manual_preview.mp4",
    "download_url": "https://cdn.pixabay.com/manual_download.mp4",
    "page_url": "https://pixabay.com/videos/2002/",
    "user": "barista_filmer",
    "keyword": "coffee shop",
    "source_type": "manual",
}

SAMPLE_TRANSCRIPT = [
    {
        "segment_index": 0,
        "start": 0.0,
        "end": 5.0,
        "duration": 5.0,
        "text": "Welcome to our video on modern technology and software.",
    },
    {
        "segment_index": 1,
        "start": 5.0,
        "end": 10.0,
        "duration": 5.0,
        "text": "Taking a break with a warm cup of coffee.",
    },
]


def run_manual_search_tests():
    print("==================================================")
    print("STARTING MANUAL STOCK SEARCH & 5-CARD TEST SUITE")
    print("==================================================")

    broll_code = (PROJECT_ROOT / "app" / "ui" / "broll.py").read_text(encoding="utf-8")

    # -------------------------------------------------------------
    # TEST 1: Workflow Card Numbering and Hierarchy
    # -------------------------------------------------------------
    print("\n[TEST 1] Verifying 5-card workflow order and step titles...")
    assert 'key="broll_transcription_card"' in broll_code
    assert 'key="broll_keywords_card"' in broll_code
    assert 'key="broll_stock_search_card"' in broll_code
    assert 'key="broll_manual_search_card"' in broll_code
    assert 'key="broll_placement_card"' in broll_code

    pos_c1 = broll_code.find('key="broll_transcription_card"')
    pos_c2 = broll_code.find('key="broll_keywords_card"')
    pos_c3 = broll_code.find('key="broll_stock_search_card"')
    pos_c4 = broll_code.find('key="broll_manual_search_card"')
    pos_c5 = broll_code.find('key="broll_placement_card"')

    assert pos_c1 < pos_c2 < pos_c3 < pos_c4 < pos_c5, (
        "Cards must appear in sequential order: Card 1 -> Card 2 -> Card 3 -> Card 4 -> Card 5"
    )

    assert "Suggested Stock Footage" in broll_code, "Card 3 must be titled 'Suggested Stock Footage'"
    assert "Manual Stock Footage Search" in broll_code, "Card 4 must be titled 'Manual Stock Footage Search'"
    assert "B-roll Placement & Timeline" in broll_code, "Card 5 must be titled 'B-roll Placement & Timeline'"
    print("[PASSED] TEST 1: All 5 cards appear in correct sequential order with exact titles.")

    # -------------------------------------------------------------
    # TEST 2: Card 4 UI Empty State
    # -------------------------------------------------------------
    print("\n[TEST 2] Verifying Card 4 UI empty state when no search performed...")
    mock_state = MockSessionState({
        "current_page": "broll",
        "app_state": AppState.IDLE,
        "processed_video": None,
        "broll_input_video": "test_video.mp4",
        "broll_source": "uploaded",
        "broll_preview_active": False,
        "broll_transcript": SAMPLE_TRANSCRIPT,
        "broll_keywords": ["modern technology"],
        "broll_stock_results": None,
        "broll_manual_results": None,
        "broll_manual_query": "",
        "broll_manual_error": None,
        "broll_selected_clips": [],
        "broll_selected_clip": None,
        "broll_is_generating": False,
        "broll_generation_error": None,
        "broll_generation_success": False,
    })

    rendered_html = []
    button_calls = {}

    def mock_markdown(content, unsafe_allow_html=False):
        rendered_html.append(content)

    def mock_button(label, key=None, **kwargs):
        button_calls[key] = label
        return False

    with patch.object(st, "session_state", mock_state):
        with patch.object(st, "markdown", side_effect=mock_markdown):
            with patch.object(st, "button", side_effect=mock_button):
                render_broll_page(Path("temp"))

    all_html = "\n".join(rendered_html)
    assert "Manual Stock Search Ready" in all_html, "Card 4 must display ready placeholder"
    assert "broll_manual_search_btn" in button_calls, "Manual Search button must be rendered"
    print("[PASSED] TEST 2: Card 4 empty state and controls verified.")

    # -------------------------------------------------------------
    # TEST 3: Card 4 Empty Query Validation
    # -------------------------------------------------------------
    print("\n[TEST 3] Testing empty search term validation in Card 4...")
    rerun_called = []

    def mock_button_click_manual(label, key=None, **kwargs):
        if key == "broll_manual_search_btn":
            return True
        return False

    with patch.object(st, "session_state", mock_state):
        with patch.object(st, "markdown", side_effect=mock_markdown):
            with patch.object(st, "button", side_effect=mock_button_click_manual):
                with patch.object(st, "text_input", return_value=""):
                    with patch.object(st, "rerun", side_effect=lambda: rerun_called.append(True)):
                        render_broll_page(Path("temp"))

    assert len(rerun_called) > 0, "Empty query must trigger st.rerun()"
    assert mock_state.get("broll_manual_error") is not None, "Error message must be set for empty query"
    print("[PASSED] TEST 3: Empty query rejected with error message.")

    # -------------------------------------------------------------
    # TEST 4: Card 4 Execution with Mocked Search Results
    # -------------------------------------------------------------
    print("\n[TEST 4] Testing manual search execution and clip gallery rendering...")
    mock_state["broll_manual_error"] = None
    mock_state["broll_manual_results"] = [SAMPLE_MANUAL_CLIP]
    mock_state["broll_manual_query"] = "coffee shop"

    rendered_html.clear()
    button_calls.clear()

    with patch.object(st, "session_state", mock_state):
        with patch.object(st, "markdown", side_effect=mock_markdown):
            with patch.object(st, "button", side_effect=mock_button):
                render_broll_page(Path("temp"))

    all_html = "\n".join(rendered_html)
    assert "Manual search completed" in all_html, "Success banner must display"
    assert "coffee shop" in all_html, "Queried term must appear"
    assert "MANUAL" in all_html, "MANUAL badge must be displayed on manual footage"
    assert "barista_filmer" in all_html, "Creator info must be displayed"
    assert f"broll_select_manual_clip_{SAMPLE_MANUAL_CLIP['id']}_0" in button_calls, "Select button must exist for manual clip"
    print("[PASSED] TEST 4: Manual search gallery, badges, and source details verified.")

    # -------------------------------------------------------------
    # TEST 5: Combining Manual & Suggested Clips on the Same Timeline
    # -------------------------------------------------------------
    print("\n[TEST 5] Testing combination of AI-suggested clip and manual clip in Card 5...")
    combined_clips = [copy.deepcopy(SAMPLE_SUGGESTED_CLIP), copy.deepcopy(SAMPLE_MANUAL_CLIP)]
    mock_state["broll_selected_clips"] = combined_clips
    mock_state["broll_selected_clip"] = combined_clips[-1]

    rendered_html.clear()
    button_calls.clear()

    with patch.object(st, "session_state", mock_state):
        with patch.object(st, "markdown", side_effect=mock_markdown):
            with patch.object(st, "button", side_effect=mock_button):
                render_broll_page(Path("temp"))

    all_html = "\n".join(rendered_html)
    assert "2 Clips Scheduled" in all_html, "Master timeline must indicate 2 clips scheduled"
    assert "1 Suggested, 1 Manual" in all_html or "1 AI-Suggested, 1 Manual" in all_html, "Should report count of suggested vs manual clips"
    assert "[MANUAL]" in all_html, "Timeline legend must include [MANUAL] tag"
    assert "[SUGGESTED]" in all_html, "Timeline legend must include [SUGGESTED] tag"
    assert "broll_generate_video_btn" in button_calls, "Generate Video button must exist"
    assert button_calls["broll_generate_video_btn"] == "Generate Video", "Button label must be Generate Video"
    print("[PASSED] TEST 5: Suggested & manual clips combined on timeline with distinct tags.")

    # -------------------------------------------------------------
    # TEST 6: Multi-search Persistence (Selecting across multiple queries)
    # -------------------------------------------------------------
    print("\n[TEST 6] Testing selection persistence across multiple manual search queries...")
    first_manual_clip = copy.deepcopy(SAMPLE_MANUAL_CLIP)
    second_manual_clip = {
        "id": 3003,
        "tags": "drone, aerial, sunset",
        "duration": 10,
        "duration_formatted": "00:10",
        "width": 1920,
        "height": 1080,
        "resolution": "1920×1080",
        "thumbnail_url": "https://cdn.pixabay.com/drone_thumb.jpg",
        "preview_url": "https://cdn.pixabay.com/drone_preview.mp4",
        "download_url": "https://cdn.pixabay.com/drone_download.mp4",
        "page_url": "https://pixabay.com/videos/3003/",
        "user": "drone_pilot",
        "keyword": "nature drone",
        "source_type": "manual",
    }

    # Simulate: User already selected clip 2002 from query 1
    mock_state["broll_selected_clips"] = [first_manual_clip]
    mock_state["broll_selected_clip"] = first_manual_clip
    # Now user executes search 2: "nature drone"
    mock_state["broll_manual_results"] = [second_manual_clip]
    mock_state["broll_manual_query"] = "nature drone"

    # User clicks "Select Clip" on the second manual clip
    rerun_called.clear()
    def mock_click_select_second(label, key=None, **kwargs):
        if key == f"broll_select_manual_clip_{second_manual_clip['id']}_0":
            return True
        return False

    with patch.object(st, "session_state", mock_state):
        with patch.object(st, "markdown", side_effect=mock_markdown):
            with patch.object(st, "button", side_effect=mock_click_select_second):
                with patch.object(st, "rerun", side_effect=lambda: rerun_called.append(True)):
                    render_broll_page(Path("temp"))

    assert len(rerun_called) > 0, "Selecting clip must trigger st.rerun()"
    # Verify BOTH clips are now present in broll_selected_clips!
    selected_ids = [c["id"] for c in mock_state["broll_selected_clips"]]
    assert 2002 in selected_ids, "Previously selected clip 2002 must remain selected"
    assert 3003 in selected_ids, "Newly selected clip 3003 must be added"
    assert len(mock_state["broll_selected_clips"]) == 2, "Both clips must be retained"
    print("[PASSED] TEST 6: Multi-search selection persistence verified without clip loss.")

    # -------------------------------------------------------------
    # TEST 7: Deselecting Manual Clip
    # -------------------------------------------------------------
    print("\n[TEST 7] Testing individual manual clip deselection...")
    rerun_called.clear()
    # Click select button for clip 3003 when it is already selected -> should deselect it!
    with patch.object(st, "session_state", mock_state):
        with patch.object(st, "markdown", side_effect=mock_markdown):
            with patch.object(st, "button", side_effect=mock_click_select_second):
                with patch.object(st, "rerun", side_effect=lambda: rerun_called.append(True)):
                    render_broll_page(Path("temp"))

    selected_ids = [c["id"] for c in mock_state["broll_selected_clips"]]
    assert 2002 in selected_ids, "Clip 2002 must still be selected"
    assert 3003 not in selected_ids, "Clip 3003 must be deselected"
    assert len(mock_state["broll_selected_clips"]) == 1
    print("[PASSED] TEST 7: Individual clip deselection verified.")

    # -------------------------------------------------------------
    # TEST 8: State Cleanup on Application Reset
    # -------------------------------------------------------------
    print("\n[TEST 8] Testing reset_and_clear_all state wipe for manual search keys...")
    with patch.object(st, "session_state", mock_state):
        with patch.object(st, "rerun"):
            with patch.object(st, "success"):
                reset_and_clear_all(Path("temp"))

    assert mock_state.get("broll_manual_results") is None, "Manual results must be wiped on reset"
    assert mock_state.get("broll_manual_query") == "", "Manual query must be reset to empty"
    assert mock_state.get("broll_manual_error") is None, "Manual error must be cleared on reset"
    assert mock_state.get("broll_selected_clips") == [], "Selected clips must be wiped on reset"
    print("[PASSED] TEST 8: State reset and cleanup verified.")

    print("\n==================================================")
    print("ALL MANUAL STOCK SEARCH TESTS PASSED (8/8)!")
    print("==================================================")


if __name__ == "__main__":
    run_manual_search_tests()
