import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient
from frontend.components.header import render_header


def render(client: ExamAPIClient) -> None:
    render_header()
    try:
        payload = client.admin_overview()
    except APIClientError as error:
        st.error(str(error))
        return
    st.markdown("<div class='section-title'>Tổng quan hệ thống</div>", unsafe_allow_html=True)
    st.caption("Trạng thái ngân hàng câu hỏi và cơ sở tri thức hiện tại.")

    first = st.columns(4)
    first[0].metric("Môn học", payload["subjects"])
    first[1].metric("Câu hỏi", payload["questions"])
    first[2].metric("Câu đang hoạt động", payload["active_questions"])
    first[3].metric("Tài khoản", payload["users"])
    second = st.columns(3)
    second[0].metric("Đơn vị tri thức", payload["knowledge_units"])
    second[1].metric("Sự kiện tri thức", payload["knowledge_facts"])
    second[2].metric("Luật đang hoạt động", payload["knowledge_rules"])

    st.subheader("Tiến độ ngân hàng câu hỏi")
    st.progress(min(1.0, payload["question_bank_completion_percent"] / 100))
    st.write(
        f"**{payload['questions']}/{payload['question_bank_target']} câu** "
        f"({payload['question_bank_completion_percent']:.1f}%)"
    )
