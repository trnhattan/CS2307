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
    st.markdown("<div class='section-title'>⚡ Adaptive Test Result</div>", unsafe_allow_html=True)
    st.write("")

    with st.container(border=True):
        columns = st.columns(3)
        columns[0].metric("Score", f"{payload['total_score']:.1f}/{payload['max_score']:.0f}")
        columns[1].metric("Percentage", f"{payload['percentage']:.1f}%")
        columns[2].metric("Questions", payload["answered_count"])

        st.write("")
        st.markdown(
            f"<div style='background-color: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 12px; padding: 1rem; color: #065f46; font-weight: 600;'>"
            f"💡 Understanding Level: {payload['understanding_label']}"
            f"</div>",
            unsafe_allow_html=True
        )
        st.write("")
        st.caption("ℹ️ The test ended under the configured adaptive stopping conditions.")

    st.write("")
    render_explanation_action(client, payload["session_id"], technical=False)
    st.write("")

    if st.button("View learning progress", type="primary", width="stretch"):
        go("taker_dashboard")
