import json

import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient
from frontend.components.header import render_header


def render(client: ExamAPIClient) -> None:
    render_header()
    st.markdown("<div class='section-title'>Cấu hình trung tâm</div>", unsafe_allow_html=True)
    st.caption("Mọi thay đổi được kiểm tra kiểu dữ liệu và lưu trực tiếp vào sys_props.")
    try:
        payload = client.admin_config()
    except APIClientError as error:
        st.error(str(error))
        return

    items = payload["items"]
    editable = [item for item in items if item["is_editable"]]
    selected_key = st.selectbox(
        "Chọn cấu hình cần điều chỉnh",
        options=[item["prop_key"] for item in editable],
        format_func=lambda key: _config_label(key, editable),
    )
    item = next(value for value in editable if value["prop_key"] == selected_key)
    st.info(item["description"])
    with st.form("admin_config_form"):
        value = _render_value_editor(item)
        submitted = st.form_submit_button(
            "Lưu cấu hình",
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
        st.success(f"Đã cập nhật {selected_key}.")
        st.rerun()

    st.subheader("Toàn bộ cấu hình")
    st.dataframe(
        [
            {
                "Khóa": value["prop_key"],
                "Giá trị": json.dumps(value["prop_value"], ensure_ascii=False),
                "Có thể sửa": value["is_editable"],
                "Cập nhật bởi": value["updated_by"],
                "Cập nhật lúc": value["updated_at"],
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
        return st.checkbox("Giá trị", value=value)
    if isinstance(value, int):
        return st.number_input("Giá trị", value=value, step=1)
    if isinstance(value, float):
        return st.number_input("Giá trị", value=value, step=0.05)
    if key == "EXAM_ALLOWED_QUESTION_STATUSES":
        return st.multiselect(
            "Trạng thái câu hỏi được sử dụng",
            ["draft", "reviewed", "active", "retired"],
            default=value,
        )
    if isinstance(value, (dict, list)):
        return st.text_area(
            "Giá trị JSON",
            value=json.dumps(value, ensure_ascii=False, indent=2),
            height=180,
        )
    return st.text_input("Giá trị", value=str(value))


def _parse_value(original, value):
    if isinstance(original, (dict, list)) and isinstance(value, str):
        return json.loads(value)
    return value


def _config_label(key: str, items: list[dict]) -> str:
    item = next(value for value in items if value["prop_key"] == key)
    return f"{key} · {item['description']}"
