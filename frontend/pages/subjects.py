import time

import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient
from frontend.components.header import render_header
from frontend.state import go


def render(client: ExamAPIClient) -> None:
    render_header()
    st.markdown("<div class='section-title'>Chọn môn thi</div>", unsafe_allow_html=True)
    mode = st.radio(
        "Hình thức",
        options=["fixed", "adaptive"],
        format_func=lambda value: "Đề cố định" if value == "fixed" else "Bài thi thích ứng",
        horizontal=True,
    )
    st.caption("Đề cố định cho phép chọn nhiều môn; bài thích ứng thực hiện từng môn một.")
    try:
        payload = client.subjects()
    except APIClientError as error:
        st.error(str(error))
        return

    labels = {
        item["subject_code"]: item["subject_name"] for item in payload["subjects"]
    }
    if mode == "fixed":
        selected = st.multiselect(
            "Môn học",
            options=list(labels),
            format_func=lambda code: labels[code],
            placeholder="Chọn ít nhất một môn học",
        )
    else:
        selected_subject = st.selectbox(
            "Môn học",
            options=[None, *labels],
            format_func=lambda code: "Chọn một môn học" if code is None else labels[code],
        )
        selected = [selected_subject] if selected_subject else []
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
                if mode == "adaptive":
                    adaptive = client.start_cat(selected[0])
                else:
                    exam = client.generate(selected)
        except APIClientError as error:
            st.error(str(error))
            return
        if mode == "adaptive":
            st.session_state.cat_payload = adaptive
            st.session_state.cat_started_at = time.time()
            st.session_state.cat_question_started_at = time.time()
            st.session_state.cat_result = None
            go("cat_exam")
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
