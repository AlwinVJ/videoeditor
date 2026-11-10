import sys
import tempfile
import cv2
import numpy as np
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from app.ui.state import AppState, initialize_session_state, reset_and_clear_all, set_state
from app.ui.broll import render_broll_page, save_broll_upload


class MockSessionState(dict):
    """Mock Streamlit session state object for deterministic unit testing."""
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


def create_dummy_mp4(filepath: Path):
    """Create a minimal valid MP4 video using OpenCV."""
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(filepath), fourcc, 24.0, (320, 240))
    for _ in range(24):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        frame[:, :] = (120, 80, 200)
        out.write(frame)
    out.release()


def run_all_tests():
    print("==================================================")
    print("STARTING AI B-ROLL PAGE INTEGRATION TEST SUITE")
    print("==================================================")

    import streamlit as st
    temp_dir = ROOT_DIR / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------
    # TEST A: Transferred Video Workflow
    # -------------------------------------------------------------
    print("\n[TEST A] Testing Editor-to-B-roll transferred video workflow...")
    st.session_state = MockSessionState()
    initialize_session_state()

    # Simulate Editor processing completion via valid FSM path
    test_proc_video = temp_dir / "test_processed_output.mp4"
    create_dummy_mp4(test_proc_video)
    set_state(AppState.UPLOADED)
    set_state(AppState.PROCESSING)
    set_state(AppState.COMPLETED)
    st.session_state.processed_video = str(test_proc_video)

    # Simulate user clicking "Continue with B-roll Editing" in editor.py
    assert st.session_state.app_state == AppState.COMPLETED
    st.session_state["broll_input_video"] = str(test_proc_video)
    st.session_state["broll_source"] = "transferred"
    st.session_state["current_page"] = "broll"

    # Verify AppState was NOT changed to EXPORTED
    assert st.session_state.app_state == AppState.COMPLETED, f"Expected COMPLETED, got {st.session_state.app_state}"
    assert st.session_state.current_page == "broll"
    assert st.session_state.broll_input_video == str(test_proc_video)
    assert Path(st.session_state.broll_input_video).exists()
    assert Path(st.session_state.broll_input_video).stat().st_size > 0

    # Call render_broll_page with mock
    render_broll_page(temp_dir)
    assert st.session_state.broll_input_video == str(test_proc_video)
    assert test_proc_video.exists(), "Processed video file must not be deleted"
    print("[PASSED] TEST A: Video transfer preserves file, session state, and valid AppState.")

    # -------------------------------------------------------------
    # TEST B: Direct B-roll Access & Direct Upload
    # -------------------------------------------------------------
    print("\n[TEST B] Testing direct B-roll access and direct video upload...")
    st.session_state = MockSessionState()
    initialize_session_state()

    # Direct access: no processed video available
    assert st.session_state.processed_video is None
    assert st.session_state.broll_input_video is None
    render_broll_page(temp_dir)

    # Simulate direct upload via save_broll_upload
    mock_upload = MockUploadedFile("my_direct_broll.mp4", b"\x00" * 4096)
    saved_path = save_broll_upload(mock_upload, temp_dir)

    assert saved_path.exists()
    assert st.session_state.broll_input_video == str(saved_path)
    assert st.session_state.broll_source == "uploaded"
    # Editor's state must remain IDLE (no side effects on Editor)
    assert st.session_state.app_state == AppState.IDLE
    assert st.session_state.input_video_path is None
    print("[PASSED] TEST B: Direct B-roll upload operates cleanly without side effects on Editor.")

    # -------------------------------------------------------------
    # TEST C: Streamlit Reruns & Idempotency
    # -------------------------------------------------------------
    print("\n[TEST C] Testing Streamlit reruns preservation...")
    prior_path = st.session_state.broll_input_video
    render_broll_page(temp_dir)
    # The active video must remain preserved across reruns
    assert st.session_state.broll_input_video == prior_path
    assert Path(prior_path).exists()
    print("[PASSED] TEST C: Selected video remains intact across Streamlit reruns.")

    # -------------------------------------------------------------
    # TEST D: Invalid / Missing Video Reference Handling
    # -------------------------------------------------------------
    print("\n[TEST D] Testing graceful handling of missing or invalid video paths...")
    st.session_state.broll_input_video = str(temp_dir / "non_existent_ghost_file.mp4")
    st.session_state.processed_video = None
    render_broll_page(temp_dir)
    # Stale reference should be cleared and fallback gracefully
    assert st.session_state.broll_input_video is None
    print("[PASSED] TEST D: Missing video files handled gracefully without crashing.")

    # -------------------------------------------------------------
    # TEST E: Existing Functionality & Widget Keys Check
    # -------------------------------------------------------------
    print("\n[TEST E] Testing widget keys uniqueness and column context managers...")
    editor_code = (ROOT_DIR / "app" / "ui" / "editor.py").read_text(encoding="utf-8")
    broll_code = (ROOT_DIR / "app" / "ui" / "broll.py").read_text(encoding="utf-8")
    export_code = (ROOT_DIR / "app" / "ui" / "export.py").read_text(encoding="utf-8")

    # Check for invalid with st.columns
    assert "with st.columns" not in editor_code, "Invalid 'with st.columns' found in editor.py"
    assert "with st.columns" not in broll_code, "Invalid 'with st.columns' found in broll.py"
    assert "with st.columns" not in export_code, "Invalid 'with st.columns' found in export.py"

    # Check keys uniqueness across files
    editor_keys = [k for k in ["primary_download_video_action_btn", "continue_to_broll_btn", "primary_process_video_action_btn"]]
    for k in editor_keys:
        assert broll_code.count(f'key="{k}"') == 0, f"Duplicate key {k} found in broll.py"
        assert export_code.count(f'key="{k}"') == 0, f"Duplicate key {k} found in export.py"

    # Reset and clear all verification
    reset_and_clear_all(temp_dir)
    assert st.session_state.app_state == AppState.IDLE
    assert st.session_state.broll_input_video is None
    assert st.session_state.broll_source is None
    assert st.session_state.broll_preview_active is False
    print("[PASSED] TEST E: Widget keys are unique, columns are valid, reset operates cleanly.")

    # Clean up test artifacts
    if test_proc_video.exists():
        test_proc_video.unlink()
    if saved_path.exists():
        saved_path.unlink()

    print("\n==================================================")
    print("ALL AI B-ROLL INTEGRATION TESTS PASSED (5/5)!")
    print("==================================================")


if __name__ == "__main__":
    run_all_tests()
