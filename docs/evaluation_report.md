# CAT/IRT Evaluation

This deterministic report uses 201 existing PostgreSQL questions, grouped by subject. It generated no question content.

| Subject | Pool mode | Questions | RMSE | MAE | Bias | Mean questions | Convergence |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| DATABASE | active | 101 | 0.3499 | 0.2796 | 0.0511 | 20.79 | 90.00% |
| NETWORK | active | 100 | 0.3499 | 0.2796 | 0.0511 | 20.79 | 90.00% |

## Reliability and limitations

- **DATABASE:** Evaluation uses the current 101 active questions; the simulator generated no question content.
- **DATABASE:** Item-fit and discrimination are simulation diagnostics, not empirical calibration from real student responses.
- **DATABASE:** Item-fit and empirical discrimination are unreliable for items with fewer than 20 simulated responses.
- **NETWORK:** Evaluation uses the current 100 active questions; the simulator generated no question content.
- **NETWORK:** Item-fit and discrimination are simulation diagnostics, not empirical calibration from real student responses.
- **NETWORK:** Item-fit and empirical discrimination are unreliable for items with fewer than 20 simulated responses.
