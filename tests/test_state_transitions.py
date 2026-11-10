import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from app.ui.state import AppState, set_state


class MockSessionState(dict):
    """Mock Streamlit session state object for deterministic unit testing."""
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value


def test_fsm_lifecycle():
    print("Testing FSM lifecycle states...")
    import streamlit as st

    mock_state = MockSessionState({
        "app_state": AppState.IDLE,
        "active_job_id": None,
        "completed_job_id": None,
        "uploaded_file_id": None,
        "input_video_path": None,
        "processed_video": None,
        "is_processing": False,
        "processing_complete": False,
        "error_message": None,
    })

    # Temporarily monkeypatch st.session_state
    st.session_state = mock_state

    # 1. Upload video
    assert st.session_state.app_state == AppState.IDLE
    set_state(AppState.UPLOADED)
    assert st.session_state.app_state == AppState.UPLOADED
    assert not st.session_state.is_processing
    assert not st.session_state.processing_complete

    # 2. Trigger processing
    set_state(AppState.PROCESSING)
    assert st.session_state.app_state == AppState.PROCESSING
    assert st.session_state.is_processing
    assert not st.session_state.processing_complete

    # 3. Processing completes
    set_state(AppState.COMPLETED)
    assert st.session_state.app_state == AppState.COMPLETED
    assert not st.session_state.is_processing
    assert st.session_state.processing_complete

    # 4. Preview / Download
    set_state(AppState.PREVIEW)
    assert st.session_state.app_state == AppState.PREVIEW
    assert not st.session_state.is_processing
    assert st.session_state.processing_complete

    set_state(AppState.EXPORTED)
    assert st.session_state.app_state == AppState.EXPORTED
    assert not st.session_state.is_processing
    assert st.session_state.processing_complete

    # 5. Failure scenario
    set_state(AppState.PROCESSING)
    set_state(AppState.FAILED)
    assert st.session_state.app_state == AppState.FAILED
    assert not st.session_state.is_processing
    assert not st.session_state.processing_complete

    # 6. Retry from failure
    set_state(AppState.PROCESSING)
    assert st.session_state.app_state == AppState.PROCESSING
    set_state(AppState.COMPLETED)
    assert st.session_state.app_state == AppState.COMPLETED

    print("[PASSED] State machine transitions are 100% compliant with specifications.")


if __name__ == "__main__":
    test_fsm_lifecycle()
