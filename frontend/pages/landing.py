import streamlit as st

from frontend.user.login import render_login_dialog
from frontend.user.register import render_register_dialog


def render() -> None:
    st.markdown(
        """
        <div class="hero">
          <div class="eyebrow">CS2307 · Công nghệ tri thức</div>
          <h1>Hệ thống sinh đề và<br/>đánh giá năng lực thích ứng</h1>
          <p>Không gian kiểm tra trực quan, thân thiện và được cá nhân hóa theo
          quá trình học tập của từng sinh viên.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    st.markdown("<div class='section-title'>Nhóm thực hiện</div>", unsafe_allow_html=True)
    st.caption("Cập nhật tên và mã số sinh viên trước khi trình bày.")
    columns = st.columns(5)
    for index, column in enumerate(columns, start=1):
        with column:
            st.markdown(
                f"""
                <div class="member">
                  <div class="avatar">{index}</div>
                  <strong>Tên thành viên {index}</strong><br/>
                  <small>0000000000</small>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.write("")
    _, login, signup, _ = st.columns([2.2, 1, 1, 2.2])
    with login:
        if st.button("Đăng nhập", type="primary", width="stretch"):
            render_login_dialog()
    with signup:
        if st.button("Đăng ký", width="stretch"):
            render_register_dialog()
