import streamlit as st

from frontend.state import go, logout


ROLE_NAVIGATION = {
    "exam_taker": [
        ("taker_dashboard", "Progress"),
        ("subjects", "Start test"),
        ("knowledge_graph", "Learning graph"),
        ("learner_chat", "Learning assistant"),
    ],
    "supervisor": [
        ("supervisor", "Taker overview"),
        ("supervisor_config", "Exam configuration"),
        ("calibration", "IRT calibration"),
        ("llm_generation", "LLM workspace"),
        ("knowledge_graph", "Ability graph"),
    ],
    "admin": [
        ("admin", "System overview"),
        ("admin_questions", "Question bank"),
        ("admin_config", "Configuration"),
        ("admin_accounts", "Accounts"),
        ("calibration", "IRT calibration"),
        ("llm_generation", "LLM workspace"),
        ("knowledge_graph", "Ability graph"),
    ],
}


def render_navigation() -> None:
    user = st.session_state.user
    navigation = list(ROLE_NAVIGATION[user["role"]])
    if user["role"] == "exam_taker" and st.session_state.exam_payload:
        navigation.append(("exam", "Current test"))
    if user["role"] == "exam_taker" and st.session_state.cat_payload:
        navigation.append(("cat_exam", "Current CAT"))

    st.markdown("<div class='topbar-card'>", unsafe_allow_html=True)
    identity = st.columns([4.5, 1.8, 0.9])
    with identity[0]:
        st.markdown(
            "<div class='workspace-name'>Adaptive Ability Assessment</div>",
            unsafe_allow_html=True,
        )
    with identity[1]:
        st.markdown(
            f"<div class='user-pill'>{user['display_name']} · "
            f"{_role_label(user['role'])}</div>",
            unsafe_allow_html=True,
        )
    with identity[2]:
        if st.button("Sign out", key="nav_logout", width="stretch"):
            logout()

    st.markdown("<div class='nav-tabs-wrapper'>", unsafe_allow_html=True)
    columns = st.columns([1] * len(navigation), gap="small")
    for column, (page, label) in zip(columns, navigation):
        with column:
            if st.button(
                label,
                key=f"nav_{page}",
                type="primary" if st.session_state.page == page else "secondary",
                width="stretch",
            ):
                go(page)
    st.markdown("</div></div>", unsafe_allow_html=True)


def _role_label(role: str) -> str:
    return {
        "exam_taker": "Exam taker",
        "supervisor": "Supervisor",
        "admin": "Administrator",
    }[role]
