import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient
from frontend.components.header import render_header


def render(client: ExamAPIClient) -> None:
    render_header()
    st.markdown(
        "<div class='section-title'>Learning assistant</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Ask about your progress, concepts to review, or a question from a completed test. "
        "The assistant finds relevant information from your learning history automatically."
    )
    try:
        subjects = client.subjects()["subjects"]
        threads = client.chat_threads()
    except APIClientError as error:
        st.error(str(error))
        return

    with st.expander("Start a new conversation", expanded=not threads):
        subject_code = st.selectbox(
            "Subject context",
            options=[None, *[item["subject_code"] for item in subjects]],
            format_func=lambda code: (
                "All assessed subjects"
                if code is None
                else next(item["subject_name"] for item in subjects if item["subject_code"] == code)
            ),
        )
        title = st.text_input("Conversation title", value="Learning assistant")
        if st.button("Create conversation", type="primary", width="stretch"):
            try:
                created = client.create_chat_thread(subject_code, title)
            except APIClientError as error:
                st.error(str(error))
            else:
                st.session_state.active_chat_thread = created["thread_id"]
                st.rerun()

    if not threads:
        st.info("Create a conversation after completing a test or placement assessment.")
        return
    thread_ids = [item["thread_id"] for item in threads]
    default_thread = st.session_state.get("active_chat_thread")
    if default_thread not in thread_ids:
        default_thread = thread_ids[0]
    thread_id = st.selectbox(
        "Conversation",
        options=thread_ids,
        index=thread_ids.index(default_thread),
        format_func=lambda value: next(
            f"{item['title']} · {item['subject_name'] or 'All subjects'}"
            for item in threads
            if item["thread_id"] == value
        ),
    )
    st.session_state.active_chat_thread = thread_id
    if st.button(
        "Delete chat history",
        key=f"delete_chat_history_{thread_id}",
        width="stretch",
    ):
        st.session_state.chat_delete_confirmation = thread_id
    if st.session_state.get("chat_delete_confirmation") == thread_id:
        st.warning(
            "This permanently deletes the selected conversation and all of its messages."
        )
        confirm, cancel = st.columns(2)
        if confirm.button(
            "Confirm deletion",
            type="primary",
            key=f"confirm_chat_deletion_{thread_id}",
            width="stretch",
        ):
            try:
                client.delete_chat_thread(thread_id)
            except APIClientError as error:
                st.error(str(error))
            else:
                st.session_state.pop("active_chat_thread", None)
                st.session_state.pop("chat_delete_confirmation", None)
                st.rerun()
        if cancel.button(
            "Cancel",
            key=f"cancel_chat_deletion_{thread_id}",
            width="stretch",
        ):
            st.session_state.pop("chat_delete_confirmation", None)
            st.rerun()
    try:
        detail = client.chat_thread(thread_id)
    except APIClientError as error:
        st.error(str(error))
        return

    for message in detail["messages"]:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    message = st.chat_input(
        "Ask about your progress, what to learn next, or a completed question"
    )
    if message:
        try:
            with st.spinner("Building a grounded response..."):
                client.send_chat_message(
                    thread_id,
                    message,
                )
        except APIClientError as error:
            st.error(str(error))
        else:
            st.rerun()
