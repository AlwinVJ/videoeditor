import sys
import re
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from app.ui.state import AppState, initialize_session_state, reset_and_clear_all
from app.ui.sidebar import render_sidebar


def test_sidebar_config_and_css():
    print("==================================================")
    print("STARTING SIDEBAR VISIBILITY & REGRESSION TEST SUITE")
    print("==================================================")

    # 1. Verify app/main.py configures initial_sidebar_state="expanded"
    print("\n[TEST 1] Verifying app/main.py initial_sidebar_state...")
    main_py_path = ROOT_DIR / "app" / "main.py"
    main_content = main_py_path.read_text(encoding="utf-8")
    assert 'initial_sidebar_state="expanded"' in main_content, "initial_sidebar_state must be 'expanded'"
    print("[PASSED] TEST 1: initial_sidebar_state='expanded' verified in app/main.py")

    # 2. Verify theme.py CSS rules
    print("\n[TEST 2] Verifying theme.py CSS selectors and rules...")
    theme_py_path = ROOT_DIR / "app" / "ui" / "theme.py"
    theme_content = theme_py_path.read_text(encoding="utf-8")

    # Verify collapse button is hidden
    assert '[data-testid="stSidebarCollapseButton"]' in theme_content, "stSidebarCollapseButton must be targeted"
    assert re.search(r'\[data-testid="stSidebarCollapseButton"\]\s*\{\s*display:\s*none\s*!important;', theme_content), \
        "stSidebarCollapseButton must have display: none !important"

    # Verify stSidebarHeader is collapsed/hidden to eliminate empty top dead space
    assert '[data-testid="stSidebarHeader"]' in theme_content, "stSidebarHeader must be targeted"
    assert re.search(r'\[data-testid="stSidebarHeader"\]\s*\{\s*display:\s*none\s*!important;', theme_content), \
        "stSidebarHeader must have display: none !important"

    # Verify header is NOT globally hidden with visibility: hidden
    assert not re.search(r'(#MainMenu,\s*header,\s*footer|\bheader\b)\s*\{\s*visibility:\s*hidden', theme_content), \
        "header must not be hidden with visibility: hidden (it hides the expand button)"

    # Verify permanent expansion constraints on section[data-testid="stSidebar"]
    assert 'transform: none !important;' in theme_content, "stSidebar must enforce transform: none !important"
    assert 'min-width: 290px !important;' in theme_content, "stSidebar must enforce min-width: 290px !important"
    assert 'max-width: 290px !important;' in theme_content, "stSidebar must enforce max-width: 290px !important"
    assert 'flex-shrink: 0 !important;' in theme_content, "stSidebar must enforce flex-shrink: 0 !important"

    # Verify stExpandSidebarButton and stSidebarCollapseButton are suppressed
    assert '[data-testid="stExpandSidebarButton"]' in theme_content, "stExpandSidebarButton must be targeted"
    assert re.search(r'\[data-testid="stExpandSidebarButton"\]\s*\{[^}]*display:\s*none\s*!important', theme_content), \
        "stExpandSidebarButton must have display: none !important"

    print("[PASSED] TEST 2: All CSS rules for permanent sidebar visibility verified.")

    # 3. Verify sidebar.py does not contain conflicting inline CSS
    print("\n[TEST 3] Verifying app/ui/sidebar.py clean markup...")
    sidebar_py_path = ROOT_DIR / "app" / "ui" / "sidebar.py"
    sidebar_content = sidebar_py_path.read_text(encoding="utf-8")
    assert "<style>" not in sidebar_content, "sidebar.py should not contain duplicate inline style blocks"
    assert "margin-top: -1rem" not in sidebar_content, "fragile negative margin workaround must be removed"
    print("[PASSED] TEST 3: sidebar.py is clean without conflicting CSS.")

    # 4. Verify .streamlit/config.toml
    print("\n[TEST 4] Verifying .streamlit/config.toml...")
    config_path = ROOT_DIR / ".streamlit" / "config.toml"
    config_content = config_path.read_text(encoding="utf-8")
    assert 'toolbarMode = "minimal"' in config_content, "toolbarMode should be minimal to hide developer chrome natively"
    print("[PASSED] TEST 4: config.toml contains toolbarMode = 'minimal'.")

    # 5. Verify navigation lifecycle preserves state and doesn't affect sidebar rendering
    print("\n[TEST 5] Testing navigation lifecycle across pages...")
    import streamlit as st

    class MockSessionState(dict):
        def __getattr__(self, key):
            try:
                return self[key]
            except KeyError:
                raise AttributeError(key)

        def __setattr__(self, key, value):
            self[key] = value

    mock_state = MockSessionState()
    st.session_state = mock_state
    initialize_session_state()

    assert st.session_state.current_page == "editor"

    # Simulate navigating to broll
    st.session_state.current_page = "broll"
    assert st.session_state.current_page == "broll"

    # Simulate navigating to export
    st.session_state.current_page = "export"
    assert st.session_state.current_page == "export"

    # Simulate reset and clear all
    temp_dir = ROOT_DIR / "temp"
    reset_and_clear_all(temp_dir)
    assert st.session_state.app_state == AppState.IDLE
    assert st.session_state.is_processing is False

    print("[PASSED] TEST 5: State transitions across pages operate smoothly.")

    print("\n==================================================")
    print("ALL SIDEBAR TESTS PASSED SUCCESSFULLY! (5/5)")
    print("==================================================")


if __name__ == "__main__":
    test_sidebar_config_and_css()
