import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient
from frontend.components.header import render_header


def render(client: ExamAPIClient) -> None:
    render_header()
    st.markdown("<div class='section-title'>Cấu hình đề thi</div>", unsafe_allow_html=True)
    st.caption("Phân bố này được đọc từ sys_props khi sinh mỗi đề mới.")
    try:
        payload = client.difficulty_config()
    except APIClientError as error:
        st.error(str(error))
        return

    distribution = payload["distribution"]
    with st.form("supervisor_difficulty_form"):
        easy = st.number_input(
            "Tỷ trọng câu dễ",
            min_value=0.0,
            max_value=1.0,
            value=float(distribution["easy"]),
            step=0.05,
        )
        medium = st.number_input(
            "Tỷ trọng câu trung bình",
            min_value=0.0,
            max_value=1.0,
            value=float(distribution["medium"]),
            step=0.05,
        )
        hard = st.number_input(
            "Tỷ trọng câu khó",
            min_value=0.0,
            max_value=1.0,
            value=float(distribution["hard"]),
            step=0.05,
        )
        total = easy + medium + hard
        st.caption(f"Tổng trọng số hiện tại: {total:.2f}. Backend sẽ chuẩn hóa về 100%.")
        submitted = st.form_submit_button(
            "Lưu phân bố độ khó",
            type="primary",
            width="stretch",
        )
    if submitted:
        try:
            updated = client.update_difficulty_config(easy, medium, hard)
        except APIClientError as error:
            st.error(str(error))
            return
        normalized = updated["distribution"]
        st.success(
            "Đã cập nhật: "
            f"dễ {normalized['easy']:.0%}, "
            f"trung bình {normalized['medium']:.0%}, "
            f"khó {normalized['hard']:.0%}."
        )

    if payload.get("updated_by"):
        st.caption(
            f"Lần cập nhật gần nhất bởi {payload['updated_by']} · {payload['updated_at']}"
        )
