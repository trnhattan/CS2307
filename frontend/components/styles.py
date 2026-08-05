import streamlit as st


def apply_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700;800&display=swap');

        /* Base styles and defaults */
        [data-testid="stSidebar"], [data-testid="collapsedControl"],
        [data-testid="stToolbar"], [data-testid="stDecoration"] { display: none !important; }
        header[data-testid="stHeader"] { height: 0 !important; min-height: 0 !important; }

        /* Font and App Background */
        .stApp {
            background: linear-gradient(135deg, #f8fafc 0%, #f0f7ff 50%, #e2e8f0 100%) !important;
            font-family: 'Inter', sans-serif !important;
        }

        h1, h2, h3, h4, h5, h6 {
            font-family: 'Outfit', sans-serif !important;
            font-weight: 700 !important;
            color: #0f172a !important;
        }

        .block-container {
            max-width: 1120px;
            padding-top: 1.5rem;
            padding-bottom: 5rem;
        }

        /* Unified Topbar Container */
        .topbar-card {
            background: rgba(255, 255, 255, 0.92);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(226, 232, 240, 0.9);
            border-radius: 20px;
            padding: 1.25rem 1.5rem 0.85rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.03);
        }

        .nav-tabs-wrapper {
            margin-top: 0.85rem;
            border-top: 1px solid rgba(226, 232, 240, 0.7);
            padding-top: 0.85rem;
        }

        .nav-tabs-wrapper div.stButton > button {
            min-height: 38px !important;
            border-radius: 10px !important;
            font-size: 0.88rem !important;
            padding: 0.4rem 0.8rem !important;
        }

        /* Hero Banner */
        .hero {
            padding: 4rem 2.5rem;
            border-radius: 24px;
            color: white;
            background: linear-gradient(135deg, #1e1b4b 0%, #312e81 40%, #4f46e5 100%);
            box-shadow: 0 20px 40px rgba(79, 70, 229, 0.15);
            text-align: center;
            margin-bottom: 2.5rem;
            border: 1px solid rgba(255, 255, 255, 0.08);
            transition: transform 0.3s ease;
        }
        .hero:hover {
            transform: translateY(-2px);
        }
        .hero h1 {
            font-size: 3.2rem;
            margin: 0 0 .8rem;
            letter-spacing: -.03em;
            line-height: 1.15;
            background: linear-gradient(to right, #ffffff, #e0e7ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800 !important;
        }
        .hero p {
            font-size: 1.15rem;
            color: #c7d2fe;
            max-width: 720px;
            margin: auto;
            line-height: 1.6;
        }
        .eyebrow {
            color: #818cf8;
            font-weight: 700;
            letter-spacing: .18em;
            font-size: .8rem;
            text-transform: uppercase;
            margin-bottom: 0.5rem;
        }

        /* Team Members */
        .member {
            background: rgba(255, 255, 255, 0.85);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(226, 232, 240, 0.8);
            border-radius: 20px;
            padding: 1.5rem 1rem;
            text-align: center;
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.03);
            min-height: 140px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .member:hover {
            transform: translateY(-4px);
            box-shadow: 0 16px 36px rgba(79, 70, 229, 0.08);
            border-color: rgba(99, 102, 241, 0.4);
            background: #ffffff;
        }
        .member .avatar {
            width: 46px;
            height: 46px;
            line-height: 46px;
            margin: 0 auto .8rem;
            border-radius: 50%;
            background: linear-gradient(135deg, #e0e7ff 0%, #c7d2fe 100%);
            color: #4f46e5;
            font-weight: 800;
            font-size: 1.1rem;
            box-shadow: 0 4px 10px rgba(79, 70, 229, 0.1);
        }
        .member strong {
            color: #0f172a;
            font-size: 0.95rem;
            font-weight: 600;
        }
        .member small {
            color: #64748b;
            font-size: 0.8rem;
            display: block;
            margin-top: 0.2rem;
        }

        /* Headers and Layout Sections */
        .section-title {
            color: #0f172a;
            font-size: 2rem;
            font-weight: 800;
            margin-top: 1rem;
            margin-bottom: .4rem;
            font-family: 'Outfit', sans-serif;
            letter-spacing: -.02em;
        }

        /* Question Cards */
        .question-card {
            border: 1px solid rgba(226, 232, 240, 0.8);
            background: #ffffff;
            border-radius: 20px;
            padding: 1.5rem 1.75rem;
            margin: 1rem 0;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.03);
            transition: all 0.2s ease;
        }
        .question-card:hover {
            box-shadow: 0 12px 36px rgba(0, 0, 0, 0.05);
            border-color: rgba(99, 102, 241, 0.2);
        }

        .badge {
            display: inline-block;
            background: linear-gradient(135deg, #e0e7ff 0%, #c7d2fe 100%);
            color: #4f46e5;
            border-radius: 99px;
            padding: .3rem .8rem;
            font-size: .78rem;
            font-weight: 700;
            margin-right: .3rem;
            margin-bottom: .6rem;
            box-shadow: 0 2px 5px rgba(79, 70, 229, 0.08);
        }

        /* Premium Buttons */
        div.stButton > button, div.stFormSubmitButton > button {
            border-radius: 12px !important;
            min-height: 48px !important;
            height: auto !important;
            font-weight: 600 !important;
            font-size: 0.95rem !important;
            line-height: 1.2 !important;
            overflow-wrap: normal !important;
            padding: .6rem 1.2rem !important;
            white-space: normal !important;
            word-break: normal !important;
            hyphens: none !important;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
            border: 1px solid rgba(226, 232, 240, 0.8) !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.02) !important;
        }

        /* Secondary Buttons Hover */
        div.stButton > button:hover, div.stFormSubmitButton > button:hover {
            color: #4f46e5 !important;
            border-color: #c7d2fe !important;
            background-color: rgba(248, 250, 252, 0.9) !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.05) !important;
        }

        /* Primary Buttons */
        div.stButton > button[type="secondary"] {
            background-color: #ffffff !important;
            color: #334155 !important;
        }

        div.stButton > button[class*="primary"], div.stFormSubmitButton > button[class*="primary"] {
            background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%) !important;
            color: white !important;
            border: none !important;
            box-shadow: 0 4px 14px rgba(79, 70, 229, 0.2) !important;
        }
        div.stButton > button[class*="primary"]:hover, div.stFormSubmitButton > button[class*="primary"]:hover {
            color: white !important;
            background: linear-gradient(135deg, #4338ca 0%, #4f46e5 100%) !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 8px 20px rgba(79, 70, 229, 0.3) !important;
        }
        div.stButton > button[class*="primary"]:active, div.stFormSubmitButton > button[class*="primary"]:active {
            transform: translateY(1px) !important;
        }

        /* Metrics */
        [data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.85);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            border: 1px solid rgba(226, 232, 240, 0.8);
            padding: 1.25rem;
            border-radius: 20px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.02);
            transition: all 0.25s ease;
        }
        [data-testid="stMetric"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 12px 30px rgba(0, 0, 0, 0.04);
            border-color: rgba(99, 102, 241, 0.15);
        }
        [data-testid="stMetricValue"] {
            font-size: 2.2rem !important;
            font-weight: 800 !important;
            font-family: 'Outfit', sans-serif !important;
            color: #0f172a !important;
            background: linear-gradient(135deg, #1e1b4b 0%, #4f46e5 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        [data-testid="stMetricLabel"] {
            font-weight: 600 !important;
            color: #64748b !important;
            font-size: 0.85rem !important;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        /* Path Step / Recommended Actions */
        .path-step {
            background: #ffffff;
            border: 1px solid rgba(226, 232, 240, 0.8);
            border-left: 6px solid #4f46e5;
            border-radius: 18px;
            padding: 1.25rem 1.5rem;
            margin: .75rem 0;
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.02);
            transition: all 0.25s ease;
        }
        .path-step:hover {
            transform: translateX(4px);
            border-color: rgba(99, 102, 241, 0.3);
            box-shadow: 0 10px 28px rgba(79, 70, 229, 0.05);
        }
        .path-step small {
            color: #64748b;
            font-weight: 500;
        }

        /* User Profile Pill */
        .user-pill {
            min-height: 48px;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: .5rem 1rem;
            border: 1px solid rgba(226, 232, 240, 0.8);
            border-radius: 14px;
            background: rgba(255, 255, 255, 0.9);
            color: #334155;
            font-size: .88rem;
            font-weight: 600;
            text-align: center;
            line-height: 1.2;
            overflow-wrap: normal;
            word-break: normal;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.02);
        }

        /* Workspace Name Header Title */
        .workspace-name {
            min-height: 48px;
            display: flex;
            align-items: center;
            color: #1e1b4b;
            font-size: 1.15rem;
            font-weight: 800;
            font-family: 'Outfit', sans-serif;
            letter-spacing: -.02em;
        }

        /* Inputs styling */
        div[data-baseweb="input"], div[data-baseweb="select"], div[data-baseweb="textarea"] {
            border-radius: 12px !important;
            transition: all 0.2s ease !important;
        }

        /* Progress bars */
        div[data-testid="stProgress"] > div {
            border-radius: 99px !important;
            height: 8px !important;
        }
        div[data-testid="stProgress"] div[role="progressbar"] {
            background: linear-gradient(90deg, #4f46e5 0%, #818cf8 100%) !important;
        }

        /* Styled expanders */
        div[data-testid="stExpander"] {
            border: 1px solid rgba(226, 232, 240, 0.8) !important;
            background-color: #ffffff !important;
            border-radius: 16px !important;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.01) !important;
            overflow: hidden !important;
        }

        /* Option cards for st.radio inside forms */
        div[data-testid="stRadio"] div[role="radiogroup"] > label {
            background-color: #ffffff !important;
            border: 1px solid rgba(226, 232, 240, 0.8) !important;
            border-radius: 12px !important;
            padding: 0.8rem 1.2rem !important;
            margin-bottom: 0.6rem !important;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.01) !important;
            width: 100% !important;
            display: flex !important;
            align-items: center !important;
            cursor: pointer !important;
        }
        div[data-testid="stRadio"] div[role="radiogroup"] > label:hover {
            border-color: rgba(79, 70, 229, 0.4) !important;
            background-color: #f8fafc !important;
            box-shadow: 0 4px 12px rgba(79, 70, 229, 0.05) !important;
            transform: translateX(3px) !important;
        }
        /* Custom highlight for checked items */
        div[data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) {
            background-color: #f5f3ff !important;
            border-color: #7c3aed !important;
            box-shadow: 0 4px 12px rgba(124, 58, 237, 0.08) !important;
            color: #7c3aed !important;
            font-weight: 600 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
