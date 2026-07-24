import streamlit as st

from frontend.user.login import render_login_dialog
from frontend.user.register import render_register_dialog


def render() -> None:
    st.markdown(
        """
        <div class="hero">
          <div class="eyebrow">CS2307 · Knowledge Engineering</div>
          <h1>Adaptive exam generation<br/>and ability assessment</h1>
          <p>A clear, responsive testing experience personalized from each
          learner's accumulated evidence.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    st.markdown("<div class='section-title'>Project team</div>", unsafe_allow_html=True)
    st.caption("Replace the placeholders with team names and student IDs before presenting.")
    columns = st.columns(5)
    for index, column in enumerate(columns, start=1):
        with column:
            st.markdown(
                f"""
                <div class="member">
                  <div class="avatar">{index}</div>
                  <strong>Member {index}</strong><br/>
                  <small>0000000000</small>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.write("")
    _, login, signup, _ = st.columns([2.2, 1, 1, 2.2])
    with login:
        if st.button("Sign in", type="primary", width="stretch"):
            render_login_dialog()
    with signup:
        if st.button("Sign up", width="stretch"):
            render_register_dialog()
