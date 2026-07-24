from pathlib import Path

from streamlit.testing.v1 import AppTest

from frontend.components import interactive_graph


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


def test_graph_tooltips_are_plain_multiline_text() -> None:
    tooltip = interactive_graph._node_tooltip(
        "topic",
        "Audit History",
        {
            "knowledge_type": "Topic",
            "understanding": "Needs review",
            "evidence_count": 1,
        },
    )

    assert tooltip == (
        "Topic\nAudit History\nKnowledge type: Topic\n"
        "Understanding: Needs review\nAnswered questions: 1"
    )
    assert "<strong>" not in tooltip
    assert "<br>" not in tooltip


def test_graph_and_navigation_buttons_do_not_break_words() -> None:
    graph_styles = (ROOT / "frontend" / "components" / "graph_explorer.css").read_text()
    app_styles = (ROOT / "frontend" / "components" / "styles.py").read_text()
    navigation = (ROOT / "frontend" / "components" / "navigation.py").read_text()

    assert "word-break: normal" in graph_styles
    assert "word-break: normal" in app_styles
    assert "identity = st.columns" in navigation
    assert "columns = st.columns([1] * len(navigation)" in navigation


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
