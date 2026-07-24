import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient
from frontend.components.header import render_header


ROLE_LABELS = {
    "admin": "Administrator",
    "supervisor": "Supervisor",
    "exam_taker": "Exam taker",
}


def render(client: ExamAPIClient) -> None:
    render_header()
    st.markdown("<div class='section-title'>Account administration</div>", unsafe_allow_html=True)
    try:
        accounts = client.admin_accounts()
    except APIClientError as error:
        st.error(str(error))
        return

    st.dataframe(
        [
            {
                "Username": item["username"],
                "Display name": item["display_name"],
                "Role": ROLE_LABELS[item["role"]],
                "Student code": item["student_code"],
                "Active": item["is_active"],
            }
            for item in accounts
        ],
        width="stretch",
        hide_index=True,
    )

    create_tab, manage_tab = st.tabs(["Create account", "Edit account"])
    with create_tab:
        role = st.selectbox(
            "New account role",
            options=list(ROLE_LABELS),
            format_func=lambda value: ROLE_LABELS[value],
            key="new_account_role",
        )
        with st.form("create_account_form"):
            username = st.text_input("Username")
            display_name = st.text_input("Display name")
            student_code = (
                st.text_input("Student code") if role == "exam_taker" else None
            )
            password = st.text_input("Initial password", type="password")
            submitted = st.form_submit_button(
                "Create account",
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
                st.success(f"Created account {username}.")
                st.rerun()

    with manage_tab:
        selected_username = st.selectbox(
            "Select account",
            options=[item["username"] for item in accounts],
            key="managed_account",
        )
        selected = next(
            item for item in accounts if item["username"] == selected_username
        )
        with st.form("update_account_form"):
            display_name = st.text_input(
                "Display name",
                value=selected["display_name"],
            )
            is_active = st.checkbox("Active", value=selected["is_active"])
            password = st.text_input(
                "New password (leave blank to keep the current password)",
                type="password",
            )
            submitted = st.form_submit_button(
                "Save account",
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
                st.success(f"Updated {selected_username}.")
                st.rerun()
