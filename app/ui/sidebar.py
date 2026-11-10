import streamlit as st
from app.ui.state import AppState, reset_and_clear_all
from pathlib import Path


def render_sidebar(temp_dir: Path):
    """
    Render the left sidebar matching the reference UI design:
    - App branding header
    - Navigation cards for Editor, AI B-roll, and Export
    - Bottom Processing Engine status indicator
    """
    with st.sidebar:
        # Branding Header
        st.markdown(
            """
            <style>
                /* Reduce the sidebar's top spacing */
                section[data-testid="stSidebar"] > div {
                    padding-top: 0rem;
                }
        
                /* Move branding slightly upward */
                .sidebar-brand-container {
                    margin-top: -1rem;
                }
            </style>
            
            <div class="sidebar-brand-container">
                <div class="brand-icon-box">
                    <span>▶</span>
                </div>
                <div>
                    <div class="brand-text-title">AI Video Editor</div>
                    <div class="brand-text-subtitle">Edit • Enhance • Add B-roll</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        current_page = st.session_state.get("current_page", "editor")

        # Navigation: Editor
        editor_active = (current_page == "editor")
        editor_btn_label = "Background & Effects" if not editor_active else "✦  Editor (Active)"
        if st.button(
            "Background & Effects",
            key="nav_editor_btn",
            use_container_width=True,
            type="primary" if editor_active else "secondary",
        ):
            if current_page != "editor":
                st.session_state.current_page = "editor"
                st.rerun()

        # Navigation: AI B-roll
        broll_active = (current_page == "broll")
        if st.button(
            "AI B-roll",
            key="nav_broll_btn",
            use_container_width=True,
            type="primary" if broll_active else "secondary",
        ):
            if current_page != "broll":
                st.session_state.current_page = "broll"
                st.rerun()

        # Navigation: Export
        export_active = (current_page == "export")
        if st.button(
            "Download processed video",
            key="nav_export_btn",
            use_container_width=True,
            type="primary" if export_active else "secondary",
        ):
            if current_page != "export":
                st.session_state.current_page = "export"
                st.rerun()

        st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)

        # Optional Reset button in sidebar for user convenience
        if st.button("Reset and Clear All", key="sidebar_reset_btn", use_container_width=True):
            reset_and_clear_all(temp_dir)

        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

        # Bottom Processing Engine Status Indicator Card
        app_state = st.session_state.get("app_state", AppState.IDLE)
        progress = st.session_state.get("processing_progress", 0.0)

        if app_state == AppState.PROCESSING:
            indicator_class = "processing"
            indicator_icon = "⏳"
            status_text = f"Processing ({int(progress * 100)}%)"
            bar_width = f"{int(progress * 100)}%"
        elif app_state == AppState.FAILED:
            indicator_class = "error"
            indicator_icon = "✕"
            status_text = "Error"
            bar_width = "100%"
        elif app_state in (AppState.COMPLETED, AppState.PREVIEW, AppState.EXPORTED):
            indicator_class = "ready"
            indicator_icon = "✓"
            status_text = "Completed"
            bar_width = "100%"
        else:
            indicator_class = "ready"
            indicator_icon = "✓"
            status_text = "Ready"
            bar_width = "100%"

        st.markdown(
            f"""
            <div class="engine-status-card">
                <div class="engine-status-header">
                    <div class="engine-status-indicator {indicator_class}">
                        {indicator_icon}
                    </div>
                    <div>
                        <div class="engine-status-title">Processing Engine</div>
                        <div class="engine-status-sub">{status_text}</div>
                    </div>
                </div>
                <div class="engine-progress-track">
                    <div class="engine-progress-bar" style="width: {bar_width};"></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
