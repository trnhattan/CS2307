import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient
from frontend.components.header import render_header
from frontend.state import go


def render(client: ExamAPIClient) -> None:
    render_header()
    st.markdown("<div class='section-title'>Tiến độ học tập của bạn</div>", unsafe_allow_html=True)
    st.caption("Kết quả được cập nhật sau mỗi bài thi đã hoàn thành.")
    try:
        payload = client.taker_dashboard()
    except APIClientError as error:
        st.error(str(error))
        return

    summary = payload["summary"]
    columns = st.columns(4)
    columns[0].metric("Bài đã hoàn thành", summary["completed_tests"])
    columns[1].metric("Tất cả phiên thi", summary["total_tests"])
    columns[2].metric("Điểm trung bình", f"{summary['average_score_percent']:.1f}%")
    columns[3].metric("Điểm cao nhất", f"{summary['best_score_percent']:.1f}%")

    st.subheader("Tiến độ theo môn")
    progress = payload["subject_progress"]
    st.dataframe(
        [
            {
                "Môn học": item["subject_name"],
                "Số bài": item["completed_tests"],
                "Điểm gần nhất": (
                    f"{item['latest_score_percent']:.1f}%"
                    if item["latest_score_percent"] is not None
                    else "Chưa có"
                ),
                "Điểm trung bình": f"{item['average_score_percent']:.1f}%",
                "Điểm cao nhất": f"{item['best_score_percent']:.1f}%",
                "Mức độ hiểu": item["understanding_label"],
            }
            for item in progress
        ],
        width="stretch",
        hide_index=True,
    )

    st.subheader("Lộ trình học tập đề xuất")
    learning_path = payload["learning_path"]
    if not learning_path:
        st.info("Hoàn thành một bài thi để hệ thống xây dựng lộ trình học tập.")
    for step in learning_path:
        evidence = (
            f"Độ chính xác {step['accuracy_percent']:.1f}% · "
            f"{step['evidence_count']} câu"
            if step["accuracy_percent"] is not None
            else "Chưa có dữ liệu làm bài"
        )
        st.markdown(
            f"""
            <div class="path-step">
              <strong>{step['priority']}. {step['unit_name']}</strong>
              <div>{step['action']}</div>
              <small>{step['subject_name']} · {evidence}</small>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.subheader("Lịch sử gần đây")
    history = payload["recent_tests"]
    if history:
        st.dataframe(
            [
                {
                    "Môn học": item["subject_name"],
                    "Điểm": f"{item['score_percent']:.1f}%",
                    "Mức độ hiểu": item["understanding_label"],
                    "Hoàn thành": item["finished_at"],
                }
                for item in history
            ],
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("Bạn chưa hoàn thành bài thi nào.")

    if st.button("Bắt đầu bài thi mới", type="primary", width="stretch"):
        go("subjects")
