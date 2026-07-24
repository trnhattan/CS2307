import time

import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient
from frontend.components.countdown import render_countdown
from frontend.components.header import render_header
from frontend.state import go


def render(client: ExamAPIClient) -> None:
    payload = st.session_state.cat_payload
    if not payload:
        go("subjects")
        return
    render_header()
    question = payload["question"]
    progress = payload["progress"]
    st.markdown(
        f"<div class='section-title'>{payload['subject_name']}</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        f"Bài thi thích ứng · đã trả lời {progress['answered']} · "
        f"tối đa {progress['maximum']} câu"
    )
    st.progress(min(1.0, progress["answered"] / max(1, progress["maximum"])))
    render_countdown(st.session_state.cat_started_at, payload["estimated_minutes"])
    st.markdown(
        f"<div class='question-card'><span class='badge'>Câu {question['order_no']}</span>"
        f"<p><strong>{question['stem']}</strong></p></div>",
        unsafe_allow_html=True,
    )
    labels = {item["option_code"]: item["option_text"] for item in question["options"]}
    with st.form(f"cat_{question['exam_item_id']}"):
        selected = st.radio(
            "Chọn đáp án",
            options=list(labels),
            format_func=lambda code: labels[code],
            index=None,
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("Trả lời", type="primary", width="stretch")
    if not submitted:
        return
    if selected is None:
        st.error("Hãy chọn một đáp án.")
        return
    elapsed = max(1, int(time.time() - st.session_state.cat_question_started_at))
    try:
        with st.spinner("Đang cập nhật và chọn câu tiếp theo..."):
            response = client.answer_cat(
                payload["session_id"],
                question["exam_item_id"],
                selected,
                elapsed,
            )
    except APIClientError as error:
        st.error(str(error))
        return
    if response["completed"]:
        st.session_state.cat_result = response["result"]
        st.session_state.cat_payload = None
        go("cat_result")
        return
    st.session_state.cat_payload = {
        **payload,
        "progress": response["progress"],
        "question": response["question"],
    }
    st.session_state.cat_question_started_at = time.time()
    st.rerun()
