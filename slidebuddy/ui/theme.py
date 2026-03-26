"""Dark Fintech Theme — global CSS injection for SlideBuddy."""

import streamlit as st

_THEME_CSS = """
<style>
/* ===== ROOT VARIABLES ===== */
:root {
    --bg-primary: #0F0F1A;
    --bg-card: #1E1E30;
    --bg-card-hover: #252540;
    --bg-input: #16162A;
    --border-subtle: #2A2A3D;
    --border-focus: #6C5CE7;
    --accent: #6C5CE7;
    --accent-light: #a855f7;
    --accent-glow: rgba(108, 92, 231, 0.3);
    --text-primary: #E8E8F0;
    --text-secondary: #8B8B9E;
    --text-muted: #5A5A72;
    --success: #10B981;
    --warning: #F59E0B;
    --error: #EF4444;
    --info: #3B82F6;
}

/* ===== GLOBAL ===== */
.stApp {
    background: var(--bg-primary) !important;
}

/* ===== SIDEBAR ===== */
section[data-testid="stSidebar"] {
    background: #0A0A14 !important;
    border-right: 1px solid var(--border-subtle) !important;
}

section[data-testid="stSidebar"] .stMarkdown h1 {
    background: linear-gradient(135deg, var(--accent), var(--accent-light));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

/* ===== BUTTONS ===== */
.stButton > button {
    background: linear-gradient(135deg, var(--accent), var(--accent-light)) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 2px 8px var(--accent-glow) !important;
}

.stButton > button:hover {
    box-shadow: 0 4px 20px var(--accent-glow) !important;
    transform: translateY(-1px) !important;
}

.stButton > button:disabled {
    background: var(--bg-card) !important;
    color: var(--text-muted) !important;
    box-shadow: none !important;
    transform: none !important;
}

/* Secondary buttons (sidebar) */
section[data-testid="stSidebar"] .stButton > button {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-subtle) !important;
    box-shadow: none !important;
}

section[data-testid="stSidebar"] .stButton > button:hover {
    background: var(--bg-card-hover) !important;
    border-color: var(--accent) !important;
    box-shadow: 0 2px 12px var(--accent-glow) !important;
}

/* ===== CONTAINERS / CARDS ===== */
div[data-testid="stExpander"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 12px !important;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3) !important;
    transition: all 0.3s ease !important;
}

div[data-testid="stExpander"]:hover {
    border-color: var(--accent) !important;
    box-shadow: 0 4px 20px var(--accent-glow) !important;
}

/* Bordered containers */
div[data-testid="stVerticalBlock"] > div[style*="border"] {
    border-color: var(--border-subtle) !important;
    border-radius: 12px !important;
    background: var(--bg-card) !important;
}

/* ===== INPUTS ===== */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div,
.stMultiselect > div > div {
    background-color: var(--bg-input) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 8px !important;
    color: var(--text-primary) !important;
    transition: border-color 0.3s ease !important;
}

.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px var(--accent-glow) !important;
}

/* ===== TABS ===== */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px !important;
    background: var(--bg-card) !important;
    border-radius: 10px !important;
    padding: 4px !important;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important;
    color: var(--text-secondary) !important;
    font-weight: 500 !important;
    transition: all 0.2s ease !important;
}

.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, var(--accent), var(--accent-light)) !important;
    color: white !important;
}

.stTabs [data-baseweb="tab-highlight"] {
    display: none !important;
}

.stTabs [data-baseweb="tab-border"] {
    display: none !important;
}

/* ===== METRICS ===== */
div[data-testid="stMetric"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 12px !important;
    padding: 16px 20px !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2) !important;
}

div[data-testid="stMetric"] label {
    color: var(--text-secondary) !important;
    font-size: 0.85rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
}

div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    font-size: 2rem !important;
    font-weight: 700 !important;
    background: linear-gradient(135deg, var(--accent), var(--accent-light));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

/* ===== DIVIDERS ===== */
hr {
    border-color: var(--border-subtle) !important;
    opacity: 0.5 !important;
}

/* ===== ALERTS ===== */
div[data-testid="stAlert"] {
    border-radius: 10px !important;
    border-left-width: 4px !important;
}

/* Success */
.stSuccess, div[data-baseweb="notification"][kind="positive"] {
    background: rgba(16, 185, 129, 0.1) !important;
    border-color: var(--success) !important;
}

/* Warning */
.stWarning {
    background: rgba(245, 158, 11, 0.1) !important;
    border-color: var(--warning) !important;
}

/* Error */
.stError {
    background: rgba(239, 68, 68, 0.1) !important;
    border-color: var(--error) !important;
}

/* Info */
.stInfo {
    background: rgba(59, 130, 246, 0.1) !important;
    border-color: var(--info) !important;
}

/* ===== PROGRESS BAR ===== */
.stProgress > div > div {
    background: var(--bg-card) !important;
    border-radius: 8px !important;
}

.stProgress > div > div > div {
    background: linear-gradient(90deg, var(--accent), var(--accent-light)) !important;
    border-radius: 8px !important;
}

/* ===== DOWNLOAD BUTTON ===== */
.stDownloadButton > button {
    background: linear-gradient(135deg, var(--success), #34D399) !important;
    box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3) !important;
}

.stDownloadButton > button:hover {
    box-shadow: 0 4px 20px rgba(16, 185, 129, 0.4) !important;
}

/* ===== SCROLLBAR ===== */
::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}

::-webkit-scrollbar-track {
    background: var(--bg-primary);
}

::-webkit-scrollbar-thumb {
    background: var(--border-subtle);
    border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
    background: var(--text-muted);
}

/* ===== SLIDER ===== */
div[data-baseweb="slider"] div[role="slider"] {
    background: var(--accent) !important;
    border-color: var(--accent) !important;
}

/* ===== FILE UPLOADER ===== */
div[data-testid="stFileUploader"] {
    border-radius: 12px !important;
}

div[data-testid="stFileUploader"] section {
    background: var(--bg-card) !important;
    border: 2px dashed var(--border-subtle) !important;
    border-radius: 12px !important;
    transition: border-color 0.3s ease !important;
}

div[data-testid="stFileUploader"] section:hover {
    border-color: var(--accent) !important;
}

/* ===== CHECKBOX / RADIO ===== */
.stCheckbox label span,
.stRadio label span {
    color: var(--text-primary) !important;
}

/* ===== CAPTIONS ===== */
.stCaption, small {
    color: var(--text-secondary) !important;
}

/* ===== FORM ===== */
div[data-testid="stForm"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 12px !important;
    padding: 20px !important;
}

/* ===== SPINNER ===== */
.stSpinner > div {
    border-top-color: var(--accent) !important;
}

/* ===== SELECTBOX DROPDOWN ===== */
div[data-baseweb="popover"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 8px !important;
}

div[data-baseweb="popover"] li {
    color: var(--text-primary) !important;
}

div[data-baseweb="popover"] li:hover {
    background: var(--bg-card-hover) !important;
}

/* ===== NUMBER INPUT ===== */
.stNumberInput > div > div > input {
    background-color: var(--bg-input) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 8px !important;
    color: var(--text-primary) !important;
}

/* ===== TOOLTIP ===== */
div[data-baseweb="tooltip"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 8px !important;
}
</style>
"""


def inject_theme():
    """Inject the dark fintech theme CSS into the Streamlit app."""
    st.markdown(_THEME_CSS, unsafe_allow_html=True)
