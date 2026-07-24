import json

import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient
from frontend.components.header import render_header


def render(client: ExamAPIClient) -> None:
    render_header()
    st.markdown("<div class='section-title'>Central configuration</div>", unsafe_allow_html=True)
    st.caption("Every change is type-checked and stored directly in sys_props.")
    try:
        payload = client.admin_config()
    except APIClientError as error:
        st.error(str(error))
        return

    items = payload["items"]
    editable = [item for item in items if item["is_editable"]]
    selected_key = st.selectbox(
        "Select a setting to edit",
        options=[item["prop_key"] for item in editable],
        format_func=lambda key: _config_label(key, editable),
    )
    item = next(value for value in editable if value["prop_key"] == selected_key)
    st.info(item["description"])
    with st.form("admin_config_form"):
        value = _render_value_editor(item)
        submitted = st.form_submit_button(
            "Save configuration",
            type="primary",
            width="stretch",
        )
    if submitted:
        try:
            parsed = _parse_value(item["prop_value"], value)
            client.update_admin_config(
                [{"prop_key": selected_key, "prop_value": parsed}]
            )
        except (APIClientError, ValueError, json.JSONDecodeError) as error:
            st.error(str(error))
            return
        st.success(f"Updated {selected_key}.")
        st.rerun()

    st.subheader("All configuration")
    st.dataframe(
        [
            {
                "Key": value["prop_key"],
                "Value": json.dumps(value["prop_value"], ensure_ascii=False),
                "Editable": value["is_editable"],
                "Updated by": value["updated_by"],
                "Updated at": value["updated_at"],
            }
            for value in items
        ],
        width="stretch",
        hide_index=True,
    )


def _render_value_editor(item: dict):
    value = item["prop_value"]
    key = item["prop_key"]
    if isinstance(value, bool):
        return st.checkbox("Value", value=value)
    if isinstance(value, int):
        return st.number_input("Value", value=value, step=1)
    if isinstance(value, float):
        return st.number_input("Value", value=value, step=0.05)
    if key == "EXAM_ALLOWED_QUESTION_STATUSES":
        return st.multiselect(
            "Allowed question statuses",
            ["draft", "reviewed", "active", "retired"],
            default=value,
        )
    if isinstance(value, (dict, list)):
        return st.text_area(
            "JSON value",
            value=json.dumps(value, ensure_ascii=False, indent=2),
            height=180,
        )
    return st.text_input("Value", value=str(value))


def _parse_value(original, value):
    if isinstance(original, (dict, list)) and isinstance(value, str):
        return json.loads(value)
    return value


def _config_label(key: str, items: list[dict]) -> str:
    item = next(value for value in items if value["prop_key"] == key)
    return f"{key} · {item['description']}"
