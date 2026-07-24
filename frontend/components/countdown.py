import time

import streamlit as st


def render_countdown(started_at: float, estimated_minutes: int) -> None:
    deadline_ms = int((started_at + estimated_minutes * 60) * 1000)
    now_ms = int(time.time() * 1000)
    st.html(
        f"""
        <div id="timer" style="font-family:Inter,system-ui;text-align:center;padding:12px;
             border-radius:14px;background:#172554;color:white;font-weight:700;"></div>
        <script>
        const deadline = {deadline_ms};
        function format(seconds) {{
          const hours = Math.floor(seconds / 3600);
          const minutes = Math.floor((seconds % 3600) / 60);
          const rest = seconds % 60;
          return `${{hours.toString().padStart(2,'0')}}:${{minutes.toString().padStart(2,'0')}}:${{rest.toString().padStart(2,'0')}}`;
        }}
        function update() {{
          const remaining = Math.floor((deadline - Date.now()) / 1000);
          const element = document.getElementById('timer');
          if (remaining >= 0) {{
            element.textContent = `Estimated time remaining · ${{format(remaining)}}`;
          }} else {{
            element.textContent = `Estimated time exceeded · ${{format(-remaining)}} · You may continue`;
            element.style.background = '#9f3a38';
          }}
        }}
        update();
        setInterval(update, 1000);
        </script>
        """,
        unsafe_allow_javascript=True,
    )
