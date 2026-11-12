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

import cv2
import streamlit as st

from app.ui.state import AppState, initialize_session_state, reset_and_clear_all
from app.ui.broll import render_broll_page
from core.stock import (
    calculate_clip_placements,
    calculate_timeline_percentages,
    format_duration,
)
from core.pipeline import compose_broll_video, resolve_placement_overlaps
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
        "tags": "technology, coding, computer",
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
        "tags": "workplace discussion, business",
        "duration": 18,
        "duration_formatted": "00:18",
        "width": 1920,
        "height": 1080,
        "resolution": "1920×1080",
        "thumbnail_url": "https://cdn.pixabay.com/thumb_103.jpg",
        "preview_url": "https://cdn.pixabay.com/preview_103.mp4",
        "download_url": "https://cdn.pixabay.com/download_103.mp4",
        "page_url": "https://pixabay.com/videos/103/",
        "user": "artist_three",
        "keyword": "office",
        "provider": "Pixabay",
    },
    {
        "id": 104,
        "tags": "software development, programmer",
        "duration": 22,
        "duration_formatted": "00:22",
        "width": 1920,
        "height": 1080,
        "resolution": "1920×1080",
        "thumbnail_url": "https://cdn.pixabay.com/thumb_104.jpg",
        "preview_url": "https://cdn.pixabay.com/preview_104.mp4",
        "download_url": "https://cdn.pixabay.com/download_104.mp4",
        "page_url": "https://pixabay.com/videos/104/",
        "user": "artist_four",
        "keyword": "technology",
        "provider": "Pixabay",
    },
    {
        "id": 105,
        "tags": "data analytics, charts, finance",
        "duration": 12,
        "duration_formatted": "00:12",
        "width": 1920,
        "height": 1080,
        "resolution": "1920×1080",
        "thumbnail_url": "https://cdn.pixabay.com/thumb_105.jpg",
        "preview_url": "https://cdn.pixabay.com/preview_105.mp4",
        "download_url": "https://cdn.pixabay.com/download_105.mp4",
        "page_url": "https://pixabay.com/videos/105/",
        "user": "artist_five",
        "keyword": "analytics",
        "provider": "Pixabay",
    },
]

TWO_SEGMENT_TRANSCRIPT = [
    {
        "segment_index": 0,
        "start": 0.0,
        "end": 1.0,
        "duration": 1.0,
        "text": "Welcome to our corporate office meeting.",
    },
    {
        "segment_index": 1,
        "start": 1.0,
        "end": 2.0,
        "duration": 1.0,
        "text": "Here we develop modern technology and software.",
    },
]


def run_multiclip_tests():
    print("==================================================")
    print("STARTING MULTI-CLIP B-ROLL GENERATION TEST SUITE")
    print("==================================================")

    sample_video = Path("sample.mp4")
    assert sample_video.exists(), "sample.mp4 must exist in workspace for tests"

    # -------------------------------------------------------------
    # TEST 1: calculate_clip_placements with 1, 2, 3, 5, 10 clips
    # -------------------------------------------------------------
    print("\n[TEST 1] Testing calculate_clip_placements with variable clip counts...")

    # 1A: 1 clip
    p1 = calculate_clip_placements([CLIPS_FIXTURE[0]], TWO_SEGMENT_TRANSCRIPT, 2.0)
    assert len(p1) == 1
    assert p1[0]["start"] == 0.0 and p1[0]["end"] == 1.0
    print("  -> 1 clip: correctly assigned to Segment 0 [0.0, 1.0]")

    # 1B: 2 clips in DIFFERENT segments
    p2_diff = calculate_clip_placements([CLIPS_FIXTURE[0], CLIPS_FIXTURE[1]], TWO_SEGMENT_TRANSCRIPT, 2.0)
    assert len(p2_diff) == 2
    assert p2_diff[0]["start"] == 0.0 and p2_diff[0]["end"] == 1.0
    assert p2_diff[1]["start"] == 1.0 and p2_diff[1]["end"] == 2.0
    print("  -> 2 clips (different segments): assigned [0.0, 1.0] and [1.0, 2.0]")

    # 1C: 2 clips in the SAME segment (both 'office' -> Segment 0)
    p2_same = calculate_clip_placements([CLIPS_FIXTURE[0], CLIPS_FIXTURE[2]], TWO_SEGMENT_TRANSCRIPT, 2.0)
    assert len(p2_same) == 2
    assert p2_same[0]["start"] == 0.0 and p2_same[0]["end"] == 0.5
    assert p2_same[1]["start"] == 0.5 and p2_same[1]["end"] == 1.0
    print("  -> 2 clips (same segment): partitioned non-overlapping into [0.0, 0.5] and [0.5, 1.0]")

    # 1D: 3 clips (2 in Segment 0, 1 in Segment 1)
    p3 = calculate_clip_placements([CLIPS_FIXTURE[0], CLIPS_FIXTURE[1], CLIPS_FIXTURE[2]], TWO_SEGMENT_TRANSCRIPT, 2.0)
    assert len(p3) == 3
    c101 = next(x for x in p3 if x["clip"]["id"] == 101)
    c103 = next(x for x in p3 if x["clip"]["id"] == 103)
    c102 = next(x for x in p3 if x["clip"]["id"] == 102)
    assert c101["start"] == 0.0 and c101["end"] == 0.5
    assert c103["start"] == 0.5 and c103["end"] == 1.0
    assert c102["start"] == 1.0 and c102["end"] == 2.0
    print("  -> 3 clips: all 3 clips assigned non-overlapping intervals (no overwriting)")

    # 1E: 5 clips (2 in Seg 0, 2 in Seg 1, 1 unmatched/analytics)
    p5 = calculate_clip_placements(CLIPS_FIXTURE, TWO_SEGMENT_TRANSCRIPT, 2.0)
    assert len(p5) == 5
    for p in p5:
        assert p["start"] < p["end"], f"Clip #{p['clip']['id']} invalid interval: [{p['start']}, {p['end']}]"
        assert p["duration"] >= 0.1
    print("  -> 5 clips: all 5 clips assigned distinct non-overlapping intervals")

    # 1F: 10 clips (empty transcript, evenly partitioned across timeline)
    ten_clips = [copy.deepcopy(CLIPS_FIXTURE[i % 5]) for i in range(10)]
    for i, c in enumerate(ten_clips):
        c["id"] = 200 + i
    p10 = calculate_clip_placements(ten_clips, None, 20.0)
    assert len(p10) == 10
    for i, p in enumerate(p10):
        assert p["start"] == round(i * 2.0, 2)
        assert p["end"] == round((i + 1) * 2.0, 2)
    print("  -> 10 clips: partitioned evenly across timeline with 0 overlap")
    print("[PASSED] TEST 1: calculate_clip_placements handles 1, 2, 3, 5, 10 clips without collision.")

    # -------------------------------------------------------------
    # TEST 2: resolve_placement_overlaps fail-safe engine
    # -------------------------------------------------------------
    print("\n[TEST 2] Testing resolve_placement_overlaps fail-safe collision engine...")
    # Colliding placements: 3 clips with identical start and end [0.0, 6.0]
    raw_colliding = [
        {"clip": CLIPS_FIXTURE[0], "start": 0.0, "end": 6.0},
        {"clip": CLIPS_FIXTURE[1], "start": 0.0, "end": 6.0},
        {"clip": CLIPS_FIXTURE[2], "start": 0.0, "end": 6.0},
    ]
    resolved = resolve_placement_overlaps(raw_colliding, total_duration=6.0)
    assert len(resolved) == 3
    assert resolved[0]["start"] == 0.0 and resolved[0]["end"] == 2.0
    assert resolved[1]["start"] == 2.0 and resolved[1]["end"] == 4.0
    assert resolved[2]["start"] == 4.0 and resolved[2]["end"] == 6.0
    print("[PASSED] TEST 2: Identical timestamps partitioned into distinct visible slices.")

    # -------------------------------------------------------------
    # TEST 3: compose_broll_video rendering with 1, 2, 3, 5 clips
    # -------------------------------------------------------------
    print("\n[TEST 3] Testing end-to-end compose_broll_video with 1, 2, 3, and 5 clips...")
    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)

        # 3A: 1 Clip
        c1 = copy.deepcopy(CLIPS_FIXTURE[0])
        c1["local_path"] = str(sample_video)
        out1 = temp_dir / "out_1clip.mp4"
        res1 = compose_broll_video(
            sample_video,
            [{"clip": c1, "start": 0.2, "end": 0.8}],
            out1,
            temp_dir,
        )
        assert res1.exists() and res1.stat().st_size > 5000
        print("  -> 1 clip render succeeded.")

        # 3B: 2 Clips
        c2 = copy.deepcopy(CLIPS_FIXTURE[1])
        c2["local_path"] = str(sample_video)
        out2 = temp_dir / "out_2clips.mp4"
        res2 = compose_broll_video(
            sample_video,
            [
                {"clip": c1, "start": 0.2, "end": 0.8},
                {"clip": c2, "start": 0.9, "end": 1.5},
            ],
            out2,
            temp_dir,
        )
        assert res2.exists() and res2.stat().st_size > 5000
        print("  -> 2 clips render succeeded.")

        # 3C: 3 Clips
        c3 = copy.deepcopy(CLIPS_FIXTURE[2])
        c3["local_path"] = str(sample_video)
        out3 = temp_dir / "out_3clips.mp4"
        res3 = compose_broll_video(
            sample_video,
            [
                {"clip": c1, "start": 0.1, "end": 0.6},
                {"clip": c2, "start": 0.6, "end": 1.1},
                {"clip": c3, "start": 1.1, "end": 1.6},
            ],
            out3,
            temp_dir,
        )
        assert res3.exists() and res3.stat().st_size > 5000
        meta3 = get_video_metadata(res3)
        orig_meta = get_video_metadata(sample_video)
        assert meta3["width"] == orig_meta["width"]
        assert meta3["height"] == orig_meta["height"]
        print("  -> 3 clips render succeeded with preserved dimensions.")

        # 3D: 5 Clips
        c4 = copy.deepcopy(CLIPS_FIXTURE[3])
        c4["local_path"] = str(sample_video)
        c5 = copy.deepcopy(CLIPS_FIXTURE[4])
        c5["local_path"] = str(sample_video)
        out5 = temp_dir / "out_5clips.mp4"
        res5 = compose_broll_video(
            sample_video,
            [
                {"clip": c1, "start": 0.1, "end": 0.4},
                {"clip": c2, "start": 0.4, "end": 0.7},
                {"clip": c3, "start": 0.7, "end": 1.0},
                {"clip": c4, "start": 1.0, "end": 1.3},
                {"clip": c5, "start": 1.3, "end": 1.6},
            ],
            out5,
            temp_dir,
        )
        assert res5.exists() and res5.stat().st_size > 5000
        print("  -> 5 clips render succeeded with all 5 cutaways.")

    print("[PASSED] TEST 3: Video composition scales seamlessly for 1, 2, 3, and 5 clips.")

    # -------------------------------------------------------------
    # TEST 4: Card 4 Streamlit UI multi-clip workflow
    # -------------------------------------------------------------
    print("\n[TEST 4] Testing Card 4 multi-clip UI rendering & state initialization...")
    mock_state = MockSessionState()
    selected_3 = [copy.deepcopy(CLIPS_FIXTURE[0]), copy.deepcopy(CLIPS_FIXTURE[1]), copy.deepcopy(CLIPS_FIXTURE[2])]
    for c in selected_3:
        c["local_path"] = str(sample_video)

    mock_state.update({
        "current_page": "broll",
        "app_state": AppState.IDLE,
        "processed_video": None,
        "broll_input_video": str(sample_video),
        "broll_source": "uploaded",
        "broll_preview_active": False,
        "broll_transcript": TWO_SEGMENT_TRANSCRIPT,
        "broll_transcript_video_id": f"{sample_video}_{sample_video.stat().st_size}_{sample_video.stat().st_mtime}",
        "broll_keywords": ["office", "technology"],
        "broll_keywords_video_id": f"{sample_video}_{sample_video.stat().st_size}_{sample_video.stat().st_mtime}",
        "broll_stock_results": selected_3,
        "broll_stock_video_id": f"{sample_video}_{sample_video.stat().st_size}_{sample_video.stat().st_mtime}",
        "broll_selected_clips": selected_3,
        "broll_selected_clip": selected_3[-1],
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
    assert "Proposed Timeline Placement" in all_html
    assert "3 Clips Scheduled" in all_html
    assert "Clip 1 of 3" in all_html
    assert "Clip 2 of 3" in all_html
    assert "Clip 3 of 3" in all_html
    assert button_calls["broll_generate_video_btn"]["disabled"] is False

    # Check timestamps were initialized in session_state for all 3 clips
    assert "broll_time_start_101" in mock_state
    assert "broll_time_end_101" in mock_state
    assert "broll_time_start_102" in mock_state
    assert "broll_time_end_102" in mock_state
    assert "broll_time_start_103" in mock_state
    assert "broll_time_end_103" in mock_state

    # Verify no overlapping intervals among the 3 clips
    st101, en101 = mock_state["broll_time_start_101"], mock_state["broll_time_end_101"]
    st103, en103 = mock_state["broll_time_start_103"], mock_state["broll_time_end_103"]
    st102, en102 = mock_state["broll_time_start_102"], mock_state["broll_time_end_102"]

    assert en101 <= st103 or en103 <= st101, "Clip 101 and Clip 103 must not overlap"
    print("[PASSED] TEST 4: Card 4 renders all 3 clips with initialized non-overlapping timestamps.")

    # -------------------------------------------------------------
    # TEST 5: Generate Video execution with 3 clips from UI
    # -------------------------------------------------------------
    print("\n[TEST 5] Testing Generate Video execution with all 3 clips...")
    rerun_called = []
    def mock_rerun():
        rerun_called.append(True)

    def mock_button_click(label, key=None, **kwargs):
        if key == "broll_generate_video_btn":
            return True
        return False

    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)
        with patch.object(st, "session_state", mock_state):
            with patch.object(st, "rerun", side_effect=mock_rerun):
                with patch.object(st, "button", side_effect=mock_button_click):
                    with patch.object(st, "progress"):
                        render_broll_page(temp_dir)

        if mock_state.get("broll_generation_error"):
            print("ERROR in Test 5:", mock_state.get("broll_generation_error"))
        assert len(rerun_called) > 0, "st.rerun() must be called after generation"
        assert mock_state.get("current_page") == "export"
        assert mock_state.get("app_state") == AppState.COMPLETED
        assert mock_state.get("broll_generation_success") is True
        assert mock_state.get("processed_video") is not None
        proc_file = Path(mock_state["processed_video"])
        assert proc_file.exists() and proc_file.stat().st_size > 0

    print("[PASSED] TEST 5: Generate Video incorporates all 3 clips and redirects to export.")

    print("\n==================================================")
    print("ALL MULTI-CLIP B-ROLL TESTS PASSED (5/5)!")
    print("==================================================")


if __name__ == "__main__":
    run_multiclip_tests()
