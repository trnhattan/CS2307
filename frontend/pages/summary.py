import streamlit as st

from frontend.components.header import render_header
from frontend.state import go


def render() -> None:
    render_header()
    st.markdown("<div class='section-title'>Tổng kết bài thi</div>", unsafe_allow_html=True)
    for result in st.session_state.results:
        with st.container(border=True):
            left, middle, right = st.columns([2, 1, 2])
            left.subheader(result["subject_code"])
            middle.metric("Điểm", f"{result['percentage']:.1f}%")
            right.write(f"Mức độ hiểu bài: **{result['understanding_label']}**")
    left, right = st.columns(2)
    if left.button("Xem tiến độ", type="primary", width="stretch"):
        _clear_exam()
        go("taker_dashboard")
    if right.button("Làm bài thi mới", width="stretch"):
        _clear_exam()
        go("subjects")


def _clear_exam() -> None:
    st.session_state.exam_payload = None
    st.session_state.results = []
    st.session_state.last_result = None
    st.session_state.exam_started_at = {}
