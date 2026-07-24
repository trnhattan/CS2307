import time

import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient
from frontend.components.header import render_header
from frontend.state import go


def render(client: ExamAPIClient) -> None:
    render_header()
    st.markdown("<div class='section-title'>Build your test</div>", unsafe_allow_html=True)
    mode = st.radio(
        "Test mode",
        options=["fixed", "adaptive"],
        format_func=lambda value: "Fixed blueprint" if value == "fixed" else "Adaptive CAT",
        horizontal=True,
    )
    st.caption(
        "A fixed blueprint exposes subject, question-count, and difficulty controls in one place. "
        "CAT adapts one subject at a time from central configuration."
    )
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
            "Subjects",
            options=list(labels),
            format_func=lambda code: labels[code],
            placeholder="Select at least one subject",
        )
    else:
        selected_subject = st.selectbox(
            "Subject",
            options=[None, *labels],
            format_func=lambda code: "Select one subject" if code is None else labels[code],
        )
        selected = [selected_subject] if selected_subject else []
    default_count = payload["config"]["default_question_count"]
    difficulty_distribution = payload["config"]["difficulty_distribution"]
    question_count = default_count
    if mode == "fixed":
        st.subheader("Fixed-exam blueprint")
        question_count = st.number_input(
            "Questions per subject",
            min_value=1,
            max_value=100,
            value=default_count,
            step=1,
        )
        profile = st.selectbox(
            "Difficulty profile",
            options=["balanced", "foundation", "challenging", "custom"],
            format_func=lambda value: {
                "balanced": "Balanced",
                "foundation": "Foundation focused",
                "challenging": "Challenge focused",
                "custom": "Custom distribution",
            }[value],
        )
        presets = {
            "balanced": difficulty_distribution,
            "foundation": {"easy": 0.6, "medium": 0.3, "hard": 0.1},
            "challenging": {"easy": 0.1, "medium": 0.3, "hard": 0.6},
        }
        if profile == "custom":
            difficulty_columns = st.columns(3)
            easy = difficulty_columns[0].number_input("Easy weight", 0.0, 1.0, 0.3, 0.05)
            medium = difficulty_columns[1].number_input("Medium weight", 0.0, 1.0, 0.4, 0.05)
            hard = difficulty_columns[2].number_input("Hard weight", 0.0, 1.0, 0.3, 0.05)
            difficulty_distribution = {"easy": easy, "medium": medium, "hard": hard}
        else:
            difficulty_distribution = presets[profile]
        st.caption(
            "Current weights · "
            + " · ".join(
                f"{label.title()} {value:.0%}"
                for label, value in difficulty_distribution.items()
            )
        )
    st.info(
        "The countdown is guidance only. You may continue after the estimated time reaches zero."
    )
    if st.button(
        "Start test",
        type="primary",
        width="stretch",
        disabled=not selected,
    ):
        try:
            with st.spinner("Preparing your test..."):
                if mode == "adaptive":
                    adaptive = client.start_cat(selected[0])
                else:
                    exam = client.generate_with_blueprint(
                        {
                            "subject_codes": selected,
                            "question_count": int(question_count),
                            "difficulty_distribution": difficulty_distribution,
                        }
                    )
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
