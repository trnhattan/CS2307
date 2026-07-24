import streamlit as st

from frontend.components.header import render_header
from frontend.components.llm_explanation import render_explanation_action
from frontend.api_client import ExamAPIClient
from frontend.state import go


def render(client: ExamAPIClient) -> None:
    payload = st.session_state.cat_result
    if not payload:
        go("subjects")
        return
    render_header()
    st.markdown("<div class='section-title'>Kết quả bài thi thích ứng</div>", unsafe_allow_html=True)
    columns = st.columns(3)
    columns[0].metric("Điểm", f"{payload['total_score']:.1f}/{payload['max_score']:.0f}")
    columns[1].metric("Tỷ lệ", f"{payload['percentage']:.1f}%")
    columns[2].metric("Số câu", payload["answered_count"])
    st.success(f"Mức độ hiểu bài: **{payload['understanding_label']}**")
    st.caption("Bài thi đã kết thúc theo điều kiện thích ứng của hệ thống.")
    render_explanation_action(client, payload["session_id"], technical=False)
    if st.button("Xem tiến độ học tập", type="primary", width="stretch"):
        go("taker_dashboard")
