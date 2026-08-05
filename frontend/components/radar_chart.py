import html
import math
import textwrap

import streamlit as st


def render_criterion_radar(payload: dict, *, height: int = 620) -> None:
    axes = payload.get("axes") or []
    scope = payload.get("scope", "subject")
    axis_kind = "subjects" if scope == "overall" else "criteria"
    evidence_label = "answered questions"
    if not axes:
        st.info(f"No {axis_kind} are available for this radar.")
        return
    assessed = [axis for axis in axes if axis.get("value_percent") is not None]
    if not assessed:
        st.info(
            "Complete a placement assessment or practice test to create your first "
            f"{axis_kind} radar. Unassessed axes are not treated as zero."
        )
        return

    display_axes = _display_axes(axes)
    width = 760
    center_x = width / 2
    center_y = 285
    radius = 205
    rings = []
    for value in (20, 40, 60, 80, 100):
        ring = radius * value / 100
        points = _points(len(display_axes), center_x, center_y, ring)
        rings.append(
            f'<polygon points="{points}" fill="none" stroke="#dbe4f5" '
            f'stroke-width="1"/><text x="{center_x + 5}" y="{center_y - ring + 14}" '
            f'fill="#64748b" font-size="11">{value}</text>'
        )

    spokes = []
    labels = []
    values = []
    for index, display_axis in enumerate(display_axes):
        axis = display_axis["axis"]
        angle = -math.pi / 2 + 2 * math.pi * index / len(display_axes)
        outer_x = center_x + radius * math.cos(angle)
        outer_y = center_y + radius * math.sin(angle)
        known = axis.get("value_percent") is not None
        spokes.append(
            f'<line x1="{center_x}" y1="{center_y}" x2="{outer_x:.2f}" '
            f'y2="{outer_y:.2f}" stroke="{("#c7d2fe" if known else "#e2e8f0")}" '
            f'stroke-width="1" stroke-dasharray="{("0" if known else "4 4")}"/>'
        )
        anchor = "start" if math.cos(angle) > 0.2 else "end" if math.cos(angle) < -0.2 else "middle"
        label_x = center_x + (radius + 32) * math.cos(angle)
        label_y = center_y + (radius + 32) * math.sin(angle)
        if display_axis["show_label"]:
            short = textwrap.shorten(axis["criterion_name"], width=22, placeholder="…")
            suffix = f"{axis['value_percent']:.1f}%" if known else "Not assessed"
            tooltip = (
                f"{axis['criterion_name']} · {suffix} · "
                f"{axis['evidence_count']} {evidence_label}"
            )
            labels.append(
                f'<g class="radar-hover" data-radar-tooltip="{html.escape(tooltip, quote=True)}">'
                f'<text x="{label_x:.2f}" y="{label_y:.2f}" text-anchor="{anchor}" '
                f'fill="{("#172554" if known else "#94a3b8")}" font-size="11" '
                f'font-family="Inter,Arial,sans-serif">'
                f'{html.escape(short)} · {html.escape(suffix)}</text></g>'
            )
        if known:
            point_radius = radius * float(axis["value_percent"]) / 100
            values.append(
                (
                    center_x + point_radius * math.cos(angle),
                    center_y + point_radius * math.sin(angle),
                    axis,
                )
            )

    shape = ""
    if len(values) >= 3:
        polygon = " ".join(f"{x:.2f},{y:.2f}" for x, y, _ in values)
        shape = (
            f'<polygon points="{polygon}" fill="rgba(79,70,229,.20)" '
            f'stroke="#4f46e5" stroke-width="3"/>'
        )
    elif len(values) == 2:
        shape = (
            f'<polyline points="{values[0][0]:.2f},{values[0][1]:.2f} '
            f'{center_x:.2f},{center_y:.2f} {values[1][0]:.2f},{values[1][1]:.2f}" '
            f'fill="none" stroke="#4f46e5" stroke-width="4"/>'
        )
    dots = []
    for x, y, axis in values:
        tooltip = (
            f"{axis['criterion_name']} · {axis['value_percent']:.1f}% · "
            f"{axis['evidence_count']} questions"
        )
        dots.append(
            f'<circle class="radar-hover" data-radar-tooltip="{html.escape(tooltip, quote=True)}" '
            f'cx="{x:.2f}" cy="{y:.2f}" r="5" fill="#4f46e5" '
            f'stroke="white" stroke-width="2"/>'
        )

    document = f"""
    <style>
      .radar-wrap {{ background: white; border: 1px solid #dbe4f5; border-radius: 18px;
        overflow: auto; padding: 12px; position: relative; }}
      .radar-hover {{ cursor: help; }}
      #radar-tooltip {{ background: #172554; border-radius: 8px; color: white;
        font: 12px Inter, Arial, sans-serif; max-width: 340px; padding: 8px 10px;
        pointer-events: none; position: absolute; z-index: 5; }}
      #radar-tooltip[hidden] {{ display: none; }}
    </style>
    <div class="radar-wrap" id="radar-wrap">
      <svg viewBox="0 0 {width} 570" width="100%" height="{height - 40}" role="img"
           aria-label="{html.escape(axis_kind.title())} mastery radar for {html.escape(payload['subject_name'])}">
        {''.join(rings)}{''.join(spokes)}{shape}{''.join(dots)}{''.join(labels)}
        <text x="{center_x}" y="555" text-anchor="middle" fill="#64748b" font-size="12">
          {payload['assessed_criteria']} of {payload['total_criteria']} {axis_kind} assessed · Missing axes are unknown, not zero
        </text>
      </svg>
      <div id="radar-tooltip" hidden></div>
    </div>
    <script>
      (() => {{
        const wrap = document.getElementById("radar-wrap");
        const tooltip = document.getElementById("radar-tooltip");
        document.querySelectorAll(".radar-hover").forEach((element) => {{
          element.addEventListener("mouseenter", () => {{
            tooltip.textContent = element.dataset.radarTooltip;
            tooltip.hidden = false;
          }});
          element.addEventListener("mousemove", (event) => {{
            const bounds = wrap.getBoundingClientRect();
            const left = event.clientX - bounds.left + wrap.scrollLeft + 12;
            const top = event.clientY - bounds.top + wrap.scrollTop + 12;
            const maximumLeft = Math.max(8, wrap.scrollWidth - tooltip.offsetWidth - 8);
            const maximumTop = Math.max(8, wrap.scrollHeight - tooltip.offsetHeight - 8);
            tooltip.style.left = `${{Math.min(left, maximumLeft)}}px`;
            tooltip.style.top = `${{Math.min(top, maximumTop)}}px`;
          }});
          element.addEventListener("mouseleave", () => {{ tooltip.hidden = true; }});
        }});
      }})();
    </script>
    """
    st.iframe(document, width="stretch", height=height, tab_index=0)


def _display_axes(axes: list[dict]) -> list[dict]:
    if len(axes) != 2:
        return [{"axis": axis, "show_label": True} for axis in axes]
    return [
        {"axis": axes[0], "show_label": True},
        {"axis": axes[1], "show_label": True},
        {"axis": axes[0], "show_label": False},
        {"axis": axes[1], "show_label": False},
    ]


def _points(count: int, center_x: float, center_y: float, radius: float) -> str:
    return " ".join(
        f"{center_x + radius * math.cos(-math.pi / 2 + 2 * math.pi * index / count):.2f},"
        f"{center_y + radius * math.sin(-math.pi / 2 + 2 * math.pi * index / count):.2f}"
        for index in range(count)
    )
