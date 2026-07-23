import streamlit as st


@st.dialog("Đăng ký tài khoản")
def render_register_dialog() -> None:
    st.info("Đăng ký tự phục vụ chưa được mở. Vui lòng liên hệ quản trị viên.")
    st.caption("Chức năng này được tách riêng để bổ sung ở giai đoạn tiếp theo.")
