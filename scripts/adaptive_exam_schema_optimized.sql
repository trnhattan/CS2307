-- Hệ thống sinh đề thi và chấm điểm tự động theo năng lực
-- DDL tối ưu cho đồ án Công nghệ tri thức dùng Rela-model + IRT 3PL
-- Target DBMS: PostgreSQL 15+
-- Encoding: UTF-8
--
-- Quy mô chủ đích: 16 bảng sau khi bổ sung nhật ký LLM.
-- Mỗi bảng chỉ được giữ khi phục vụ ít nhất một trong bốn mục tiêu:
--   (1) ngân hàng 200 câu hỏi / 2 môn;
--   (2) sinh đề, lưu bài làm và cập nhật năng lực;
--   (3) Rela-model K = (C, R, Rules) và vết suy luận;
--   (4) cấu hình hệ thống.

BEGIN;

-- ============================================================
-- A. DANH MỤC TRI THỨC VÀ NGÂN HÀNG CÂU HỎI (5 bảng)
-- ============================================================

CREATE TABLE subjects (
    subject_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_code        VARCHAR(50)  NOT NULL UNIQUE,
    subject_name        VARCHAR(255) NOT NULL,
    description         TEXT,
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Gộp topics và skills vì cả hai đều là đơn vị tri thức thuộc một môn.
-- unit_type phân biệt chủ đề và kỹ năng; parent_unit_id tạo cây tri thức.
CREATE TABLE knowledge_units (
    unit_id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_id          BIGINT       NOT NULL REFERENCES subjects(subject_id),
    parent_unit_id      BIGINT       REFERENCES knowledge_units(unit_id),
    unit_code           VARCHAR(100) NOT NULL,
    unit_name           VARCHAR(255) NOT NULL,
    unit_type           VARCHAR(20)  NOT NULL,
    description         TEXT,
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_knowledge_units_subject_code UNIQUE (subject_id, unit_code),
    -- Dùng cho khóa ngoại tổng hợp trong student_abilities.
    CONSTRAINT uq_knowledge_units_subject_id UNIQUE (subject_id, unit_id),
    CONSTRAINT ck_knowledge_units_type CHECK (unit_type IN ('topic', 'skill')),
    CONSTRAINT ck_knowledge_units_not_self_parent
        CHECK (parent_unit_id IS NULL OR parent_unit_id <> unit_id)
);

-- Một câu hỏi chỉ có một bộ tham số IRT đang hiệu lực, nên IRT được gộp vào
-- questions. Nếu sau này cần lịch sử hiệu chỉnh nhiều phiên bản, mới tách bảng.
CREATE TABLE questions (
    question_id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    question_code           VARCHAR(80)  NOT NULL UNIQUE,
    subject_id              BIGINT       NOT NULL REFERENCES subjects(subject_id),
    stem                    TEXT         NOT NULL,
    question_type           VARCHAR(30)  NOT NULL DEFAULT 'single_choice',
    scoring_mode            VARCHAR(30)  NOT NULL DEFAULT 'binary',
    bloom_level             VARCHAR(20)  NOT NULL,
    difficulty_label        VARCHAR(20)  NOT NULL,
    difficulty_norm         NUMERIC(6,5) NOT NULL,
    avg_time_sec            INTEGER      NOT NULL,
    explanation             TEXT,

    -- Chính sách chọn phương án từ pool. Kích thước pool thực tế được COUNT
    -- từ answer_options, không lưu lặp trong questions.
    display_option_count    SMALLINT     NOT NULL DEFAULT 4,
    must_include_best       BOOLEAN      NOT NULL DEFAULT TRUE,
    randomize_options       BOOLEAN      NOT NULL DEFAULT TRUE,

    -- IRT 3PL: P(theta) = c + (1-c)/(1 + exp(-a(theta-b))).
    irt_a                   NUMERIC(8,5) NOT NULL,
    irt_b                   NUMERIC(8,5) NOT NULL,
    irt_c                   NUMERIC(8,5) NOT NULL,
    irt_status              VARCHAR(20)  NOT NULL DEFAULT 'draft',
    irt_sample_size         INTEGER      NOT NULL DEFAULT 0,
    irt_model_version       VARCHAR(50)  NOT NULL DEFAULT '3PL-v1',

    status                  VARCHAR(20)  NOT NULL DEFAULT 'draft',
    source                  VARCHAR(255),
    created_by              VARCHAR(100),
    reviewed_by             VARCHAR(100),
    reviewed_at             TIMESTAMPTZ,
    provenance              JSONB        NOT NULL DEFAULT '{}'::JSONB,
    version_no              INTEGER      NOT NULL DEFAULT 1,
    created_at              TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT ck_questions_type
        CHECK (question_type IN ('single_choice', 'weighted_choice')),
    CONSTRAINT ck_questions_scoring
        CHECK (scoring_mode IN ('binary', 'partial_credit')),
    CONSTRAINT ck_questions_type_scoring CHECK (
        (question_type = 'single_choice' AND scoring_mode = 'binary') OR
        (question_type = 'weighted_choice' AND scoring_mode = 'partial_credit')
    ),
    CONSTRAINT ck_questions_bloom CHECK (
        bloom_level IN ('remember', 'understand', 'apply', 'analyze', 'evaluate')
    ),
    CONSTRAINT ck_questions_difficulty
        CHECK (difficulty_label IN ('easy', 'medium', 'hard')),
    CONSTRAINT ck_questions_difficulty_norm CHECK (difficulty_norm BETWEEN 0 AND 1),
    CONSTRAINT ck_questions_avg_time CHECK (avg_time_sec > 0),
    CONSTRAINT ck_questions_display_count CHECK (display_option_count BETWEEN 2 AND 10),
    CONSTRAINT ck_questions_irt_a CHECK (irt_a > 0),
    CONSTRAINT ck_questions_irt_b CHECK (irt_b BETWEEN -4 AND 4),
    CONSTRAINT ck_questions_irt_c CHECK (irt_c BETWEEN 0 AND 0.5),
    CONSTRAINT ck_questions_irt_status
        CHECK (irt_status IN ('draft', 'estimated', 'calibrated', 'retired')),
    CONSTRAINT ck_questions_irt_sample CHECK (irt_sample_size >= 0),
    CONSTRAINT ck_questions_status
        CHECK (status IN ('draft', 'reviewed', 'active', 'retired')),
    CONSTRAINT ck_questions_version CHECK (version_no > 0),
    CONSTRAINT ck_questions_provenance_object
        CHECK (jsonb_typeof(provenance) = 'object')
);

CREATE TABLE answer_options (
    answer_option_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    question_id             BIGINT       NOT NULL REFERENCES questions(question_id) ON DELETE CASCADE,
    option_code             VARCHAR(20)  NOT NULL,
    option_text             TEXT         NOT NULL,
    score_weight            NUMERIC(6,5) NOT NULL DEFAULT 0,
    is_best_answer          BOOLEAN      NOT NULL DEFAULT FALSE,
    distractor_type         VARCHAR(30)  NOT NULL DEFAULT 'clear_wrong',
    misconception_code      VARCHAR(100),
    diagnosis               TEXT,
    explanation             TEXT,
    is_active               BOOLEAN      NOT NULL DEFAULT TRUE,
    source                  VARCHAR(255),
    provenance              JSONB        NOT NULL DEFAULT '{}'::JSONB,
    created_at              TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_answer_options_code UNIQUE (question_id, option_code),
    CONSTRAINT ck_answer_options_weight CHECK (score_weight BETWEEN 0 AND 1),
    CONSTRAINT ck_answer_options_best_weight CHECK (
        (is_best_answer = TRUE  AND score_weight = 1) OR
        (is_best_answer = FALSE AND score_weight < 1)
    ),
    CONSTRAINT ck_answer_options_distractor CHECK (
        distractor_type IN ('best', 'near_correct', 'misconception', 'clear_wrong')
    ),
    CONSTRAINT ck_answer_options_best_type CHECK (
        (is_best_answer = TRUE  AND distractor_type = 'best') OR
        (is_best_answer = FALSE AND distractor_type <> 'best')
    ),
    CONSTRAINT ck_answer_options_provenance_object
        CHECK (jsonb_typeof(provenance) = 'object')
);

-- Một câu hỏi có thể thuộc một chủ đề và đo một hoặc nhiều kỹ năng.
CREATE TABLE question_knowledge_units (
    question_id         BIGINT       NOT NULL REFERENCES questions(question_id) ON DELETE CASCADE,
    unit_id             BIGINT       NOT NULL REFERENCES knowledge_units(unit_id),
    unit_role           VARCHAR(30)  NOT NULL,
    measurement_weight  NUMERIC(5,4) NOT NULL DEFAULT 1,
    PRIMARY KEY (question_id, unit_id),
    CONSTRAINT ck_question_units_role CHECK (
        unit_role IN ('topic', 'primary_skill', 'supporting_skill')
    ),
    CONSTRAINT ck_question_units_weight CHECK (measurement_weight BETWEEN 0 AND 1)
);

-- Mỗi câu có tối đa một chủ đề chính và một kỹ năng chính.
CREATE UNIQUE INDEX uq_question_one_topic
    ON question_knowledge_units(question_id)
    WHERE unit_role = 'topic';

CREATE UNIQUE INDEX uq_question_one_primary_skill
    ON question_knowledge_units(question_id)
    WHERE unit_role = 'primary_skill';

-- Mỗi câu chỉ có tối đa một đáp án tốt nhất đang hoạt động.
-- Điều kiện "phải có đúng một" được kiểm tra bởi view v_question_pool_validation
-- trước khi chuyển câu sang trạng thái active.
CREATE UNIQUE INDEX uq_answer_options_one_active_best
    ON answer_options(question_id)
    WHERE is_best_answer = TRUE AND is_active = TRUE;

-- ============================================================
-- B. TÀI KHOẢN, SINH VIÊN, NĂNG LỰC VÀ PHIÊN THI (5 bảng)
-- ============================================================

CREATE TABLE students (
    student_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_code        VARCHAR(80)  NOT NULL UNIQUE,
    display_name        VARCHAR(255) NOT NULL,
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE app_users (
    user_id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username            VARCHAR(80)  NOT NULL UNIQUE,
    password_hash       TEXT         NOT NULL,
    display_name        VARCHAR(255) NOT NULL,
    role                VARCHAR(20)  NOT NULL,
    student_id          BIGINT UNIQUE REFERENCES students(student_id) ON DELETE SET NULL,
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_app_users_role
        CHECK (role IN ('admin', 'supervisor', 'exam_taker')),
    CONSTRAINT ck_app_users_student_role CHECK (
        (role = 'exam_taker' AND student_id IS NOT NULL) OR
        (role IN ('admin', 'supervisor') AND student_id IS NULL)
    )
);

-- knowledge_unit_id NULL biểu diễn năng lực tổng quát theo môn;
-- khác NULL biểu diễn năng lực theo một chủ đề/kỹ năng.
CREATE TABLE student_abilities (
    ability_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id          BIGINT       NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    subject_id          BIGINT       NOT NULL REFERENCES subjects(subject_id),
    knowledge_unit_id   BIGINT,
    theta               NUMERIC(9,6) NOT NULL DEFAULT 0,
    standard_error      NUMERIC(9,6) NOT NULL DEFAULT 1,
    mastery_probability NUMERIC(8,5),
    evidence_count      INTEGER      NOT NULL DEFAULT 0,
    model_version       VARCHAR(50)  NOT NULL DEFAULT 'IRT-3PL-EAP-v1',
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_student_abilities_unit
        FOREIGN KEY (subject_id, knowledge_unit_id)
        REFERENCES knowledge_units(subject_id, unit_id),
    CONSTRAINT ck_student_abilities_theta CHECK (theta BETWEEN -6 AND 6),
    CONSTRAINT ck_student_abilities_se CHECK (standard_error > 0),
    CONSTRAINT ck_student_abilities_mastery
        CHECK (mastery_probability IS NULL OR mastery_probability BETWEEN 0 AND 1),
    CONSTRAINT ck_student_abilities_evidence CHECK (evidence_count >= 0)
);

-- NULLS NOT DISTINCT bảo đảm chỉ có một năng lực tổng quát (unit NULL)
-- cho mỗi cặp sinh viên/môn, đồng thời duy nhất cho từng unit cụ thể.
CREATE UNIQUE INDEX uq_student_abilities_scope
    ON student_abilities(student_id, subject_id, knowledge_unit_id) NULLS NOT DISTINCT;

-- Không cần exam_blueprints riêng trong MVP. Cấu hình sinh đề được snapshot
-- vào generation_config để tái hiện được đề cũ và thuận tiện nhận từ API/form.
CREATE TABLE exam_sessions (
    session_id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id              BIGINT       NOT NULL REFERENCES students(student_id),
    subject_id              BIGINT       NOT NULL REFERENCES subjects(subject_id),
    mode                    VARCHAR(20)  NOT NULL DEFAULT 'fixed',
    status                  VARCHAR(20)  NOT NULL DEFAULT 'in_progress',
    generation_config       JSONB        NOT NULL,
    random_seed             BIGINT,
    theta_initial           NUMERIC(9,6) NOT NULL DEFAULT 0,
    theta_current           NUMERIC(9,6) NOT NULL DEFAULT 0,
    standard_error_current  NUMERIC(9,6) NOT NULL DEFAULT 1,
    total_score             NUMERIC(10,5) NOT NULL DEFAULT 0,
    max_score               NUMERIC(10,5) NOT NULL DEFAULT 0,
    started_at              TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at             TIMESTAMPTZ,

    CONSTRAINT ck_exam_sessions_mode CHECK (mode IN ('fixed', 'adaptive')),
    CONSTRAINT ck_exam_sessions_status
        CHECK (status IN ('in_progress', 'completed', 'abandoned', 'expired')),
    CONSTRAINT ck_exam_sessions_config_object
        CHECK (jsonb_typeof(generation_config) = 'object'),
    CONSTRAINT ck_exam_sessions_theta
        CHECK (theta_initial BETWEEN -6 AND 6 AND theta_current BETWEEN -6 AND 6),
    CONSTRAINT ck_exam_sessions_se CHECK (standard_error_current > 0),
    CONSTRAINT ck_exam_sessions_score CHECK (
        total_score >= 0 AND max_score >= 0 AND total_score <= max_score
    ),
    CONSTRAINT ck_exam_sessions_time
        CHECK (finished_at IS NULL OR finished_at >= started_at)
);

-- Gộp exam_questions, exam_question_options và student_responses.
-- Mỗi item chỉ có tối đa một câu trả lời; displayed_options là snapshot JSONB
-- của đúng các phương án đã hiển thị, không phải pool đáp án gốc.
CREATE TABLE exam_items (
    exam_item_id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id              BIGINT       NOT NULL REFERENCES exam_sessions(session_id) ON DELETE CASCADE,
    question_id             BIGINT       NOT NULL REFERENCES questions(question_id),
    question_version        INTEGER      NOT NULL,
    order_no                SMALLINT     NOT NULL,
    stem_snapshot           TEXT         NOT NULL,
    displayed_options       JSONB        NOT NULL,
    selection_rule_code     VARCHAR(80),
    selection_reason        TEXT,
    item_information        NUMERIC(12,8),
    theta_before            NUMERIC(9,6) NOT NULL,
    presented_at            TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Các cột dưới đây NULL cho đến khi sinh viên trả lời.
    selected_option_code    VARCHAR(20),
    is_correct              BOOLEAN,
    awarded_score           NUMERIC(6,5),
    irt_response            SMALLINT,
    response_time_sec       INTEGER,
    theta_after             NUMERIC(9,6),
    standard_error_after    NUMERIC(9,6),
    scoring_detail          JSONB        NOT NULL DEFAULT '{}'::JSONB,
    answered_at             TIMESTAMPTZ,

    CONSTRAINT uq_exam_items_order UNIQUE (session_id, order_no),
    CONSTRAINT uq_exam_items_no_repeat UNIQUE (session_id, question_id),
    CONSTRAINT ck_exam_items_version CHECK (question_version > 0),
    CONSTRAINT ck_exam_items_order CHECK (order_no > 0),
    CONSTRAINT ck_exam_items_options_array CHECK (
        jsonb_typeof(displayed_options) = 'array' AND
        jsonb_array_length(displayed_options) >= 2
    ),
    CONSTRAINT ck_exam_items_theta_before CHECK (theta_before BETWEEN -6 AND 6),
    CONSTRAINT ck_exam_items_awarded_score
        CHECK (awarded_score IS NULL OR awarded_score BETWEEN 0 AND 1),
    CONSTRAINT ck_exam_items_irt_response
        CHECK (irt_response IS NULL OR irt_response IN (0, 1)),
    CONSTRAINT ck_exam_items_response_time
        CHECK (response_time_sec IS NULL OR response_time_sec >= 0),
    CONSTRAINT ck_exam_items_theta_after
        CHECK (theta_after IS NULL OR theta_after BETWEEN -6 AND 6),
    CONSTRAINT ck_exam_items_se_after
        CHECK (standard_error_after IS NULL OR standard_error_after > 0),
    CONSTRAINT ck_exam_items_scoring_object
        CHECK (jsonb_typeof(scoring_detail) = 'object'),
    CONSTRAINT ck_exam_items_answered_time
        CHECK (answered_at IS NULL OR answered_at >= presented_at),
    CONSTRAINT ck_exam_items_response_bundle CHECK (
        (
            selected_option_code IS NULL AND
            is_correct IS NULL AND
            awarded_score IS NULL AND
            irt_response IS NULL AND
            response_time_sec IS NULL AND
            theta_after IS NULL AND
            standard_error_after IS NULL AND
            answered_at IS NULL
        ) OR (
            selected_option_code IS NOT NULL AND
            is_correct IS NOT NULL AND
            awarded_score IS NOT NULL AND
            irt_response IS NOT NULL AND
            response_time_sec IS NOT NULL AND
            theta_after IS NOT NULL AND
            standard_error_after IS NOT NULL AND
            answered_at IS NOT NULL
        )
    )
);

COMMENT ON COLUMN exam_items.displayed_options IS
'JSON array snapshot: [{option_code, option_text, score_weight, is_best_answer, display_order}]';

COMMENT ON COLUMN exam_items.irt_response IS
'Phản hồi nhị phân cho IRT 3PL: 1 nếu chọn đáp án tốt nhất, ngược lại 0. awarded_score có thể vẫn là partial credit.';

-- ============================================================
-- C. RELA-MODEL K = (C, R, Rules) VÀ VẾT SUY LUẬN (4 bảng)
-- ============================================================

-- Gộp định nghĩa khái niệm C và quan hệ R vào một bảng có discriminator.
-- C: definition_type = concept, có concept_level C(0)..C(3).
-- R: definition_type = relation, có miền/đối miền và tính chất quan hệ.
CREATE TABLE kb_definitions (
    definition_id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    definition_code         VARCHAR(100) NOT NULL UNIQUE,
    definition_name         VARCHAR(255) NOT NULL,
    definition_type         VARCHAR(20)  NOT NULL,
    concept_level           SMALLINT,
    parent_definition_id    BIGINT REFERENCES kb_definitions(definition_id),
    source_definition_id    BIGINT REFERENCES kb_definitions(definition_id),
    target_definition_id    BIGINT REFERENCES kb_definitions(definition_id),
    is_symmetric            BOOLEAN NOT NULL DEFAULT FALSE,
    is_transitive           BOOLEAN NOT NULL DEFAULT FALSE,
    is_reflexive            BOOLEAN NOT NULL DEFAULT FALSE,
    is_antisymmetric        BOOLEAN NOT NULL DEFAULT FALSE,
    attributes_schema       JSONB   NOT NULL DEFAULT '{}'::JSONB,
    description             TEXT,
    source                  VARCHAR(255),
    provenance              JSONB   NOT NULL DEFAULT '{}'::JSONB,
    is_active               BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT ck_kb_definitions_type
        CHECK (definition_type IN ('concept', 'relation')),
    CONSTRAINT ck_kb_definitions_level CHECK (
        (definition_type = 'concept' AND concept_level BETWEEN 0 AND 3) OR
        (definition_type = 'relation' AND concept_level IS NULL)
    ),
    CONSTRAINT ck_kb_definitions_not_self_parent
        CHECK (parent_definition_id IS NULL OR parent_definition_id <> definition_id),
    CONSTRAINT ck_kb_definitions_schema_object
        CHECK (jsonb_typeof(attributes_schema) = 'object'),
    CONSTRAINT ck_kb_definitions_provenance_object
        CHECK (jsonb_typeof(provenance) = 'object')
);

CREATE TABLE kb_rules (
    rule_code               VARCHAR(80) PRIMARY KEY,
    rule_name               VARCHAR(255) NOT NULL,
    rule_type               VARCHAR(30)  NOT NULL,
    hypothesis              JSONB        NOT NULL,
    goal                    JSONB        NOT NULL,
    priority                INTEGER      NOT NULL DEFAULT 100,
    weight                  NUMERIC(10,5) NOT NULL DEFAULT 1,
    explanation_template    TEXT         NOT NULL,
    source                  VARCHAR(255),
    provenance              JSONB        NOT NULL DEFAULT '{}'::JSONB,
    version_no              INTEGER      NOT NULL DEFAULT 1,
    is_active               BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at              TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT ck_kb_rules_type CHECK (
        rule_type IN (
            'generation', 'classification', 'scoring',
            'ability_update', 'recommendation', 'general'
        )
    ),
    CONSTRAINT ck_kb_rules_hypothesis_array CHECK (jsonb_typeof(hypothesis) = 'array'),
    CONSTRAINT ck_kb_rules_goal_array CHECK (jsonb_typeof(goal) = 'array'),
    CONSTRAINT ck_kb_rules_weight CHECK (weight >= 0),
    CONSTRAINT ck_kb_rules_version CHECK (version_no > 0),
    CONSTRAINT ck_kb_rules_provenance_object
        CHECK (jsonb_typeof(provenance) = 'object')
);

-- Một dòng là toàn bộ một lần suy diễn. Danh sách steps phù hợp để API trả
-- vết suy luận theo thứ tự và đủ nhẹ cho demo; không cần inference_runs riêng.
CREATE TABLE inference_traces (
    inference_trace_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id              BIGINT REFERENCES exam_sessions(session_id) ON DELETE SET NULL,
    strategy                VARCHAR(20) NOT NULL,
    goal                    JSONB,
    initial_facts           JSONB       NOT NULL DEFAULT '[]'::JSONB,
    derived_facts           JSONB       NOT NULL DEFAULT '[]'::JSONB,
    steps                   JSONB       NOT NULL DEFAULT '[]'::JSONB,
    status                  VARCHAR(20) NOT NULL DEFAULT 'running',
    started_at              TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at             TIMESTAMPTZ,

    CONSTRAINT ck_inference_traces_strategy
        CHECK (strategy IN ('forward', 'backward', 'hybrid')),
    CONSTRAINT ck_inference_traces_status
        CHECK (status IN ('running', 'completed', 'failed', 'no_solution')),
    CONSTRAINT ck_inference_traces_goal_type
        CHECK (goal IS NULL OR jsonb_typeof(goal) = 'object'),
    CONSTRAINT ck_inference_traces_initial_array
        CHECK (jsonb_typeof(initial_facts) = 'array'),
    CONSTRAINT ck_inference_traces_derived_array
        CHECK (jsonb_typeof(derived_facts) = 'array'),
    CONSTRAINT ck_inference_traces_steps_array
        CHECK (jsonb_typeof(steps) = 'array'),
    CONSTRAINT ck_inference_traces_time
        CHECK (finished_at IS NULL OR finished_at >= started_at)
);

COMMENT ON COLUMN inference_traces.steps IS
'JSON array: [{step_no, rule_code, input_fact_ids, output_fact_ids, explanation}]';

-- Năm loại sự kiện theo Rela-model:
-- 1) type; 2) determined_object; 3) constant_assignment;
-- 4) equality; 5) binary_relation.
CREATE TABLE kb_facts (
    fact_id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fact_type               VARCHAR(30)  NOT NULL,
    subject_ref             VARCHAR(255) NOT NULL,
    predicate_code          VARCHAR(100) NOT NULL REFERENCES kb_definitions(definition_code),
    object_ref              TEXT,
    object_value            JSONB,
    fact_args               JSONB        NOT NULL DEFAULT '[]'::JSONB,
    confidence              NUMERIC(6,5) NOT NULL DEFAULT 1,
    is_inferred             BOOLEAN      NOT NULL DEFAULT FALSE,
    derived_by_rule_code    VARCHAR(80)  REFERENCES kb_rules(rule_code),
    inference_trace_id      BIGINT       REFERENCES inference_traces(inference_trace_id),
    source                  VARCHAR(255) NOT NULL,
    created_by              VARCHAR(100),
    provenance              JSONB        NOT NULL DEFAULT '{}'::JSONB,
    created_at              TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT ck_kb_facts_type CHECK (
        fact_type IN (
            'type', 'determined_object', 'constant_assignment',
            'equality', 'binary_relation'
        )
    ),
    CONSTRAINT ck_kb_facts_object
        CHECK (
            object_ref IS NOT NULL OR object_value IS NOT NULL OR
            jsonb_array_length(fact_args) > 0
        ),
    CONSTRAINT ck_kb_facts_args_array CHECK (jsonb_typeof(fact_args) = 'array'),
    CONSTRAINT ck_kb_facts_confidence CHECK (confidence BETWEEN 0 AND 1),
    CONSTRAINT ck_kb_facts_inference_provenance CHECK (
        (is_inferred = FALSE AND derived_by_rule_code IS NULL) OR
        (is_inferred = TRUE  AND derived_by_rule_code IS NOT NULL AND inference_trace_id IS NOT NULL)
    ),
    CONSTRAINT ck_kb_facts_provenance_object
        CHECK (jsonb_typeof(provenance) = 'object')
);

CREATE UNIQUE INDEX uq_kb_facts_arguments
    ON kb_facts (fact_type, predicate_code, (fact_args::TEXT));

-- ============================================================
-- D. CẤU HÌNH HỆ THỐNG (1 bảng)
-- ============================================================

-- prop_value dùng JSONB để Python nhận đúng kiểu int/float/bool/object,
-- không cần value_type và không phải parse chuỗi TEXT thủ công.
CREATE TABLE sys_props (
    prop_key            VARCHAR(100) PRIMARY KEY,
    prop_value          JSONB        NOT NULL,
    description         TEXT         NOT NULL,
    is_editable         BOOLEAN      NOT NULL DEFAULT TRUE,
    updated_by          VARCHAR(100),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE llm_artifacts (
    artifact_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    artifact_type       VARCHAR(40)  NOT NULL,
    session_id          BIGINT REFERENCES exam_sessions(session_id) ON DELETE SET NULL,
    question_id         BIGINT REFERENCES questions(question_id) ON DELETE SET NULL,
    audience            VARCHAR(20)  NOT NULL,
    provider            VARCHAR(100) NOT NULL,
    model               VARCHAR(200) NOT NULL,
    request_payload     JSONB        NOT NULL DEFAULT '{}'::JSONB,
    response_payload    JSONB        NOT NULL DEFAULT '{}'::JSONB,
    usage               JSONB        NOT NULL DEFAULT '{}'::JSONB,
    status              VARCHAR(20)  NOT NULL DEFAULT 'pending',
    error_message       TEXT,
    created_by          VARCHAR(100),
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_llm_artifacts_type CHECK (
        artifact_type IN ('question_generation', 'exam_explanation')
    ),
    CONSTRAINT ck_llm_artifacts_audience CHECK (
        audience IN ('reviewer', 'staff', 'taker')
    ),
    CONSTRAINT ck_llm_artifacts_status CHECK (
        status IN ('pending', 'success', 'failed')
    ),
    CONSTRAINT ck_llm_artifacts_request_object
        CHECK (jsonb_typeof(request_payload) = 'object'),
    CONSTRAINT ck_llm_artifacts_response_object
        CHECK (jsonb_typeof(response_payload) = 'object'),
    CONSTRAINT ck_llm_artifacts_usage_object
        CHECK (jsonb_typeof(usage) = 'object')
);

-- ============================================================
-- E. INDEX, VIEW KIỂM TRA VÀ updated_at
-- ============================================================

CREATE INDEX ix_knowledge_units_subject
    ON knowledge_units(subject_id, unit_type, is_active);

CREATE INDEX ix_questions_selection
    ON questions(subject_id, bloom_level, difficulty_label, status);

CREATE INDEX ix_answer_options_pool
    ON answer_options(question_id, is_active, distractor_type);

CREATE INDEX ix_question_units_unit
    ON question_knowledge_units(unit_id, question_id);

CREATE INDEX ix_student_abilities_student
    ON student_abilities(student_id, subject_id);

CREATE INDEX ix_app_users_role
    ON app_users(role, is_active);

CREATE INDEX ix_exam_sessions_student
    ON exam_sessions(student_id, started_at DESC);

CREATE UNIQUE INDEX uq_exam_sessions_active_cat
    ON exam_sessions(student_id, subject_id)
    WHERE mode = 'adaptive' AND status = 'in_progress';

CREATE INDEX ix_exam_items_session
    ON exam_items(session_id, order_no);

CREATE INDEX ix_kb_facts_spo
    ON kb_facts(subject_ref, predicate_code);

CREATE INDEX ix_inference_traces_session
    ON inference_traces(session_id, started_at DESC);

CREATE INDEX ix_llm_artifacts_lookup
    ON llm_artifacts(artifact_type, session_id, audience, created_at DESC);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_subjects_updated_at
BEFORE UPDATE ON subjects
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_knowledge_units_updated_at
BEFORE UPDATE ON knowledge_units
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_questions_updated_at
BEFORE UPDATE ON questions
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_answer_options_updated_at
BEFORE UPDATE ON answer_options
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_students_updated_at
BEFORE UPDATE ON students
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_app_users_updated_at
BEFORE UPDATE ON app_users
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_kb_rules_updated_at
BEFORE UPDATE ON kb_rules
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_sys_props_updated_at
BEFORE UPDATE ON sys_props
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_llm_artifacts_updated_at
BEFORE UPDATE ON llm_artifacts
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- View dùng trước khi activate câu hỏi. Pool kỳ vọng lấy từ SYS_PROPS,
-- không hard-code lặp ở questions.
CREATE VIEW v_question_pool_validation AS
WITH pool_stats AS (
    SELECT
        q.question_id,
        q.question_code,
        q.bloom_level,
        q.display_option_count,
        COUNT(ao.answer_option_id) FILTER (WHERE ao.is_active) AS actual_pool_size,
        COUNT(ao.answer_option_id) FILTER (
            WHERE ao.is_active AND ao.is_best_answer
        ) AS active_best_count
    FROM questions q
    LEFT JOIN answer_options ao ON ao.question_id = q.question_id
    GROUP BY q.question_id, q.question_code, q.bloom_level, q.display_option_count
), configured AS (
    SELECT
        ps.*,
        (sp.prop_value ->> ps.bloom_level)::INTEGER AS expected_pool_size
    FROM pool_stats ps
    LEFT JOIN sys_props sp ON sp.prop_key = 'ANSWER_POOL_SIZE_BY_BLOOM'
)
SELECT
    question_id,
    question_code,
    bloom_level,
    expected_pool_size,
    actual_pool_size,
    display_option_count,
    active_best_count,
    (
        expected_pool_size IS NOT NULL AND
        actual_pool_size = expected_pool_size AND
        display_option_count <= actual_pool_size AND
        active_best_count = 1
    ) AS is_pool_valid
FROM configured;

-- ============================================================
-- F. CẤU HÌNH VÀ TRI THỨC KHỞI TẠO
-- ============================================================

INSERT INTO students (student_code, display_name)
VALUES
    ('TAKER001', 'Sinh viên 1'),
    ('TAKER002', 'Sinh viên 2')
ON CONFLICT (student_code) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    is_active = TRUE;

INSERT INTO app_users (
    username, password_hash, display_name, role, student_id
)
VALUES
    (
        'admin',
        'pbkdf2_sha256$310000$cs2307-admin-salt$5M62y8rWbox9ncP1o-HMpwSoZNEe2D4mP860PO2fPqQ',
        'Quản trị hệ thống',
        'admin',
        NULL
    ),
    (
        'supervisor',
        'pbkdf2_sha256$310000$cs2307-supervisor-salt$dsoRs-hWeUPMqDZr-6TON5K7U4vIAiKr8HHkQvMbtDE',
        'Giám sát kỳ thi',
        'supervisor',
        NULL
    ),
    (
        'taker1',
        'pbkdf2_sha256$310000$cs2307-taker1-salt$atTjJfMRy_3sdgMQW_sVdMFJmUwQJz2G9M4zlIa5HhM',
        'Sinh viên 1',
        'exam_taker',
        (SELECT student_id FROM students WHERE student_code = 'TAKER001')
    ),
    (
        'taker2',
        'pbkdf2_sha256$310000$cs2307-taker2-salt$9eCNSFS1QeVYJq6vKgnRvdxQ-YeiaIKQmGG2Mde0nCg',
        'Sinh viên 2',
        'exam_taker',
        (SELECT student_id FROM students WHERE student_code = 'TAKER002')
    );

INSERT INTO sys_props (prop_key, prop_value, description, is_editable)
VALUES
    ('QUESTION_BANK_TARGET_SIZE', '200'::JSONB,
     'Tổng số câu hỏi mục tiêu của đồ án.', TRUE),
    ('DEFAULT_EXAM_QUESTION_COUNT', '20'::JSONB,
     'Số câu hỏi mặc định của một đề thi.', TRUE),
    ('DISPLAY_OPTION_COUNT', '4'::JSONB,
     'Số phương án được chọn từ pool và hiển thị.', TRUE),
    ('ANSWER_POOL_SIZE_BY_BLOOM',
     '{"remember":4,"understand":5,"apply":6,"analyze":8,"evaluate":10}'::JSONB,
     'Kích thước pool đáp án theo 5 mức Bloom.', TRUE),
    ('MUST_INCLUDE_BEST_ANSWER', 'true'::JSONB,
     'Tập phương án hiển thị phải chứa đáp án tốt nhất.', TRUE),
    ('RANDOMIZE_OPTION_ORDER', 'true'::JSONB,
     'Đảo thứ tự phương án khi hiển thị.', TRUE),
    ('IRT_MODEL', '"3PL"'::JSONB,
     'Mô hình IRT dùng để ước lượng năng lực.', FALSE),
    ('PARTIAL_CREDIT_AFFECTS_IRT', 'false'::JSONB,
     'IRT 3PL dùng irt_response nhị phân; partial credit chỉ dùng cho điểm và chẩn đoán.', FALSE),
    ('CAT_INITIAL_THETA', '0.0'::JSONB,
     'Năng lực ban đầu khi sinh viên chưa có lịch sử.', TRUE),
    ('CAT_MIN_QUESTION_COUNT', '10'::JSONB,
     'Số câu tối thiểu trước khi CAT được phép dừng.', TRUE),
    ('CAT_MAX_QUESTION_COUNT', '30'::JSONB,
     'Số câu tối đa của một phiên CAT.', TRUE),
    ('CAT_STOP_STANDARD_ERROR', '0.30'::JSONB,
     'Ngưỡng sai số chuẩn để dừng CAT.', TRUE),
    ('CAT_STABILITY_EPSILON', '0.05'::JSONB,
     'Biên độ theta ổn định để dừng CAT.', TRUE),
    ('CAT_STABILITY_WINDOW', '3'::JSONB,
     'Số lần cập nhật theta ổn định liên tiếp.', TRUE),
    ('CAT_INFORMATION_WEIGHT', '1.0'::JSONB,
     'Trọng số Fisher information khi chọn câu CAT.', TRUE),
    ('CAT_WEAK_UNIT_WEIGHT', '0.35'::JSONB,
     'Trọng số ưu tiên đơn vị tri thức yếu.', TRUE),
    ('CAT_CONTENT_BALANCE_WEIGHT', '0.20'::JSONB,
     'Trọng số cân bằng nội dung CAT.', TRUE),
    ('CAT_EXPOSURE_PENALTY', '0.15'::JSONB,
     'Mức phạt câu hỏi có độ phơi nhiễm cao.', TRUE),
    ('CAT_DIFFICULTY_DISTRIBUTION',
     '{"easy":0.3,"medium":0.4,"hard":0.3}'::JSONB,
     'Phân bố độ khó mặc định của CAT.', TRUE),
    ('CAT_TOPIC_CODES', '[]'::JSONB,
     'Giới hạn chủ đề CAT; rỗng nghĩa là mọi chủ đề.', TRUE),
    ('CAT_SKILL_CODES', '[]'::JSONB,
     'Giới hạn kỹ năng CAT; rỗng nghĩa là mọi kỹ năng.', TRUE),
    ('CAT_BLOOM_LEVELS', '[]'::JSONB,
     'Giới hạn Bloom CAT; rỗng nghĩa là mọi mức.', TRUE),
    ('LEARNING_REMEDIATE_THRESHOLD', '0.5'::JSONB,
     'Ngưỡng đề xuất ôn nền.', TRUE),
    ('LEARNING_ADVANCE_THRESHOLD', '0.75'::JSONB,
     'Ngưỡng đề xuất bài nâng cao.', TRUE),
    ('FIXED_EXAM_DIFFICULTY_DISTRIBUTION',
     '{"easy":0.3,"medium":0.4,"hard":0.3}'::JSONB,
     'Tỷ lệ độ khó mặc định cho đề thi cố định.', TRUE),
    ('EXAM_ALLOWED_QUESTION_STATUSES',
     '["active"]'::JSONB,
     'Chỉ câu hỏi active được phép dùng trong đề thi.', TRUE),
    ('EXAM_GENERATION_STRATEGY', '"irt_information_balanced"'::JSONB,
     'Chiến lược sinh đề cố định có cân bằng nội dung và Fisher information.', TRUE),
    ('IRT_SCALE_CONSTANT', '1.7'::JSONB,
     'Hằng số D trong mô hình IRT 3PL.', FALSE),
    ('LLM_ENABLED', 'true'::JSONB,
     'Cho phép các thao tác LLM theo yêu cầu rõ ràng của người dùng.', TRUE),
    ('LLM_MODEL', '"qwen3.5-4b"'::JSONB,
     'Tên model OpenAI-compatible; khóa API chỉ nằm trong biến môi trường.', TRUE),
    ('LLM_QUESTION_MAX_TOKENS', '1600'::JSONB,
     'Ngân sách token đầu ra tối đa cho một bản nháp câu hỏi.', TRUE),
    ('LLM_EXPLANATION_MAX_TOKENS', '350'::JSONB,
     'Ngân sách token đầu ra tối đa cho một diễn giải phiên thi.', TRUE),
    ('LLM_MAX_SOURCE_CHARS', '6000'::JSONB,
     'Số ký tự nguồn tối đa gửi trong một yêu cầu LLM.', TRUE),
    ('LLM_TEMPERATURE', '0.2'::JSONB,
     'Độ ngẫu nhiên cho tác vụ sinh bản nháp.', TRUE);

-- Khái niệm C(0)-C(3) dùng cho đồ án.
INSERT INTO kb_definitions (
    definition_code, definition_name, definition_type, concept_level,
    attributes_schema, description, source
)
VALUES
    ('NUMBER', 'Số', 'concept', 0, '{}'::JSONB,
     'Khái niệm cơ sở dùng cho theta, a, b, c, trọng số và thời gian.', 'course_theory'),
    ('TEXT', 'Chuỗi ký tự', 'concept', 0, '{}'::JSONB,
     'Khái niệm cơ sở dùng cho mã và nội dung.', 'course_theory'),
    ('BOOLEAN', 'Luận lý', 'concept', 0, '{}'::JSONB,
     'Khái niệm cơ sở đúng/sai.', 'course_theory'),
    ('SUBJECT', 'Môn học', 'concept', 1,
     '{"attrs":["subject_code","subject_name"]}'::JSONB,
     'Lớp đối tượng đơn giản biểu diễn môn học.', 'project_model'),
    ('KNOWLEDGE_UNIT', 'Đơn vị tri thức', 'concept', 1,
     '{"attrs":["unit_code","unit_name","unit_type"]}'::JSONB,
     'Chủ đề hoặc kỹ năng thuộc một môn.', 'project_model'),
    ('BLOOM_LEVEL', 'Mức Bloom', 'concept', 1,
     '{"values":["remember","understand","apply","analyze","evaluate"]}'::JSONB,
     'Năm mức nhận thức được dùng trong đồ án.', 'project_model'),
    ('STUDENT', 'Sinh viên', 'concept', 1,
     '{"attrs":["student_code","display_name"]}'::JSONB,
     'Người thực hiện bài thi.', 'project_model'),
    ('QUESTION', 'Câu hỏi', 'concept', 2,
     '{"attrs":["stem","bloom_level","irt_a","irt_b","irt_c"]}'::JSONB,
     'Đối tượng nâng cao chứa thuộc tính và liên kết đến đơn vị tri thức.', 'project_model'),
    ('ANSWER_OPTION', 'Phương án trả lời', 'concept', 2,
     '{"attrs":["option_text","score_weight","is_best_answer"]}'::JSONB,
     'Phương án thuộc pool đáp án của câu hỏi.', 'project_model'),
    ('ABILITY_STATE', 'Trạng thái năng lực', 'concept', 2,
     '{"attrs":["theta","standard_error","evidence_count"]}'::JSONB,
     'Năng lực sinh viên do IRT 3PL ước lượng.', 'project_model'),
    ('EXAM_SESSION', 'Phiên thi', 'concept', 3,
     '{"attrs":["mode","generation_config","theta_current","status"]}'::JSONB,
     'Đối tượng cao cấp kết hợp sinh viên, câu hỏi, phản hồi và năng lực.', 'project_model');

-- Quan hệ R của miền tri thức.
INSERT INTO kb_definitions (
    definition_code, definition_name, definition_type,
    source_definition_id, target_definition_id,
    is_symmetric, is_transitive, is_reflexive, is_antisymmetric,
    description, source
)
VALUES
    ('is_a', 'thuộc kiểu', 'relation', NULL, NULL,
     FALSE, FALSE, FALSE, FALSE,
     'Quan hệ dùng cho sự kiện loại 1: x:c.', 'course_theory'),
    ('belongs_to', 'thuộc về', 'relation',
     (SELECT definition_id FROM kb_definitions WHERE definition_code = 'KNOWLEDGE_UNIT'),
     (SELECT definition_id FROM kb_definitions WHERE definition_code = 'SUBJECT'),
     FALSE, FALSE, FALSE, TRUE,
     'Đơn vị tri thức thuộc một môn học.', 'project_model'),
    ('measures', 'đo lường', 'relation',
     (SELECT definition_id FROM kb_definitions WHERE definition_code = 'QUESTION'),
     (SELECT definition_id FROM kb_definitions WHERE definition_code = 'KNOWLEDGE_UNIT'),
     FALSE, FALSE, FALSE, FALSE,
     'Câu hỏi đo một chủ đề hoặc kỹ năng.', 'project_model'),
    ('prerequisite_of', 'là tiên quyết của', 'relation',
     (SELECT definition_id FROM kb_definitions WHERE definition_code = 'KNOWLEDGE_UNIT'),
     (SELECT definition_id FROM kb_definitions WHERE definition_code = 'KNOWLEDGE_UNIT'),
     FALSE, TRUE, FALSE, TRUE,
     'Quan hệ tiên quyết giữa các đơn vị tri thức.', 'project_model'),
    ('has_bloom_level', 'có mức Bloom', 'relation',
     (SELECT definition_id FROM kb_definitions WHERE definition_code = 'QUESTION'),
     (SELECT definition_id FROM kb_definitions WHERE definition_code = 'BLOOM_LEVEL'),
     FALSE, FALSE, FALSE, FALSE,
     'Phân loại mức nhận thức của câu hỏi.', 'project_model'),
    ('selected_option', 'chọn phương án', 'relation',
     (SELECT definition_id FROM kb_definitions WHERE definition_code = 'STUDENT'),
     (SELECT definition_id FROM kb_definitions WHERE definition_code = 'ANSWER_OPTION'),
     FALSE, FALSE, FALSE, FALSE,
     'Sự kiện sinh viên chọn một phương án.', 'project_model');

INSERT INTO kb_definitions (
    definition_code, definition_name, definition_type,
    is_symmetric, is_transitive, description, source
)
VALUES
    ('unit_accuracy', 'độ chính xác đơn vị tri thức', 'relation', FALSE, FALSE, 'Bằng chứng chính xác theo sinh viên và đơn vị.', 'project_model'),
    ('recommended_next', 'khuyến nghị tiếp theo', 'relation', FALSE, FALSE, 'Hành động học tập được suy ra.', 'project_model'),
    ('weak_unit', 'đơn vị tri thức yếu', 'relation', FALSE, FALSE, 'Đơn vị cần ưu tiên đánh giá hoặc ôn tập.', 'project_model'),
    ('has_mastery', 'có mức làm chủ', 'relation', FALSE, FALSE, 'Trạng thái làm chủ theo đơn vị tri thức.', 'project_model'),
    ('question_ready', 'câu hỏi sẵn sàng', 'relation', FALSE, FALSE, 'Câu hỏi vượt qua kiểm tra xác định.', 'project_model'),
    ('best_option', 'phương án tốt nhất', 'relation', FALSE, FALSE, 'Đáp án tốt nhất của câu hỏi.', 'project_model'),
    ('displayed_options_include', 'phương án hiển thị chứa', 'relation', FALSE, FALSE, 'Ràng buộc hiển thị đáp án.', 'project_model'),
    ('option_weight', 'trọng số phương án', 'relation', FALSE, FALSE, 'Trọng số chấm điểm của phương án.', 'project_model'),
    ('awarded_score', 'điểm được trao', 'relation', FALSE, FALSE, 'Điểm suy ra từ phương án.', 'project_model'),
    ('has_binary_response', 'có phản hồi nhị phân', 'relation', FALSE, FALSE, 'Phản hồi dùng cho IRT.', 'project_model'),
    ('has_irt_parameters', 'có tham số IRT', 'relation', FALSE, FALSE, 'Bộ tham số a b c.', 'project_model'),
    ('updated_theta', 'theta đã cập nhật', 'relation', FALSE, FALSE, 'Năng lực mới sau phản hồi.', 'project_model'),
    ('computed_theta', 'theta do IRT tính', 'relation', FALSE, FALSE, 'Giá trị theta do module IRT cung cấp cho bộ suy diễn.', 'project_model'),
    ('valid_question_pool', 'ngân hàng hợp lệ', 'relation', FALSE, FALSE, 'Ngân hàng đủ điều kiện chọn.', 'project_model'),
    ('student_theta', 'theta sinh viên', 'relation', FALSE, FALSE, 'Theta đầu vào của lựa chọn.', 'project_model'),
    ('difficulty_blueprint', 'blueprint độ khó', 'relation', FALSE, FALSE, 'Phân bố độ khó yêu cầu.', 'project_model'),
    ('exam_generated_with_constraints', 'đề thỏa ràng buộc', 'relation', FALSE, FALSE, 'Mục tiêu sinh đề cố định.', 'project_model'),
    ('subject_has_no_evidence', 'môn chưa có bằng chứng', 'relation', FALSE, FALSE, 'Môn chưa có lịch sử trả lời.', 'project_model');

-- Các luật mẫu tối thiểu để cơ sở tri thức không chỉ là cấu trúc rỗng.
INSERT INTO kb_rules (
    rule_code, rule_name, rule_type, hypothesis, goal,
    priority, weight, explanation_template, source
)
VALUES
    (
        'R_GEN_INCLUDE_BEST',
        'Sinh tập phương án hợp lệ',
        'generation',
        '[{"predicate":"question_ready","args":["?q"]},{"predicate":"best_option","args":["?q","?best"]}]'::JSONB,
        '[{"predicate":"displayed_options_include","args":["?q","?best"]}]'::JSONB,
        10, 1,
        'Tập phương án của câu {q} phải chứa đáp án tốt nhất {best}.',
        'project_rule'
    ),
    (
        'R_SCORE_SELECTED_OPTION',
        'Chấm phương án đã chọn',
        'scoring',
        '[{"predicate":"selected_option","args":["?student","?q","?option"]},{"predicate":"option_weight","args":["?option","?w"]}]'::JSONB,
        '[{"predicate":"awarded_score","args":["?student","?q","?w"]}]'::JSONB,
        20, 1,
        'Sinh viên {student} nhận điểm {w} cho câu {q}.',
        'project_rule'
    ),
    (
        'R_UPDATE_ABILITY_3PL',
        'Cập nhật năng lực bằng IRT 3PL',
        'ability_update',
        '[{"predicate":"has_binary_response","args":["?student","?q","?u"]},{"predicate":"has_irt_parameters","args":["?q","?a","?b","?c"]},{"predicate":"computed_theta","args":["?student","?theta_new"]}]'::JSONB,
        '[{"predicate":"updated_theta","args":["?student","?theta_new"]}]'::JSONB,
        30, 1,
        'Cập nhật theta của {student} từ phản hồi nhị phân {u} bằng IRT 3PL.',
        'project_rule'
    ),
    (
        'R_GEN_IRT_BALANCED',
        'Sinh đề cân bằng bằng IRT',
        'generation',
        '[{"predicate":"valid_question_pool","args":["?subject"]},{"predicate":"student_theta","args":["?student","?theta"]},{"predicate":"difficulty_blueprint","args":["?distribution"]}]'::JSONB,
        '[{"predicate":"exam_generated_with_constraints","args":["?student","?subject"]}]'::JSONB,
        15, 1,
        'Chọn câu theo tỷ lệ độ khó, cân bằng chủ đề và Fisher information tại theta hiện tại.',
        'project_rule'
    ),
    (
        'R_LEARNING_START_SUBJECT',
        'Bắt đầu đánh giá môn học',
        'recommendation',
        '[{"predicate":"subject_has_no_evidence","args":["?student","?subject"]}]'::JSONB,
        '[{"predicate":"recommended_next","args":["?student","?subject","initial_assessment"]}]'::JSONB,
        10, 1,
        'Sinh viên chưa có bằng chứng ở môn {subject}, cần hoàn thành bài đánh giá đầu tiên.',
        'project_rule'
    ),
    (
        'R_LEARNING_REMEDIATE',
        'Ôn lại đơn vị tri thức yếu',
        'recommendation',
        '[{"predicate":"unit_accuracy","args":["?student","?unit","?accuracy"]},{"operator":"lt","left":"?accuracy","right":0.5}]'::JSONB,
        '[{"predicate":"weak_unit","args":["?student","?unit"]},{"predicate":"recommended_next","args":["?student","?unit","remediate"]}]'::JSONB,
        20, 1,
        'Độ chính xác ở {unit} dưới 50%, ưu tiên ôn kiến thức nền.',
        'project_rule'
    ),
    (
        'R_LEARNING_REINFORCE',
        'Củng cố đơn vị tri thức',
        'recommendation',
        '[{"predicate":"unit_accuracy","args":["?student","?unit","?accuracy"]},{"operator":"gte","left":"?accuracy","right":0.5},{"operator":"lt","left":"?accuracy","right":0.75}]'::JSONB,
        '[{"predicate":"recommended_next","args":["?student","?unit","reinforce"]}]'::JSONB,
        30, 1,
        'Độ chính xác ở {unit} từ 50% đến dưới 75%, cần luyện tập củng cố.',
        'project_rule'
    ),
    (
        'R_LEARNING_ADVANCE',
        'Nâng cao đơn vị tri thức đã nắm',
        'recommendation',
        '[{"predicate":"unit_accuracy","args":["?student","?unit","?accuracy"]},{"operator":"gte","left":"?accuracy","right":0.75}]'::JSONB,
        '[{"predicate":"has_mastery","args":["?student","?unit",true]},{"predicate":"recommended_next","args":["?student","?unit","advance"]}]'::JSONB,
        40, 1,
        'Độ chính xác ở {unit} đạt ít nhất 75%, có thể chuyển sang vận dụng cao hơn.',
        'project_rule'
    );

COMMIT;

-- Kiểm tra số bảng sau khi chạy DDL (kỳ vọng: 15):
-- SELECT COUNT(*)
-- FROM information_schema.tables
-- WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
--   AND table_name IN (
--     'subjects', 'knowledge_units', 'questions', 'answer_options',
--     'question_knowledge_units', 'students', 'student_abilities',
--     'exam_sessions', 'exam_items', 'kb_definitions', 'kb_rules',
--     'inference_traces', 'kb_facts', 'sys_props', 'llm_artifacts'
--   );
