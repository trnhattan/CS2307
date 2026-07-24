import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient


def render_explanation_action(
    client: ExamAPIClient,
    session_id: int,
    *,
    technical: bool,
) -> None:
    key = f"llm_explanation_grounded_v1_{'staff' if technical else 'taker'}_{session_id}"
    cached = st.session_state.get(key)
    label = "Generate technical explanation" if technical else "Get Vietnamese learning feedback"
    st.caption("The LLM runs only on request. The Vietnamese response is persisted and reused to control token cost.")
    if st.button(label, key=f"button_{key}", width="stretch"):
        try:
            with st.spinner("Generating Vietnamese feedback from scored evidence..."):
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
    st.caption(
        f"Persisted artifact #{cached['artifact_id']} · model {cached['model']} · "
        f"{'cache reused' if cached.get('cached') else 'new generation'}"
    )
    if cached.get("evidence_used"):
        with st.expander("Evidence used"):
            for value in cached["evidence_used"]:
                st.write(f"- {value}")
    if cached.get("limitations"):
        st.caption("Limitations: " + " · ".join(cached["limitations"]))
    if cached.get("cached"):
        st.caption("The persisted explanation was reused; no additional LLM call was made.")
