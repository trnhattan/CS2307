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
    members = [
        ("D\u01b0\u01a1ng Nguy\u1ec5n Thu\u1eadn", "250101068"),
        ("Tr\u1ecbnh Nh\u1eadt T\u00e2n", "240101071"),
        ("\u0110inh Ph\u01b0\u01a1ng Nam", "250101044"),
        ("Nguy\u1ec5n Ph\u00fac H\u01b0ng", "250101026"),
        ("L\u00ea Tr\u1ea7n Nh\u1eadt", "250101050"),
    ]
    columns = st.columns(5)
    for (name, student_id), column in zip(members, columns):
        with column:
            st.markdown(
                f"""
                <div class="member">
                  <strong>{name}</strong><br/>
                  <small>{student_id}</small>
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
