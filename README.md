# Adaptive Exam System

FastAPI and Streamlit application for question ingestion, IRT-informed exam generation, scoring, ability estimation, and traceable Rela-model reasoning.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

docker compose -f docker/docker-compose.yaml up -d postgres
docker compose -f docker/docker-compose.yaml exec -T postgres \
  psql -U postgres -d app < scripts/adaptive_exam_schema_optimized.sql

python -m uvicorn backend.main:app --reload --env-file .env
```

With the existing Conda environment, replace the first two commands with:

```bash
conda activate CS2307
pip install -r requirements.txt
```

For a database created before the exam generator was added, apply its idempotent configuration seed once:

```bash
docker compose -f docker/docker-compose.yaml exec -T postgres \
  psql -U postgres -d app < scripts/seed_exam_generator_config.sql
```

For a database created before role-based login was added, apply the authentication migration once:

```bash
docker compose -f docker/docker-compose.yaml exec -T postgres \
  psql -U postgres -d app < scripts/migrate_add_auth.sql
```

For a database created before personalized learning dashboards were added, seed the recommendation rules once:

```bash
docker compose -f docker/docker-compose.yaml exec -T postgres \
  psql -U postgres -d app < scripts/migrate_dashboard_features.sql
```

In a second terminal, start the frontend:

```bash
conda activate CS2307
python -m streamlit run frontend/app.py
```

- Application UI: `http://localhost:8501`
- Swagger UI: `http://localhost:8000/docs`
- CloudBeaver: `http://localhost:8978`

CloudBeaver must connect to host `postgres`, port `5432`, database `app`, user `postgres`, and password `postgres`.

## Exam workflow

1. The landing page displays the project title, five member placeholders, and login/signup actions. Signup remains a placeholder.
2. Login routes exam takers to their personal progress dashboard and staff to role-specific workspaces. One or more subjects may be selected when starting a new exam.
3. The backend reads the blueprint from `sys_props`, creates one persisted session per subject, and chooses questions with difficulty/content balancing plus IRT Fisher information at the student's current `theta`.
4. Submission uses IRT 3PL EAP to update `theta`, standard error, mastery probability, response facts, and inference traces.
5. The countdown starts from the configured estimated duration. Reaching zero changes it to overtime but never blocks or submits the exam.

The taker interface and its API responses only expose questions, remaining estimated time, scores, understanding labels, and answer explanations. Bloom distribution, IRT ability, standard error, Fisher information, and generation configuration are visible only to supervisors and administrators.

Role-specific navigation:

- Exam taker: personal progress, score history, learning path, new exam, and active exam.
- Supervisor: taker overview, generated sessions, IRT metrics, and default difficulty distribution.
- Administrator: system overview, read-only question bank, central configuration forms, and account administration.

Learning-path steps are derived from answered topic/skill evidence. Each recommendation includes a stored Rela-model rule code and evidence explanation in the API; the taker UI presents only the learning action and understandable progress evidence.

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
GET  /api/v1/taker/dashboard
GET  /api/v1/supervisor/dashboard
GET  /api/v1/supervisor/config/difficulty-distribution
PUT  /api/v1/supervisor/config/difficulty-distribution
GET  /api/v1/admin/dashboard
GET  /api/v1/admin/overview
GET  /api/v1/admin/questions
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
  -F "file=@data/database_bloom_5_questions.jsonl;type=application/x-ndjson"
```

Successful lines report `created` or `updated`; invalid lines report their JSON path and error. Re-uploading the same bundle updates its aggregate without duplicating the question or source facts.

## Tests

```bash
pytest -q
python -m scripts.smoke_exam_flow
python -m scripts.smoke_auth_roles
python -m scripts.smoke_dashboards
```

The smoke flows require the local PostgreSQL container. The exam flow signs in as `taker1`, writes a completed exam, and verifies scoring. The role flow verifies all four credentials. The dashboard flow verifies personalized progress, supervisor configuration, question-bank reporting, account updates, and role boundaries.

See [docs/exam_generator_design.md](docs/exam_generator_design.md) for the CSTT, Rela-model, and IRT mapping.
