import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient
from frontend.components.header import render_header
from frontend.components.interactive_graph import render_interactive_graph
from frontend.components.profile_table import render_criterion_profile_table
from frontend.components.radar_chart import render_criterion_radar
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

    st.subheader("Overview")
    try:
        profile = client.taker_profile()
    except APIClientError as error:
        st.warning(f"Criterion profile is temporarily unavailable: {error}")
        profile = {"subjects": []}
    profile_subjects = profile.get("subjects") or []
    if not profile_subjects:
        st.info("No assessment criteria are available yet.")
    else:
        selected_subject = st.selectbox(
            "Radar view",
            options=["OVERALL", *[item["subject_code"] for item in profile_subjects]],
            format_func=lambda code: next(
                (
                    "Overall"
                    if code == "OVERALL"
                    else item["subject_name"]
                    for item in profile_subjects
                    if code == "OVERALL" or item["subject_code"] == code
                )
            ),
        )
        radar = None
        try:
            radar = client.taker_radar(selected_subject)
        except APIClientError as error:
            st.warning(f"Criterion radar is temporarily unavailable: {error}")
        if selected_subject == "OVERALL":
            overview = st.columns(4)
            overview[0].metric("Assessed subjects", len(profile_subjects))
            overview[1].metric(
                "Mastered criteria",
                sum(len(item["strengths"]) for item in profile_subjects),
            )
            overview[2].metric(
                "Improved criteria",
                sum(len(item["improved"]) for item in profile_subjects),
            )
            overview[3].metric(
                "Needs attention",
                sum(len(item["weaknesses"]) for item in profile_subjects),
            )
            if radar:
                render_criterion_radar(radar)
            st.dataframe(
                [
                    {
                        "Subject": item["subject_name"],
                        "Mastered criteria": len(item["strengths"]),
                        "Improved criteria": len(item["improved"]),
                        "Needs attention": len(item["weaknesses"]),
                        "Not assessed": len(item["insufficient_evidence"]),
                    }
                    for item in profile_subjects
                ],
                width="stretch",
                hide_index=True,
            )
        else:
            selected_profile = next(
                item for item in profile_subjects
                if item["subject_code"] == selected_subject
            )
            overview = st.columns(4)
            overview[0].metric("Strengths", len(selected_profile["strengths"]))
            overview[1].metric("Needs attention", len(selected_profile["weaknesses"]))
            overview[2].metric("Improved", len(selected_profile["improved"]))
            overview[3].metric(
                "Not assessed", len(selected_profile["insufficient_evidence"])
            )
            if radar:
                render_criterion_radar(radar)
            render_criterion_profile_table(
                selected_profile["criteria"],
                (radar or {}).get("axes", []),
            )

    st.subheader("Recommended learning path")
    learning_path = payload["learning_path"]
    if not learning_path:
        st.info("Complete a test to build your evidence-based learning path.")
    else:
        st.caption(
            "Each subject is ordered from the lowest current criterion mastery through "
            "the Understands level. Mastered criteria are omitted."
        )
        grouped_paths: dict[str, list[dict]] = {}
        for step in learning_path:
            grouped_paths.setdefault(step["subject_code"], []).append(step)
        path_nodes = []
        path_edges = []
        for subject_code, subject_steps in grouped_paths.items():
            subject_steps.sort(
                key=lambda step: (
                    step.get("mastery_percent") is not None,
                    (
                        step.get("mastery_percent")
                        if step.get("mastery_percent") is not None
                        else -1
                    ),
                    -int(step.get("evidence_count") or 0),
                    step["unit_name"],
                )
            )
            subject_node_id = f"path-subject:{subject_code}"
            path_nodes.append(
                {
                    "id": subject_node_id,
                    "label": subject_steps[0]["subject_name"],
                    "type": "subject",
                    "attributes": {
                        "criteria_to_improve": len(subject_steps),
                        "lowest_mastery": (
                            f"{subject_steps[0].get('mastery_percent'):.1f}%"
                            if subject_steps[0].get("mastery_percent") is not None
                            else "Not assessed"
                        ),
                    },
                }
            )
            criterion_nodes = []
            for index, step in enumerate(subject_steps, 1):
                criterion_nodes.append(
                    {
                        "id": f"path:{subject_code}:{step['unit_code'] or index}",
                        "label": f"{index}. {step['unit_name']}",
                        "type": "path",
                        "attributes": {
                            "mastery": (
                                f"{step.get('mastery_percent'):.1f}%"
                                if step.get("mastery_percent") is not None
                                else "Not assessed"
                            ),
                            "understanding": step.get("understanding_label"),
                            "action": step["action"],
                        },
                    }
                )
            path_nodes.extend(criterion_nodes)
            if criterion_nodes:
                path_edges.append(
                    {
                        "source": subject_node_id,
                        "target": criterion_nodes[0]["id"],
                        "relation": "has learning step",
                        "display_label": "Start here",
                        "provenance": {
                            "source": "Rela-model criterion mastery rules",
                        },
                    }
                )
            path_edges.extend(
                {
                    "source": previous["id"],
                    "target": current["id"],
                    "relation": "recommended next",
                    "display_label": "Next step",
                    "provenance": {
                        "source": "Rela-model criterion mastery rules",
                    },
                }
                for previous, current in zip(criterion_nodes, criterion_nodes[1:])
            )
        render_interactive_graph(
            path_nodes,
            path_edges,
            key="taker_learning_paths_by_subject",
            height=520,
            expand_roots_initially=False,
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
