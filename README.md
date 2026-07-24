# Adaptive Exam System

FastAPI and Streamlit application for question ingestion, IRT-informed exam generation, scoring, ability estimation, and traceable Rela-model reasoning.

## Run locally

Start only the PostgreSQL and CloudBeaver infrastructure with Docker:

```bash
docker compose --env-file .env -f docker/docker-compose.yaml up -d
```

FastAPI and Streamlit intentionally run in the local Conda environment while the application is under development. The repository does not build application containers yet.

A clean database starts with schema, rules, configuration, and the four demo accounts. The reproducible operational seed creates 200 complete English MCQs: 100 Database Systems and 100 Computer Networks. Every item includes a topic, primary skill, Bloom level, difficulty, answer pool, explanation, average time, initial IRT parameters, and provenance. The seed inserts items as `draft`, runs the same deterministic administrator review used by the API, and activates only items that pass. Legacy questions are retired rather than deleted when `--retire-legacy` is used.

Copy the environment template once, then fill in local credentials:

```bash
cp .env.example .env
```

`.env` is ignored by Git. It contains only deployment/runtime settings: database location and credentials, backend/frontend host and port, frontend-to-backend endpoint, authentication secret, upload limits, LLM endpoint/key, and network timeouts. Do not commit or share this file.

Exam behavior remains in PostgreSQL `sys_props`, including fixed/CAT question counts, Bloom answer-pool sizes, difficulty distributions, IRT/CAT parameters, learning thresholds, the LLM model, token budgets, temperature, source limit and LLM kill switch. Credentials are never stored in `sys_props`.

For the existing Conda environment:

```bash
conda activate CS2307
pip install -r requirements.txt

docker compose --env-file .env -f docker/docker-compose.yaml up -d
docker compose --env-file .env -f docker/docker-compose.yaml exec -T postgres \
  psql -U postgres -d app < scripts/adaptive_exam_schema_optimized.sql
docker compose --env-file .env -f docker/docker-compose.yaml exec -T postgres \
  psql -U postgres -d app < scripts/migrate_mandatory_non_llm.sql
docker compose --env-file .env -f docker/docker-compose.yaml exec -T postgres \
  psql -U postgres -d app < scripts/migrate_calibration_and_english.sql

python -m scripts.seed_english_question_bank --activate --retire-legacy

python -m scripts.start_backend
```

The ASGI module is `backend.main:app`, not `main:app` from the repository root.

In a second terminal, start the frontend:

```bash
conda activate CS2307
python -m scripts.start_frontend
```

- Application UI: `http://localhost:8501`
- Swagger UI: `http://localhost:8000/docs`
- CloudBeaver: `http://localhost:8978`

CloudBeaver must connect to host `postgres`, port `5432`, database `app`, user `postgres`, and password `postgres`.

## Exam workflow

1. The English landing page displays the project title, five member placeholders, and sign-in/sign-up actions. Sign-up remains a placeholder.
2. Login routes exam takers to their personal progress dashboard and staff to role-specific workspaces. The fixed-exam page combines subject, question-count, and difficulty-profile controls; CAT uses one subject per session.
3. The backend reads fixed and CAT blueprints from `sys_props`. CAT selects active, validated, unanswered questions using information, weak-unit evidence, content balance, and exposure control.
4. Each response uses IRT 3PL EAP to refresh subject and topic/skill ability from response history and stores inference traces.
5. The countdown starts from the configured estimated duration. Reaching zero changes it to overtime but never blocks or submits the exam.

The taker interface and its API responses only expose questions, remaining estimated time, scores, understanding labels, and answer explanations. Bloom distribution, IRT ability, standard error, Fisher information, and generation configuration are visible only to supervisors and administrators.

Role-specific navigation:

- Exam taker: personal progress, score history, interactive learning path, new exam, and active exam.
- Supervisor: taker overview, generated sessions, CAT trajectory, IRT metrics, empirical calibration, adaptive defaults, interactive Knowledge Graph, one-question LLM drafts, and technical result explanations.
- Administrator: system overview, question readiness/review/activation, empirical calibration, central configuration, interactive Knowledge Graph, account administration, and the LLM draft queue.

Learning-path steps are derived from answered topic/skill evidence. Rule codes and trace identifiers stay in staff diagnostics; the taker API and UI expose only the learning action and understandable progress evidence.

The visible interface is English across every role. The only intentional Vietnamese output is the on-demand LLM learning explanation required by the XAI workflow; its buttons, status, evidence headings, and surrounding page remain English.

Knowledge and learning graphs use NetworkX for graph structure and a PyVis/vis-network canvas for interaction. The ability graph initially shows only the exam taker and subjects. Double-clicking a node, or using **Expand selected**, reveals the next semantic level; **Collapse branch** hides it again. Search, node-type filters, relationship filters, drag, zoom, layout pause/resume, reset, and show-all controls are available. Visible labels and relationships are plain English rather than database identifiers. Long text is wrapped to three lines on the node and preserved in full in its hover tooltip.

## Seeded accounts

| Role | Username | Password | Landing destination |
|---|---|---|---|
| Administrator | `admin` | `admin` | System overview |
| Supervisor | `supervisor` | `supervisor` | Taker overview |
| Exam taker | `taker1` | `taker1` | Personal progress |
| Exam taker | `taker2` | `taker2` | Personal progress |

Passwords are stored as salted PBKDF2-SHA256 hashes. Change the default credentials and `AUTH_SECRET` outside local development.

Main endpoints:

```text
POST /api/v1/auth/login
GET  /api/v1/auth/me
GET  /api/v1/exams/subjects
POST /api/v1/exams/generate
POST /api/v1/exams/{session_id}/submit
POST /api/v1/cat/start
POST /api/v1/cat/{session_id}/answer
GET  /api/v1/cat/{session_id}/result
GET  /api/v1/supervisor/cat/{session_id}
POST /api/v1/kb/closure
POST /api/v1/kb/validate-rule
GET  /api/v1/kb/traces/{trace_id}
GET  /api/v1/taker/knowledge-graph
GET  /api/v1/students/{student_id}/knowledge-graph
GET  /api/v1/taker/dashboard
GET  /api/v1/supervisor/dashboard
GET  /api/v1/supervisor/config/difficulty-distribution
PUT  /api/v1/supervisor/config/difficulty-distribution
GET  /api/v1/calibration/latest
POST /api/v1/calibration/run
GET  /api/v1/admin/dashboard
GET  /api/v1/admin/overview
GET  /api/v1/admin/questions
GET  /api/v1/admin/questions/readiness
GET  /api/v1/admin/questions/{question_code}
PATCH /api/v1/admin/questions/{question_code}
POST /api/v1/admin/questions/{question_code}/review
POST /api/v1/admin/questions/{question_code}/activate
POST /api/v1/admin/questions/bulk-activate
GET  /api/v1/generation/status
GET  /api/v1/generation/catalog
GET  /api/v1/generation/recent
POST /api/v1/generation/questions
POST /api/v1/explanations/sessions/{session_id}
POST /api/v1/taker/explanations/{session_id}
GET  /api/v1/admin/config
PUT  /api/v1/admin/config
GET  /api/v1/admin/accounts
POST /api/v1/admin/accounts
PATCH /api/v1/admin/accounts/{username}
```

Exam and dashboard endpoints require `Authorization: Bearer <access_token>` and enforce role boundaries.

## Import question bundles

Validate only:

```bash
curl -X POST \
  "http://localhost:8000/api/v1/questions/import-jsonl?dry_run=true" \
  -F "file=@data/database_bloom_5_questions.jsonl;type=application/x-ndjson"
```

Write to PostgreSQL:

```bash
curl -X POST \
  "http://localhost:8000/api/v1/questions/import-jsonl" \
  -H "Authorization: Bearer <admin-token>" \
  -F "file=@data/database_bloom_5_questions.jsonl;type=application/x-ndjson"
```

Successful lines report `created` or `updated`; invalid lines report their JSON path and error. Re-uploading the same bundle updates its aggregate without duplicating the question or source facts.

Every imported question is kept in `draft` until an administrator reviews and activates it. LLM generation is a separate, explicit staff action that creates exactly one persisted English `draft` per call. It never pads the bank automatically, never activates its output, and cannot bypass deterministic validation or admin review. The administrator can complete review and activation on the same LLM workspace page. Question generation uses [question_generation_system_en.txt](backend/prompts/templates/question_generation_system_en.txt).

The result pages can request persisted XAI feedback. Deterministic score, unit evidence, ability change, and rule-trace context are passed to the provider; the provider is not allowed to recalculate them. Taker and staff outputs are required to be concise Vietnamese by [exam_explanation_system_vi.txt](backend/prompts/templates/exam_explanation_system_vi.txt), then cached by session and audience. The server, rather than the LLM, constructs the displayed evidence list. Contradictory fractions or percentages in generated prose are rejected and replaced before the versioned response is persisted.

The empirical calibration page uses only completed real response events. It reports observed accuracy, predicted accuracy, point-biserial discrimination, response time, binned fit RMSE, and a conditional difficulty estimate. Items below the thresholds stored in `sys_props` are explicitly marked `insufficient` or `provisional`; production IRT parameters are changed only when the apply threshold is met.

## Tests

```bash
pytest -q
python -m scripts.evaluate_cat
python -m scripts.smoke_exam_flow
python -m scripts.smoke_auth_roles
python -m scripts.smoke_dashboards
```

The smoke flows require the local PostgreSQL container. The exam flow signs in as `taker1`, writes a completed exam, and verifies scoring. The role flow verifies all four credentials. The dashboard flow verifies personalized progress, supervisor configuration, question-bank reporting, account updates, and role boundaries.

See [docs/report.md](docs/report.md) for the course-theory mapping and [docs/evaluation_report.md](docs/evaluation_report.md) for the CAT evaluation workflow.
