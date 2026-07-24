import time

import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient
from frontend.components.countdown import render_countdown
from frontend.components.header import render_header
from frontend.state import go


def render(client: ExamAPIClient) -> None:
    payload = st.session_state.exam_payload
    if not payload:
        go("subjects")
        return
    render_header()
    session = payload["sessions"][st.session_state.session_index]
    total_sessions = len(payload["sessions"])
    session_key = str(session["session_id"])
    if session_key not in st.session_state.exam_started_at:
        st.session_state.exam_started_at[session_key] = time.time()
    started_at = st.session_state.exam_started_at[session_key]

    st.progress((st.session_state.session_index + 1) / total_sessions)
    st.markdown(
        f"<div class='section-title'>{session['subject_name']}</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        f"Subject {st.session_state.session_index + 1}/{total_sessions} · "
        f"{session['question_count']} questions"
    )
    render_countdown(started_at, session["estimated_minutes"])

    answers: dict[int, str | None] = {}
    with st.form(f"exam_{session['session_id']}"):
        for question in session["questions"]:
            st.markdown(
                f"""
                <div class="question-card">
                  <span class="badge">Question {question['order_no']}</span>
                  <p><strong>{question['stem']}</strong></p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            option_labels = {
                option["option_code"]: option["option_text"]
                for option in question["options"]
            }
            answers[question["exam_item_id"]] = st.radio(
                f"Select an answer for question {question['order_no']}",
                options=list(option_labels),
                format_func=lambda code, labels=option_labels: labels[code],
                index=None,
                key=f"answer_{question['exam_item_id']}",
                label_visibility="collapsed",
            )
        submitted = st.form_submit_button(
            "Submit test",
            type="primary",
            width="stretch",
        )

    if not submitted:
        return
    missing = sum(value is None for value in answers.values())
    if missing:
        st.error(f"{missing} questions are still unanswered.")
        return
    elapsed = max(1, int(time.time() - started_at))
    average_time = max(1, elapsed // len(answers))
    body = [
        {
            "exam_item_id": item_id,
            "selected_option_code": option_code,
            "response_time_sec": average_time,
        }
        for item_id, option_code in answers.items()
    ]
    try:
        with st.spinner("Scoring your test..."):
            result = client.submit(session["session_id"], body)
    except APIClientError as error:
        st.error(str(error))
        return
    st.session_state.last_result = result
    st.session_state.results.append(result)
    go("result")
