import copy
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

import streamlit as st

from app.ui.state import AppState, initialize_session_state, reset_and_clear_all
from app.ui.broll import render_broll_page


class MockSessionState(dict):
    """Mock Streamlit session state object for deterministic unit testing."""
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value


CLIPS_FIXTURE = [
    {
        "id": 101,
        "tags": "modern office, team meeting",
        "duration": 15,
        "duration_formatted": "00:15",
        "width": 1920,
        "height": 1080,
        "resolution": "1920×1080",
        "thumbnail_url": "https://cdn.pixabay.com/thumb_101.jpg",
        "preview_url": "https://cdn.pixabay.com/preview_101.mp4",
        "download_url": "https://cdn.pixabay.com/download_101.mp4",
        "page_url": "https://pixabay.com/videos/101/",
        "user": "artist_one",
        "keyword": "office",
        "provider": "Pixabay",
    },
    {
        "id": 102,
        "tags": "technology, keyboard, code",
        "duration": 20,
        "duration_formatted": "00:20",
        "width": 1280,
        "height": 720,
        "resolution": "1280×720",
        "thumbnail_url": "https://cdn.pixabay.com/thumb_102.jpg",
        "preview_url": "https://cdn.pixabay.com/preview_102.mp4",
        "download_url": "https://cdn.pixabay.com/download_102.mp4",
        "page_url": "https://pixabay.com/videos/102/",
        "user": "artist_two",
        "keyword": "technology",
        "provider": "Pixabay",
    },
    {
        "id": 103,
        "tags": "city skyline, sunset, drone",
        "duration": 25,
        "duration_formatted": "00:25",
        "width": 3840,
        "height": 2160,
        "resolution": "3840×2160",
        "thumbnail_url": "https://cdn.pixabay.com/thumb_103.jpg",
        "preview_url": "https://cdn.pixabay.com/preview_103.mp4",
        "download_url": "https://cdn.pixabay.com/download_103.mp4",
        "page_url": "https://pixabay.com/videos/103/",
        "user": "artist_three",
        "keyword": "city",
        "provider": "Pixabay",
    },
    {
        "id": 104,
        "tags": "nature, forest, trees",
        "duration": 18,
        "duration_formatted": "00:18",
        "width": 1920,
        "height": 1080,
        "resolution": "1920×1080",
        "thumbnail_url": "https://cdn.pixabay.com/thumb_104.jpg",
        "preview_url": "https://cdn.pixabay.com/preview_104.mp4",
        "download_url": "https://cdn.pixabay.com/download_104.mp4",
        "page_url": "https://pixabay.com/videos/104/",
        "user": "artist_four",
        "keyword": "nature",
        "provider": "Pixabay",
    },
]


def run_stock_multiselect_tests():
    print("==================================================")
    print("STARTING STOCK MULTI-SELECTION TEST SUITE")
    print("==================================================")

    sample_video = Path("sample.mp4")
    assert sample_video.exists(), "sample.mp4 must exist in workspace for tests"
    vid_stat = sample_video.stat()
    video_id_1 = f"{sample_video}_{vid_stat.st_size}_{vid_stat.st_mtime}"

    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)

        # -------------------------------------------------------------
        # TEST 1: Select one footage clip
        # -------------------------------------------------------------
        print("\n[TEST 1] Testing single clip selection...")
        mock_state = MockSessionState()
        with patch.object(st, "session_state", mock_state):
            initialize_session_state()
            mock_state.update({
                "current_page": "broll",
                "app_state": AppState.IDLE,
                "broll_input_video": str(sample_video),
                "broll_source": "uploaded",
                "broll_stock_results": CLIPS_FIXTURE,
                "broll_stock_video_id": video_id_1,
                "broll_transcript": [{"start": 0.0, "end": 2.0, "text": "intro text"}],
                "broll_transcript_video_id": video_id_1,
                "broll_keywords": ["office", "technology"],
                "broll_keywords_video_id": video_id_1,
            })

            def mock_select_first(label, **kwargs):
                if "broll_select_clip_101_0" in kwargs.get("key", ""):
                    return True
                return False

            with patch.object(st, "button", side_effect=mock_select_first), \
                 patch.object(st, "rerun") as mock_rerun:
                render_broll_page(temp_dir)
                assert mock_rerun.called

            assert "broll_selected_clips" in mock_state
            assert len(mock_state["broll_selected_clips"]) == 1
            assert mock_state["broll_selected_clips"][0]["id"] == 101
            assert mock_state["broll_selected_clip"]["id"] == 101
        print("[PASSED] TEST 1: First clip successfully selected.")

        # -------------------------------------------------------------
        # TEST 2: Select a second clip, confirm first remains selected
        # -------------------------------------------------------------
        print("\n[TEST 2] Testing second clip selection (multi-selection persistence)...")
        with patch.object(st, "session_state", mock_state):
            def mock_select_second(label, **kwargs):
                if "broll_select_clip_102_1" in kwargs.get("key", ""):
                    return True
                return False

            with patch.object(st, "button", side_effect=mock_select_second), \
                 patch.object(st, "rerun") as mock_rerun:
                render_broll_page(temp_dir)
                assert mock_rerun.called

            selected = mock_state["broll_selected_clips"]
            assert len(selected) == 2, f"Expected 2 selected clips, found {len(selected)}"
            selected_ids = [c["id"] for c in selected]
            assert 101 in selected_ids, "Clip 101 must remain selected"
            assert 102 in selected_ids, "Clip 102 must now be selected"
        print("[PASSED] TEST 2: Second clip selected without overwriting the first.")

        # -------------------------------------------------------------
        # TEST 3: Select several additional clips
        # -------------------------------------------------------------
        print("\n[TEST 3] Testing selection of additional clips...")
        with patch.object(st, "session_state", mock_state):
            def mock_select_third(label, **kwargs):
                if "broll_select_clip_103_2" in kwargs.get("key", ""):
                    return True
                return False

            with patch.object(st, "button", side_effect=mock_select_third), \
                 patch.object(st, "rerun") as mock_rerun:
                render_broll_page(temp_dir)

            def mock_select_fourth(label, **kwargs):
                if "broll_select_clip_104_3" in kwargs.get("key", ""):
                    return True
                return False

            with patch.object(st, "button", side_effect=mock_select_fourth), \
                 patch.object(st, "rerun") as mock_rerun:
                render_broll_page(temp_dir)

            selected = mock_state["broll_selected_clips"]
            assert len(selected) == 4, f"Expected 4 selected clips, found {len(selected)}"
            assert [c["id"] for c in selected] == [101, 102, 103, 104]
        print("[PASSED] TEST 3: Multiple clips (4/4) selected simultaneously.")

        # -------------------------------------------------------------
        # TEST 4: Visual indication of all selected clips in UI
        # -------------------------------------------------------------
        print("\n[TEST 4] Testing visual indications for multiple selected clips...")
        rendered_html = []
        button_labels = {}

        def mock_markdown(content, unsafe_allow_html=False):
            rendered_html.append(content)

        def mock_button_record(label, key=None, **kwargs):
            if key and "broll_select_clip" in key:
                button_labels[key] = label
            return False

        with patch.object(st, "session_state", mock_state):
            with patch.object(st, "markdown", side_effect=mock_markdown):
                with patch.object(st, "button", side_effect=mock_button_record):
                    render_broll_page(temp_dir)

        all_html = "\n".join(rendered_html)
        assert "4 footage clips selected for B-roll" in all_html
        # All 4 buttons must reflect selected state
        assert button_labels["broll_select_clip_101_0"] == "✓ Selected for B-roll"
        assert button_labels["broll_select_clip_102_1"] == "✓ Selected for B-roll"
        assert button_labels["broll_select_clip_103_2"] == "✓ Selected for B-roll"
        assert button_labels["broll_select_clip_104_3"] == "✓ Selected for B-roll"
        print("[PASSED] TEST 4: Visual indicator bar, badges, and button labels verified.")

        # -------------------------------------------------------------
        # TEST 5: Deselect an individual clip without affecting others
        # -------------------------------------------------------------
        print("\n[TEST 5] Testing individual clip deselection...")
        with patch.object(st, "session_state", mock_state):
            # Deselect clip 102 (index 1)
            def mock_deselect_clip(label, **kwargs):
                if "broll_select_clip_102_1" in kwargs.get("key", ""):
                    return True
                return False

            with patch.object(st, "button", side_effect=mock_deselect_clip), \
                 patch.object(st, "rerun") as mock_rerun:
                render_broll_page(temp_dir)
                assert mock_rerun.called

            remaining_ids = [c["id"] for c in mock_state["broll_selected_clips"]]
            assert 102 not in remaining_ids, "Clip 102 must be deselected"
            assert 101 in remaining_ids, "Clip 101 must remain selected"
            assert 103 in remaining_ids, "Clip 103 must remain selected"
            assert 104 in remaining_ids, "Clip 104 must remain selected"
            assert len(remaining_ids) == 3, f"Expected 3 clips remaining, got {len(remaining_ids)}"
        print("[PASSED] TEST 5: Single clip deselected; remaining 3 clips kept intact.")

        # -------------------------------------------------------------
        # TEST 6: Duplicate selection prevention
        # -------------------------------------------------------------
        print("\n[TEST 6] Testing duplicate selection prevention...")
        with patch.object(st, "session_state", mock_state):
            # Attempt to select clip 101 again (which is already selected)
            def mock_click_already_selected(label, **kwargs):
                if "broll_select_clip_101_0" in kwargs.get("key", ""):
                    return True
                return False

            with patch.object(st, "button", side_effect=mock_click_already_selected), \
                 patch.object(st, "rerun"):
                # Clicking an already selected clip toggles it off (deselection)
                render_broll_page(temp_dir)

            ids_after_toggle = [c["id"] for c in mock_state["broll_selected_clips"]]
            assert 101 not in ids_after_toggle, "Clicking an already selected clip toggles it off"
            assert len(ids_after_toggle) == 2, "Only 2 clips should remain"

            # Re-select clip 101 once
            with patch.object(st, "button", side_effect=mock_click_already_selected), \
                 patch.object(st, "rerun"):
                render_broll_page(temp_dir)

            ids_after_readd = [c["id"] for c in mock_state["broll_selected_clips"]]
            assert ids_after_readd.count(101) == 1, "Clip 101 must appear exactly once (no duplicates)"
        print("[PASSED] TEST 6: Duplicate selections prevented.")

        # -------------------------------------------------------------
        # TEST 7: Metadata preservation across selections
        # -------------------------------------------------------------
        print("\n[TEST 7] Testing metadata preservation for all selected clips...")
        with patch.object(st, "session_state", mock_state):
            for clip_item in mock_state["broll_selected_clips"]:
                assert "id" in clip_item and clip_item["id"] is not None
                assert "download_url" in clip_item and clip_item["download_url"].startswith("http")
                assert "preview_url" in clip_item and clip_item["preview_url"].startswith("http")
                assert "thumbnail_url" in clip_item and clip_item["thumbnail_url"].startswith("http")
                assert "provider" in clip_item and clip_item["provider"] in ("Pixabay", "Pexels")
                assert "duration" in clip_item and clip_item["duration"] > 0
                assert "resolution" in clip_item and "×" in clip_item["resolution"]
                assert "width" in clip_item and clip_item["width"] > 0
                assert "height" in clip_item and clip_item["height"] > 0
        print("[PASSED] TEST 7: All required metadata fields fully preserved.")

        # -------------------------------------------------------------
        # TEST 8: Target video switch invalidation (no leak between videos)
        # -------------------------------------------------------------
        print("\n[TEST 8] Testing target video switch invalidation...")
        # Create a second dummy video file to simulate switching to another video
        other_video = temp_dir / "other_sample.mp4"
        shutil.copy(str(sample_video), str(other_video))
        other_stat = other_video.stat()
        other_video_id = f"{other_video}_{other_stat.st_size}_{other_stat.st_mtime}"

        with patch.object(st, "session_state", mock_state):
            assert len(mock_state["broll_selected_clips"]) > 0, "Pre-condition: clips are selected"

            # Switch input video to the second video
            mock_state["broll_input_video"] = str(other_video)
            # The cached stock video id belongs to the old video
            mock_state["broll_stock_video_id"] = "old_video_id_1"
            mock_state["broll_transcript_video_id"] = "old_video_id_1"

            with patch.object(st, "button", return_value=False):
                try:
                    render_broll_page(temp_dir)
                except Exception:
                    pass

            assert mock_state.get("broll_selected_clips") == [], "Selected clips must be wiped when video switches"
            assert mock_state.get("broll_selected_clip") is None, "broll_selected_clip must be None"
        print("[PASSED] TEST 8: Selections invalidated upon switching target videos (zero cross-video leakage).")

        # -------------------------------------------------------------
        # TEST 9: Streamlit reset_and_clear_all wipes selections
        # -------------------------------------------------------------
        print("\n[TEST 9] Testing reset_and_clear_all wipe...")
        mock_state["broll_selected_clips"] = copy.deepcopy(CLIPS_FIXTURE[:2])
        mock_state["broll_selected_clip"] = CLIPS_FIXTURE[0]
        with patch.object(st, "session_state", mock_state):
            with patch.object(st, "rerun"), patch.object(st, "success"):
                reset_and_clear_all(temp_dir)

            assert mock_state.get("broll_selected_clips") == []
            assert mock_state.get("broll_selected_clip") is None
        print("[PASSED] TEST 9: Reset and clear all wiped all selected clips cleanly.")

    print("\n==================================================")
    print("ALL STOCK MULTI-SELECTION TESTS PASSED (9/9)!")
    print("==================================================")


if __name__ == "__main__":
    run_stock_multiselect_tests()
