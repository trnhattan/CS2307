import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient
from frontend.components.header import render_header


def render(client: ExamAPIClient) -> None:
    render_header()
    st.markdown("<div class='section-title'>Question bank</div>", unsafe_allow_html=True)
    st.caption("Inspect readiness, run deterministic review, and govern item activation.")
    try:
        payload = client.admin_questions()
        readiness = client.question_readiness()
    except APIClientError as error:
        st.error(str(error))
        return

    metrics = st.columns(4)
    metrics[0].metric("Total questions", readiness["total_questions"])
    metrics[1].metric("Active", readiness["active_questions"])
    metrics[2].metric("Invalid", readiness["invalid_questions"])
    metrics[3].metric("Target gap", readiness["target_gap"])
    for limitation in readiness["limitations"]:
        st.warning(limitation)
    confirm_bulk = st.checkbox(
        "I confirm deterministic review and activation of every item that passes validation"
    )
    if st.button(
        "Review and activate eligible items",
        disabled=not confirm_bulk,
        width="stretch",
    ):
        try:
            response = client.bulk_activate_questions(
                [item["question_code"] for item in payload["questions"]]
            )
            st.success(f"Activated {len(response['activated'])} valid questions.")
            if response["rejected"]:
                st.warning(f"Rejected {len(response['rejected'])} questions.")
            st.rerun()
        except APIClientError as error:
            st.error(str(error))
    st.dataframe(
        [
            {
                "Subject": item["subject_code"],
                "Total": item["total_questions"],
                "Active": item["active_questions"],
                "Topics": item["topic_count"],
                "Bloom": item["bloom_coverage"],
                "Difficulty bands": item["difficulty_coverage"],
                "CAT feasible": "Yes" if item["cat_feasible"] else "Not yet",
            }
            for item in readiness["subjects"]
        ],
        width="stretch",
        hide_index=True,
    )
    for subject in payload["subjects"]:
        with st.expander(
            f"{subject['subject_name']} · {subject['total_questions']} questions",
            expanded=True,
        ):
            charts = st.columns(3)
            charts[0].caption("Difficulty")
            charts[0].bar_chart(
                _chart_rows(subject["difficulty_distribution"]),
                x="Level",
                y="Questions",
            )
            charts[1].caption("Bloom")
            charts[1].bar_chart(
                _chart_rows(subject["bloom_distribution"]),
                x="Level",
                y="Questions",
            )
            charts[2].caption("Status")
            charts[2].bar_chart(
                _chart_rows(subject["status_distribution"]),
                x="Level",
                y="Questions",
            )

    questions = payload["questions"]
    subject_options = sorted({item["subject_name"] for item in questions})
    difficulty_options = sorted({item["difficulty_label"] for item in questions})
    filters = st.columns(3)
    selected_subjects = filters[0].multiselect("Filter subjects", subject_options)
    selected_difficulties = filters[1].multiselect("Filter difficulty", difficulty_options)
    search = filters[2].text_input("Search code or content")
    visible = [
        item
        for item in questions
        if (not selected_subjects or item["subject_name"] in selected_subjects)
        and (
            not selected_difficulties
            or item["difficulty_label"] in selected_difficulties
        )
        and (
            not search
            or search.lower() in item["question_code"].lower()
            or search.lower() in item["stem"].lower()
        )
    ]
    st.dataframe(
        [
            {
                "Code": item["question_code"],
                "Subject": item["subject_name"],
                "Stem": item["stem"],
                "Bloom": item["bloom_level"],
                "Difficulty": item["difficulty_label"],
                "Status": item["status"],
                "IRT": item["irt_status"],
                "Options": item["option_count"],
                "Knowledge units": ", ".join(item["knowledge_units"]),
            }
            for item in visible
        ],
        width="stretch",
        hide_index=True,
    )
    st.caption(f"Showing {len(visible)} questions.")
    if not visible:
        st.info("No questions match the current filters.")
        return
    selected_code = st.selectbox(
        "Inspect question",
        options=[item["question_code"] for item in visible],
    )
    try:
        detail = client.admin_question(selected_code)
    except APIClientError as error:
        st.error(str(error))
        return
    with st.expander("Details and provenance", expanded=False):
        st.write(detail["stem"])
        st.json(
            {
                "difficulty_norm": detail["difficulty_norm"],
                "irt": {
                    "a": detail["irt_a"],
                    "b": detail["irt_b"],
                    "c": detail["irt_c"],
                },
                "units": detail["knowledge_units"],
                "provenance": detail["provenance"],
            }
        )
    with st.expander("Edit existing question", expanded=False):
        with st.form(f"edit_question_{selected_code}"):
            stem = st.text_area("Stem", value=detail["stem"], height=120)
            metadata = st.columns(3)
            bloom_values = ["remember", "understand", "apply", "analyze", "evaluate"]
            bloom = metadata[0].selectbox(
                "Bloom",
                bloom_values,
                index=bloom_values.index(detail["bloom_level"]),
            )
            difficulty_values = ["easy", "medium", "hard"]
            difficulty = metadata[1].selectbox(
                "Difficulty",
                difficulty_values,
                index=difficulty_values.index(detail["difficulty_label"]),
            )
            difficulty_norm = metadata[2].number_input(
                "Difficulty norm",
                min_value=0.0,
                max_value=1.0,
                value=float(detail["difficulty_norm"]),
                step=0.01,
            )
            timing = st.columns(2)
            avg_time_sec = timing[0].number_input(
                "Estimated time (seconds)",
                min_value=1,
                value=int(detail["avg_time_sec"]),
            )
            source = timing[1].text_input("Source", value=detail["source"] or "")
            explanation = st.text_area(
                "Answer explanation",
                value=detail["explanation"] or "",
                height=100,
            )
            irt = st.columns(4)
            irt_a = irt[0].number_input("IRT a", min_value=0.01, value=float(detail["irt_a"]))
            irt_b = irt[1].number_input(
                "IRT b", min_value=-4.0, max_value=4.0, value=float(detail["irt_b"])
            )
            irt_c = irt[2].number_input(
                "IRT c", min_value=0.0, max_value=0.5, value=float(detail["irt_c"])
            )
            irt_statuses = ["draft", "estimated", "calibrated", "retired"]
            irt_status = irt[3].selectbox(
                "IRT status",
                irt_statuses,
                index=irt_statuses.index(detail["irt_status"]),
            )
            save = st.form_submit_button("Save and return to draft", width="stretch")
        if save:
            try:
                client.update_admin_question(
                    selected_code,
                    {
                        "stem": stem,
                        "bloom_level": bloom,
                        "difficulty_label": difficulty,
                        "difficulty_norm": difficulty_norm,
                        "avg_time_sec": avg_time_sec,
                        "explanation": explanation,
                        "irt_a": irt_a,
                        "irt_b": irt_b,
                        "irt_c": irt_c,
                        "irt_status": irt_status,
                        "source": source,
                    },
                )
                st.success("Saved. The question must be reviewed again before activation.")
                st.rerun()
            except APIClientError as error:
                st.error(str(error))
    review, activate = st.columns(2)
    if review.button("Run deterministic review", width="stretch"):
        try:
            response = client.review_question(selected_code)
            _show_review(response)
            st.rerun()
        except APIClientError as error:
            st.error(str(error))
    if activate.button("Activate if valid", type="primary", width="stretch"):
        try:
            response = client.activate_question(selected_code)
            st.success(f"Activated {response['question_code']}.")
            st.rerun()
        except APIClientError as error:
            st.error(str(error))


def _chart_rows(distribution: dict) -> list[dict]:
    return [
        {"Level": key, "Questions": value}
        for key, value in distribution.items()
    ]


def _show_review(response: dict) -> None:
    if response["valid"]:
        st.success("The question passed deterministic validation.")
    else:
        st.error("The question still has blocking validation issues.")
    for issue in response["issues"]:
        if issue["severity"] == "blocking":
            st.error(issue["message"])
        else:
            st.warning(issue["message"])
