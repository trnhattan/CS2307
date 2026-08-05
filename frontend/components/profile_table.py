import html

import streamlit as st


def render_criterion_profile_table(
    criteria: list[dict], radar_axes: list[dict]
) -> None:
    mastery_by_code = {
        axis["criterion_code"]: axis.get("value_percent") for axis in radar_axes
    }
    rows = []
    for criterion in criteria:
        mastery = mastery_by_code.get(criterion["criterion_code"])
        if criterion["criterion_code"] not in mastery_by_code:
            probability = criterion.get("mastery_probability")
            mastery = probability * 100 if probability is not None else None
        cells = [
            (criterion["criterion_name"], "criterion"),
            (criterion["success_statement"], "achievement"),
            (criterion["understanding_label"], "status"),
            (f"{mastery:.1f}%" if mastery is not None else "Unknown", "number"),
            (criterion["trend"].replace("_", " ").title(), "status"),
        ]
        rows.append(
            "<tr>"
            + "".join(
                f'<td class="{css_class}" title="{_escape(value)}">'
                f"{_escape(value)}</td>"
                for value, css_class in cells
            )
            + "</tr>"
        )

    document = f"""
    <style>
      html, body {{ margin: 0; background: transparent; color: #172554;
        font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
      .profile-table {{ border: 1px solid #dbe4f5; border-radius: 14px;
        max-height: 580px; overflow: auto; }}
      table {{ border-collapse: separate; border-spacing: 0; table-layout: fixed;
        width: 100%; }}
      th {{ background: #f8fafc; color: #64748b; font-size: 12px; font-weight: 700;
        padding: 11px 10px; position: sticky; text-align: left; top: 0; z-index: 1; }}
      td {{ border-top: 1px solid #e2e8f0; font-size: 12px; padding: 10px;
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
      tbody tr:hover {{ background: #eef3ff; }}
      .criterion {{ width: 20%; }} .achievement {{ width: 40%; }}
      .status {{ width: 14%; }} .number {{ text-align: right; width: 10%; }}
    </style>
    <div class="profile-table">
      <table aria-label="Assessment criterion mastery table">
        <thead><tr>
          <th class="criterion">Criterion</th>
          <th class="achievement">Expected achievement</th>
          <th class="status">Understanding</th>
          <th class="number">Mastery</th>
          <th class="status">Trend</th>
        </tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
    """
    height = min(620, max(150, 48 + 42 * len(criteria)))
    st.iframe(document, width="stretch", height=height, tab_index=0)


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)
