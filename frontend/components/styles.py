import streamlit as st


def apply_styles() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"], [data-testid="collapsedControl"],
        [data-testid="stToolbar"], [data-testid="stDecoration"] { display: none !important; }
        header[data-testid="stHeader"] { height: 0 !important; min-height: 0 !important; }
        .stApp { background: linear-gradient(145deg, #f7f9ff 0%, #eef3ff 55%, #f9fbff 100%); }
        .block-container { max-width: 1120px; padding-top: 1.75rem; padding-bottom: 4rem; }
        .hero { padding: 3.6rem 2.5rem; border-radius: 28px; color: white;
                background: linear-gradient(125deg, #172554 0%, #2547a8 55%, #5b7cfa 100%);
                box-shadow: 0 24px 70px rgba(37,71,168,.24); text-align: center; }
        .hero h1 { font-size: 3rem; margin: 0 0 .8rem; letter-spacing: -.04em; }
        .hero p { font-size: 1.08rem; color: #dbe7ff; max-width: 760px; margin: auto; }
        .eyebrow { color: #b8c9ff; font-weight: 700; letter-spacing: .14em;
                   font-size: .75rem; text-transform: uppercase; }
        .member { background: rgba(255,255,255,.92); border: 1px solid #dce5fb;
                  border-radius: 18px; padding: 1.1rem .75rem; text-align: center;
                  box-shadow: 0 8px 24px rgba(30,58,138,.07); min-height: 112px; }
        .member .avatar { width: 38px; height: 38px; line-height: 38px; margin: 0 auto .5rem;
                          border-radius: 50%; background: #e6edff; color: #2848aa; font-weight: 800; }
        .member strong { color: #172554; font-size: .9rem; }
        .member small { color: #64748b; }
        .section-title { color: #172554; font-size: 1.8rem; font-weight: 800; margin-bottom: .2rem; }
        .question-card { border: 1px solid #dbe4f5; background: white; border-radius: 20px;
                         padding: 1.1rem 1.25rem .45rem; margin: .7rem 0 .25rem;
                         box-shadow: 0 8px 28px rgba(30,58,138,.06); }
        .badge { display: inline-block; background: #edf2ff; color: #2947a6; border-radius: 99px;
                 padding: .25rem .65rem; font-size: .76rem; font-weight: 700; margin-right: .3rem; }
        div.stButton > button, div.stFormSubmitButton > button {
            border-radius: 12px; min-height: 46px; height: auto; font-weight: 700;
            line-height: 1.2; overflow-wrap: normal; padding: .55rem .65rem;
            white-space: normal; word-break: normal; hyphens: none;
        }
        [data-testid="stMetric"] { background: white; border: 1px solid #dbe4f5;
                                   padding: 1rem; border-radius: 16px; }
        .path-step { background: white; border: 1px solid #dbe4f5; border-left: 5px solid #4f6fe8;
                     border-radius: 16px; padding: 1rem 1.2rem; margin: .55rem 0; }
        .path-step small { color: #64748b; }
        .user-pill { min-height: 46px; display: flex; align-items: center; justify-content: center;
                     padding: .45rem .7rem; border: 1px solid #dbe4f5; border-radius: 12px;
                     background: rgba(255,255,255,.82); color: #475569; font-size: .8rem;
                     text-align: center; line-height: 1.2; overflow-wrap: normal;
                     word-break: normal; }
        .workspace-name { min-height: 46px; display: flex; align-items: center;
                          color: #172554; font-size: .92rem; font-weight: 800; }
        </style>
        """,
        unsafe_allow_html=True,
    )
