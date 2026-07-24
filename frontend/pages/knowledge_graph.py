import json

import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient
from frontend.components.header import render_header


def render(client: ExamAPIClient) -> None:
    render_header()
    user = st.session_state.user
    st.markdown("<div class='section-title'>Đồ thị tri thức và năng lực</div>", unsafe_allow_html=True)
    try:
        if user["role"] == "exam_taker":
            payload = client.taker_knowledge_graph()
        else:
            dashboard = client.supervisor_dashboard()
            takers = dashboard["takers"]
            if not takers:
                st.info("Chưa có thí sinh để hiển thị.")
                return
            selected = st.selectbox(
                "Thí sinh",
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
            "Chưa có bằng chứng bài làm để xây dựng đồ thị. "
            "Đồ thị sẽ xuất hiện sau khi thí sinh hoàn thành ít nhất một bài thi."
        )
        return
    st.graphviz_chart(_dot(payload), width="stretch")
    st.caption("Các liên kết thể hiện môn học, đơn vị tri thức, câu đã làm và đề xuất tiếp theo.")


def _dot(payload: dict) -> str:
    lines = ["digraph G {", "rankdir=LR;", 'node [shape=box, style="rounded,filled"];']
    colors = {
        "student": "#dbeafe",
        "subject": "#dcfce7",
        "topic": "#fef3c7",
        "skill": "#fae8ff",
        "question": "#f3f4f6",
        "evidence": "#fee2e2",
    }
    for node in payload["nodes"]:
        node_id = json.dumps(node["id"])
        label = json.dumps(node["label"])
        color = colors.get(node["type"], "#ffffff")
        lines.append(f"{node_id} [label={label}, fillcolor=\"{color}\"];")
    for edge in payload["edges"]:
        lines.append(
            f"{json.dumps(edge['source'])} -> {json.dumps(edge['target'])} "
            f"[label={json.dumps(edge['relation'])}];"
        )
    lines.append("}")
    return "\n".join(lines)
