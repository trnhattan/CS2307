# Adaptive Ability Assessment — Application and Test Guide

This document is the teammate-facing guide for installing, running, understanding, demonstrating, and manually testing the Adaptive Ability Assessment application.

The application combines:

- FastAPI for authenticated APIs and application services.
- PostgreSQL for questions, knowledge, configuration, responses, abilities, traces, and LLM artifacts.
- Streamlit for role-specific user interfaces.
- Rela-model `K = (C, R, Rules)` for explicit facts, relations, rules, inference, and provenance.
- IRT 3PL and EAP for ability estimation.
- CAT for adaptive question selection and stopping.
- NetworkX and PyVis/vis-network for interactive knowledge and learning graphs.
- OpenRouter and Gemini 3.1 Flash-Lite for reviewed question drafts and grounded Vietnamese explanations.

The visible application interface is English. The intentionally Vietnamese output is the on-demand LLM learning or technical explanation.

For the criterion model, learner-state history, placement assessment, grounded chat,
learner graph, radar chart, and step-by-step acceptance tests, see
[`learner_model_testing.md`](learner_model_testing.md).

For the requirement-driven seven-minute demonstration order, speaker script, UI clicks,
expected results, and failure-safe alternatives, see
[`presentation_scenario_7_minutes.md`](presentation_scenario_7_minutes.md).

## 1. Current implementation status

| Capability | Status |
| --- | --- |
| Local PostgreSQL, FastAPI, and Streamlit application | Implemented |
| Authentication and role-specific navigation | Implemented |
| 200 operational questions across two subjects | Implemented by the clean deterministic seed |
| Fixed exam by subject, count, and difficulty | Implemented |
| Real-time adaptive CAT | Implemented |
| IRT 3PL ability estimation and Fisher information | Implemented |
| Subject and knowledge-unit ability history | Implemented |
| Rela-model facts, relations, rules, closure, and traces | Implemented |
| Personalized evidence-based learning path | Implemented |
| Interactive student Knowledge Graph | Implemented |
| Question review, activation, and readiness governance | Implemented |
| Real-response item calibration pipeline | Implemented; reliability depends on sample size |
| LLM question draft, validation, review, and activation | Implemented |
| Grounded Vietnamese XAI explanation with caching | Implemented |
| Deterministic CAT convergence evaluation | Implemented |
| Deep Knowledge Tracing | Deferred |
| Reinforcement Learning question policy | Deferred |

A clean seed produces 100 Database Systems questions and 100 Computer Networks questions. A development database may contain more records because legacy, imported, retired, and LLM-generated questions are retained for provenance. The administrator dashboard therefore may show a total greater than 200 while the operational seed itself remains 200.

## 2. System architecture

```text
Streamlit frontend
    |
    | Bearer-token HTTP requests
    v
FastAPI backend
    |-- Authentication and role authorization
    |-- Fixed-exam service
    |-- CAT selection and stopping service
    |-- IRT and ability service
    |-- Rela-model inference engine
    |-- Question governance and calibration
    |-- LLM generation and explanation adapters
    |
    v
PostgreSQL
    |-- Subjects, topics, skills, questions, options
    |-- Students, users, sessions, response events
    |-- Ability states and inference traces
    |-- Concepts, relations, facts, and rules
    |-- sys_props and LLM/calibration artifacts
```

Important module boundaries:

```text
backend/auth/             Login, tokens, and role checks
backend/exams/            Fixed exam generation and scoring
backend/cat/              Adaptive session, selection, and stopping
backend/irt/              3PL probability, information, and EAP
backend/abilities/        Subject/unit ability refresh and learning facts
backend/kb/               Facts, unification, closure, inference, traces
backend/knowledge_graph/  Privacy-aware graph construction
backend/calibration/      Empirical item diagnostics
backend/generation/       LLM question draft pipeline
backend/explanations/     Grounded Vietnamese XAI pipeline
frontend/pages/           Role-specific Streamlit pages
frontend/components/      Navigation, countdown, and graph components
scripts/                  Schema, migrations, seed, startup, and evaluation
```

## 3. Prerequisites

- Docker Desktop, or Docker Engine with Docker Compose v2.
- Git when building from source. It is not required if the repository is delivered as an archive.
- At least 4 GB of free memory for the complete stack.
- Host ports `5432`, `8000`, `8501`, and optionally `8978` available, or changed in `.env`.
- An LLM API key only when testing LLM features. Every other feature works without it.

The supported teammate workflow is Docker Compose. It runs PostgreSQL, FastAPI, Streamlit, and CloudBeaver on one private Docker network. Do not start the backend or frontend image with a standalone `docker run`: both depend on service discovery, environment overrides, health checks, and startup ordering defined by Compose.

Conda is optional and is described only in the contributor section below.

## 4. Run with Docker

### 4.1 Get the deployment files

```bash
git clone <repository-url>
cd CS2307
```

The commands in this guide assume the current directory is the repository root.

### 4.2 Create the environment file and mount directories

```bash
cp .env.example .env
./docker/setup.sh
```

At minimum, replace `AUTH_SECRET` and review the database password in `.env`. To enable the optional LLM workflows, set either `OPENROUTER_API_KEY` or `GEMINI_API_KEY`.

Important Docker-facing values are:

```dotenv
BACKEND_PORT=8000
FRONTEND_PORT=8501
CLOUDBEAVER_PORT=8978

BACKEND_IMAGE=nhattant/cs2307:backend-v1.0.0
FRONTEND_IMAGE=nhattant/cs2307:frontend-v1.0.0

POSTGRES_PORT=5432
POSTGRES_DB=app
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

AUTH_SECRET=replace-with-a-long-random-secret

OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_API_KEY=replace-with-your-openrouter-key
OPENROUTER_HTTP_REFERER=http://localhost:8501
OPENROUTER_APP_TITLE=CS2307 Adaptive Exam

GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
GEMINI_API_KEY=replace-with-your-gemini-key
GEMINI_THINKING_LEVEL=low
MCP_ISSUER_URL=http://localhost:8000
MCP_PUBLIC_URL=http://localhost:8000/mcp
```

The administrator selects the provider and model centrally in Configuration. The values
are stored as `sys_props.LLM_PROVIDER` (`openrouter` or `gemini`) and `LLM_MODEL`.
Choose `gemini` with `gemini-3.1-flash-lite`, or choose `openrouter` with an OpenRouter
model slug such as `~deepseek/deepseek-v4-flash-latest`. This same selection is used by
taker learning chat and feedback, supervisor LLM drafting and explanations, and the
administrator workspace. Restart the backend only after changing `.env` credentials or
endpoints.

`BACKEND_PORT`, `FRONTEND_PORT`, `POSTGRES_PORT`, and `CLOUDBEAVER_PORT` are host ports. Compose always uses `backend:8000` and `postgres:5432` between containers, so keep the internal service overrides in `docker/docker-compose.yaml` unchanged.

Never commit `.env`. Deployment locations, credentials, endpoints, and timeouts belong in `.env`. Exam behavior remains centrally managed in PostgreSQL `sys_props`.

The backend exposes the authenticated learner knowledge tools through Streamable HTTP MCP at `MCP_PUBLIC_URL`. It accepts the same exam-taker bearer token as the REST API. The Learning Assistant invokes the same tools internally for learner profile, completed-test history, completed-question review, and subject-knowledge retrieval.

### 4.3 Choose an image source

For a contributor build from the current source tree, keep the default image names and build locally:

```bash
docker compose --env-file .env -f docker/docker-compose.yaml up -d --build --wait
```

For a teammate release, set the immutable image tags supplied by the maintainer:

```dotenv
BACKEND_IMAGE=nhattant/cs2307:backend-v1.0.0
FRONTEND_IMAGE=nhattant/cs2307:frontend-v1.0.0
```

Then authenticate if the registry is private and start without compiling application images:

```bash
docker login
docker compose --env-file .env -f docker/docker-compose.yaml pull backend frontend
docker compose --env-file .env -f docker/docker-compose.yaml up -d --no-build --wait
```

The PostgreSQL and CloudBeaver images are pulled automatically. A release tag such as `v0.1.0` is reproducible; avoid relying only on `latest` for team demonstrations.

### 4.4 Initialize a new database

The backend automatically creates a missing schema and applies all idempotent migrations before becoming healthy. On a new PostgreSQL mount, run this command once to create the reviewed and active English question bank:

```bash
docker compose --env-file .env -f docker/docker-compose.yaml exec backend \
  python -m scripts.seed_english_question_bank --activate --retire-legacy
```

Expected result:

- Two operational subjects exist.
- The deterministic seed contributes 200 reviewed and active English questions.
- Every operational question has options, an explanation, knowledge links, Bloom level, average time, provenance, and IRT parameters.
- Four demonstration accounts, Rela-model data, inference rules, and `sys_props` exist.

The seed is not required on every restart. If the team supplies a PostgreSQL snapshot, restore the snapshot instead of running the clean seed workflow.

### 4.5 Verify and open the application

```bash
docker compose --env-file .env -f docker/docker-compose.yaml ps
curl http://localhost:8000/ready
curl http://localhost:8501/_stcore/health
```

Expected result: `postgres`, `backend`, and `frontend` report healthy; the backend returns `{"status":"ready"}` and Streamlit returns `ok`.

If custom host ports were set in `.env`, replace `8000`, `8501`, and `8978` in all browser and `curl` URLs with those values.

Open:

| Service | URL | Purpose |
| --- | --- | --- |
| Application | `http://localhost:8501` | Role-specific exam UI |
| FastAPI Swagger | `http://localhost:8000/docs` | API exploration |
| Backend readiness | `http://localhost:8000/ready` | Database-aware health check |
| CloudBeaver | `http://localhost:8978` | Optional database browser |

For CloudBeaver, connect to host `postgres`, port `5432`, and the database credentials from `.env`. The hostname is `postgres`, not `localhost`, because CloudBeaver is inside the Compose network.

### 4.6 Daily Docker lifecycle

Start an existing installation:

```bash
docker compose --env-file .env -f docker/docker-compose.yaml up -d --wait
```

Inspect status and follow application logs:

```bash
docker compose --env-file .env -f docker/docker-compose.yaml ps
docker compose --env-file .env -f docker/docker-compose.yaml logs -f backend frontend
```

Restart the application services without restarting PostgreSQL:

```bash
docker compose --env-file .env -f docker/docker-compose.yaml restart backend frontend
```

After changing `.env`, recreate containers so the new variables are loaded:

```bash
docker compose --env-file .env -f docker/docker-compose.yaml up -d --force-recreate --wait
```

Stop and remove the containers while preserving PostgreSQL and CloudBeaver bind-mounted data:

```bash
docker compose --env-file .env -f docker/docker-compose.yaml down
```

Do not delete `docker/.mnt/postgresql/data` unless an intentional, backed-up database reset is required.

### 4.7 Update the running version

For a source build:

```bash
git pull
docker compose --env-file .env -f docker/docker-compose.yaml up -d --build --wait
```

For versioned release images, change `BACKEND_IMAGE` and `FRONTEND_IMAGE` to the new matching tag, then run:

```bash
docker compose --env-file .env -f docker/docker-compose.yaml pull backend frontend
docker compose --env-file .env -f docker/docker-compose.yaml up -d --no-build --wait
```

Backend startup applies repository migrations automatically. Database state persists across image upgrades.

### 4.8 Publish versioned images for teammates

Use immutable release tags; do not rely only on `latest`. Publish both targets to Docker Hub under the same repository with role-specific tags:

```bash
docker login

docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --file docker/Dockerfile \
  --target backend \
  --tag nhattant/cs2307:backend-v1.0.0 \
  --push .

docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --file docker/Dockerfile \
  --target frontend \
  --tag nhattant/cs2307:frontend-v1.0.0 \
  --push .
```

Teammates then set:

```dotenv
BACKEND_IMAGE=nhattant/cs2307:backend-v1.0.0
FRONTEND_IMAGE=nhattant/cs2307:frontend-v1.0.0
```

After publishing, send teammates the repository or deployment archive, the matching two image tags, and any separately approved database snapshot. Never send `.env` containing real credentials or provider keys.

### 4.9 Optional Conda contributor workflow

Use this only when editing or debugging code outside application containers:

```bash
conda activate CS2307
pip install -r requirements.txt
docker compose --env-file .env -f docker/docker-compose.yaml up -d postgres cloudbeaver
python -m scripts.start_backend
```

In another terminal:

```bash
conda activate CS2307
python -m scripts.start_frontend
```

Do not run `uvicorn main:app`; the application module is `backend.main:app`. The Docker workflow does not require Conda or a host Python installation.

## 5. Demonstration accounts

| Role | Username | Password | Initial page |
| --- | --- | --- | --- |
| Administrator | `admin` | `admin` | System overview |
| Supervisor | `supervisor` | `supervisor` | Taker overview |
| Exam taker 1 | `taker1` | `taker1` | Progress |
| Exam taker 2 | `taker2` | `taker2` | Progress |
| Growth demo taker | `demo_taker` | `demo_taker` | Progress |

These are local demonstration credentials. Change them outside coursework testing.

Create the realistic growth profile after the operational question bank is available:

```bash
python -m scripts.seed_demo_learner --show-credentials
```

The command is idempotent. It creates Alex Nguyen with five Database Systems results
(`65% → 75% → 85% → 90% → 95%`) and three Computer Networks results
(`45% → 55% → 65%`). Every session uses one distinct active question per assessment
criterion and passes through the normal IRT, snapshot, and inference pipeline. Use
`--replace` only when intentionally upgrading an older deterministic demo profile.

## 6. Knowledge-engineering model

### 6.1 Rela-model

The knowledge base follows:

```text
K = (C, R, Rules)
```

- `C` contains concepts from primitive values through composite assessment objects.
- `R` contains typed relations such as `measures`, `belongs_to`, `prerequisite_of`, `has_ability`, and `recommended_next`.
- `Rules` contains external, persisted inference rules with priority, weight, source, and explanation templates.

Concept levels used by the project:

| Level | Examples |
| --- | --- |
| `C(0)` | Number, text, Boolean, probability, theta, time |
| `C(1)` | Subject, knowledge unit, Bloom level, student |
| `C(2)` | Question, answer option, IRT item, ability state, learning path |
| `C(3)` | Exam session, adaptive learning profile, explainable assessment |

Five normalized fact forms are supported:

1. Type fact: `student_1 : Student`.
2. Determined object: `Question(DB_REM_01)` exists.
3. Constant assignment: `DB_REM_01.irt_b = -0.8`.
4. Equality: `difficulty(DB_REM_01) = easy`.
5. Binary or canonical multi-argument relation: `question measures skill`.

### 6.2 Closure and inference

Given initial facts `F`, forward reasoning repeatedly applies applicable rules until no new fact can be produced:

```text
F_0 = F
F_(t+1) = F_t union ApplyApplicableRules(F_t)
Closure(F) = F_n when F_(n+1) = F_n
```

The engine supports forward, backward, and hybrid strategies, comparison clauses, cycle protection, duplicate prevention, and reduced traces. Every derived fact records its rule, input facts, bindings, source, and trace identifier.

The assessment problem can be expressed as:

```text
(O, F) -> G
```

where `O` contains assessment objects, `F` contains known question/student/configuration facts, and `G` is a generated exam, updated ability, or recommended learning action.

## 7. IRT, CAT, scoring, and metrics

### 7.1 IRT 3PL probability

For question `i`, the probability of a correct response is:

```text
P_i(theta) = c_i + (1 - c_i) / (1 + exp(-D a_i (theta - b_i)))
```

with `D = 1.7` by default.

- `theta`: student ability.
- `a_i`: discrimination; how strongly the item separates ability levels.
- `b_i`: difficulty location; larger values represent harder items.
- `c_i`: guessing lower bound.

### 7.2 EAP ability estimate

The system evaluates a theta grid from `-4` to `4`, combines a normal prior with the response likelihood, normalizes the posterior weights, and computes:

```text
theta_EAP = sum(theta_j * posterior_weight_j) / sum(posterior_weight_j)
SE = sqrt(sum(weight_j * (theta_j - theta_EAP)^2) / sum(weight_j))
```

The response ledger remains historical. The latest subject and unit estimates are stored separately in `student_abilities`.

Mastery shown to staff and used by adaptive rules is:

```text
mastery(theta) = 1 / (1 + exp(-theta))
```

### 7.3 Fisher information

The implemented 3PL information function is:

```text
I_i(theta) = D^2 a_i^2 (1 - P_i(theta)) (P_i(theta) - c_i)^2
             ---------------------------------------------------
                       P_i(theta) (1 - c_i)^2
```

An informative item reduces uncertainty near the current ability estimate. A common interpretation is:

```text
SE(theta) approximately 1 / sqrt(sum I_i(theta))
```

The application uses the EAP posterior standard deviation as its operational standard error.

### 7.4 CAT selection score

Every eligible unused candidate receives:

```text
score(q) =
    w_information * normalized_information(q)
  + w_weak       * weak_unit_benefit(q)
  + w_balance    * content_balance_benefit(q)
  - w_exposure   * exposure_penalty(q)
```

where:

```text
normalized_information = I / (1 + I)
weak_unit_benefit       = max(1 - mastery(unit))
```

Only active, structurally valid, subject-compatible, unused questions are candidates. Topic, skill, Bloom, and difficulty constraints are applied before scoring.

### 7.5 CAT stopping

CAT stops when one of these conditions is reached:

1. Maximum question count.
2. Eligible question pool exhausted.
3. Minimum count reached and standard error is below its threshold.
4. Minimum count reached and theta changes remain within epsilon for the configured stability window.

The countdown is guidance only. Reaching zero shows overtime and never submits or blocks the test.

### 7.6 Score and understanding labels

```text
percentage = 100 * awarded_score / maximum_score
```

| Percentage | Taker-facing understanding |
| ---: | --- |
| `< 50%` | Needs review |
| `50% to < 70%` | Foundational understanding |
| `70% to < 85%` | Good understanding |
| `>= 85%` | Strong understanding |

Takers do not see theta, standard error, Bloom distributions, Fisher information, or inference diagnostics. Supervisors and administrators can inspect those technical values.

### 7.7 Empirical calibration metrics

The calibration page uses completed real responses, not simulated responses.

- Observed accuracy: mean of binary item responses.
- Predicted accuracy: mean IRT probability at each response's pre-answer theta.
- Point-biserial: correlation between pre-answer theta and correctness.
- Fit RMSE: root mean squared difference between observed and predicted accuracy across theta bins.
- Suggested `b`: conditional maximum-likelihood search while holding `a` and `c` fixed.
- Mean response time: average recorded time for the item.

Default reliability thresholds are stored in `sys_props`:

- Fewer than 30 responses: `insufficient`.
- At least 30 but fewer than 100: `provisional`.
- At least 100 with response and theta variation: `eligible` for optional application.

Sparse evidence is shown honestly and never silently overwrites production parameters.

### 7.8 CAT simulation metrics

For true simulated ability `theta_n` and estimate `theta_hat_n`:

```text
RMSE = sqrt(mean((theta_hat_n - theta_n)^2))
MAE  = mean(abs(theta_hat_n - theta_n))
Bias = mean(theta_hat_n - theta_n)
```

Convergence rate is the proportion of sessions stopping because the SE threshold or theta-stability condition was reached. Mean questions reports test length, and SE-by-step shows whether uncertainty decreases during CAT.

Run the deterministic evaluation with:

```bash
python -m scripts.evaluate_cat
```

Outputs are written to `data/evaluation/` and `docs/evaluation_report.md`. Simulation verifies algorithm behavior but is not a replacement for real-response calibration.

## 8. LLM safety and persistence boundary

The LLM is an auxiliary module, not the inference engine.

Question generation:

1. Staff selects subject, topic, skills, Bloom level, difficulty, and optional authorized source context.
2. The LLM produces exactly one English draft.
3. The backend validates answer structure, metadata, duplication risk, source, and knowledge-unit links.
4. Initial IRT values come from the deterministic rubric.
5. The question remains `draft` until administrator review and activation.

Explanation generation:

1. The backend calculates score, evidence, ability movement, rules, and trace context.
2. The LLM receives those facts and produces concise Vietnamese prose.
3. The backend rejects contradictory numeric claims.
4. The response and evidence are persisted and reused to control token cost.

Prompts are independent files:

```text
backend/prompts/templates/question_generation_system_en.txt
backend/prompts/templates/exam_explanation_system_vi.txt
```

## 9. Role and feature map

| Page | Exam taker | Supervisor | Administrator |
| --- | :---: | :---: | :---: |
| Progress | Yes | No | No |
| Start test / current test | Yes | No | No |
| Learning or ability graph | Own privacy-safe graph | Selected taker's technical graph | Selected taker's technical graph |
| Taker overview and session metrics | No | Yes | No |
| Exam configuration | No | Yes | No |
| Empirical IRT calibration | No | Yes | Yes |
| LLM workspace | No | Generate drafts | Generate, review, activate |
| System overview | No | No | Yes |
| Question bank governance | No | No | Yes |
| Central `sys_props` configuration | No | No | Yes |
| Account administration | No | No | Yes |

## 10. Public API map

| Area | Main endpoints | Purpose |
| --- | --- | --- |
| Health | `GET /health`, `GET /ready` | Process and PostgreSQL readiness |
| Authentication | `POST /api/v1/auth/login`, `GET /api/v1/auth/me` | Login and current identity |
| Fixed exams | `GET /api/v1/exams/subjects`, `POST /api/v1/exams/generate`, `POST /api/v1/exams/{id}/submit` | Blueprint generation and scoring |
| CAT | `POST /api/v1/cat/start`, `POST /api/v1/cat/{id}/answer`, `GET /api/v1/cat/{id}/result` | Real-time adaptive testing |
| Staff CAT | `GET /api/v1/supervisor/cat/{id}` | Technical trajectory and selection evidence |
| Dashboards | `GET /api/v1/taker/dashboard`, `GET /api/v1/supervisor/dashboard`, `GET /api/v1/admin/overview` | Role-specific progress and operations |
| Knowledge base | `POST /api/v1/kb/closure`, `POST /api/v1/kb/validate-rule`, `GET /api/v1/kb/traces/{id}` | Inference, rule validation, and provenance |
| Graphs | `GET /api/v1/taker/knowledge-graph`, `GET /api/v1/students/{id}/knowledge-graph` | Privacy-safe and technical graph data |
| Question import | `POST /api/v1/questions/import-jsonl` | Validated JSONL ingestion |
| Question governance | `/api/v1/admin/questions...` | Readiness, edit, review, and activation |
| Configuration | Supervisor and `/api/v1/admin/config` endpoints | Typed `sys_props` management |
| Calibration | `GET /api/v1/calibration/latest`, `POST /api/v1/calibration/run` | Real-response item evaluation |
| LLM generation | `/api/v1/generation...` | Status, catalog, one-draft generation, and history |
| LLM explanation | `/api/v1/taker/explanations/{id}`, `/api/v1/explanations/sessions/{id}` | Persisted grounded XAI |
| Accounts | `/api/v1/admin/accounts...` | Account creation and administration |

The fixed-exam API additionally accepts optional topic, skill, Bloom, estimated-duration, difficulty-distribution, and deterministic-seed constraints. The current taker UI intentionally consolidates the most important controls—subject, count, and difficulty—while the complete contract remains available in Swagger.

## 11. Manual UI acceptance tests

Run these tests against a clean seed when possible. Complete at least one taker test before testing progress, staff metrics, calibration, graphs, or explanations.

### UI-01 — Landing, sign-in, and role navigation

Precondition: backend and frontend are running.

Steps:

1. Open `http://localhost:8501`.
2. Confirm the project title and five member placeholders appear.
3. Click **Sign up**.
4. Close the dialog, click **Sign in**, and enter `taker1` / `taker1`.

Expected:

- Sign-up says self-service registration is not enabled.
- Successful taker login opens **Progress**.
- Navigation contains **Progress**, **Start test**, and **Learning graph** only.
- The user identity and **Sign out** appear.
- Staff-only pages are not exposed in navigation.

Repeat with `supervisor` and `admin` and compare navigation with the role matrix above.

### UI-02 — Fixed exam generation and scoring

Precondition: at least one subject has enough active questions.

Steps:

1. Sign in as `taker1`.
2. Click **Start test**.
3. Select **Fixed blueprint**.
4. Select one subject.
5. Set **Questions per subject** to a small value such as 5.
6. Select **Balanced**, **Foundation focused**, **Challenge focused**, or a valid custom distribution.
7. Click **Start test**.
8. Answer every question and click **Submit test**.
9. Expand **Review answers and explanations**.

Expected:

- The generated test contains exactly the requested number of unique questions.
- Every question shows its stem and answer options.
- The countdown shows estimated remaining time.
- An unanswered submission displays the number of missing answers and does not submit.
- Time expiration changes to overtime but does not block submission.
- The result shows score, percentage, and an understanding label.
- Review shows the question, selected answer, best answer when incorrect, and explanation.

### UI-03 — Multi-subject fixed exam

Steps:

1. On **Start test**, select **Fixed blueprint**.
2. Select both subjects and request a small number of questions per subject.
3. Complete the first subject.
4. Click **Continue to the next subject →**.
5. Complete the second subject and click **View test summary**.

Expected:

- One session is created per subject.
- The second subject starts only after the first result.
- **Test summary** shows each subject's percentage and understanding.
- **View progress** returns to the personalized dashboard.

### UI-04 — Adaptive CAT session

Steps:

1. Sign in as a taker and click **Start test**.
2. Select **Adaptive CAT** and one subject.
3. Click **Start test**.
4. Answer each presented question with **Submit answer** until CAT stops.

Expected:

- Only one question is shown at a time.
- Progress shows answered count and configured maximum.
- No question repeats within the session.
- The next question is selected after each response.
- The test stops according to maximum length, pool exhaustion, SE, or theta stability after the minimum.
- The taker result shows score, percentage, answered count, and understanding but no theta, SE, Fisher, or Bloom metrics.

### UI-05 — Personalized progress and learning path

Precondition: `taker1` has completed at least one test.

Steps:

1. Click **Progress**.
2. Inspect summary cards, **Progress by subject**, **Recommended learning path**, and **Recent history**.
3. Drag and zoom the learning-path graph.
4. Double-click a learning step to expand or collapse its next step.

Expected:

- Completed, average, best, latest, and understanding values reflect persisted sessions.
- The learning path contains evidence-based actions such as remediate, reinforce, or advance.
- Accuracy and evidence count match completed responses.
- The graph is interactive and its hover text is readable without raw HTML or database-style identifiers.
- A new account with no completed responses receives an informative empty state.

### UI-06 — Taker Knowledge Graph

Precondition: the taker has completed-response evidence.

Steps:

1. Click **Learning graph**.
2. Select a visible node.
3. Use **Expand selected**, **Collapse branch**, **Show all**, and **Reset view**.
4. Search for a subject, topic, skill, or question.
5. Filter by node type and relationship.
6. Drag nodes and zoom the canvas.

Expected:

- Initial view is collapsed around the taker and subjects.
- Expanding progressively reveals related topics, skills, questions, and evidence.
- Search reveals and focuses the matching node and its ancestor path.
- Labels and relationships use plain English rather than underscored predicates.
- Long labels are shortened on nodes and remain available in hover text.
- Technical ability parameters and internal trace identifiers are absent from the taker graph.

### UI-07 — Grounded taker explanation

Precondition: a completed result and configured LLM API.

Steps:

1. Open a fixed or CAT result.
2. Click **Get Vietnamese learning feedback**.
3. Expand **Evidence used**.
4. Revisit the same result and request the explanation again.

Expected:

- The explanation is Vietnamese and consistent with the scored result.
- Evidence lists deterministic score and learning evidence supplied by the backend.
- An artifact ID and model are displayed.
- A repeated request reports cache reuse and does not require another provider call.
- The taker explanation contains no staff-only theta, SE, Fisher, or rule diagnostics.

### UI-08 — Supervisor taker and session overview

Precondition: at least one completed fixed or CAT session.

Steps:

1. Sign in as `supervisor` / `supervisor`.
2. Open **Taker overview**.
3. Select a session under **Session details**.
4. Select an adaptive session when available.

Expected:

- Summary shows sessions, completion states, taker count, and average score.
- Taker table shows score and staff-only average theta/mastery.
- Session detail shows post-test theta, theta delta, SE, average Fisher information, difficulty distribution, Bloom distribution, and generation snapshot.
- Adaptive sessions show a CAT trajectory containing theta before/after, SE, information, correctness, and selection reason.
- **Generate technical explanation** is available only for completed sessions.

### UI-09 — Supervisor exam configuration

Steps:

1. Click **Exam configuration**.
2. Change easy, medium, and hard weights and click **Save difficulty distribution**.
3. Change CAT minimum/maximum, SE threshold, stability values, selection weights, or constraints.
4. Click **Save adaptive-test configuration**.
5. Return to the page or inspect **Configuration** as an administrator.

Expected:

- Difficulty weights are normalized to 100% by the backend.
- Invalid values or minimum greater than maximum return a clear error.
- Valid values persist in `sys_props`.
- New CAT sessions use the updated snapshot; existing sessions retain their generation snapshot.

Restore shared defaults after testing so later demonstrations remain comparable.

### UI-10 — Empirical IRT calibration

Steps:

1. Sign in as supervisor or administrator.
2. Open **IRT calibration**.
3. Leave application unchecked and click **Run calibration**.
4. Review limitations and item rows.
5. Optionally check **Apply estimates only when the configured production sample threshold is met** and rerun.

Expected:

- Only real completed response events are counted.
- Items show observed/predicted accuracy, point-biserial, fit RMSE, current/suggested `b`, reliability, and application state when calculable.
- Sparse items are `insufficient` or `provisional`.
- No item changes unless the production threshold is satisfied and application was explicitly requested.

### UI-11 — Supervisor or administrator ability graph

Steps:

1. Open **Ability graph**.
2. Select an exam taker.
3. Exercise search, filters, expand/collapse, reset, drag, and zoom.

Expected:

- The selected taker's persisted graph appears after response evidence exists.
- Staff hover details may include theta, standard error, mastery, evidence, and provenance.
- Internal identifiers are translated into readable English labels.
- Selecting a taker with no evidence produces a clear empty state rather than a blank graph.

### UI-12 — LLM draft generation as supervisor

Precondition: `OPENROUTER_API_KEY` is configured and `LLM_ENABLED` is true in `sys_props`.

Steps:

1. Sign in as supervisor.
2. Open **LLM workspace**.
3. Select subject, topic, at least one measured skill, Bloom level, and difficulty.
4. Add a learning objective and authorized source title/excerpt when available.
5. Click **Generate one draft**.

Expected:

- Status shows LLM enabled, API configured, and the selected model.
- Exactly one English question is persisted as `draft`.
- Stem, options, best-answer marker, explanation, IRT rubric, and validation issues appear.
- The artifact appears in **Persisted generation history**.
- A supervisor cannot activate the draft from this page.
- Provider or format failures remain persisted with a readable error.

### UI-13 — Administrator system overview

Steps:

1. Sign in as `admin` / `admin`.
2. Open **System overview**.

Expected:

- Cards show subjects, total/active questions, accounts, knowledge units, facts, and active rules.
- Readiness compares the bank with the configured target of 200.
- A clean seed reports at least 200 active operational questions; a development database may contain additional retained records.

### UI-14 — Question bank governance

Steps:

1. Open **Question bank**.
2. Inspect readiness metrics and coverage by subject.
3. Filter by subject/difficulty or search by code/content.
4. Select **Inspect question** and open **Details and provenance**.
5. Edit a noncritical draft, then click **Save and return to draft**.
6. Click **Run deterministic review**.
7. Click **Activate if valid** only after review passes.

Expected:

- Readiness shows totals, active, invalid, target gap, topic/Bloom/difficulty coverage, and CAT feasibility.
- Editing returns the question to draft/review-required state.
- Review lists blocking and nonblocking validation issues.
- Invalid or incomplete questions cannot activate.
- A valid reviewed question becomes eligible for operational selection.

Bulk activation requires checking the explicit confirmation before **Review and activate eligible items** becomes available.

### UI-15 — Administrator central configuration

Steps:

1. Open **Configuration**.
2. Select an editable setting.
3. Change it using the type-specific editor and click **Save configuration**.
4. Inspect **All configuration**.

Expected:

- Values are type-checked by the backend.
- Invalid JSON or out-of-range values are rejected clearly.
- Valid values persist with updater and timestamp.
- Secrets such as database passwords and LLM API keys do not appear in `sys_props`.

### UI-16 — Account administration

Steps:

1. Open **Accounts**.
2. In **Create account**, create a uniquely named exam taker with a student code.
3. Sign out and verify the new login.
4. Sign back in as admin, open **Edit account**, change its display name or password, and save.
5. Optionally deactivate the new account and verify login is refused.

Expected:

- New accounts appear in the table with the correct role and state.
- Passwords are never displayed.
- Changes persist.
- A deactivated account cannot authenticate.

### UI-17 — Administrator LLM review and activation

Steps:

1. Sign in as administrator and open **LLM workspace**.
2. Generate one draft in the current workspace.
3. Click **Review persisted draft**.
4. If review passes, click **Activate reviewed draft**.
5. Confirm it appears in **Question bank**.

Expected:

- Activation is disabled until deterministic review passes.
- Blocking issues require editing before activation.
- A valid item changes from draft to active and retains LLM model, prompt/request, validation, reviewer, and timestamps as provenance.

## 12. API-only acceptance tests

Some knowledge-engineering functions are exposed through Swagger rather than a dedicated Streamlit page.

### API-01 — Authenticate in Swagger

1. Open `http://localhost:8000/docs`.
2. Call `POST /api/v1/auth/login` with a seeded account.
3. Copy `access_token` and authorize with `Bearer <token>`.

Expected: `/api/v1/auth/me` returns the authenticated identity and role.

### API-02 — Rela-model closure and trace

As supervisor or admin, call `POST /api/v1/kb/closure` with:

```json
{
  "facts": [
    {
      "fact_type": "binary_relation",
      "predicate": "unit_accuracy",
      "args": ["TAKER001", "SQL_JOIN", 0.4],
      "source": "manual_test"
    }
  ],
  "strategy": "hybrid",
  "persist": true
}
```

Expected:

- Derived facts include a weak unit and remediation recommendation when the matching rule is active.
- Steps contain rule codes, input/output facts, bindings, and explanations.
- `trace_id` is returned when persistence is enabled.
- `GET /api/v1/kb/traces/{trace_id}` returns the stored provenance.

Only administrators can call `POST /api/v1/kb/validate-rule`.

### API-03 — JSONL question import

Validate without writing:

```bash
curl -X POST \
  "http://localhost:8000/api/v1/questions/import-jsonl?dry_run=true" \
  -F "file=@data/database_bloom_5_questions.jsonl;type=application/x-ndjson"
```

Expected: every line reports validation status and no question is written.

For a real import, use an admin Bearer token and omit `dry_run=true`. Imported items remain draft until administrator review and activation. Reimport updates the existing aggregate rather than duplicating it.

### API-04 — Authorization boundaries

Call an administrator endpoint using a taker token, for example `GET /api/v1/admin/config`.

Expected: HTTP `403`. Calling a protected endpoint without a token should return HTTP `401`.

## 13. Automated verification

The release-container health checks are the minimum teammate verification:

```bash
docker compose --env-file .env -f docker/docker-compose.yaml ps
curl --fail http://localhost:8000/ready
curl --fail http://localhost:8501/_stcore/health
```

Use the configured host ports instead of `8000` and `8501` when `.env` overrides them.

For source contributors, run the complete unit/integration suite in the `CS2307` Conda environment before building release images:

```bash
conda activate CS2307
pytest -q
```

Expected: every test passes. The suite covers authentication, configuration, JSONL validation/import, question governance, IRT, CAT, evaluation, calibration, Rela-model inference, learning paths, Knowledge Graphs, LLM boundaries, and frontend structure.

Database-backed smoke tests are also contributor checks:

```bash
python -m scripts.smoke_auth_roles
python -m scripts.smoke_exam_flow
python -m scripts.smoke_dashboards
python -m scripts.smoke_frontend_roles
```

Run these against disposable demonstration data because exam/dashboard smoke tests create or update persisted state.

## 14. Requirement coverage

| Project requirement | Application evidence |
| --- | --- |
| 200 MCQs from at least two subjects | Deterministic 100 Database + 100 Network clean seed |
| IRT `a`, `b`, `c`, difficulty, and time | Question schema, governance, readiness, calibration |
| Fixed exam by subject, number, and difficulty | Consolidated **Start test** fixed blueprint |
| Ability updated after testing | EAP subject/unit refresh from response history |
| Rela-model `K=(C,R,Rules)` | PostgreSQL definitions, facts, external rules, traces |
| Five fact forms and unification | KB domain model and inference tests |
| Closure and inference strategies | Closure API with forward/backward/hybrid and reduced trace |
| CAT next-question optimization | Fisher, weak-unit, balance, exposure selector |
| Real-time adaptive testing | One-question-at-a-time CAT UI and API |
| Personalized learning | Rule-derived progress and learning path |
| Knowledge Graph per student | Role-safe interactive NetworkX/PyVis graph |
| LLM question generation by Bloom | Persisted one-draft workflow with validation/review |
| Explainable assessment | Deterministic evidence plus persisted Vietnamese XAI |
| Difficulty evaluation | Real-response calibration and simulation diagnostics |
| Mathematical convergence evaluation | RMSE, MAE, bias, SE-by-step, mean length, convergence |
| DKT | Deferred and not claimed |
| Reinforcement Learning | Deferred and not claimed |

## 15. Common problems

### A service is unhealthy or continuously restarting

Inspect the service state and logs:

```bash
docker compose --env-file .env -f docker/docker-compose.yaml ps
docker compose --env-file .env -f docker/docker-compose.yaml logs --tail=200 backend frontend postgres
```

Do not override the backend command with `uvicorn main:app`. The image already starts the correct `backend.main:app` module through `scripts.start_backend`.

### A host port is already allocated

Change only the host-side value in `.env`, for example:

```dotenv
BACKEND_PORT=18000
FRONTEND_PORT=18501
POSTGRES_PORT=15432
CLOUDBEAVER_PORT=18978
```

Recreate the stack and use the corresponding browser URLs.

### Backend starts but `/ready` returns 503

Check PostgreSQL and `.env`:

```bash
docker compose --env-file .env -f docker/docker-compose.yaml ps
docker compose --env-file .env -f docker/docker-compose.yaml logs postgres
```

### Database has no questions

For a clean initialized schema, run:

```bash
docker compose --env-file .env -f docker/docker-compose.yaml exec backend \
  python -m scripts.seed_english_question_bank --activate --retire-legacy
```

Then verify **Question bank** as admin. Do not rerun the base schema on a populated database.

### Graph is empty

Complete at least one test for the selected taker. The graph intentionally requires persisted response evidence. Then hard-refresh the browser if frontend assets were recently updated.

### Graph canvas is blank or browser reports `vis is not defined`

Pull or rebuild the current frontend image, recreate the frontend container, and hard-refresh the browser. The graph is rendered as an isolated iframe so the inlined vis-network library loads before graph initialization.

### LLM buttons are disabled

Check:

- `OPENROUTER_API_KEY` contains an active OpenRouter key in `.env`.
- `OPENROUTER_BASE_URL` is `https://openrouter.ai/api/v1` without Markdown link syntax or query parameters.
- `LLM_ENABLED` is true in `sys_props`.
- Containers were recreated after changing `.env`.

### Calibration shows insufficient evidence

This is expected until individual questions have enough varied real responses. Do not lower thresholds merely to make the page appear successful; the limitation is part of the correct evaluation result.

### Fixed exam reports insufficient availability

The requested exact distribution or filters exceed the active eligible pool. Reduce the count, loosen the blueprint, or review and activate additional real questions. The application does not duplicate or fabricate fallback items.

## 16. Team database changes

Use append-only SQL migrations for shared schema or required-data changes. Do not distribute the Docker `.mnt` directory.

Each teammate should apply the new migration with:

```bash
docker compose --env-file .env -f docker/docker-compose.yaml exec -T postgres \
  psql -v ON_ERROR_STOP=1 -U postgres -d app \
  < path/to/new_migration.sql
```

Use a PostgreSQL dump only for an onboarding snapshot or an intentional baseline reset. Never commit `.env`, provider keys, real student information, or production credentials.

Create a compressed snapshot from the running PostgreSQL container:

```bash
docker compose --env-file .env -f docker/docker-compose.yaml exec -T postgres \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
  > cs2307_database.dump
```

Share snapshots only when they contain demonstration data. Prefer append-only migrations for normal team updates because a snapshot replaces a baseline rather than describing a reviewable schema change.

## 17. Further documentation

- `docs/knowledge_representation_and_algorithms.md`: detailed Rela-model, problem formulations, equations, inference, IRT/CAT, learning, calibration, graph, and LLM-control mechanisms.
- `docs/report.md`: course-theory mapping and implementation audit.
- `docs/evaluation_report.md`: current deterministic CAT/IRT evaluation.
- `README.md`: concise project entry point and endpoint list.
- `http://localhost:8000/docs`: live API contract.
