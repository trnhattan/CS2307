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
    render_assessment_dashboard(payload, "Bảng điều khiển giám sát")


def render_assessment_dashboard(payload: dict, title: str) -> None:
    st.markdown(f"<div class='section-title'>{title}</div>", unsafe_allow_html=True)
    summary = payload["summary"]
    columns = st.columns(5)
    columns[0].metric("Phiên thi", summary["total_sessions"])
    columns[1].metric("Hoàn thành", summary["completed_sessions"])
    columns[2].metric("Đang làm", summary["in_progress_sessions"])
    columns[3].metric("Thí sinh", summary["exam_takers"])
    columns[4].metric("Điểm trung bình", f"{summary['average_score_percent']:.1f}%")

    st.subheader("Tổng quan thí sinh")
    takers = payload["takers"]
    st.dataframe(
        [
            {
                "Thí sinh": item["student_name"],
                "Mã sinh viên": item["student_code"],
                "Bài hoàn thành": item["completed_tests"],
                "Môn đã đánh giá": item["subjects_assessed"],
                "Điểm trung bình": f"{item['average_score_percent']:.1f}%",
                "Điểm cao nhất": f"{item['best_score_percent']:.1f}%",
                "Điểm gần nhất": (
                    f"{item['latest_score_percent']:.1f}%"
                    if item["latest_score_percent"] is not None
                    else "Chưa có"
                ),
                "Theta trung bình": (
                    round(item["average_theta"], 3)
                    if item["average_theta"] is not None
                    else None
                ),
                "Làm chủ trung bình": (
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

    st.subheader("Các bài thi đã sinh")
    sessions = payload["sessions"]
    if not sessions:
        st.info("Chưa có phiên thi nào.")
    else:
        table = [
            {
                "Phiên": item["session_id"],
                "Thí sinh": item["student_name"],
                "Môn": item["subject_name"],
                "Trạng thái": item["status"],
                "Đã trả lời": f"{item['answered_count']}/{item['question_count']}",
                "Điểm": f"{item['score_percent']:.1f}%",
                "Theta": round(item["theta_current"], 3),
                "SE": round(item["standard_error"], 3),
            }
            for item in sessions
        ]
        st.dataframe(table, width="stretch", hide_index=True)
        selected_id = st.selectbox(
            "Chi tiết phiên thi",
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
                st.subheader("Quỹ đạo CAT")
                st.dataframe(
                    [
                        {
                            "Câu": item["order_no"],
                            "Mã": item["question_code"],
                            "Đúng": item["is_correct"],
                            "Theta trước": item["theta_before"],
                            "Theta sau": item["theta_after"],
                            "SE": item["standard_error_after"],
                            "Information": item["item_information"],
                            "Lý do chọn": item["selection_reason"],
                        }
                        for item in adaptive["items"]
                    ],
                    width="stretch",
                    hide_index=True,
                )
            except APIClientError as error:
                st.error(str(error))

    st.subheader("Năng lực theo thí sinh và môn học")
    abilities = payload["abilities"]
    if abilities:
        st.dataframe(
            [
                {
                    "Thí sinh": item["student_name"],
                    "Môn": item["subject_name"],
                    "Theta": round(item["theta"], 4),
                    "Sai số chuẩn": round(item["standard_error"], 4),
                    "Xác suất làm chủ": (
                        round(item["mastery_probability"], 4)
                        if item["mastery_probability"] is not None
                        else None
                    ),
                    "Bằng chứng": item["evidence_count"],
                }
                for item in abilities
            ],
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("Chưa có kết quả năng lực sau bài thi.")


def render_session_detail(session: dict) -> None:
    theta_delta = session["theta_current"] - session["theta_initial"]
    left, middle, right = st.columns(3)
    left.metric(
        "Theta sau bài",
        f"{session['theta_current']:.3f}",
        delta=f"{theta_delta:+.3f}",
    )
    middle.metric("Sai số chuẩn", f"{session['standard_error']:.3f}")
    right.metric(
        "Fisher information TB",
        f"{session['average_item_information']:.3f}",
    )
    charts = st.columns(2)
    with charts[0]:
        st.caption("Phân bố độ khó")
        st.bar_chart(
            [
                {"Mức": key, "Số câu": value}
                for key, value in session["difficulty_distribution"].items()
            ],
            x="Mức",
            y="Số câu",
        )
    with charts[1]:
        st.caption("Phân bố Bloom")
        st.bar_chart(
            [
                {"Mức": key, "Số câu": value}
                for key, value in session["bloom_distribution"].items()
            ],
            x="Mức",
            y="Số câu",
        )
    with st.expander("Cấu hình đã dùng để sinh đề"):
        st.json(session["generation_config"])


def _session_label(session_id: int, sessions: list[dict]) -> str:
    session = next(item for item in sessions if item["session_id"] == session_id)
    return (
        f"#{session_id} · {session['student_name']} · "
        f"{session['subject_name']} · {session['status']}"
    )
