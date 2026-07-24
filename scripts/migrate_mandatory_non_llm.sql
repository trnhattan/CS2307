BEGIN;

CREATE TABLE IF NOT EXISTS llm_artifacts (
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
    CONSTRAINT ck_llm_artifacts_type CHECK (artifact_type IN ('question_generation', 'exam_explanation')),
    CONSTRAINT ck_llm_artifacts_audience CHECK (audience IN ('reviewer', 'staff', 'taker')),
    CONSTRAINT ck_llm_artifacts_status CHECK (status IN ('pending', 'success', 'failed')),
    CONSTRAINT ck_llm_artifacts_request_object CHECK (jsonb_typeof(request_payload) = 'object'),
    CONSTRAINT ck_llm_artifacts_response_object CHECK (jsonb_typeof(response_payload) = 'object'),
    CONSTRAINT ck_llm_artifacts_usage_object CHECK (jsonb_typeof(usage) = 'object')
);

CREATE INDEX IF NOT EXISTS ix_llm_artifacts_lookup
    ON llm_artifacts(artifact_type, session_id, audience, created_at DESC);

DROP TRIGGER IF EXISTS trg_llm_artifacts_updated_at ON llm_artifacts;
CREATE TRIGGER trg_llm_artifacts_updated_at
BEFORE UPDATE ON llm_artifacts
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE UNIQUE INDEX IF NOT EXISTS uq_exam_sessions_active_cat
    ON exam_sessions(student_id, subject_id)
    WHERE mode = 'adaptive' AND status = 'in_progress';

ALTER TABLE questions
    ADD COLUMN IF NOT EXISTS difficulty_norm NUMERIC(6,5);

UPDATE questions
SET difficulty_norm = COALESCE(
    CASE
        WHEN jsonb_typeof(provenance #> '{ingest,difficulty_norm}') = 'number'
            THEN (provenance #>> '{ingest,difficulty_norm}')::NUMERIC
        ELSE NULL
    END,
    CASE difficulty_label WHEN 'easy' THEN 0.25 WHEN 'medium' THEN 0.55 ELSE 0.85 END
)
WHERE difficulty_norm IS NULL;

ALTER TABLE questions
    ALTER COLUMN difficulty_norm SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_questions_difficulty_norm'
    ) THEN
        ALTER TABLE questions ADD CONSTRAINT ck_questions_difficulty_norm
            CHECK (difficulty_norm BETWEEN 0 AND 1);
    END IF;
END $$;

ALTER TABLE kb_facts
    ADD COLUMN IF NOT EXISTS fact_args JSONB NOT NULL DEFAULT '[]'::JSONB;

UPDATE kb_facts
SET fact_args = CASE
    WHEN fact_type = 'determined_object' THEN jsonb_build_array(subject_ref)
    WHEN object_ref IS NOT NULL THEN jsonb_build_array(subject_ref, object_ref)
    WHEN object_value IS NOT NULL THEN jsonb_build_array(subject_ref, object_value)
    ELSE jsonb_build_array(subject_ref)
END
WHERE fact_args = '[]'::JSONB;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_kb_facts_args_array'
    ) THEN
        ALTER TABLE kb_facts ADD CONSTRAINT ck_kb_facts_args_array
            CHECK (jsonb_typeof(fact_args) = 'array' AND jsonb_array_length(fact_args) > 0);
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_kb_facts_arguments
    ON kb_facts (fact_type, predicate_code, (fact_args::TEXT));

DROP INDEX IF EXISTS uq_kb_facts_canonical;

INSERT INTO sys_props (prop_key, prop_value, description, is_editable)
VALUES
    ('CAT_STABILITY_EPSILON', '0.05'::JSONB, 'Biên độ theta ổn định để dừng CAT.', TRUE),
    ('CAT_STABILITY_WINDOW', '3'::JSONB, 'Số lần cập nhật theta ổn định liên tiếp.', TRUE),
    ('CAT_INFORMATION_WEIGHT', '1.0'::JSONB, 'Trọng số Fisher information khi chọn câu CAT.', TRUE),
    ('CAT_WEAK_UNIT_WEIGHT', '0.35'::JSONB, 'Trọng số ưu tiên đơn vị tri thức yếu.', TRUE),
    ('CAT_CONTENT_BALANCE_WEIGHT', '0.20'::JSONB, 'Trọng số cân bằng nội dung CAT.', TRUE),
    ('CAT_EXPOSURE_PENALTY', '0.15'::JSONB, 'Mức phạt câu hỏi có độ phơi nhiễm cao.', TRUE),
    ('CAT_DIFFICULTY_DISTRIBUTION', '{"easy":0.3,"medium":0.4,"hard":0.3}'::JSONB, 'Phân bố độ khó mặc định của CAT.', TRUE),
    ('CAT_TOPIC_CODES', '[]'::JSONB, 'Giới hạn chủ đề CAT; rỗng nghĩa là mọi chủ đề.', TRUE),
    ('CAT_SKILL_CODES', '[]'::JSONB, 'Giới hạn kỹ năng CAT; rỗng nghĩa là mọi kỹ năng.', TRUE),
    ('CAT_BLOOM_LEVELS', '[]'::JSONB, 'Giới hạn Bloom CAT; rỗng nghĩa là mọi mức.', TRUE),
    ('LEARNING_REMEDIATE_THRESHOLD', '0.5'::JSONB, 'Ngưỡng đề xuất ôn nền.', TRUE),
    ('LEARNING_ADVANCE_THRESHOLD', '0.75'::JSONB, 'Ngưỡng đề xuất bài nâng cao.', TRUE)
    ,('LLM_ENABLED', 'true'::JSONB, 'Cho phép các thao tác LLM theo yêu cầu rõ ràng của người dùng.', TRUE)
    ,('LLM_MODEL', '"qwen3.5-4b"'::JSONB, 'Tên model OpenAI-compatible; khóa API chỉ nằm trong biến môi trường.', TRUE)
    ,('LLM_QUESTION_MAX_TOKENS', '1600'::JSONB, 'Ngân sách token đầu ra tối đa cho một bản nháp câu hỏi.', TRUE)
    ,('LLM_EXPLANATION_MAX_TOKENS', '350'::JSONB, 'Ngân sách token đầu ra tối đa cho một diễn giải phiên thi.', TRUE)
    ,('LLM_MAX_SOURCE_CHARS', '6000'::JSONB, 'Số ký tự nguồn tối đa gửi trong một yêu cầu LLM.', TRUE)
    ,('LLM_TEMPERATURE', '0.2'::JSONB, 'Độ ngẫu nhiên cho tác vụ sinh bản nháp.', TRUE)
ON CONFLICT (prop_key) DO NOTHING;

UPDATE sys_props
SET prop_value = '["active"]'::JSONB,
    description = 'Chỉ câu hỏi active được phép dùng trong đề thi.'
WHERE prop_key = 'EXAM_ALLOWED_QUESTION_STATUSES';

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
    ('subject_has_no_evidence', 'môn chưa có bằng chứng', 'relation', FALSE, FALSE, 'Môn chưa có lịch sử trả lời.', 'project_model')
ON CONFLICT (definition_code) DO UPDATE SET is_active = TRUE;

UPDATE kb_rules
SET hypothesis = '[
        {"predicate":"has_binary_response","args":["?student","?q","?u"]},
        {"predicate":"has_irt_parameters","args":["?q","?a","?b","?c"]},
        {"predicate":"computed_theta","args":["?student","?theta_new"]}
    ]'::JSONB
WHERE rule_code = 'R_UPDATE_ABILITY_3PL';

UPDATE kb_rules
SET hypothesis = '[
        {"predicate":"unit_accuracy","args":["?student","?unit","?accuracy"]},
        {"operator":"lt","left":"?accuracy","right":0.5}
    ]'::JSONB,
    goal = '[
        {"predicate":"weak_unit","args":["?student","?unit"]},
        {"predicate":"recommended_next","args":["?student","?unit","remediate"]}
    ]'::JSONB
WHERE rule_code = 'R_LEARNING_REMEDIATE';

UPDATE kb_rules
SET hypothesis = '[
        {"predicate":"unit_accuracy","args":["?student","?unit","?accuracy"]},
        {"operator":"gte","left":"?accuracy","right":0.5},
        {"operator":"lt","left":"?accuracy","right":0.75}
    ]'::JSONB,
    goal = '[{"predicate":"recommended_next","args":["?student","?unit","reinforce"]}]'::JSONB
WHERE rule_code = 'R_LEARNING_REINFORCE';

UPDATE kb_rules
SET hypothesis = '[
        {"predicate":"unit_accuracy","args":["?student","?unit","?accuracy"]},
        {"operator":"gte","left":"?accuracy","right":0.75}
    ]'::JSONB,
    goal = '[
        {"predicate":"has_mastery","args":["?student","?unit",true]},
        {"predicate":"recommended_next","args":["?student","?unit","advance"]}
    ]'::JSONB
WHERE rule_code = 'R_LEARNING_ADVANCE';

COMMIT;
