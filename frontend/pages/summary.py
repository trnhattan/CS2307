import streamlit as st

from frontend.components.header import render_header
from frontend.state import go


def render() -> None:
    render_header()
    st.markdown("<div class='section-title'>Test summary</div>", unsafe_allow_html=True)
    for result in st.session_state.results:
        with st.container(border=True):
            left, middle, right = st.columns([2, 1, 2])
            left.subheader(result["subject_code"])
            middle.metric("Score", f"{result['percentage']:.1f}%")
            right.write(f"Understanding: **{result['understanding_label']}**")
    left, right = st.columns(2)
    if left.button("View progress", type="primary", width="stretch"):
        _clear_exam()
        go("taker_dashboard")
    if right.button("Start another test", width="stretch"):
        _clear_exam()
        go("subjects")


def _clear_exam() -> None:
    st.session_state.exam_payload = None
    st.session_state.results = []
    st.session_state.last_result = None
    st.session_state.exam_started_at = {}
