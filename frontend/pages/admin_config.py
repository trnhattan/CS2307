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
    _render_llm_configuration(client, items)

    st.subheader("Other system configuration")
    editable = [
        item
        for item in items
        if item["is_editable"]
        and item["prop_key"] not in {"LLM_ENABLED", "LLM_PROVIDER", "LLM_MODEL", "LLM_REASONING_ENABLED"}
    ]
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


def _render_llm_configuration(client: ExamAPIClient, items: list[dict]) -> None:
    by_key = {item["prop_key"]: item for item in items}
    required = {"LLM_ENABLED", "LLM_PROVIDER", "LLM_MODEL", "LLM_REASONING_ENABLED"}
    if not required <= set(by_key):
        st.warning("Restart the backend once to apply the LLM-provider migration.")
        return

    st.subheader("Language model for all users")
    st.caption(
        "This is the central model used by taker feedback and learning chat, as well as "
        "supervisor question drafting and technical explanations. API keys stay in .env."
    )
    provider = str(by_key["LLM_PROVIDER"]["prop_value"])
    model = str(by_key["LLM_MODEL"]["prop_value"])
    selected_provider = _provider_selector(provider)
    models = _available_models(selected_provider, model)

    with st.form("admin_llm_configuration_form"):
        enabled = st.checkbox(
            "Enable LLM features",
            value=bool(by_key["LLM_ENABLED"]["prop_value"]),
        )
        custom_label = "Custom model ID"
        selected_model = st.selectbox(
            "Model",
            options=[*models, custom_label],
            index=models.index(model) if model in models else len(models),
        )
        model_value = st.text_input(
            "Custom model ID",
            value=model if selected_model == custom_label else "",
            disabled=selected_model != custom_label,
            help="Use the provider's exact model ID. Gemini model IDs must begin with gemini-.",
        )
        reasoning = st.checkbox(
            "Request provider-supported reasoning",
            value=bool(by_key["LLM_REASONING_ENABLED"]["prop_value"]),
        )
        submitted = st.form_submit_button(
            "Save language model configuration",
            type="primary",
            width="stretch",
        )
    if submitted:
        target_model = model_value.strip() if selected_model == custom_label else selected_model
        if not target_model:
            st.error("Enter a model ID or choose a listed model.")
            return
        try:
            client.update_admin_config(
                [
                    {"prop_key": "LLM_ENABLED", "prop_value": enabled},
                    {"prop_key": "LLM_PROVIDER", "prop_value": selected_provider},
                    {"prop_key": "LLM_MODEL", "prop_value": target_model},
                    {"prop_key": "LLM_REASONING_ENABLED", "prop_value": reasoning},
                ]
            )
        except APIClientError as error:
            st.error(str(error))
            return
        st.success(
            f"All takers and supervisors will now use {target_model} through {selected_provider}."
        )
        st.rerun()


def _provider_selector(current_provider: str) -> str:
    state_key = "admin_llm_provider"
    if state_key not in st.session_state:
        st.session_state[state_key] = current_provider
    if st.session_state[state_key] not in {"openrouter", "gemini"}:
        st.session_state[state_key] = "openrouter"
    return st.selectbox(
        "Provider",
        options=["openrouter", "gemini"],
        key=state_key,
        format_func=lambda value: "Gemini" if value == "gemini" else "OpenRouter",
        help="Changing provider updates the model list below. Save to apply this choice to all users.",
    )


def _available_models(provider: str, current_model: str) -> list[str]:
    models = (
        ["gemini-3.1-flash-lite"]
        if provider == "gemini"
        else ["~deepseek/deepseek-v4-flash-latest"]
    )
    if current_model and current_model not in models:
        model_matches_provider = current_model.lower().startswith("gemini-")
        if model_matches_provider == (provider == "gemini"):
            models.insert(0, current_model)
    return models


def _parse_value(original, value):
    if isinstance(original, (dict, list)) and isinstance(value, str):
        return json.loads(value)
    return value


def _config_label(key: str, items: list[dict]) -> str:
    item = next(value for value in items if value["prop_key"] == key)
    return f"{key} · {item['description']}"
