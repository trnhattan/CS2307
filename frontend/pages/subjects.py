import time

import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient
from frontend.components.header import render_header
from frontend.state import go


def render(client: ExamAPIClient) -> None:
    render_header()
    st.markdown("<div class='section-title'>🎯 Build your test</div>", unsafe_allow_html=True)
    st.write("")

    try:
        payload = client.subjects()
    except APIClientError as error:
        st.error(str(error))
        return

    labels = {
        item["subject_code"]: item["subject_name"] for item in payload["subjects"]
    }

    # Configuration Container
    with st.container(border=True):
        st.markdown("### ⚙️ Choose Test Settings")

        mode = st.radio(
            "Test mode",
            options=["placement", "fixed", "adaptive"],
            format_func=lambda value: {
                "placement": "Placement assessment",
                "fixed": "Fixed blueprint",
                "adaptive": "Adaptive CAT (Computer Adaptive Testing)",
            }[value],
            horizontal=True,
        )
        st.markdown(
            "<small style='color: #64748b; display: block; margin-top: -0.5rem; margin-bottom: 1.5rem;'>"
            "• Fixed blueprint: Customize subjects, question counts, and difficulty profiles.<br/>"
            "• Adaptive CAT: System adjusts difficulty in real-time based on your responses.<br/>"
            "• Placement assessment: Establish a criterion-level baseline for one subject."
            "</small>",
            unsafe_allow_html=True
        )

        st.divider()

        if mode == "fixed":
            st.markdown("#### 📘 Fixed-exam blueprint")
            selected = st.multiselect(
                "Subjects",
                options=list(labels),
                format_func=lambda code: labels[code],
                placeholder="Select at least one subject",
            )

            col1, col2 = st.columns(2)
            with col1:
                default_count = payload["config"]["default_question_count"]
                question_count = st.number_input(
                    "Questions per subject",
                    min_value=1,
                    max_value=100,
                    value=default_count,
                    step=1,
                )
            with col2:
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

            difficulty_distribution = payload["config"]["difficulty_distribution"]
            presets = {
                "balanced": difficulty_distribution,
                "foundation": {"easy": 0.6, "medium": 0.3, "hard": 0.1},
                "challenging": {"easy": 0.1, "medium": 0.3, "hard": 0.6},
            }

            if profile == "custom":
                with st.container(border=True):
                    st.markdown("<small>Define custom difficulty weights (sum should ideally be 1.0)</small>", unsafe_allow_html=True)
                    difficulty_columns = st.columns(3)
                    easy = difficulty_columns[0].number_input("Easy weight", 0.0, 1.0, 0.3, 0.05)
                    medium = difficulty_columns[1].number_input("Medium weight", 0.0, 1.0, 0.4, 0.05)
                    hard = difficulty_columns[2].number_input("Hard weight", 0.0, 1.0, 0.3, 0.05)
                    difficulty_distribution = {"easy": easy, "medium": medium, "hard": hard}
            else:
                difficulty_distribution = presets[profile]

            # Display selected weights visually
            weight_text = " · ".join(
                f"**{label.title()}:** {value:.0%}"
                for label, value in difficulty_distribution.items()
            )
            st.markdown(f"<p style='font-size: 0.9rem; color: #4f46e5; margin-top: 0.5rem;'>📊 Current profile weights: {weight_text}</p>", unsafe_allow_html=True)

        else:
            st.markdown(
                "#### ⚡ Adaptive CAT Settings"
                if mode == "adaptive"
                else "#### 🧭 Placement assessment"
            )
            selected_subject = st.selectbox(
                "Subject",
                options=[None, *labels],
                format_func=lambda code: "Select one subject" if code is None else labels[code],
            )
            selected = [selected_subject] if selected_subject else []
            difficulty_distribution = payload["config"]["difficulty_distribution"]
            question_count = payload["config"]["default_question_count"]
            if mode == "placement":
                st.info(
                    "The placement blueprint is controlled centrally and prioritizes broad "
                    "assessment-criterion coverage. It creates your baseline learning profile."
                )
                try:
                    placement = client.placement_status()
                    current = next(
                        (
                            item for item in placement["subjects"]
                            if item["subject_code"] == selected_subject
                        ),
                        None,
                    )
                    if current:
                        st.caption(
                            "Current placement status: "
                            f"{current['status'].replace('_', ' ').title()}"
                        )
                except APIClientError:
                    pass

    st.write("")

    # Timing advice
    st.info(
        "⏱️ Note: The countdown is guidance only. You may continue after the estimated time reaches zero."
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
                elif mode == "placement":
                    exam = client.start_placement(selected[0])
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
