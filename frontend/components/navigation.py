import streamlit as st

from frontend.state import go, logout


ROLE_NAVIGATION = {
    "exam_taker": [
        ("taker_dashboard", "Tiến độ"),
        ("subjects", "Bắt đầu bài thi"),
    ],
    "supervisor": [
        ("supervisor", "Tổng quan thí sinh"),
        ("supervisor_config", "Cấu hình đề thi"),
    ],
    "admin": [
        ("admin", "Tổng quan hệ thống"),
        ("admin_questions", "Ngân hàng câu hỏi"),
        ("admin_config", "Cấu hình"),
        ("admin_accounts", "Tài khoản"),
    ],
}


def render_navigation() -> None:
    user = st.session_state.user
    navigation = list(ROLE_NAVIGATION[user["role"]])
    if user["role"] == "exam_taker" and st.session_state.exam_payload:
        navigation.append(("exam", "Bài đang làm"))

    columns = st.columns([*([1] * len(navigation)), 1.3, 0.8])
    for column, (page, label) in zip(columns, navigation):
        with column:
            if st.button(
                label,
                key=f"nav_{page}",
                type="primary" if st.session_state.page == page else "secondary",
                width="stretch",
            ):
                go(page)
    with columns[-2]:
        st.caption(f"{user['display_name']} · {_role_label(user['role'])}")
    with columns[-1]:
        if st.button("Đăng xuất", key="nav_logout", width="stretch"):
            logout()
    st.divider()


def _role_label(role: str) -> str:
    return {
        "exam_taker": "Thí sinh",
        "supervisor": "Giám sát",
        "admin": "Quản trị",
    }[role]
