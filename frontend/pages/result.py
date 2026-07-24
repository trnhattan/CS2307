import time

import streamlit as st

from frontend.components.header import render_header
from frontend.components.llm_explanation import render_explanation_action
from frontend.api_client import ExamAPIClient
from frontend.state import go


def render(client: ExamAPIClient) -> None:
    result = st.session_state.last_result
    if not result:
        go("subjects")
        return
    render_header()
    st.markdown("<div class='section-title'>Kết quả môn thi</div>", unsafe_allow_html=True)
    score, percent = st.columns(2)
    score.metric("Điểm", f"{result['total_score']:.1f}/{result['max_score']:.0f}")
    percent.metric("Tỷ lệ", f"{result['percentage']:.1f}%")
    st.success(f"Mức độ hiểu bài: **{result['understanding_label']}**")
    render_explanation_action(client, result["session_id"], technical=False)

    with st.expander("Xem đáp án và giải thích", expanded=False):
        for index, item in enumerate(result["feedback"], start=1):
            icon = "✅" if item["is_correct"] else "❌"
            st.markdown(f"**{icon} Câu {index}**")
            st.write(f"Bạn chọn: {item['selected_option_text']}")
            if not item["is_correct"]:
                st.write(f"Đáp án đúng: {item['correct_option_text']}")
            if item["explanation"]:
                st.caption(item["explanation"])
            st.divider()

    has_next = st.session_state.session_index + 1 < len(
        st.session_state.exam_payload["sessions"]
    )
    if has_next:
        if st.button("Tiếp tục môn kế tiếp →", type="primary", width="stretch"):
            st.session_state.session_index += 1
            next_session = st.session_state.exam_payload["sessions"][
                st.session_state.session_index
            ]
            st.session_state.exam_started_at[str(next_session["session_id"])] = time.time()
            go("exam")
    elif st.button("Xem tổng kết", type="primary", width="stretch"):
        go("summary")
