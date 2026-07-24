import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient
from frontend.components.header import render_header
from frontend.components.interactive_graph import render_interactive_graph
from frontend.state import go


def render(client: ExamAPIClient) -> None:
    render_header()
    st.markdown("<div class='section-title'>Your learning progress</div>", unsafe_allow_html=True)
    st.caption("Progress is updated after every completed test.")
    try:
        payload = client.taker_dashboard()
    except APIClientError as error:
        st.error(str(error))
        return

    summary = payload["summary"]
    columns = st.columns(4)
    columns[0].metric("Completed tests", summary["completed_tests"])
    columns[1].metric("All sessions", summary["total_tests"])
    columns[2].metric("Average score", f"{summary['average_score_percent']:.1f}%")
    columns[3].metric("Best score", f"{summary['best_score_percent']:.1f}%")

    st.subheader("Progress by subject")
    progress = payload["subject_progress"]
    st.dataframe(
        [
            {
                "Subject": item["subject_name"],
                "Tests": item["completed_tests"],
                "Latest score": (
                    f"{item['latest_score_percent']:.1f}%"
                    if item["latest_score_percent"] is not None
                    else "Not assessed"
                ),
                "Average score": f"{item['average_score_percent']:.1f}%",
                "Best score": f"{item['best_score_percent']:.1f}%",
                "Understanding": item["understanding_label"],
            }
            for item in progress
        ],
        width="stretch",
        hide_index=True,
    )

    st.subheader("Recommended learning path")
    learning_path = payload["learning_path"]
    if not learning_path:
        st.info("Complete a test to build your evidence-based learning path.")
    else:
        path_nodes = [
            {
                "id": f"path:{step['priority']}",
                "label": f"{step['priority']}. {step['unit_name']}",
                "type": "path",
                "attributes": {
                    "subject": step["subject_name"],
                    "action": step["action"],
                    "accuracy_percent": step["accuracy_percent"],
                    "evidence_count": step["evidence_count"],
                },
            }
            for step in learning_path
        ]
        path_edges = [
            {
                "source": path_nodes[index]["id"],
                "target": path_nodes[index + 1]["id"],
                "relation": "recommended next",
                "provenance": {"source": "Rela-model learning rules"},
            }
            for index in range(len(path_nodes) - 1)
        ]
        st.caption(
            "Double-click a learning step to expand or collapse the next recommendation."
        )
        render_interactive_graph(path_nodes, path_edges, key="taker_learning_path", height=380)
    for step in learning_path:
        evidence = (
            f"Accuracy {step['accuracy_percent']:.1f}% · "
            f"{step['evidence_count']} questions"
            if step["accuracy_percent"] is not None
            else "No response evidence yet"
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

    st.subheader("Recent history")
    history = payload["recent_tests"]
    if history:
        st.dataframe(
            [
                {
                    "Subject": item["subject_name"],
                    "Score": f"{item['score_percent']:.1f}%",
                    "Understanding": item["understanding_label"],
                    "Completed": item["finished_at"],
                }
                for item in history
            ],
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("You have not completed a test yet.")

    if st.button("Start a new test", type="primary", width="stretch"):
        go("subjects")
