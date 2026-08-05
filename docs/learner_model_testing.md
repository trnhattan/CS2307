# Learner Model, Placement, Graph, Radar, and Assistant

This document describes the implemented learner-facing assessment mechanisms and
provides repeatable manual tests. The application interface is English. The learning
assistant intentionally answers in Vietnamese.

## 1. Assessment criteria and question mapping

Each active subject has an explicit catalog of assessment criteria. A criterion stores:

- A human-readable name.
- A learning objective and an observable success statement.
- A mastery threshold, importance weight, and display order.
- Its topic and the active questions that measure it.

The current operational bank contains 20 active criteria for Database Systems and 20
for Computer Networks. Every operational criterion has five active mapped questions.
The mapping reuses the reviewed knowledge-unit links already attached to the question
bank; it does not infer criteria from question text at runtime.

Criterion understanding is calculated from completed response evidence. Unknown
criteria remain unknown and are never displayed as zero. Evidence confidence is
reported separately so that one correct response is not presented as a reliable
mastery conclusion.

### Manual test

1. Open `http://localhost:8501` and sign in as `taker1`.
2. Open **Progress**.
3. Under **Assessment criteria and radar**, leave **Overall** selected and verify that
   each axis represents one subject's current mastery.
4. Choose a subject and verify that the axes switch to readable criterion names.
5. Verify that each row shows the expected achievement, understanding, accuracy,
   evidence confidence, and trend.
6. Select an unassessed account or subject and confirm that missing evidence is shown
   as **Unknown** or **Not assessed**, not `0%`.

Expected result: the radar and table describe the same criterion profile, and no IRT
theta, standard error, Bloom level, Fisher information, or rule diagnostics are exposed
to an exam taker.

## 2. Longitudinal learner state

The system persists two complementary forms of learner state:

1. Current subject and criterion abilities in `student_abilities`.
2. Immutable post-assessment snapshots in `student_ability_snapshots`.

After a completed fixed, placement, or adaptive assessment, the ability service uses
the accumulated response history to refresh subject and criterion states. Each snapshot
records the current estimate, previous estimate, mastery change, evidence count, and
the session that produced it. The profile service classifies the evidence into strengths,
weaknesses, improvements, regressions, and insufficient evidence.

The learning recommendations are deterministic and evidence-grounded. The backend
automatically retrieves relevant completed-question context from the message and combines
it with profile facts and subject criteria. The LLM is not allowed to invent scores or
access another student's data.

### Manual test

1. Sign in as an exam taker and complete a test.
2. Return to **Progress** and record the criterion accuracy, evidence count, and trend.
3. Complete another test in the same subject with a different answer pattern.
4. Return to **Progress**.

Expected result: evidence counts increase, current understanding changes when supported
by evidence, and the **Improved** or **Needs attention** summaries reflect the stored
history rather than only the latest score.

## 3. Grounded learning assistant

The **Learning assistant** is a persisted conversation interface for several tasks:

- Asking what to improve and what to learn next.
- Asking why an answer was correct or incorrect.
- Asking what has been learned so far or how performance changed.
- Asking for keywords, explanations, or a starting point for a criterion.

The backend acts as a guarded retrieval layer. For every message it searches only the
authenticated learner's completed tests, relevant question text, selected answer,
stored best answer, deterministic explanation, criterion mapping, longitudinal profile,
and recent messages. The learner does not need to enter a session ID or question code.
Assistant answers retain internal provenance, limitations, model identifier, and provider
status, but these implementation details are not shown in the taker conversation.

Direct-answer requests are rejected before any LLM call. Unanswered questions and
in-progress sessions are excluded from retrieval, and one learner cannot access another
learner's history. A completed question may be explained, but the assistant will not
select an answer for a live assessment.

The OpenRouter provider call uses the independent system prompt at
`backend/prompts/templates/learner_chat_system_vi.txt`. If the provider is unavailable,
the system returns and persists a deterministic Vietnamese fallback so the workflow
remains usable and transparent.

### Manual test: improvement advice

1. Sign in as an exam taker and open **Learning assistant**.
2. Expand **Start a new conversation**.
3. Select a subject, enter a title, and click **Create conversation**.
4. Ask `Tôi cần cải thiện điều gì trước?`.

Expected result: a natural Vietnamese answer references the learner's actual weak or
insufficiently assessed criteria without showing internal evidence/debug panels.

### Manual test: answer rationale

1. Complete a test that contains a question about indexes or transactions.
2. In **Learning assistant**, ask naturally, for example
   `Tại sao câu về transaction isolation của tôi sai?`.
3. Ask a follow-up such as `Tôi nên nhớ những từ khóa nào?`.

Expected result: the answer is grounded in the stored question, selected answer, best
answer, explanation, and mapped criterion. The relevant completed question is found
automatically and the follow-up remains connected to the conversation.

### Manual test: assessment security

1. Start an assessment or describe an unanswered question.
2. Ask `What is the correct answer for this question?`.

Expected result: the assistant refuses to provide or choose an answer and offers concept
help, a staged hint, or a review after the assessment is complete.

## 4. Ability-aware adaptive testing

The CAT policy begins from the learner's persisted subject ability when available. For
every next item it combines:

- Fisher information near the current theta estimate.
- Extra value for weak topics and criteria.
- Criterion coverage, so repeatedly tested capabilities do not crowd out unmeasured
  ones.
- Content balance and an exposure penalty.

After every answer, theta and standard error are recomputed from response evidence and
the next item is selected from the remaining valid pool. No item repeats within a CAT
session. The session stops after the configured minimum when precision or stability is
sufficient, at the maximum length, or when the eligible pool is exhausted.

### Manual test

1. Sign in as an exam taker and open **Start test**.
2. Choose **Adaptive CAT**, select one subject, and click **Start test**.
3. Answer several questions and observe that each next question appears immediately.
4. Complete the session and review the learner profile.
5. Sign in as `supervisor`, open the completed CAT session, and inspect the technical
   selection components and ability history.

Expected result: the exam taker sees questions and progress without technical metrics;
the supervisor can see the changing ability estimate, information, criterion-coverage
component, and stopping reason.

## 5. Placement assessment

A placement assessment is a fixed-length, one-subject baseline controlled by `sys_props`.
It uses the active validated bank and prioritizes previously unused criteria while still
respecting the configured difficulty distribution. It never generates, duplicates, or
silently substitutes questions.

Current database verification shows that each 20-question placement blueprint covers
20 distinct criteria for both operational subjects.

### Manual test

1. Sign in as an exam taker and open **Start test**.
2. Choose **Placement assessment** and select one subject.
3. Click **Start test**, answer all questions, and submit.
4. Return to **Start test** and inspect **Current placement status**.
5. Open **Progress** to inspect the newly established criterion baseline.

Expected result: the session is marked as a placement assessment, the status is
completed, and the radar/profile now contains evidence across the subject criteria.

## 6. Learner knowledge graph

The graph is a privacy-aware projection over PostgreSQL, not a second source of truth.
Its hierarchy is:

```text
Exam taker
  -> Subject
      -> Assessment criterion, with understanding and evidence on the edge
          -> Answered question, with result and difficulty on the edge
```

The initial view contains only the learner and subject nodes. Expanding a subject shows
its criteria. Expanding a criterion shows only questions that the learner has answered
for that criterion. The canvas supports zooming, dragging, searching, filtering, and
branch expansion/collapse. Labels are readable English rather than database identifiers.

### Manual test

1. Sign in as an exam taker and open **Learning graph**.
2. Verify that the initial view contains the learner and subjects only.
3. Double-click a subject or select it and use **Expand selected**.
4. For a learner with only one or two completed subject tests, verify that structural
   edge labels remain **Has learning profile for** and **Requires understanding of**.
5. For `demo_taker`, verify that subject and criterion edges show evidence-aware labels:
   **Needs review** below 45%, **Developing** from 45% to below 60%, **Understands**
   from 60% to below 75%, and **Mastered/Proficient** from 75%.
6. Expand one criterion.
7. Verify that only answered questions mapped to that criterion appear, with correctness
   and difficulty available in the edge/node details.
8. Test search, node-type filtering, relationship filtering, zoom, drag, collapse, and
   **Reset view**.

Expected result: no unanswered question is exposed under a criterion and no other
learner's evidence appears.

## 7. Overall and criterion radar

The default **Overall** radar uses one axis per subject and plots the current IRT-derived
subject mastery. Selecting a subject switches the radar to one axis per assessment
criterion. Both modes use a 0–100 display scale, preserve missing evidence as unknown,
and provide exact values through hover text.

The radar is descriptive, not a substitute for confidence. The adjacent table should
always be used to interpret evidence count and confidence.

## 8. Verification record and limitations

Verified on 4 August 2026:

- Python compilation succeeded in the `CS2307` Conda environment.
- `87` automated tests passed.
- Role-specific Streamlit smoke tests passed against the already-running services on
  ports `8501` and `8000`.
- The live PostgreSQL bank produced 20-question, 20-criterion placement selections for
  both Database Systems and Computer Networks without creating sessions.
- Live criteria, profile, radar, graph, placement-status, and persisted-chat routes were
  exercised successfully.

Known limitations:

- Criterion wording and success statements are structurally complete but should receive
  final subject-matter-expert review before a high-stakes deployment.
- Historical criterion snapshots were backfilled from available completed-response
  evidence. New snapshots use the current IRT ability pipeline consistently.
- OpenRouter requires `OPENROUTER_API_KEY` in `.env`. The deterministic Vietnamese
  fallback remains available when OpenRouter is not configured or temporarily unavailable.
- DKT and reinforcement learning remain outside this implementation, as requested.
