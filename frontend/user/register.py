import streamlit as st


@st.dialog("Create an account")
def render_register_dialog() -> None:
    st.info("Self-service registration is not enabled. Contact an administrator.")
    st.caption("The registration form remains a separate module for a later release.")
