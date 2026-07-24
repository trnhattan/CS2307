import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient
from frontend.state import set_authenticated


@st.dialog("Sign in")
def render_login_dialog() -> None:
    st.caption("Use the account assigned to your role.")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button(
            "Sign in",
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
