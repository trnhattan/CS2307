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

    st.subheader("Bài thi thích ứng")
    try:
        cat = client.cat_config()
    except APIClientError as error:
        st.error(str(error))
        return
    with st.form("supervisor_cat_form"):
        lengths = st.columns(2)
        minimum = lengths[0].number_input(
            "Số câu tối thiểu", min_value=1, max_value=100, value=cat["minimum"]
        )
        maximum = lengths[1].number_input(
            "Số câu tối đa", min_value=1, max_value=100, value=cat["maximum"]
        )
        stopping = st.columns(3)
        threshold = stopping[0].number_input(
            "Ngưỡng sai số", min_value=0.05, max_value=3.0,
            value=float(cat["standard_error_threshold"]), step=0.05,
        )
        epsilon = stopping[1].number_input(
            "Biên ổn định", min_value=0.001, max_value=1.0,
            value=float(cat["stability_epsilon"]), step=0.01,
        )
        window = stopping[2].number_input(
            "Số bước ổn định", min_value=1, max_value=20,
            value=cat["stability_window"],
        )
        weights = st.columns(4)
        information = weights[0].number_input(
            "Trọng số thông tin", min_value=0.0, max_value=10.0,
            value=float(cat["information_weight"]), step=0.05,
        )
        weak = weights[1].number_input(
            "Ưu tiên điểm yếu", min_value=0.0, max_value=10.0,
            value=float(cat["weak_unit_weight"]), step=0.05,
        )
        balance = weights[2].number_input(
            "Cân bằng nội dung", min_value=0.0, max_value=10.0,
            value=float(cat["content_balance_weight"]), step=0.05,
        )
        exposure = weights[3].number_input(
            "Phạt phơi nhiễm", min_value=0.0, max_value=10.0,
            value=float(cat["exposure_penalty"]), step=0.05,
        )
        distribution = cat["difficulty_distribution"]
        difficulty = st.columns(3)
        cat_easy = difficulty[0].number_input(
            "CAT dễ", min_value=0.0, max_value=1.0,
            value=float(distribution["easy"]), step=0.05,
        )
        cat_medium = difficulty[1].number_input(
            "CAT trung bình", min_value=0.0, max_value=1.0,
            value=float(distribution["medium"]), step=0.05,
        )
        cat_hard = difficulty[2].number_input(
            "CAT khó", min_value=0.0, max_value=1.0,
            value=float(distribution["hard"]), step=0.05,
        )
        constraints = st.columns(3)
        topics = constraints[0].text_input(
            "Mã chủ đề (phân cách dấu phẩy)",
            value=", ".join(cat.get("topic_codes", [])),
        )
        skills = constraints[1].text_input(
            "Mã kỹ năng (phân cách dấu phẩy)",
            value=", ".join(cat.get("skill_codes", [])),
        )
        bloom_options = ["remember", "understand", "apply", "analyze", "evaluate"]
        bloom_levels = constraints[2].multiselect(
            "Mức Bloom",
            options=bloom_options,
            default=cat.get("bloom_levels", []),
        )
        save_cat = st.form_submit_button(
            "Lưu cấu hình bài thi thích ứng", type="primary", width="stretch"
        )
    if save_cat:
        try:
            client.update_cat_config(
                {
                    "minimum": minimum,
                    "maximum": maximum,
                    "standard_error_threshold": threshold,
                    "stability_epsilon": epsilon,
                    "stability_window": window,
                    "information_weight": information,
                    "weak_unit_weight": weak,
                    "content_balance_weight": balance,
                    "exposure_penalty": exposure,
                    "difficulty_distribution": {
                        "easy": cat_easy,
                        "medium": cat_medium,
                        "hard": cat_hard,
                    },
                    "topic_codes": [value.strip() for value in topics.split(",") if value.strip()],
                    "skill_codes": [value.strip() for value in skills.split(",") if value.strip()],
                    "bloom_levels": bloom_levels,
                }
            )
            st.success("Đã cập nhật cấu hình bài thi thích ứng.")
        except APIClientError as error:
            st.error(str(error))
