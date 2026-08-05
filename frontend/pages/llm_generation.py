import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient
from frontend.components.header import render_header


def render(client: ExamAPIClient) -> None:
    render_header()
    st.markdown(
        "<div class='section-title'>LLM question workspace</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Each request creates one persisted English draft. Deterministic validation and "
        "initial IRT assignment run before an administrator may review and activate it."
    )
    try:
        status = client.generation_status()
        catalog = client.generation_catalog()
    except APIClientError as error:
        st.error(str(error))
        return

    left, middle, right = st.columns(3)
    left.metric("LLM", "Enabled" if status["enabled"] else "Disabled")
    middle.metric("API", "Configured" if status["configured"] else "Missing key")
    right.metric("Model", status["model"])
    st.caption(f"Administrator-selected provider endpoint: {status['provider']}")
    if not status["configured"]:
        st.warning("The selected provider key is not configured in the backend environment.")

    subjects = catalog["subjects"]
    if not subjects:
        st.info("No subjects and knowledge units are available for generation.")
        return
    selected_subject_code = st.selectbox(
        "Subject",
        [item["code"] for item in subjects],
        format_func=lambda value: _subject_label(value, subjects),
    )
    subject = next(item for item in subjects if item["code"] == selected_subject_code)
    topics = [unit for unit in subject["units"] if unit["type"] == "topic"]
    skills = [unit for unit in subject["units"] if unit["type"] == "skill"]
    if not topics or not skills:
        st.warning("This subject does not have enough topics and skills for item linking.")
        _recent(client)
        return

    with st.form("llm_generation_form"):
        topic_code = st.selectbox(
            "Topic",
            [item["code"] for item in topics],
            format_func=lambda value: _unit_label(value, topics),
        )
        skill_codes = st.multiselect(
            "Measured skills",
            [item["code"] for item in skills],
            format_func=lambda value: _unit_label(value, skills),
        )
        first, second = st.columns(2)
        bloom_level = first.selectbox("Bloom level", catalog["bloom_levels"])
        difficulty = second.selectbox("Difficulty", catalog["difficulty_labels"])
        learning_objective = st.text_input("Specific learning objective (optional)")
        source_title = st.text_input("Source title (recommended)")
        source_context = st.text_area(
            "Authorized source excerpt (recommended)",
            height=180,
            placeholder="Paste an authorized textbook or course-material excerpt...",
        )
        submitted = st.form_submit_button(
            "Generate one draft",
            type="primary",
            width="stretch",
            disabled=not status["enabled"] or not status["configured"],
        )
    if submitted:
        if not skill_codes:
            st.error("Select at least one measured skill.")
        else:
            try:
                with st.spinner("The LLM is creating a persisted draft for review..."):
                    result = client.generate_question_draft(
                        {
                            "subject_code": selected_subject_code,
                            "topic_code": topic_code,
                            "skill_codes": skill_codes,
                            "bloom_level": bloom_level,
                            "difficulty_label": difficulty,
                            "learning_objective": learning_objective or None,
                            "source_title": source_title or None,
                            "source_context": source_context or None,
                        }
                    )
                    st.session_state.generated_question_draft = result
            except APIClientError as error:
                st.error(str(error))
    result = st.session_state.get("generated_question_draft")
    if result:
        _render_result(client, result)
    _recent(client)


def _render_result(client: ExamAPIClient, result: dict) -> None:
    st.success(f"Persisted {result['question_code']} with draft status.")
    st.markdown(f"### {result['stem']}")
    for option in result["options"]:
        marker = "✓" if option["is_best_answer"] else ""
        st.write(f"**{option['code']}.** {option['text']} {marker}")
    st.write("**Explanation:**", result["explanation"])
    with st.expander("IRT rubric and deterministic validation", expanded=True):
        st.json({"irt": result["irt"], "issues": result["validation_issues"]})
    blockers = [
        issue for issue in result["validation_issues"] if issue["severity"] == "blocking"
    ]
    if blockers:
        st.warning("The draft has blocking issues and cannot be activated before editing.")
    if st.session_state.user["role"] == "admin":
        review, activate = st.columns(2)
        if review.button("Review persisted draft", width="stretch"):
            try:
                report = client.review_question(result["question_code"])
                st.session_state.generated_question_review = report
            except APIClientError as error:
                st.error(str(error))
        report = st.session_state.get("generated_question_review")
        if report:
            (st.success if report["valid"] else st.error)(
                "Deterministic review passed." if report["valid"] else "Deterministic review found blocking issues."
            )
        if activate.button(
            "Activate reviewed draft",
            type="primary",
            width="stretch",
            disabled=bool(blockers) or not (report and report["valid"]),
        ):
            try:
                activated = client.activate_question(result["question_code"])
                st.success(f"Activated {activated['question_code']} for exam selection.")
            except APIClientError as error:
                st.error(str(error))


def _recent(client: ExamAPIClient) -> None:
    st.subheader("Persisted generation history")
    try:
        items = client.recent_generations()["items"]
    except APIClientError as error:
        st.error(str(error))
        return
    if not items:
        st.info("No persisted generation request exists yet.")
        return
    st.dataframe(
        [
            {
                "Artifact": item["artifact_id"],
                "Question": item["question_code"],
                "Status": item["status"],
                "Subject": item["subject_code"],
                "Bloom": item["bloom_level"],
                "Difficulty": item["difficulty_label"],
                "Model": item["model"],
                "Requested by": item["created_by"],
                "Created at": item["created_at"],
                "Error": item["error_message"],
            }
            for item in items
        ],
        width="stretch",
        hide_index=True,
    )


def _subject_label(code: str, subjects: list[dict]) -> str:
    subject = next(item for item in subjects if item["code"] == code)
    return f"{subject['name']} ({code})"


def _unit_label(code: str, units: list[dict]) -> str:
    unit = next(item for item in units if item["code"] == code)
    return f"{unit['name']} ({code})"
