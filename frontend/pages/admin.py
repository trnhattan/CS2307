import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient
from frontend.components.header import render_header


def render(client: ExamAPIClient) -> None:
    render_header()
    try:
        payload = client.admin_overview()
    except APIClientError as error:
        st.error(str(error))
        return
    st.markdown("<div class='section-title'>System overview</div>", unsafe_allow_html=True)
    st.caption("Current operational state of the question bank and knowledge base.")

    first = st.columns(4)
    first[0].metric("Subjects", payload["subjects"])
    first[1].metric("Questions", payload["questions"])
    first[2].metric("Active questions", payload["active_questions"])
    first[3].metric("Accounts", payload["users"])
    second = st.columns(3)
    second[0].metric("Knowledge units", payload["knowledge_units"])
    second[1].metric("Knowledge facts", payload["knowledge_facts"])
    second[2].metric("Active rules", payload["knowledge_rules"])

    st.subheader("Question-bank readiness")
    st.progress(min(1.0, payload["question_bank_completion_percent"] / 100))
    st.write(
        f"**{payload['questions']}/{payload['question_bank_target']} questions** "
        f"({payload['question_bank_completion_percent']:.1f}%)"
    )
