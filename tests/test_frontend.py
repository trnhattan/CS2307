from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


def test_landing_page_loads_login_and_signup() -> None:
    app = AppTest.from_file(ROOT / "frontend" / "app.py").run(timeout=10)

    assert not app.exception
    assert [button.label for button in app.button] == ["Đăng nhập", "Đăng ký"]


def test_login_opens_as_a_dialog() -> None:
    app = AppTest.from_file(ROOT / "frontend" / "app.py").run(timeout=10)

    app.button[0].click().run(timeout=10)

    assert not app.exception
    assert [field.label for field in app.text_input] == [
        "Tên đăng nhập",
        "Mật khẩu",
    ]


def test_taker_pages_do_not_render_staff_metrics() -> None:
    taker_pages = [
        "taker_dashboard.py",
        "subjects.py",
        "exam.py",
        "result.py",
        "summary.py",
    ]
    forbidden = ("theta", "bloom", "fisher", "standard_error", "irt")

    for filename in taker_pages:
        source = (ROOT / "frontend" / "pages" / filename).read_text().lower()
        assert all(term not in source for term in forbidden)


def test_countdown_expiry_does_not_submit_or_block_exam() -> None:
    source = (ROOT / "frontend" / "components" / "countdown.py").read_text()

    assert "Bạn vẫn có thể tiếp tục" in source
    assert "form_submit_button" not in source


def test_navigation_is_role_specific() -> None:
    source = (ROOT / "frontend" / "components" / "navigation.py").read_text()

    assert '"taker_dashboard", "Tiến độ"' in source
    assert '"supervisor_config", "Cấu hình đề thi"' in source
    assert '"admin_questions", "Ngân hàng câu hỏi"' in source
    assert '"admin_accounts", "Tài khoản"' in source
