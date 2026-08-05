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
    st.markdown("<div class='section-title'>🏆 Test Result Summary</div>", unsafe_allow_html=True)
    st.write("")

    with st.container(border=True):
        score, percent = st.columns(2)
        score.metric("Score", f"{result['total_score']:.1f}/{result['max_score']:.0f}")
        percent.metric("Percentage", f"{result['percentage']:.1f}%")

        st.write("")
        st.markdown(
            f"<div style='background-color: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 12px; padding: 1rem; color: #065f46; font-weight: 600;'>"
            f"💡 Understanding Level: {result['understanding_label']}"
            f"</div>",
            unsafe_allow_html=True
        )
        st.write("")

    st.write("")
    render_explanation_action(client, result["session_id"], technical=False)
    st.write("")

    with st.expander("📝 Review answers and detailed explanations", expanded=False):
        for index, item in enumerate(result["feedback"], start=1):
            is_correct = item["is_correct"]
            bg_color = "#f0fdf4" if is_correct else "#fef2f2"
            border_color = "#bbf7d0" if is_correct else "#fecaca"
            text_color = "#166534" if is_correct else "#991b1b"
            icon = "✅" if is_correct else "❌"

            st.markdown(
                f"""
                <div style='background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 14px; padding: 1.25rem; margin-bottom: 1rem;'>
                  <span style='color: {text_color}; font-weight: 700; font-size: 0.95rem;'>{icon} Question {index}</span>
                </div>
                """,
                unsafe_allow_html=True
            )

            if item.get("stem"):
                st.markdown(f"**{item['stem']}**")

            st.write(f"**Your answer:** {item['selected_option_text']}")
            if not is_correct:
                st.markdown(f"<span style='color: #b91c1c;'>**Correct answer:** {item['correct_option_text']}</span>", unsafe_allow_html=True)

            if item["explanation"]:
                st.markdown(
                    f"<div style='background-color: #f8fafc; border-left: 4px solid #cbd5e1; padding: 0.75rem 1rem; margin-top: 0.5rem; font-size: 0.88rem; color: #475569;'>"
                    f"ℹ️ {item['explanation']}"
                    f"</div>",
                    unsafe_allow_html=True
                )
            st.divider()

    st.write("")
    has_next = st.session_state.session_index + 1 < len(
        st.session_state.exam_payload["sessions"]
    )
    if has_next:
        if st.button("Continue to the next subject →", type="primary", width="stretch"):
            st.session_state.session_index += 1
            next_session = st.session_state.exam_payload["sessions"][
                st.session_state.session_index
            ]
            st.session_state.exam_started_at[str(next_session["session_id"])] = time.time()
            go("exam")
    elif st.button("View test summary", type="primary", width="stretch"):
        go("summary")
