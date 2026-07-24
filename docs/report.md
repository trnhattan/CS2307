# Adaptive Exam and Ability Assessment System

## 1. Product scope

The project is a running FastAPI, PostgreSQL, and Streamlit knowledge-based system for fixed exam generation, real-time CAT, IRT 3PL scoring, evolving ability estimation, personalized learning recommendations, governed LLM question drafting, explainable feedback, empirical calibration, and interactive student Knowledge Graphs.

The operational bank contains 200 complete English MCQs: 100 Database Systems and 100 Computer Networks. The current database also contains one reviewed LLM demonstration item and 55 retired legacy items retained for historical session integrity. Question counts are always read from PostgreSQL rather than hard-coded into readiness reports.

DKT and Reinforcement Learning remain intentionally outside the implemented scope. The IRT/CAT baseline is not relabeled as either technology.

## 2. CSTT design process

The course model describes a knowledge-based system that receives a problem, translates it into an internal representation, uses an inference engine, and returns a solution with an explanation [*2a. Các quy trình trong Thiết kế hệ CSTT*, p. 4]. Its four design stages appear on page 6 and map to this system as follows:

1. **Knowledge acquisition:** collect questions, subjects, topics, skills, Bloom levels, IRT parameters, response times, learning paths, and response evidence [*2a...*, p. 8; *3. Các quy trình trong Thiết kế hệ CSTT*, p. 5].
2. **Knowledge-base design:** store concepts, relations, facts, rules, questions, and provenance separately in PostgreSQL [*2a...*, p. 9; *3...*, p. 6].
3. **Inference-engine design:** implement fact unification, closure, forward/backward/hybrid reasoning, trace reduction, ability updates, CAT selection, and recommendation rules [*2a...*, p. 10; *3...*, p. 7].
4. **Interface design:** provide role-specific interfaces for exam takers, supervisors, and knowledge engineers/administrators [*2a...*, p. 11; *3...*, p. 8].

## 3. Rela-model `K = (C, R, Rules)`

The Rela-model source defines the knowledge base as `K = (C, R, Rules)` and organizes concepts across `C(0)` through `C(3)` [*6b. Cấu trúc tri thức quan hệ*, p. 2].

- `C(0)`: number, string, Boolean, probability, theta, and duration.
- `C(1)`: `Subject`, `KnowledgeUnit`, `BloomLevel`, `Student`, and `ResponseEvent`.
- `C(2)`: `Question`, `IRTItem`, `AbilityState`, `ExamBlueprint`, and `LearningPath`.
- `C(3)`: `ExamSession`, `AdaptiveLearningProfile`, `ExplainableAssessment`, and student Knowledge Graph.

Relations include `belongs_to_subject`, `measures`, `prerequisite_of`, `selected_option`, `has_ability`, `weak_unit`, and `recommended_next`. Relation metadata supports symmetric and transitive semantics.

Rules live in `kb_rules`, outside the inference code, with identifiers, hypothesis facts, goal facts, priority, weight, source, provenance, and explanation templates. Explicit course examples now include:

- `R_DIFFICULTY_HARD`: `difficulty_norm >= 0.80 -> classified_as hard`.
- `R_LOW_TOPIC_INCREASE_FREQUENCY`: a weak unit increases adaptive assessment priority.
- Learning rules for remediation, reinforcement, advancement, scoring, and ability update.

The five Rela-model fact types are normalized as `type`, `determined_object`, `constant_assignment`, `equality`, and `binary_relation`. Their unification behavior, including equality symmetry and relation metadata, follows the source description [*6b...*, p. 4]. Canonical multi-argument `fact_args` coexist with legacy subject/object columns for backward compatibility.

## 4. Closure and reasoning strategies

The inference engine begins with normalized known facts, repeatedly applies applicable rules ordered by priority/weight, adds unseen facts with provenance, and terminates at a fixed point or target. This implements `Obj.Closure(F)` [*6b...*, pp. 5–7].

Forward reasoning starts from known facts and expands them until the goal is reached or no rule remains applicable [*4a. Các chiến lược suy diễn*, p. 3]. Backward mode restricts proof search from the target predicate. Hybrid mode computes closure and walks backward through provenance to reduce the final explanation, aligning with the mixed-strategy discussion [*4a...*, p. 5]. Cycle protection and duplicate prevention guarantee termination for the supported rule language.

The general problem is represented as `(O, F) -> G`, whose solvability is defined by a sequence of applicable rules [*6b...*, p. 8]. Rule priority, weight, goal relevance, and missing-object relevance implement transparent heuristics [*6b...*, p. 9]. IRT/CAT act as computational modules and emit facts and traces back into the symbolic system. This matches the computational-network view `Closure(A)` [*4b. Các chiến lược suy diễn (tt.)*, p. 3] and the weighted network `(A, D, w)` [*5a. Mạng tính toán*, pp. 4–5].

## 5. Question bank and fixed exams

The reproducible English operational seed contains 20 domain concepts per subject and five assessment forms per concept, covering remember, understand, apply, analyze, and evaluate. Each item contains:

- subject, topic, and primary measured skill;
- complete stem and Bloom-sized answer pool;
- exactly one best answer, misconception diagnoses, and explanation;
- difficulty label, normalized difficulty, average time, and IRT `a`, `b`, `c`;
- source, language, authoring method, rubric version, and review provenance.

The seed inserts drafts and calls the same deterministic review service used by the administrator API. It activated all 200 operational items with zero validation rejections. Legacy questions were retired, not deleted, preserving completed response events and snapshots.

The fixed-exam page now places subject, question count, and difficulty distribution in one blueprint. The API additionally supports topic, skill, Bloom, estimated-duration, and deterministic-seed constraints. Selection never duplicates or invents an item and returns an availability error when the exact blueprint is impossible.

## 6. IRT, CAT, and personalized learning

The system uses the IRT 3PL probability:

```text
P_i(theta) = c_i + (1-c_i) / (1 + exp(-1.7*a_i*(theta-b_i)))
```

EAP updates subject and unit ability from the full response ledger. `student_abilities` stores the latest theta, standard error, mastery probability, and evidence count without overwriting historical response events.

CAT filters active, structurally valid, unanswered items for one subject. Candidate scores combine Fisher information, weak-unit priority, content balance, and exposure penalty. It stops after the configured minimum when standard error is sufficient, theta stabilizes, the maximum is reached, or the valid pool is exhausted. The estimated-time countdown remains advisory.

Response evidence creates `unit_accuracy(student, unit, value)` facts. Rules derive weak units, mastery, and ordered recommendations. Takers see scores, understanding, progress, weak units, and learning actions; staff can additionally inspect theta, standard error, Bloom distribution, Fisher information, selection reasons, and traces.

## 7. Interactive Knowledge Graph

The course e-learning source emphasizes organized learning-domain knowledge, semantic retrieval, and related-knowledge recommendations [*6d. Ứng dụng - Hệ thống tra cứu kiến thức*, pp. 11, 15]. Its ontology example combines concepts, relations, operators, rules, problems, and methods [*6d...*, p. 21]. The legal knowledge-query example also combines Rela-model and Knowledge Graph concepts, relations, and rules [*6a. Ứng dụng - Hệ truy vấn kiến thức luật*, pp. 3, 8].

The project constructs role-specific graphs directly from PostgreSQL. NetworkX composes nodes and edges; PyVis/vis-network provides an interactive canvas with zoom, drag, search, node and relationship filters, tooltips, and navigation controls. The graph opens as a collapsed hierarchy containing only the student and subjects. Double-click and explicit expand/collapse actions progressively reveal topics, skills, questions, and response evidence instead of rendering the full graph at once. Search reveals a matching node and its ancestor path; reset restores the collapsed view.

All displayed graph labels and relations are human-readable English. Internal identifiers and Rela predicates remain available to the backend but are translated at the presentation boundary. Long labels wrap to three lines and use an ellipsis while the complete text remains in a width-constrained hover tooltip. Archived non-English response content receives a safe English contextual label. The taker graph hides technical ability parameters while the staff graph retains human-readable provenance and metrics. The taker dashboard also renders the ordered learning path as a collapsible interactive graph.

## 8. LLM generation and XAI

LLM use remains an auxiliary layer. The question-generation system prompt is an independent file at `backend/prompts/templates/question_generation_system_en.txt`. It requires one complete English JSON item, exactly one best answer, plausible distractors, and no self-assigned IRT parameters or approval claims.

The live OpenAI-compatible flow was verified and persisted:

- a provider-format error was recorded as a failed artifact;
- the adapter was hardened to normalize a common correct-answer marker only at `correct_index`;
- artifact `2` created question `LLM-00000002`;
- deterministic review returned no blocking issues;
- administrator activation completed successfully.

The XAI prompt is independently stored at `backend/prompts/templates/exam_explanation_system_vi.txt`. It receives deterministic score, unit evidence, recommendations, ability movement, and traces; it cannot recalculate or invent those facts. All user-facing LLM feedback must be concise Vietnamese. Taker prompts exclude internal metrics, while staff prompts may reference them. The server replaces model-authored evidence with deterministic score and unit facts, validates numerical claims in the prose, and versions the persisted grounding format. Session `17` verified that an incorrect model claim of `20/20 (10%)` was rejected in favor of the scored `4/20 (20%)`; artifact `7` persisted the corrected response and a second request verified cache reuse without another LLM call.

## 9. Empirical difficulty calibration

Simulation remains useful for convergence, but it is not empirical item calibration. The new calibration service reads only real completed `exam_items` response events and reports:

- observed and model-predicted accuracy;
- mean response time;
- point-biserial discrimination;
- binned item-fit RMSE;
- a conditional maximum-likelihood estimate of `b` while holding `a` and `c` fixed;
- sample-size reliability and whether an estimate was applied.

Thresholds are stored in `sys_props`. The first persisted run found 55 real responses across 21 historical items. Every item had fewer than 30 responses and none reached the 100-response production threshold, so all results are correctly marked insufficient and no parameter was overwritten. This implements the empirical pipeline without making unsupported calibration claims.

## 10. Mathematical convergence evaluation

The deterministic simulator reuses the production CAT selector and stopping service. With the current active bank, 100 simulated students per subject produced:

| Subject | Active items | RMSE | MAE | Bias | Mean items | Convergence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Database Systems | 101 | 0.3499 | 0.2796 | 0.0511 | 20.79 | 90% |
| Computer Networks | 100 | 0.3499 | 0.2796 | 0.0511 | 20.79 | 90% |

The full SE-by-step, simulated item-fit, discrimination, and coverage diagnostics are in `docs/evaluation_report.md`. These remain simulation diagnostics and are not presented as real-response calibration.

## 11. Requirements matrix

| Requirement | Status | Evidence |
| --- | --- | --- |
| Local FastAPI/PostgreSQL/Streamlit web application | Implemented and verified | Launchers, health/readiness, modular role UI |
| 200 active MCQs across at least two subjects | Implemented and verified | 100 Database + 100 Network operational items |
| IRT parameters and average time for every item | Implemented and verified | Question schema, rubric, governance validation |
| Fixed exam by subject, count, and difficulty | Implemented and verified | Consolidated UI and exact-constraint API |
| Real-time CAT and ability update | Implemented and verified | Active-only selection, EAP update, stopping rules |
| Rela-model `K=(C,R,Rules)` and `C(0)-C(3)` | Implemented and verified | Definitions, facts, external rules, traces |
| Five fact types, unification, closure | Implemented and verified | Inference engine and tests |
| Forward/backward/hybrid reasoning and reduced traces | Implemented and verified | KB APIs and automated tests |
| Personalized learning path | Implemented and verified | Rule-derived unit recommendations |
| Interactive student Knowledge Graph | Implemented and verified | NetworkX/PyVis role-safe graphs |
| LLM generation by Bloom with validation and provenance | Implemented and verified | Persisted live draft, review, activation, artifacts |
| Vietnamese XAI ability feedback | Implemented and verified | External prompt, persisted artifact, cache verification |
| Mathematical CAT convergence evaluation | Implemented and verified | Production-service simulator and current report |
| Empirical difficulty-calibration pipeline | Implemented, currently data-limited | 55 real responses; no item safely eligible to apply |
| Deep Knowledge Tracing | Deferred by team decision | Not implemented or claimed |
| Reinforcement Learning selection policy | Deferred by team decision | Not implemented or claimed |

Excluding the explicitly deferred DKT and RL research extensions, all mandatory product paths are implemented. The only remaining evidence limitation is statistically reliable empirical IRT calibration, which requires substantially more real responses per active item.
