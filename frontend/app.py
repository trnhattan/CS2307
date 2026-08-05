import sys
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from frontend.api_client import ExamAPIClient
from frontend.components.styles import apply_styles
from frontend.pages import (
    admin,
    admin_accounts,
    admin_config,
    admin_questions,
    cat_exam,
    cat_result,
    calibration,
    exam,
    knowledge_graph,
    landing,
    learner_chat,
    llm_generation,
    result,
    subjects,
    summary,
    supervisor,
    supervisor_config,
    taker_dashboard,
)
from frontend.state import ROLE_DEFAULT_PAGE, allowed_page, initialize_state


st.set_page_config(
    page_title="Adaptive Ability Assessment",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

apply_styles()
initialize_state()

if st.session_state.page != "landing" and not st.session_state.user:
    st.session_state.page = "landing"
elif st.session_state.user and not allowed_page(
    st.session_state.user["role"],
    st.session_state.page,
):
    st.session_state.page = ROLE_DEFAULT_PAGE[st.session_state.user["role"]]

client = ExamAPIClient(st.session_state.access_token)
pages = {
    "landing": lambda: landing.render(),
    "taker_dashboard": lambda: taker_dashboard.render(client),
    "subjects": lambda: subjects.render(client),
    "exam": lambda: exam.render(client),
    "result": lambda: result.render(client),
    "cat_exam": lambda: cat_exam.render(client),
    "cat_result": lambda: cat_result.render(client),
    "calibration": lambda: calibration.render(client),
    "knowledge_graph": lambda: knowledge_graph.render(client),
    "learner_chat": lambda: learner_chat.render(client),
    "summary": lambda: summary.render(),
    "supervisor": lambda: supervisor.render(client),
    "supervisor_config": lambda: supervisor_config.render(client),
    "llm_generation": lambda: llm_generation.render(client),
    "admin": lambda: admin.render(client),
    "admin_questions": lambda: admin_questions.render(client),
    "admin_config": lambda: admin_config.render(client),
    "admin_accounts": lambda: admin_accounts.render(client),
}
pages.get(st.session_state.page, pages["landing"])()
