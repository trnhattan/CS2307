import streamlit as st


ROLE_PAGES = {
    "exam_taker": {
        "taker_dashboard",
        "subjects",
        "exam",
        "result",
        "summary",
    },
    "supervisor": {"supervisor", "supervisor_config"},
    "admin": {"admin", "admin_questions", "admin_config", "admin_accounts"},
}

ROLE_DEFAULT_PAGE = {
    "exam_taker": "taker_dashboard",
    "supervisor": "supervisor",
    "admin": "admin",
}


def initialize_state() -> None:
    defaults = {
        "page": "landing",
        "access_token": None,
        "user": None,
        "exam_payload": None,
        "session_index": 0,
        "results": [],
        "last_result": None,
        "exam_started_at": {},
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def go(page: str) -> None:
    st.session_state.page = page
    st.rerun()


def set_authenticated(payload: dict) -> None:
    st.session_state.access_token = payload["access_token"]
    st.session_state.user = payload["user"]
    destination = {
        "exam_taker": "taker_dashboard",
        "supervisor": "supervisor",
        "admin": "admin",
    }[payload["user"]["role"]]
    st.session_state.page = destination


def allowed_page(role: str, page: str) -> bool:
    return page in ROLE_PAGES.get(role, set())


def logout() -> None:
    for key in (
        "access_token",
        "user",
        "exam_payload",
        "results",
        "last_result",
    ):
        st.session_state[key] = None if key != "results" else []
    st.session_state.exam_started_at = {}
    st.session_state.session_index = 0
    st.session_state.page = "landing"
    st.rerun()
