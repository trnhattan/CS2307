from pathlib import Path

from streamlit.testing.v1 import AppTest

from frontend.components import interactive_graph
from frontend.components import profile_table
from frontend.pages import admin_config


ROOT = Path(__file__).resolve().parents[1]


def test_landing_page_loads_login_and_signup() -> None:
    app = AppTest.from_file(ROOT / "frontend" / "app.py").run(timeout=10)

    assert not app.exception
    assert [button.label for button in app.button] == ["Sign in", "Sign up"]


def test_login_opens_as_a_dialog() -> None:
    app = AppTest.from_file(ROOT / "frontend" / "app.py").run(timeout=10)

    app.button[0].click().run(timeout=10)

    assert not app.exception
    assert [field.label for field in app.text_input] == [
        "Username",
        "Password",
    ]


def test_taker_pages_do_not_render_staff_metrics() -> None:
    taker_pages = [
        "taker_dashboard.py",
        "subjects.py",
        "exam.py",
        "result.py",
        "summary.py",
        "cat_exam.py",
        "cat_result.py",
        "knowledge_graph.py",
        "learner_chat.py",
    ]
    forbidden = ("theta", "bloom", "fisher", "standard_error", "irt")

    for filename in taker_pages:
        source = (ROOT / "frontend" / "pages" / filename).read_text().lower()
        assert all(term not in source for term in forbidden)


def test_countdown_expiry_does_not_submit_or_block_exam() -> None:
    source = (ROOT / "frontend" / "components" / "countdown.py").read_text()

    assert "You may continue" in source
    assert "form_submit_button" not in source


def test_navigation_is_role_specific() -> None:
    source = (ROOT / "frontend" / "components" / "navigation.py").read_text()

    assert '"taker_dashboard", "Progress"' in source
    assert '"supervisor_config", "Exam configuration"' in source
    assert '"admin_questions", "Question bank"' in source
    assert '"admin_accounts", "Accounts"' in source


def test_fixed_exam_controls_are_consolidated() -> None:
    source = (ROOT / "frontend" / "pages" / "subjects.py").read_text()

    assert "Questions per subject" in source
    assert "Difficulty profile" in source
    assert "generate_with_blueprint" in source


def test_interactive_graph_uses_networkx_and_pyvis() -> None:
    source = (ROOT / "frontend" / "components" / "interactive_graph.py").read_text()
    explorer = (ROOT / "frontend" / "components" / "graph_explorer.js").read_text()

    assert "import networkx as nx" in source
    assert "from pyvis.network import Network" in source
    assert "navigationButtons" in source
    assert "MultiDiGraph" in source
    assert 'network.on("doubleClick"' in explorer
    assert "expandNode" in explorer
    assert "collapseNode" in explorer
    assert "graph-node-filter" in explorer
    assert "graph-edge-filter" in explorer


def test_graph_disables_global_stabilization_overlay(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(
        interactive_graph.st,
        "iframe",
        lambda document, **options: captured.append((document, options)),
    )
    interactive_graph.render_interactive_graph(
        [
            {"id": f"node:{index}", "label": f"Node {index}", "type": "topic"}
            for index in range(101)
        ],
        [],
        key="loading-overlay-test",
        height=300,
    )

    document, options = captured[0]
    assert 'id="loadingBar"' not in document
    assert 'network.on("stabilizationProgress"' not in document
    assert options == {"width": "stretch", "height": "content", "tab_index": 0}


def test_graph_runs_in_an_isolated_iframe() -> None:
    source = (ROOT / "frontend" / "components" / "interactive_graph.py").read_text()

    assert "st.iframe(document" in source
    assert "st.html(document" not in source


def test_graph_tooltips_use_structured_bold_labels() -> None:
    tooltip = interactive_graph._node_tooltip(
        "topic",
        "Audit History",
        {
            "knowledge_type": "Topic",
            "understanding": "Needs review",
            "evidence_count": 1,
        },
    )

    assert tooltip == [
        {"label": "Topic", "value": None, "heading": True},
        {"label": "Topic", "value": "Audit History", "heading": False},
        {"label": "Knowledge type", "value": "Topic", "heading": False},
        {"label": "Understanding", "value": "Needs review", "heading": False},
        {"label": "Answered questions", "value": "1", "heading": False},
    ]
    explorer = (ROOT / "frontend" / "components" / "graph_explorer.js").read_text()
    assert 'document.createElement("strong")' in explorer
    assert "textContent" in explorer


def test_graph_uses_explicit_colors_instead_of_vis_group_palette() -> None:
    source = (ROOT / "frontend" / "components" / "interactive_graph.py").read_text()
    explorer = (ROOT / "frontend" / "components" / "graph_explorer.js").read_text()

    assert "nodeType=node_type" in source
    assert "group=node_type" not in source
    assert "nodeStore[nodeId].nodeType" in explorer
    assert '"highlight": {"background": background, "border": "#1d4ed8"}' in source


def test_graph_mastery_relations_preserve_progressive_hierarchy() -> None:
    roots, parents, children = interactive_graph._expansion_structure(
        [
            {"id": "student:1", "type": "student"},
            {"id": "subject:db", "type": "subject"},
            {"id": "criterion:where", "type": "criterion"},
        ],
        [
            {
                "source": "student:1",
                "target": "subject:db",
                "relation": "subject_understands",
            },
            {
                "source": "subject:db",
                "target": "criterion:where",
                "relation": "criterion_mastered",
            },
        ],
    )

    assert roots == ["student:1"]
    assert parents == {
        "subject:db": "student:1",
        "criterion:where": "subject:db",
    }
    assert children["student:1"] == ["subject:db"]


def test_learning_path_graph_starts_with_only_subject_roots(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(
        interactive_graph.st,
        "iframe",
        lambda document, **options: captured.append((document, options)),
    )

    interactive_graph.render_interactive_graph(
        [
            {"id": "subject:db", "label": "Database Systems", "type": "subject"},
            {"id": "path:db:index", "label": "1. Apply B-tree index", "type": "path"},
            {"id": "path:db:join", "label": "2. Apply SQL join", "type": "path"},
            {"id": "subject:network", "label": "Computer Networks", "type": "subject"},
            {"id": "path:network:qos", "label": "1. Apply QoS policy", "type": "path"},
        ],
        [
            {
                "source": "subject:db",
                "target": "path:db:index",
                "relation": "has learning step",
            },
            {
                "source": "path:db:index",
                "target": "path:db:join",
                "relation": "recommended next",
            },
            {
                "source": "subject:network",
                "target": "path:network:qos",
                "relation": "has learning step",
            },
        ],
        key="subject-roots-test",
        height=300,
        expand_roots_initially=False,
    )

    document, _ = captured[0]
    assert '"rootNodeIds": ["subject:db", "subject:network"]' in document
    assert '"initialExpanded": []' in document
    assert '"path:db:index": "subject:db"' in document
    assert '"path:db:join": "path:db:index"' in document
    assert '"path:network:qos": "subject:network"' in document


def test_graph_and_navigation_buttons_do_not_break_words() -> None:
    graph_styles = (ROOT / "frontend" / "components" / "graph_explorer.css").read_text()
    app_styles = (ROOT / "frontend" / "components" / "styles.py").read_text()
    navigation = (ROOT / "frontend" / "components" / "navigation.py").read_text()

    assert "word-break: normal" in graph_styles
    assert "word-break: normal" in app_styles
    assert "identity = st.columns" in navigation
    assert "columns = st.columns([1] * len(navigation)" in navigation


def test_admin_model_options_follow_the_selected_provider() -> None:
    assert admin_config._available_models(
        "gemini", "~deepseek/deepseek-v4-flash-latest"
    ) == ["gemini-3.1-flash-lite"]
    assert admin_config._available_models(
        "openrouter", "gemini-3.1-flash-lite"
    ) == ["~deepseek/deepseek-v4-flash-latest"]


def test_result_feedback_displays_question_stem() -> None:
    page = (ROOT / "frontend" / "pages" / "result.py").read_text()
    schema = (ROOT / "backend" / "exams" / "schemas.py").read_text()

    assert 'item.get("stem")' in page
    assert "stem: str" in schema.split("class AnswerFeedback", 1)[1]


def test_frontend_interface_copy_is_english() -> None:
    frontend_files = [
        *ROOT.joinpath("frontend").rglob("*.py"),
        *ROOT.joinpath("frontend").rglob("*.js"),
        *ROOT.joinpath("frontend").rglob("*.css"),
    ]
    vietnamese_characters = set("ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠẢẤẦẨẪẬẮẰẲẴẶẸẺẼỀỀỂỄỆỈỊỌỎỐỒỔỖỘỚỜỞỠỢỤỦỨỪỬỮỰỲỴÝỶỸàáâãèéêìíòóôõùúăđĩũơưạảấầẩẫậắằẳẵặẹẻẽềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵýỷỹ")

    for path in frontend_files:
        assert not (set(path.read_text()) & vietnamese_characters), path


def test_native_streamlit_navigation_and_toolbar_are_hidden() -> None:
    config = (ROOT / ".streamlit" / "config.toml").read_text()
    styles = (ROOT / "frontend" / "components" / "styles.py").read_text()

    assert "showSidebarNavigation = false" in config
    assert 'toolbarMode = "minimal"' in config
    assert '[data-testid="stSidebar"]' in styles
    assert 'header[data-testid="stHeader"]' in styles


def test_llm_page_is_staff_only() -> None:
    source = (ROOT / "frontend" / "state.py").read_text()

    taker_block = source.split('"exam_taker":', 1)[1].split('"supervisor":', 1)[0]
    assert "llm_generation" not in taker_block
    assert source.count('"llm_generation"') == 2


def test_taker_has_profile_radar_chat_and_placement_workflows() -> None:
    dashboard = (ROOT / "frontend" / "pages" / "taker_dashboard.py").read_text()
    radar = (ROOT / "frontend" / "components" / "radar_chart.py").read_text()
    subjects = (ROOT / "frontend" / "pages" / "subjects.py").read_text()
    state = (ROOT / "frontend" / "state.py").read_text()

    assert "render_criterion_radar" in dashboard
    assert 'st.subheader("Overview")' in dashboard
    assert 'options=["OVERALL"' in dashboard
    assert "Expected achievement" in (
        ROOT / "frontend" / "components" / "profile_table.py"
    ).read_text()
    assert "render_criterion_profile_table" in dashboard
    assert "st.iframe(document" in radar
    assert "st.html(document" not in radar
    assert '"placement"' in subjects
    assert "start_placement" in subjects
    assert '"learner_chat"' in state
    assert 'class="path-step"' not in dashboard


def test_profile_table_uses_radar_mastery_and_full_text_hover(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(
        profile_table.st,
        "iframe",
        lambda document, **options: captured.append((document, options)),
    )
    profile_table.render_criterion_profile_table(
        [
            {
                "criterion_code": "INDEX",
                "criterion_name": "Apply a composite database index",
                "success_statement": "Choose and justify a suitable composite index.",
                "understanding_label": "Developing",
                "mastery_probability": 0.8,
                "evidence_count": 6,
                "evidence_confidence": "Moderate",
                "trend": "stable",
            }
        ],
        [{"criterion_code": "INDEX", "value_percent": 29.25}],
    )

    document, options = captured[0]
    assert "29.2%" in document
    assert ">Mastery<" in document
    assert ">Evidence<" not in document
    assert ">Confidence<" not in document
    assert 'title="Apply a composite database index"' in document
    assert 'title="Choose and justify a suitable composite index."' in document
    assert options["width"] == "stretch"


def test_radar_has_full_text_hover_tooltip() -> None:
    source = (ROOT / "frontend" / "components" / "radar_chart.py").read_text()

    assert "data-radar-tooltip" in source
    assert 'element.addEventListener("mouseenter"' in source
    assert "evidence_confidence" not in source
    assert "confidence" not in source.lower()


def test_learning_paths_are_rendered_per_subject() -> None:
    source = (ROOT / "frontend" / "pages" / "taker_dashboard.py").read_text()

    assert "grouped_paths" in source
    assert "Mastered criteria are omitted" in source
    assert 'key="taker_learning_paths_by_subject"' in source
    assert '"type": "subject"' in source
    assert '"relation": "has learning step"' in source
    assert '"relation": "recommended next"' in source
    assert '"display_label": "Start here"' in source
    assert '"display_label": "Next step"' in source
    assert "zip(criterion_nodes, criterion_nodes[1:])" in source
    assert "expand_roots_initially=False" in source


def test_taker_feedback_hides_provider_errors_and_model_details() -> None:
    component = (ROOT / "frontend" / "components" / "llm_explanation.py").read_text()

    assert "generated directly from scored evidence" in component
    assert "elif technical" in component


def test_learner_chat_has_natural_retrieval_without_debug_context_controls() -> None:
    page = (ROOT / "frontend" / "pages" / "learner_chat.py").read_text()

    assert "finds relevant information" in page
    assert "Evidence used" not in page
    assert "Optional answer context" not in page
    assert "Completed session ID" not in page
    assert "Deterministic fallback" not in page
    assert "Delete chat history" in page
    assert "Confirm deletion" in page
    assert "delete_chat_thread" in page
