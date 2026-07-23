import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient
from frontend.state import set_authenticated


@st.dialog("Đăng nhập")
def render_login_dialog() -> None:
    st.caption("Sử dụng tài khoản được cấp theo vai trò.")
    with st.form("login_form"):
        username = st.text_input("Tên đăng nhập")
        password = st.text_input("Mật khẩu", type="password")
        submitted = st.form_submit_button(
            "Đăng nhập",
            type="primary",
            width="stretch",
        )
    if submitted:
        try:
            payload = ExamAPIClient().login(username, password)
        except APIClientError as error:
            st.error(str(error))
            return
        set_authenticated(payload)
        st.rerun()
