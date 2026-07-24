import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient
from frontend.components.header import render_header


def render(client: ExamAPIClient) -> None:
    render_header()
    st.markdown(
        "<div class='section-title'>Sinh bản nháp câu hỏi bằng LLM</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Mỗi lần chỉ sinh một câu. Câu mới luôn là draft, dùng IRT khởi tạo xác định "
        "và phải được admin review trước khi có thể dùng trong đề."
    )
    try:
        status = client.generation_status()
        catalog = client.generation_catalog()
    except APIClientError as error:
        st.error(str(error))
        return

    left, middle, right = st.columns(3)
    left.metric("LLM", "Bật" if status["enabled"] else "Tắt")
    middle.metric("API", "Đã cấu hình" if status["configured"] else "Thiếu khóa")
    right.metric("Model", status["model"])
    if not status["configured"]:
        st.warning("Backend chưa có biến môi trường LLM_API_KEY.")

    subjects = catalog["subjects"]
    if not subjects:
        st.info("Chưa có môn học và đơn vị tri thức để tạo mục tiêu câu hỏi.")
        return
    selected_subject_code = st.selectbox(
        "Môn học",
        [item["code"] for item in subjects],
        format_func=lambda value: _subject_label(value, subjects),
    )
    subject = next(item for item in subjects if item["code"] == selected_subject_code)
    topics = [unit for unit in subject["units"] if unit["type"] == "topic"]
    skills = [unit for unit in subject["units"] if unit["type"] == "skill"]
    if not topics or not skills:
        st.warning("Môn học này chưa có đủ topic và skill để liên kết câu hỏi.")
        _recent(client)
        return

    with st.form("llm_generation_form"):
        topic_code = st.selectbox(
            "Chủ đề",
            [item["code"] for item in topics],
            format_func=lambda value: _unit_label(value, topics),
        )
        skill_codes = st.multiselect(
            "Kỹ năng đo được",
            [item["code"] for item in skills],
            format_func=lambda value: _unit_label(value, skills),
        )
        first, second = st.columns(2)
        bloom_level = first.selectbox("Mức Bloom", catalog["bloom_levels"])
        difficulty = second.selectbox("Độ khó", catalog["difficulty_labels"])
        learning_objective = st.text_input("Mục tiêu học tập cụ thể (không bắt buộc)")
        source_title = st.text_input("Tên nguồn (khuyến nghị)")
        source_context = st.text_area(
            "Đoạn nguồn để câu hỏi bám sát (khuyến nghị)",
            height=180,
            placeholder="Dán đoạn giáo trình hoặc tài liệu đã được phép sử dụng...",
        )
        submitted = st.form_submit_button(
            "Sinh 1 bản nháp",
            type="primary",
            width="stretch",
            disabled=not status["enabled"] or not status["configured"],
        )
    if submitted:
        if not skill_codes:
            st.error("Hãy chọn ít nhất một kỹ năng.")
        else:
            try:
                with st.spinner("LLM đang tạo một bản nháp để review..."):
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
        _render_result(result)
    _recent(client)


def _render_result(result: dict) -> None:
    st.success(f"Đã lưu {result['question_code']} ở trạng thái draft.")
    st.markdown(f"### {result['stem']}")
    for option in result["options"]:
        marker = "✓" if option["is_best_answer"] else ""
        st.write(f"**{option['code']}.** {option['text']} {marker}")
    st.write("**Giải thích:**", result["explanation"])
    with st.expander("Rubric và kiểm tra xác định", expanded=True):
        st.json({"irt": result["irt"], "issues": result["validation_issues"]})
    blockers = [
        issue for issue in result["validation_issues"] if issue["severity"] == "blocking"
    ]
    if blockers:
        st.warning("Bản nháp còn lỗi chặn; admin không thể kích hoạt trước khi sửa.")


def _recent(client: ExamAPIClient) -> None:
    st.subheader("Lịch sử gần đây")
    try:
        items = client.recent_generations()["items"]
    except APIClientError as error:
        st.error(str(error))
        return
    if not items:
        st.info("Chưa có lần sinh bản nháp nào.")
        return
    st.dataframe(
        [
            {
                "Artifact": item["artifact_id"],
                "Câu hỏi": item["question_code"],
                "Trạng thái": item["status"],
                "Môn": item["subject_code"],
                "Bloom": item["bloom_level"],
                "Độ khó": item["difficulty_label"],
                "Model": item["model"],
                "Người gọi": item["created_by"],
                "Thời gian": item["created_at"],
                "Lỗi": item["error_message"],
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
