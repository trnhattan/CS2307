import streamlit as st

from frontend.api_client import APIClientError, ExamAPIClient
from frontend.components.header import render_header


def render(client: ExamAPIClient) -> None:
    render_header()
    st.markdown("<div class='section-title'>Empirical IRT calibration</div>", unsafe_allow_html=True)
    st.caption(
        "Evaluate assigned item difficulty from real completed responses. Sparse items remain "
        "descriptive and cannot update production parameters."
    )
    controls = st.columns([2, 1])
    apply_eligible = controls[0].checkbox(
        "Apply estimates only when the configured production sample threshold is met"
    )
    if controls[1].button("Run calibration", type="primary", width="stretch"):
        try:
            with st.spinner("Evaluating real response evidence..."):
                st.session_state.calibration_result = client.run_calibration(apply_eligible)
        except APIClientError as error:
            st.error(str(error))

    payload = st.session_state.get("calibration_result")
    if payload is None:
        try:
            payload = client.latest_calibration()
        except APIClientError:
            st.info("No empirical calibration run exists yet.")
            return

    metrics = st.columns(5)
    metrics[0].metric("Real responses", payload["total_responses"])
    metrics[1].metric("Evaluated items", payload["evaluated_items"])
    metrics[2].metric("Eligible items", payload["eligible_items"])
    metrics[3].metric("Applied items", payload["applied_items"])
    metrics[4].metric("Apply threshold", payload["minimum_apply_sample"])
    st.caption(
        f"Method: {payload['method']} · Run #{payload['run_id']} · "
        f"Evaluation threshold: {payload['minimum_evaluation_sample']} responses"
    )
    for limitation in payload["limitations"]:
        st.warning(limitation)

    if not payload["items"]:
        st.info("No answered items are available for analysis.")
        return
    st.dataframe(
        [
            {
                "Question": item["question_code"],
                "Subject": item["subject_code"],
                "Responses": item["sample_size"],
                "Observed accuracy": item["observed_accuracy"],
                "Predicted accuracy": item["predicted_accuracy"],
                "Point-biserial": item["point_biserial"],
                "Fit RMSE": item["fit_rmse"],
                "Current b": item["current_b"],
                "Suggested b": item["suggested_b"],
                "Reliability": item["reliability"],
                "Applied": item["applied"],
            }
            for item in payload["items"]
        ],
        width="stretch",
        hide_index=True,
    )
