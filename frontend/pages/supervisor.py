import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient
from frontend.components.header import render_header
from frontend.components.llm_explanation import render_explanation_action


def render(client: ExamAPIClient) -> None:
    render_header()
    try:
        payload = client.supervisor_dashboard()
    except APIClientError as error:
        st.error(str(error))
        return
    render_assessment_dashboard(client, payload, "Supervisor dashboard")


def render_assessment_dashboard(
    client: ExamAPIClient, payload: dict, title: str
) -> None:
    st.markdown(f"<div class='section-title'>{title}</div>", unsafe_allow_html=True)
    summary = payload["summary"]
    columns = st.columns(5)
    columns[0].metric("Sessions", summary["total_sessions"])
    columns[1].metric("Completed", summary["completed_sessions"])
    columns[2].metric("In progress", summary["in_progress_sessions"])
    columns[3].metric("Exam takers", summary["exam_takers"])
    columns[4].metric("Average score", f"{summary['average_score_percent']:.1f}%")

    st.subheader("Exam-taker overview")
    takers = payload["takers"]
    st.dataframe(
        [
            {
                "Exam taker": item["student_name"],
                "Student code": item["student_code"],
                "Completed tests": item["completed_tests"],
                "Subjects assessed": item["subjects_assessed"],
                "Average score": f"{item['average_score_percent']:.1f}%",
                "Best score": f"{item['best_score_percent']:.1f}%",
                "Latest score": (
                    f"{item['latest_score_percent']:.1f}%"
                    if item["latest_score_percent"] is not None
                    else "Not assessed"
                ),
                "Average theta": (
                    round(item["average_theta"], 3)
                    if item["average_theta"] is not None
                    else None
                ),
                "Average mastery": (
                    f"{item['average_mastery_probability']:.1%}"
                    if item["average_mastery_probability"] is not None
                    else None
                ),
            }
            for item in takers
        ],
        width="stretch",
        hide_index=True,
    )

    st.subheader("Generated exam sessions")
    sessions = payload["sessions"]
    if not sessions:
        st.info("No exam session exists yet.")
    else:
        table = [
            {
                "Session": item["session_id"],
                "Exam taker": item["student_name"],
                "Subject": item["subject_name"],
                "Status": item["status"],
                "Purpose": item.get("assessment_purpose", "practice").title(),
                "Answered": f"{item['answered_count']}/{item['question_count']}",
                "Score": f"{item['score_percent']:.1f}%",
                "Theta": round(item["theta_current"], 3),
                "SE": round(item["standard_error"], 3),
            }
            for item in sessions
        ]
        st.dataframe(table, width="stretch", hide_index=True)
        selected_id = st.selectbox(
            "Session details",
            options=[item["session_id"] for item in sessions],
            format_func=lambda value: _session_label(value, sessions),
        )
        selected = next(item for item in sessions if item["session_id"] == selected_id)
        render_session_detail(selected)
        if selected["status"] == "completed":
            render_explanation_action(client, selected_id, technical=True)
        if selected["mode"] == "adaptive":
            try:
                adaptive = client.staff_cat(selected_id)
                st.subheader("CAT trajectory")
                st.dataframe(
                    [
                        {
                            "Question": item["order_no"],
                            "Code": item["question_code"],
                            "Correct": item["is_correct"],
                            "Theta before": item["theta_before"],
                            "Theta after": item["theta_after"],
                            "SE": item["standard_error_after"],
                            "Information": item["item_information"],
                            "Selection reason": item["selection_reason"],
                        }
                        for item in adaptive["items"]
                    ],
                    width="stretch",
                    hide_index=True,
                )
            except APIClientError as error:
                st.error(str(error))

    st.subheader("Ability by exam taker and subject")
    abilities = payload["abilities"]
    if abilities:
        st.dataframe(
            [
                {
                    "Exam taker": item["student_name"],
                    "Subject": item["subject_name"],
                    "Theta": round(item["theta"], 4),
                    "Standard error": round(item["standard_error"], 4),
                    "Mastery probability": (
                        round(item["mastery_probability"], 4)
                        if item["mastery_probability"] is not None
                        else None
                    ),
                    "Evidence": item["evidence_count"],
                }
                for item in abilities
            ],
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("No post-test ability estimate is available yet.")


def render_session_detail(session: dict) -> None:
    theta_delta = session["theta_current"] - session["theta_initial"]
    left, middle, right = st.columns(3)
    left.metric(
        "Post-test theta",
        f"{session['theta_current']:.3f}",
        delta=f"{theta_delta:+.3f}",
    )
    middle.metric("Standard error", f"{session['standard_error']:.3f}")
    right.metric(
        "Average Fisher information",
        f"{session['average_item_information']:.3f}",
    )
    charts = st.columns(2)
    with charts[0]:
        st.caption("Difficulty distribution")
        st.bar_chart(
            [
                {"Level": key, "Questions": value}
                for key, value in session["difficulty_distribution"].items()
            ],
            x="Level",
            y="Questions",
        )
    with charts[1]:
        st.caption("Bloom distribution")
        st.bar_chart(
            [
                {"Level": key, "Questions": value}
                for key, value in session["bloom_distribution"].items()
            ],
            x="Level",
            y="Questions",
        )
    with st.expander("Generation configuration snapshot"):
        st.json(session["generation_config"])


def _session_label(session_id: int, sessions: list[dict]) -> str:
    session = next(item for item in sessions if item["session_id"] == session_id)
    return (
        f"#{session_id} · {session['student_name']} · "
        f"{session['subject_name']} · {session['status']}"
    )
