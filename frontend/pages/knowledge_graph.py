import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient
from frontend.components.header import render_header
from frontend.components.interactive_graph import render_interactive_graph


def render(client: ExamAPIClient) -> None:
    render_header()
    user = st.session_state.user
    st.markdown("<div class='section-title'>Knowledge and ability graph</div>", unsafe_allow_html=True)
    try:
        if user["role"] == "exam_taker":
            payload = client.taker_knowledge_graph()
        else:
            dashboard = client.supervisor_dashboard()
            takers = dashboard["takers"]
            if not takers:
                st.info("No exam takers are available yet.")
                return
            selected = st.selectbox(
                "Exam taker",
                options=[item["student_id"] for item in takers],
                format_func=lambda value: next(
                    item["student_name"] for item in takers if item["student_id"] == value
                ),
            )
            payload = client.staff_knowledge_graph(selected)
    except APIClientError as error:
        st.error(str(error))
        return
    evidence_nodes = [node for node in payload["nodes"] if node["type"] != "student"]
    if not evidence_nodes:
        st.info(
            "There is no completed-response evidence yet. The graph will appear "
            "after the exam taker completes at least one test."
        )
        return
    render_interactive_graph(
        payload["nodes"],
        payload["edges"],
        key=f"knowledge_graph_{payload['student_id']}",
    )
    st.caption(
        "Double-click a node to expand or collapse its branch. You can also drag nodes, "
        "zoom the canvas, search by plain-English names, and filter node types or relationships."
    )
