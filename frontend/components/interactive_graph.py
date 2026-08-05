import html
import json
import textwrap
from pathlib import Path
from typing import Any

import networkx as nx
import streamlit as st
from pyvis.network import Network


ASSET_DIR = Path(__file__).resolve().parent

NODE_COLORS = {
    "student": "#8fb3ff",
    "subject": "#72d6a0",
    "topic": "#ffd166",
    "skill": "#d6a2e8",
    "criterion": "#d6a2e8",
    "question": "#cbd5e1",
    "evidence": "#ffaaa5",
    "recommendation": "#67e8f9",
    "path": "#a7f3d0",
}

NODE_BORDERS = {
    "student": "#3b6fc4",
    "subject": "#2f855a",
    "topic": "#c48b16",
    "skill": "#8b5aa5",
    "criterion": "#8b5aa5",
    "question": "#64748b",
    "evidence": "#c66b67",
    "recommendation": "#16879a",
    "path": "#3b8f70",
}

NODE_TYPE_LABELS = {
    "student": "Exam taker",
    "subject": "Subject",
    "topic": "Topic",
    "skill": "Skill",
    "criterion": "Assessment criterion",
    "question": "Question",
    "evidence": "Response",
    "recommendation": "Recommendation",
    "path": "Learning step",
}

RELATION_LABELS = {
    "has_ability": "Has learning evidence for",
    "belongs_to_subject": "Belongs to subject",
    "prerequisite_of": "Prepares for",
    "produced_evidence": "Produced response",
    "answers": "Answers",
    "measures": "Measures",
    "supports_ability": "Supports understanding of",
    "recommended_next": "Recommended next step",
    "has_learning_step": "Needs improvement in",
    "has_subject": "Has learning profile for",
    "has_criterion": "Requires understanding of",
    "answered_question": "Answered question",
    "subject_needs_review": "Needs review",
    "subject_developing": "Developing",
    "subject_understands": "Understands",
    "subject_mastered": "Proficient",
    "criterion_needs_review": "Needs review",
    "criterion_developing": "Developing",
    "criterion_understands": "Understands",
    "criterion_mastered": "Mastered",
}

ATTRIBUTE_LABELS = {
    "knowledge_type": "Knowledge type",
    "unit_type": "Knowledge type",
    "understanding": "Understanding",
    "evidence_count": "Answered questions",
    "correct": "Answer result",
    "result": "Answer result",
    "question_text": "Question",
    "accuracy_percent": "Accuracy",
    "mastery_probability": "Mastery probability",
    "standard_error": "Standard error",
    "theta": "Ability estimate",
    "answered_at": "Answered at",
    "action": "Learning action",
    "subject": "Subject",
    "recommendation": "Recommendation",
    "reasoning_rule": "Reasoning rule",
    "reasoning_trace": "Reasoning trace",
    "source": "Evidence source",
    "learning_objective": "Learning objective",
    "success_statement": "Success criterion",
    "difficulty": "Question difficulty",
    "bloom_level": "Cognitive level",
    "mastery_percent": "Understanding",
    "answer_result": "Answer result",
    "question_code": "Question reference",
    "completed_tests": "Completed tests",
}

SOURCE_LABELS = {
    "knowledge_units": "Course knowledge structure",
    "knowledge_units.parent_unit_id": "Course prerequisite structure",
    "question_knowledge_units": "Question knowledge mapping",
    "exam_items": "Completed test responses",
}

HIDDEN_TOOLTIP_FIELDS = {"exam_item_id", "trace_id", "rule_code"}


def render_interactive_graph(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    *,
    key: str,
    height: int = 650,
    expand_roots_initially: bool = True,
) -> None:
    graph = nx.MultiDiGraph()
    node_ids = {str(node["id"]) for node in nodes}
    normalized_edges = []
    for index, edge in enumerate(edges):
        source = str(edge["source"])
        target = str(edge["target"])
        if source not in node_ids or target not in node_ids:
            continue
        relation_key = _relation_key(edge.get("relation"))
        normalized_edges.append(
            {
                "id": f"relationship-{index}",
                "source": source,
                "target": target,
                "relation": relation_key,
                "label": _clean_label(
                    edge.get("display_label"),
                    RELATION_LABELS.get(relation_key, _humanize(relation_key)),
                ),
                "provenance": edge.get("provenance") or {},
            }
        )
    root_ids, parent_by_node, children_by_parent = _expansion_structure(
        nodes, normalized_edges
    )
    initially_visible = set(root_ids)
    if expand_roots_initially:
        for root_id in root_ids:
            initially_visible.update(children_by_parent.get(root_id, []))

    for node in nodes:
        node_id = str(node["id"])
        node_type = str(node.get("type", "node"))
        full_label = _clean_label(node.get("label"), NODE_TYPE_LABELS.get(node_type, "Node"))
        attributes = node.get("attributes") or {}
        background = NODE_COLORS.get(node_type, "#e2e8f0")
        border = NODE_BORDERS.get(node_type, "#64748b")
        graph.add_node(
            node_id,
            label=_wrap_label(full_label),
            fullLabel=full_label,
            tooltipRows=_node_tooltip(node_type, full_label, attributes),
            color={
                "background": background,
                "border": border,
                "highlight": {"background": background, "border": "#1d4ed8"},
                "hover": {"background": background, "border": "#334155"},
            },
            shape="dot" if node_type in {"student", "subject"} else "box",
            size=30 if node_type == "student" else 21,
            nodeType=node_type,
            borderWidth=2 if node_type in {"student", "subject"} else 1,
            borderWidthSelected=3,
            widthConstraint={"maximum": 205},
            margin=11,
            hidden=node_id not in initially_visible,
            physics=node_id in initially_visible,
        )
    for edge in normalized_edges:
        source = edge["source"]
        target = edge["target"]
        relation_key = edge["relation"]
        relation_label = edge["label"]
        graph.add_edge(
            source,
            target,
            id=edge["id"],
            label=relation_label,
            relationKey=relation_key,
            relationLabel=relation_label,
            tooltipRows=_edge_tooltip(relation_label, edge["provenance"]),
            arrows="to",
            color="#94a3b8",
            width=1.15,
            hidden=source not in initially_visible or target not in initially_visible,
            physics=source in initially_visible and target in initially_visible,
        )

    network = Network(
        height=f"{height}px",
        width="100%",
        bgcolor="#f8fafc",
        font_color="#172554",
        directed=True,
        cdn_resources="in_line",
        select_menu=False,
        filter_menu=False,
    )
    network.from_nx(graph)
    network.set_options(
        json.dumps(
            {
                "interaction": {
                    "dragNodes": True,
                    "dragView": True,
                    "hover": True,
                    "keyboard": {"enabled": True},
                    "multiselect": False,
                    "navigationButtons": True,
                    "zoomView": True,
                },
                "physics": {
                    "enabled": False,
                    "stabilization": {"enabled": False},
                    "barnesHut": {
                        "gravitationalConstant": -4300,
                        "centralGravity": 0.12,
                        "springLength": 175,
                        "springConstant": 0.025,
                        "damping": 0.3,
                        "avoidOverlap": 0.65,
                    },
                },
                "edges": {
                    "smooth": {"enabled": True, "type": "dynamic"},
                    "font": {
                        "size": 10,
                        "face": "Inter, Arial, sans-serif",
                        "color": "#475569",
                        "background": "rgba(248,250,252,.88)",
                        "strokeWidth": 0,
                    },
                },
                "nodes": {
                    "font": {
                        "size": 13,
                        "face": "Inter, Arial, sans-serif",
                        "color": "#172554",
                        "multi": False,
                    },
                    "chosen": True,
                },
            }
        )
    )
    graph_config = {
        "key": key,
        "rootNodeIds": root_ids,
        "parentByNode": parent_by_node,
        "childrenByParent": children_by_parent,
        "initialExpanded": root_ids if expand_roots_initially else [],
    }
    document = network.generate_html(notebook=False)
    document = _inject_explorer(document, nodes, normalized_edges, graph_config)
    st.iframe(document, width="stretch", height="content", tab_index=0)


def _inject_explorer(
    document: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    graph_config: dict[str, Any],
) -> str:
    css = (ASSET_DIR / "graph_explorer.css").read_text()
    javascript = (ASSET_DIR / "graph_explorer.js").read_text()
    node_types = sorted({str(node.get("type", "node")) for node in nodes})
    relations = sorted({edge["relation"] for edge in edges})
    search_options = "".join(
        f'<option value="{html.escape(_clean_label(node.get("label"), "Node"), quote=True)}"></option>'
        for node in nodes
    )
    type_options = "".join(
        f'<option value="{html.escape(node_type, quote=True)}">'
        f'{html.escape(NODE_TYPE_LABELS.get(node_type, _humanize(node_type)))}</option>'
        for node_type in node_types
    )
    relation_options = "".join(
        f'<option value="{html.escape(relation, quote=True)}">'
        f'{html.escape(RELATION_LABELS.get(relation, _humanize(relation)))}</option>'
        for relation in relations
    )
    legend = "".join(
        f'<span class="legend-item"><span class="legend-dot" style="background:{NODE_COLORS.get(node_type, "#e2e8f0")}"></span>'
        f'{html.escape(NODE_TYPE_LABELS.get(node_type, _humanize(node_type)))}</span>'
        for node_type in node_types
    )
    toolbar = f"""
    <div class="graph-explorer">
      <div class="graph-toolbar" role="toolbar" aria-label="Graph navigation controls">
        <div class="graph-filter-row">
          <div class="graph-field">
            <label for="graph-search">Search nodes</label>
            <input id="graph-search" list="graph-search-options" placeholder="Type a subject, topic, skill, or question" />
            <datalist id="graph-search-options">{search_options}</datalist>
          </div>
          <div class="graph-field">
            <label for="graph-node-filter">Node type</label>
            <select id="graph-node-filter"><option value="all">All node types</option>{type_options}</select>
          </div>
          <div class="graph-field">
            <label for="graph-edge-filter">Relationship</label>
            <select id="graph-edge-filter"><option value="all">All relationships</option>{relation_options}</select>
          </div>
          <button id="graph-find" type="button">Find</button>
        </div>
        <div class="graph-action-row">
          <button id="graph-expand" type="button" disabled>Expand selected</button>
          <button id="graph-collapse" type="button" disabled>Collapse branch</button>
          <button id="graph-show-all" type="button">Show all</button>
          <button id="graph-reset" type="button">Reset view</button>
          <button id="graph-physics" type="button">Resume layout</button>
        </div>
      </div>
      <div class="graph-meta">
        <span id="graph-status" class="graph-help">Select a node, then expand or collapse its branch. Double-click toggles a branch.</span>
        <span id="graph-count" class="graph-count"></span>
        <span class="graph-legend">{legend}</span>
      </div>
    """
    document = document.replace("</head>", f"<style>{css}</style></head>")
    document = document.replace(
        '<div id="mynetwork" class="card-body"></div>',
        f'{toolbar}<div id="mynetwork" class="card-body"></div></div>',
    )
    safe_config = json.dumps(graph_config, ensure_ascii=True).replace("</", "<\\/")
    enhanced_draw = f"drawGraph();\nwindow.graphExplorerConfig = {safe_config};\n{javascript}"
    document = document.replace("drawGraph();", enhanced_draw, 1)
    return document


def _expansion_structure(
    nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
) -> tuple[list[str], dict[str, str], dict[str, list[str]]]:
    types = {str(node["id"]): str(node.get("type", "node")) for node in nodes}
    parent_by_node: dict[str, str] = {}
    priorities: dict[str, int] = {}

    def assign(child: str, parent: str, priority: int) -> None:
        if child == parent or child not in types or parent not in types:
            return
        if priority >= priorities.get(child, -1):
            parent_by_node[child] = parent
            priorities[child] = priority

    for edge in edges:
        source = edge["source"]
        target = edge["target"]
        relation = edge["relation"]
        if relation == "has_ability" and types.get(target) == "subject":
            assign(target, source, 10)
        elif (
            relation == "has_subject" or relation.startswith("subject_")
        ) and types.get(target) == "subject":
            assign(target, source, 10)
        elif (
            relation == "has_criterion" or relation.startswith("criterion_")
        ) and types.get(target) == "criterion":
            assign(target, source, 20)
        elif relation == "answered_question" and types.get(target) == "question":
            assign(target, source, 30)
        elif relation == "belongs_to_subject":
            assign(source, target, 20)
        elif relation == "prerequisite_of":
            assign(target, source, 30)
        elif relation == "measures":
            assign(source, target, 45 if types.get(target) == "skill" else 40)
        elif relation == "answers":
            assign(source, target, 50)
        elif relation == "recommended_next" and types.get(source) == types.get(target) == "path":
            assign(target, source, 50)
        elif relation == "has_learning_step" and types.get(target) == "path":
            assign(target, source, 50)

    node_ids = [str(node["id"]) for node in nodes]
    root_ids = [node_id for node_id in node_ids if node_id not in parent_by_node]
    if not root_ids and node_ids:
        root_ids = [node_ids[0]]
        parent_by_node.pop(node_ids[0], None)
    children_by_parent: dict[str, list[str]] = {}
    for child, parent in parent_by_node.items():
        children_by_parent.setdefault(parent, []).append(child)
    for children in children_by_parent.values():
        children.sort(key=lambda node_id: (_node_rank(types[node_id]), node_id))
    root_ids.sort(key=lambda node_id: (_node_rank(types[node_id]), node_id))
    return root_ids, parent_by_node, children_by_parent


def _node_rank(node_type: str) -> int:
    return {
        "student": 0,
        "subject": 1,
        "topic": 2,
        "skill": 3,
        "criterion": 3,
        "question": 4,
        "evidence": 5,
        "path": 0,
    }.get(node_type, 6)


def _wrap_label(value: str, width: int = 24, maximum_lines: int = 3) -> str:
    lines = textwrap.wrap(value, width=width, break_long_words=False, break_on_hyphens=False)
    if not lines:
        return value
    if len(lines) > maximum_lines:
        lines = lines[:maximum_lines]
        lines[-1] = lines[-1].rstrip(" .") + "…"
    return "\n".join(lines)


def _clean_label(value: Any, fallback: str) -> str:
    label = " ".join(str(value or "").split()).strip()
    return label or fallback


def _relation_key(value: Any) -> str:
    return "_".join(str(value or "related to").strip().lower().replace("-", " ").split())


def _humanize(value: Any) -> str:
    words = str(value or "").replace("_", " ").replace(".", " ").split()
    acronyms = {"api", "cat", "dns", "id", "ip", "irt", "sql", "tcp", "udp", "vlan"}
    result = [word.upper() if word.lower() in acronyms else word.lower() for word in words]
    return " ".join(result).capitalize()


def _human_value(name: str, value: Any) -> str:
    if isinstance(value, bool):
        if name in {"correct", "result"}:
            return "Correct" if value else "Incorrect"
        return "Yes" if value else "No"
    if name == "source":
        return SOURCE_LABELS.get(str(value), _humanize(value))
    if name in {"mastery_probability"} and isinstance(value, (float, int)):
        return f"{float(value) * 100:.1f}%"
    if name in {"accuracy_percent", "mastery_percent"} and isinstance(value, (float, int)):
        return f"{float(value):.1f}%"
    if isinstance(value, float):
        return f"{value:.3f}"
    return _humanize(value) if name in {"unit_type", "knowledge_type"} else str(value)


def _node_tooltip(
    kind: str, label: str, attributes: dict[str, Any]
) -> list[dict[str, Any]]:
    kind_label = NODE_TYPE_LABELS.get(kind, _humanize(kind))
    rows: list[dict[str, Any]] = [
        {"label": kind_label, "value": None, "heading": True},
        {"label": kind_label, "value": label, "heading": False},
    ]
    for name, value in attributes.items():
        if name in HIDDEN_TOOLTIP_FIELDS or value is None or isinstance(value, (dict, list)):
            continue
        field_label = ATTRIBUTE_LABELS.get(name, _humanize(name))
        rows.append(
            {
                "label": field_label,
                "value": _human_value(name, value),
                "heading": False,
            }
        )
    return rows


def _edge_tooltip(label: str, attributes: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {"label": label, "value": None, "heading": True}
    ]
    for name, value in attributes.items():
        if name in HIDDEN_TOOLTIP_FIELDS or value is None or isinstance(value, (dict, list)):
            continue
        field_label = ATTRIBUTE_LABELS.get(name, _humanize(name))
        rows.append(
            {
                "label": field_label,
                "value": _human_value(name, value),
                "heading": False,
            }
        )
    return rows
