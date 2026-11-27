"""Custom dark theme for the AICompanyOS Streamlit interface."""

import streamlit as st


def apply_custom_theme() -> None:
    """Inject the Cairo-based dark theme with gold and purple accents."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');

        :root { color-scheme: dark; }
        html, body, .stApp, [data-testid="stSidebar"],
        [data-testid="stMarkdownContainer"], .stTextInput, .stTextArea,
        .stSelectbox, .stNumberInput, .stRadio, .stAlert, .stDateInput,
        .stMultiSelect, .stButton, .stDownloadButton {
            font-family: 'Cairo', sans-serif !important;
            direction: rtl;
            text-align: right;
        }

        .stApp {
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
            color: #f8fafc;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #111827 0%, #1e1b4b 100%);
            border-left: 1px solid #4c3b75;
        }

        .stButton > button, .stDownloadButton > button {
            background: linear-gradient(90deg, #7c3aed 0%, #6d28d9 55%, #a855f7 100%);
            color: #fff;
            border: 1px solid #8b5cf6;
            border-radius: 8px;
            font-weight: 700;
            transition: all 0.3s ease;
        }
        .stButton > button:hover, .stDownloadButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(124, 58, 237, 0.4);
            border-color: #fbbf24;
            color: #fff;
        }

        [data-testid="stMetric"] {
            background: linear-gradient(145deg, #1e293b, #26204b);
            border: 1px solid #55417d;
            border-radius: 14px;
            padding: 14px;
        }
        [data-testid="stMetricValue"] {
            color: #fbbf24 !important;
            font-size: 2rem !important;
            font-weight: 800 !important;
        }
        [data-testid="stMetricLabel"] { color: #ddd6fe !important; }

        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea,
        .stNumberInput input,
        .stDateInput input {
            background-color: #334155 !important;
            color: #f8fafc !important;
            border: 1px solid #64748b !important;
            border-radius: 6px;
        }
        .stSelectbox [data-baseweb="select"],
        .stMultiSelect [data-baseweb="select"] {
            background-color: #334155 !important;
            color: #f8fafc !important;
        }

        [data-testid="stHeader"] { background: rgba(15, 23, 42, 0.92); }
        [data-testid="stExpander"] {
            background: rgba(30, 41, 59, 0.75);
            border: 1px solid #55417d;
            border-radius: 12px;
        }
        [data-testid="stDataFrame"], [data-testid="stTable"] {
            border: 1px solid #55417d;
            border-radius: 12px;
            overflow: hidden;
        }
        h1, h2, h3, p, label { color: #f8fafc; }
        hr { border-color: #55417d; }
        #MainMenu, footer { visibility: hidden; }
        </style>
        """,
        unsafe_allow_html=True,
    )
