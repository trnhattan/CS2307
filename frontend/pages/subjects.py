import time

import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient
from frontend.components.header import render_header
from frontend.state import go


def render(client: ExamAPIClient) -> None:
    render_header()
    st.markdown("<div class='section-title'>Chọn môn thi</div>", unsafe_allow_html=True)
    st.caption("Bạn có thể chọn một hoặc nhiều môn. Các môn sẽ được thực hiện lần lượt.")
    try:
        payload = client.subjects()
    except APIClientError as error:
        st.error(str(error))
        return

    labels = {
        item["subject_code"]: item["subject_name"] for item in payload["subjects"]
    }
    selected = st.multiselect(
        "Môn học",
        options=list(labels),
        format_func=lambda code: labels[code],
        placeholder="Chọn ít nhất một môn học",
    )
    question_count = payload["config"]["default_question_count"]
    st.info(
        f"Mỗi môn gồm **{question_count} câu**. Thời gian hiển thị là thời gian "
        "dự kiến; bạn vẫn có thể tiếp tục nếu đồng hồ về 0."
    )
    if st.button(
        "Bắt đầu bài thi",
        type="primary",
        width="stretch",
        disabled=not selected,
    ):
        try:
            with st.spinner("Đang chuẩn bị đề thi..."):
                exam = client.generate(selected)
        except APIClientError as error:
            st.error(str(error))
            return
        st.session_state.exam_payload = exam
        st.session_state.session_index = 0
        st.session_state.results = []
        st.session_state.last_result = None
        first_session = exam["sessions"][0]
        st.session_state.exam_started_at = {
            str(first_session["session_id"]): time.time()
        }
        go("exam")
