import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient
from frontend.components.header import render_header


ROLE_LABELS = {
    "admin": "Quản trị viên",
    "supervisor": "Giám sát",
    "exam_taker": "Thí sinh",
}


def render(client: ExamAPIClient) -> None:
    render_header()
    st.markdown("<div class='section-title'>Quản lý tài khoản</div>", unsafe_allow_html=True)
    try:
        accounts = client.admin_accounts()
    except APIClientError as error:
        st.error(str(error))
        return

    st.dataframe(
        [
            {
                "Tên đăng nhập": item["username"],
                "Tên hiển thị": item["display_name"],
                "Vai trò": ROLE_LABELS[item["role"]],
                "Mã sinh viên": item["student_code"],
                "Hoạt động": item["is_active"],
            }
            for item in accounts
        ],
        width="stretch",
        hide_index=True,
    )

    create_tab, manage_tab = st.tabs(["Tạo tài khoản", "Chỉnh sửa tài khoản"])
    with create_tab:
        role = st.selectbox(
            "Vai trò mới",
            options=list(ROLE_LABELS),
            format_func=lambda value: ROLE_LABELS[value],
            key="new_account_role",
        )
        with st.form("create_account_form"):
            username = st.text_input("Tên đăng nhập")
            display_name = st.text_input("Tên hiển thị")
            student_code = (
                st.text_input("Mã sinh viên") if role == "exam_taker" else None
            )
            password = st.text_input("Mật khẩu ban đầu", type="password")
            submitted = st.form_submit_button(
                "Tạo tài khoản",
                type="primary",
                width="stretch",
            )
        if submitted:
            try:
                client.create_account(
                    {
                        "username": username,
                        "password": password,
                        "display_name": display_name,
                        "role": role,
                        "student_code": student_code or None,
                    }
                )
            except APIClientError as error:
                st.error(str(error))
            else:
                st.success(f"Đã tạo tài khoản {username}.")
                st.rerun()

    with manage_tab:
        selected_username = st.selectbox(
            "Chọn tài khoản",
            options=[item["username"] for item in accounts],
            key="managed_account",
        )
        selected = next(
            item for item in accounts if item["username"] == selected_username
        )
        with st.form("update_account_form"):
            display_name = st.text_input(
                "Tên hiển thị",
                value=selected["display_name"],
            )
            is_active = st.checkbox("Đang hoạt động", value=selected["is_active"])
            password = st.text_input(
                "Mật khẩu mới (để trống nếu không đổi)",
                type="password",
            )
            submitted = st.form_submit_button(
                "Lưu tài khoản",
                type="primary",
                width="stretch",
            )
        if submitted:
            changes = {
                "display_name": display_name,
                "is_active": is_active,
            }
            if password:
                changes["password"] = password
            try:
                client.update_account(selected_username, changes)
            except APIClientError as error:
                st.error(str(error))
            else:
                st.success(f"Đã cập nhật {selected_username}.")
                st.rerun()
