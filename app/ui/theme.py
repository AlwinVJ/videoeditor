import streamlit as st


def apply_theme():
    """
    Inject custom CSS to reproduce the exact dark navy & purple accent design
    from the reference UI image.
    """
    custom_css = """
    <style>
    /* =====================================================================
       GLOBAL THEME & RESET
       ===================================================================== */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"], .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        background-color: #0b0d14 !important;
        color: #f1f2f6 !important;
    }

    /* Main container padding */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 1400px !important;
    }

    /* =====================================================================
       SIDEBAR STYLING & PERMANENT VISIBILITY
       ===================================================================== */
    section[data-testid="stSidebar"] {
        background-color: #12141e !important;
        border-right: 1px solid #1f2336 !important;
        width: 290px !important;
    }

    /* Completely hide the sidebar collapse button to prevent accidental collapsing */
    [data-testid="stSidebarCollapseButton"] {
        display: none !important;
    }

    /* Collapse the default empty sidebar header bar to eliminate top dead space */
    [data-testid="stSidebarHeader"] {
        display: none !important;
    }

    section[data-testid="stSidebar"] > div {
        padding-top: 1.25rem !important;
        padding-bottom: 1.5rem !important;
        padding-left: 1.25rem !important;
        padding-right: 1.25rem !important;
    }

    /* Ensure the expand button remains visible, styled, and accessible if ever collapsed */
    [data-testid="stExpandSidebarButton"] {
        visibility: visible !important;
        display: flex !important;
        color: #f1f2f6 !important;
        background: #12141e !important;
        border: 1px solid #1f2336 !important;
        border-radius: 8px !important;
        z-index: 1000 !important;
    }

    [data-testid="stExpandSidebarButton"]:hover {
        background: #1f2336 !important;
        border-color: #6c5ce7 !important;
    }

    /* Sidebar Logo Header */
    .sidebar-brand-container {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 2rem;
        padding-left: 4px;
    }

    .brand-icon-box {
        width: 40px;
        height: 40px;
        background: linear-gradient(135deg, #7c5cfc, #5b3ce6);
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
        color: white;
        box-shadow: 0 4px 12px rgba(124, 92, 252, 0.35);
    }

    .brand-text-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: #ffffff;
        line-height: 1.2;
    }

    .brand-text-subtitle {
        font-size: 0.72rem;
        color: #8b90a7;
        margin-top: 2px;
    }

    /* Sidebar Navigation Item */
    .sidebar-nav-card {
        padding: 12px 14px;
        border-radius: 12px;
        margin-bottom: 8px;
        transition: all 0.2s ease;
        cursor: pointer;
        display: flex;
        align-items: flex-start;
        gap: 12px;
        text-decoration: none !important;
    }

    .sidebar-nav-card.active {
        background: #6c5ce7;
        box-shadow: 0 4px 16px rgba(108, 92, 231, 0.4);
    }

    .sidebar-nav-card.active .nav-title {
        color: #ffffff !important;
        font-weight: 600;
    }

    .sidebar-nav-card.active .nav-subtitle {
        color: #e0dcfc !important;
    }

    .sidebar-nav-card.active .nav-icon {
        color: #ffffff !important;
    }

    .sidebar-nav-card.inactive {
        background: transparent;
        border: 1px solid transparent;
    }

    .sidebar-nav-card.inactive:hover {
        background: #181b2a;
        border-color: #262b42;
    }

    .sidebar-nav-card.inactive .nav-title {
        color: #d8dbe9 !important;
        font-weight: 500;
    }

    .sidebar-nav-card.inactive .nav-subtitle {
        color: #7b8098 !important;
    }

    .sidebar-nav-card.inactive .nav-icon {
        color: #9aa0ba !important;
    }

    .nav-title {
        font-size: 0.92rem;
        margin-bottom: 2px;
        line-height: 1.2;
    }

    .nav-subtitle {
        font-size: 0.72rem;
        line-height: 1.2;
    }

    /* Engine Status Widget */
    .engine-status-card {
        background: #161926;
        border: 1px solid #23273e;
        border-radius: 14px;
        padding: 14px;
        margin-top: auto;
        display: flex;
        flex-direction: column;
        gap: 8px;
    }

    .engine-status-header {
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .engine-status-indicator {
        width: 24px;
        height: 24px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 13px;
    }

    .engine-status-indicator.ready {
        background: rgba(16, 185, 129, 0.2);
        color: #10b981;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }

    .engine-status-indicator.processing {
        background: rgba(108, 92, 231, 0.2);
        color: #7c5cfc;
        border: 1px solid rgba(108, 92, 231, 0.3);
    }

    .engine-status-indicator.error {
        background: rgba(239, 68, 68, 0.2);
        color: #ef4444;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }

    .engine-status-title {
        font-size: 0.85rem;
        font-weight: 600;
        color: #ffffff;
        margin: 0;
    }

    .engine-status-sub {
        font-size: 0.72rem;
        color: #8b90a7;
        margin: 0;
    }

    .engine-progress-track {
        width: 100%;
        height: 4px;
        background: #23273e;
        border-radius: 2px;
        overflow: hidden;
    }

    .engine-progress-bar {
        height: 100%;
        background: #7c5cfc;
        border-radius: 2px;
    }

    /* =====================================================================
       CARDS & PANELS
       ===================================================================== */
    .editor-card {
        background: #141622;
        border: 1px solid #22263a;
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
    }

    .editor-card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 16px;
    }

    .card-title-group {
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .card-step-badge {
        width: 24px;
        height: 24px;
        border-radius: 50%;
        background: #6c5ce7;
        color: white;
        font-size: 12px;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .card-title-text {
        font-size: 1.05rem;
        font-weight: 600;
        color: #ffffff;
        margin: 0;
    }

    /* =====================================================================
       HEADER
       ===================================================================== */
    .page-header-container {
        display: flex;
        align-items: center;
        gap: 16px;
        margin-bottom: 24px;
    }

    .header-icon-box {
        width: 44px;
        height: 44px;
        background: #1a1c2a;
        border: 1px solid #2b2f48;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 22px;
    }

    .header-text-title {
        font-size: 1.65rem;
        font-weight: 700;
        color: #ffffff;
        margin: 0;
        line-height: 1.2;
    }

    .header-text-desc {
        font-size: 0.88rem;
        color: #8b90a7;
        margin-top: 4px;
        margin-bottom: 0;
    }

    /* =====================================================================
       UPLOAD COMPONENT
       ===================================================================== */
    .file-info-chip {
        background: #1a1d2d;
        border: 1px solid #282d44;
        border-radius: 12px;
        padding: 10px 14px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-top: 14px;
    }

    .file-info-left {
        display: flex;
        align-items: center;
        gap: 12px;
    }

    .file-thumb-icon {
        width: 38px;
        height: 38px;
        border-radius: 8px;
        background: #252a3f;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 16px;
        color: #a2a8c2;
    }

    .file-name-text {
        font-size: 0.88rem;
        font-weight: 600;
        color: #f1f2f6;
        margin: 0;
    }

    .file-meta-text {
        font-size: 0.72rem;
        color: #7b8098;
        margin-top: 2px;
        margin-bottom: 0;
    }

    /* =====================================================================
       PREVIEW CONTROLS & BADGES
       ===================================================================== */
    .video-frame-container {
        position: relative;
        border-radius: 12px;
        overflow: hidden;
        background: #0f111a;
        border: 1px solid #22263a;
    }

    .preview-badge-overlay {
        position: absolute;
        top: 10px;
        left: 10px;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.3px;
        z-index: 10;
        pointer-events: none;
    }

    .badge-original {
        background: rgba(30, 34, 52, 0.85);
        color: #d1d5db;
        border: 1px solid rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(4px);
    }

    .badge-processed {
        background: rgba(108, 92, 231, 0.9);
        color: #ffffff;
        border: 1px solid rgba(255, 255, 255, 0.2);
        backdrop-filter: blur(4px);
        box-shadow: 0 2px 8px rgba(108, 92, 231, 0.4);
    }

    /* =====================================================================
       STATUS BANNER
       ===================================================================== */
    .status-banner-card {
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.25);
        border-radius: 12px;
        padding: 12px 16px;
        display: flex;
        align-items: center;
        gap: 14px;
        margin-top: 14px;
    }

    .status-banner-card.error {
        background: rgba(239, 68, 68, 0.1);
        border-color: rgba(239, 68, 68, 0.25);
    }

    .status-banner-card.processing {
        background: rgba(108, 92, 231, 0.1);
        border-color: rgba(108, 92, 231, 0.25);
    }

    .status-banner-icon {
        width: 32px;
        height: 32px;
        border-radius: 8px;
        background: #10b981;
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 16px;
        flex-shrink: 0;
    }

    .status-banner-icon.error {
        background: #ef4444;
    }

    .status-banner-icon.processing {
        background: #6c5ce7;
    }

    .status-banner-title {
        font-size: 0.88rem;
        font-weight: 600;
        color: #ffffff;
        margin: 0;
    }

    .status-banner-desc {
        font-size: 0.74rem;
        color: #9ca3af;
        margin-top: 2px;
        margin-bottom: 0;
    }

    /* =====================================================================
       STREAMLIT NATIVE COMPONENT OVERRIDES
       ===================================================================== */
    /* Selectboxes */
    div[data-baseweb="select"] {
        background-color: #1a1d2c !important;
        border: 1px solid #282d42 !important;
        border-radius: 10px !important;
    }

    div[data-baseweb="select"] * {
        color: #ffffff !important;
        font-size: 0.88rem !important;
    }

    /* Sliders */
    div[data-testid="stSlider"] > div > div > div > div {
        background-color: #6c5ce7 !important;
    }

    /* Buttons */
    div.stButton > button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        transition: all 0.2s ease !important;
        border: none !important;
    }

    /* Primary Process Button */
    button[data-testid="baseButton-primary"], .primary-action-btn button {
        background: #6c5ce7 !important;
        color: #ffffff !important;
        box-shadow: 0 4px 14px rgba(108, 92, 231, 0.35) !important;
    }

    button[data-testid="baseButton-primary"]:hover, .primary-action-btn button:hover {
        background: #5b4bd8 !important;
        box-shadow: 0 6px 20px rgba(108, 92, 231, 0.5) !important;
    }

    /* Secondary Action Button (Download) */
    .secondary-action-btn button, div[data-testid="stDownloadButton"] > button {
        background: #1a1d2c !important;
        color: #ffffff !important;
        border: 1px solid #2f354e !important;
    }

    .secondary-action-btn button:hover, div[data-testid="stDownloadButton"] > button:hover {
        background: #24283c !important;
        border-color: #484f72 !important;
    }

    /* File uploader styling */
    div[data-testid="stFileUploader"] {
        background: transparent !important;
    }

    div[data-testid="stFileUploader"] > section {
        background: #141724 !important;
        border: 1.5px dashed #2e3450 !important;
        border-radius: 12px !important;
        padding: 1.5rem 1rem !important;
        transition: all 0.2s ease !important;
    }

    div[data-testid="stFileUploader"] > section:hover {
        border-color: #6c5ce7 !important;
        background: #171b2b !important;
    }

    /* =====================================================================
       STREAMLIT CHROME OVERRIDES
       ===================================================================== */
    /* Hide Streamlit hamburger menu and footer WITHOUT hiding the header container */
    #MainMenu {
        visibility: hidden !important;
        display: none !important;
    }

    footer {
        visibility: hidden !important;
        display: none !important;
    }

    /* Hide deploy button and extra toolbar actions */
    [data-testid="stToolbarActions"],
    [data-testid="stDeployButton"] {
        display: none !important;
    }

    /* Keep header transparent so expand button is visible if ever needed */
    header[data-testid="stHeader"] {
        background: transparent !important;
    }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)
