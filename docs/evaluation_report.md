# CAT/IRT Evaluation

This deterministic report uses 55 existing PostgreSQL questions, grouped by subject. It generated no question content.

| Subject | Pool mode | Questions | RMSE | MAE | Bias | Mean questions | Convergence |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| DATABASE | validated_existing_offline | 30 | 0.5478 | 0.4376 | 0.0814 | 16.69 | 100.00% |
| NETWORK | validated_existing_offline | 25 | 0.5816 | 0.4618 | 0.0665 | 15.53 | 97.00% |

## Reliability and limitations

- **DATABASE:** No active items exist for this subject; the offline evaluation uses only existing records that pass deterministic structural checks. They remain ineligible for production CAT until explicit admin review and activation.
- **DATABASE:** Evaluation uses the current 30 provided questions; no questions were generated to reach 200.
- **DATABASE:** RMSE, MAE, bias, and convergence are exploratory because the subject pool has fewer than 50 items.
- **DATABASE:** Item-fit and discrimination are simulation diagnostics, not empirical calibration from real student responses.
- **DATABASE:** The IRT difficulty range is narrow relative to the simulated theta range [-3, 3].
- **NETWORK:** No active items exist for this subject; the offline evaluation uses only existing records that pass deterministic structural checks. They remain ineligible for production CAT until explicit admin review and activation.
- **NETWORK:** Evaluation uses the current 25 provided questions; no questions were generated to reach 200.
- **NETWORK:** RMSE, MAE, bias, and convergence are exploratory because the subject pool has fewer than 50 items.
- **NETWORK:** Item-fit and discrimination are simulation diagnostics, not empirical calibration from real student responses.
- **NETWORK:** The IRT difficulty range is narrow relative to the simulated theta range [-3, 3].
