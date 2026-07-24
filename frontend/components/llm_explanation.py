import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient


def render_explanation_action(
    client: ExamAPIClient,
    session_id: int,
    *,
    technical: bool,
) -> None:
    key = f"llm_explanation_{'staff' if technical else 'taker'}_{session_id}"
    cached = st.session_state.get(key)
    label = "Tạo diễn giải kỹ thuật" if technical else "Nhận nhận xét học tập"
    st.caption("Chỉ gọi LLM khi bạn bấm nút; kết quả được lưu để không tốn token lặp lại.")
    if st.button(label, key=f"button_{key}", width="stretch"):
        try:
            with st.spinner("Đang diễn giải từ bằng chứng đã chấm..."):
                cached = (
                    client.staff_exam_explanation(session_id)
                    if technical
                    else client.taker_exam_explanation(session_id)
                )
                st.session_state[key] = cached
        except APIClientError as error:
            st.error(str(error))
            return
    if not cached:
        return
    st.info(cached["explanation"])
    if cached.get("evidence_used"):
        with st.expander("Bằng chứng được dùng"):
            for value in cached["evidence_used"]:
                st.write(f"- {value}")
    if cached.get("limitations"):
        st.caption("Giới hạn: " + " · ".join(cached["limitations"]))
    if cached.get("cached"):
        st.caption("Đã dùng bản diễn giải được lưu trước đó.")
