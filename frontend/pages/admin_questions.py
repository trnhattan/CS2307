import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient
from frontend.components.header import render_header


def render(client: ExamAPIClient) -> None:
    render_header()
    st.markdown("<div class='section-title'>Ngân hàng câu hỏi</div>", unsafe_allow_html=True)
    st.caption("Chế độ xem dành cho quản trị hệ thống; dữ liệu câu hỏi không được chỉnh sửa tại đây.")
    try:
        payload = client.admin_questions()
    except APIClientError as error:
        st.error(str(error))
        return

    st.metric("Tổng số câu hỏi", payload["total_questions"])
    for subject in payload["subjects"]:
        with st.expander(
            f"{subject['subject_name']} · {subject['total_questions']} câu",
            expanded=True,
        ):
            charts = st.columns(3)
            charts[0].caption("Độ khó")
            charts[0].bar_chart(
                _chart_rows(subject["difficulty_distribution"]),
                x="Mức",
                y="Số câu",
            )
            charts[1].caption("Bloom")
            charts[1].bar_chart(
                _chart_rows(subject["bloom_distribution"]),
                x="Mức",
                y="Số câu",
            )
            charts[2].caption("Trạng thái")
            charts[2].bar_chart(
                _chart_rows(subject["status_distribution"]),
                x="Mức",
                y="Số câu",
            )

    questions = payload["questions"]
    subject_options = sorted({item["subject_name"] for item in questions})
    difficulty_options = sorted({item["difficulty_label"] for item in questions})
    filters = st.columns(3)
    selected_subjects = filters[0].multiselect("Lọc môn học", subject_options)
    selected_difficulties = filters[1].multiselect("Lọc độ khó", difficulty_options)
    search = filters[2].text_input("Tìm mã hoặc nội dung")
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
                "Mã": item["question_code"],
                "Môn": item["subject_name"],
                "Nội dung": item["stem"],
                "Bloom": item["bloom_level"],
                "Độ khó": item["difficulty_label"],
                "Trạng thái": item["status"],
                "IRT": item["irt_status"],
                "Phương án": item["option_count"],
                "Đơn vị tri thức": ", ".join(item["knowledge_units"]),
            }
            for item in visible
        ],
        width="stretch",
        hide_index=True,
    )
    st.caption(f"Đang hiển thị {len(visible)} câu.")


def _chart_rows(distribution: dict) -> list[dict]:
    return [
        {"Mức": key, "Số câu": value}
        for key, value in distribution.items()
    ]
