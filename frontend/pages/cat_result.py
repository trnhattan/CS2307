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
    st.markdown("<div class='section-title'>Adaptive test result</div>", unsafe_allow_html=True)
    columns = st.columns(3)
    columns[0].metric("Score", f"{payload['total_score']:.1f}/{payload['max_score']:.0f}")
    columns[1].metric("Percentage", f"{payload['percentage']:.1f}%")
    columns[2].metric("Questions", payload["answered_count"])
    st.success(f"Understanding: **{payload['understanding_label']}**")
    st.caption("The test ended under the configured adaptive stopping conditions.")
    render_explanation_action(client, payload["session_id"], technical=False)
    if st.button("View learning progress", type="primary", width="stretch"):
        go("taker_dashboard")
