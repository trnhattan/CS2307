BEGIN;

CREATE TABLE IF NOT EXISTS irt_calibration_runs (
    run_id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    method              VARCHAR(80) NOT NULL,
    total_responses     INTEGER NOT NULL,
    evaluated_items     INTEGER NOT NULL,
    eligible_items      INTEGER NOT NULL,
    applied_items       INTEGER NOT NULL,
    summary             JSONB NOT NULL,
    created_by          VARCHAR(100) NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_irt_calibration_counts CHECK (
        total_responses >= 0 AND evaluated_items >= 0 AND
        eligible_items >= 0 AND applied_items >= 0
    ),
    CONSTRAINT ck_irt_calibration_summary CHECK (jsonb_typeof(summary) = 'object')
);

INSERT INTO sys_props (prop_key, prop_value, description, is_editable)
VALUES
    ('IRT_CALIBRATION_MIN_RESPONSES', '30'::JSONB,
     'Minimum real responses before an item estimate is more than descriptive.', TRUE),
    ('IRT_CALIBRATION_APPLY_MIN_RESPONSES', '100'::JSONB,
     'Minimum real responses before empirical difficulty may update production IRT parameters.', TRUE)
ON CONFLICT (prop_key) DO UPDATE
SET description = EXCLUDED.description,
    is_editable = EXCLUDED.is_editable;

UPDATE subjects
SET subject_name = CASE subject_code
        WHEN 'DATABASE' THEN 'Database Systems'
        WHEN 'NETWORK' THEN 'Computer Networks'
        ELSE subject_name
    END,
    description = CASE subject_code
        WHEN 'DATABASE' THEN 'Relational modeling, SQL, transactions, indexing, and database operations.'
        WHEN 'NETWORK' THEN 'Network models, addressing, routing, transport, services, security, and troubleshooting.'
        ELSE description
    END,
    updated_at = CURRENT_TIMESTAMP
WHERE subject_code IN ('DATABASE', 'NETWORK');

WITH english_labels AS (
    SELECT
        unit_id,
        INITCAP(REPLACE(REGEXP_REPLACE(unit_code, '^(DB|NET)_', ''), '_', ' ')) AS label
    FROM knowledge_units
    WHERE unit_code ~ '^(DB|NET)_'
      AND unit_code !~ '^(DB|NET)_EN_'
)
UPDATE knowledge_units AS unit
SET unit_name = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                    REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                    REPLACE(REPLACE(REPLACE(REPLACE(english_labels.label,
                    'Acid', 'ACID'), 'Arp', 'ARP'), 'Ddl', 'DDL'), 'Dns', 'DNS'),
                    'Https', 'HTTPS'), 'Ip', 'IP'), 'Ipv4', 'IPv4'), 'Join', 'JOIN'),
                    'Mtu', 'MTU'), 'Nat', 'NAT'), 'Pat', 'PAT'), 'Pmtud', 'PMTUD'),
                    'Qos', 'QoS'), 'Rtp', 'RTP'), 'Sql', 'SQL'), 'Tcp', 'TCP'),
                    'Tls', 'TLS'), 'Ttl', 'TTL'), 'Udp', 'UDP'), 'Vlan', 'VLAN'),
    updated_at = CURRENT_TIMESTAMP
FROM english_labels
WHERE unit.unit_id = english_labels.unit_id;

UPDATE students
SET display_name = CASE student_code
        WHEN 'TAKER001' THEN 'Student 1'
        WHEN 'TAKER002' THEN 'Student 2'
        ELSE display_name
    END
WHERE student_code IN ('TAKER001', 'TAKER002');

UPDATE app_users
SET display_name = CASE username
        WHEN 'admin' THEN 'System Administrator'
        WHEN 'supervisor' THEN 'Exam Supervisor'
        WHEN 'taker1' THEN 'Student 1'
        WHEN 'taker2' THEN 'Student 2'
        ELSE display_name
    END
WHERE username IN ('admin', 'supervisor', 'taker1', 'taker2');

UPDATE sys_props AS property
SET description = english.description
FROM (VALUES
    ('QUESTION_BANK_TARGET_SIZE', 'Target number of questions for the coursework.'),
    ('DEFAULT_EXAM_QUESTION_COUNT', 'Default number of questions in a fixed exam.'),
    ('DISPLAY_OPTION_COUNT', 'Number of answer options displayed from the answer pool.'),
    ('ANSWER_POOL_SIZE_BY_BLOOM', 'Required answer-pool size for each supported Bloom level.'),
    ('MUST_INCLUDE_BEST_ANSWER', 'Displayed answer options must include the best answer.'),
    ('RANDOMIZE_OPTION_ORDER', 'Randomize answer-option order when presenting a question.'),
    ('IRT_MODEL', 'IRT model used for ability estimation.'),
    ('PARTIAL_CREDIT_AFFECTS_IRT', 'IRT 3PL uses binary responses; partial credit is limited to scoring and diagnostics.'),
    ('CAT_INITIAL_THETA', 'Initial ability when an exam taker has no prior evidence.'),
    ('CAT_MIN_QUESTION_COUNT', 'Minimum answered questions before CAT may stop.'),
    ('CAT_MAX_QUESTION_COUNT', 'Maximum questions in a CAT session.'),
    ('CAT_STOP_STANDARD_ERROR', 'Standard-error threshold for CAT stopping.'),
    ('CAT_STABILITY_EPSILON', 'Theta-change epsilon used by CAT stability stopping.'),
    ('CAT_STABILITY_WINDOW', 'Number of consecutive stable theta updates required for stopping.'),
    ('CAT_INFORMATION_WEIGHT', 'Fisher-information weight in CAT selection.'),
    ('CAT_WEAK_UNIT_WEIGHT', 'Weak-knowledge-unit priority weight in CAT selection.'),
    ('CAT_CONTENT_BALANCE_WEIGHT', 'Content-balance weight in CAT selection.'),
    ('CAT_EXPOSURE_PENALTY', 'Penalty applied to highly exposed questions.'),
    ('CAT_DIFFICULTY_DISTRIBUTION', 'Default CAT difficulty distribution.'),
    ('CAT_TOPIC_CODES', 'CAT topic constraint; an empty list allows every topic.'),
    ('CAT_SKILL_CODES', 'CAT skill constraint; an empty list allows every skill.'),
    ('CAT_BLOOM_LEVELS', 'CAT Bloom constraint; an empty list allows every supported level.'),
    ('LEARNING_REMEDIATE_THRESHOLD', 'Accuracy threshold below which remediation is recommended.'),
    ('LEARNING_ADVANCE_THRESHOLD', 'Accuracy threshold at which advanced learning is recommended.'),
    ('FIXED_EXAM_DIFFICULTY_DISTRIBUTION', 'Default difficulty distribution for fixed exams.'),
    ('EXAM_ALLOWED_QUESTION_STATUSES', 'Question statuses eligible for operational exams.'),
    ('EXAM_GENERATION_STRATEGY', 'Fixed-exam selection strategy balancing constraints and Fisher information.'),
    ('IRT_SCALE_CONSTANT', 'Scale constant D in the IRT 3PL model.'),
    ('IRT_CALIBRATION_MIN_RESPONSES', 'Minimum real responses before an item estimate is more than descriptive.'),
    ('IRT_CALIBRATION_APPLY_MIN_RESPONSES', 'Minimum real responses before empirical difficulty may update production IRT parameters.'),
    ('LLM_ENABLED', 'Enable explicit, user-triggered LLM operations.'),
    ('LLM_MODEL', 'OpenAI-compatible model name; the API key remains in the environment.'),
    ('LLM_QUESTION_MAX_TOKENS', 'Maximum output-token budget for one question draft.'),
    ('LLM_EXPLANATION_MAX_TOKENS', 'Maximum output-token budget for one exam explanation.'),
    ('LLM_MAX_SOURCE_CHARS', 'Maximum authorized source characters sent in one LLM request.'),
    ('LLM_TEMPERATURE', 'Temperature used for LLM draft generation.')
) AS english(prop_key, description)
WHERE property.prop_key = english.prop_key;

UPDATE kb_definitions AS definition
SET definition_name = english.definition_name,
    description = english.description
FROM (VALUES
    ('NUMBER', 'Number', 'Primitive concept for theta, IRT parameters, weights, and time.'),
    ('TEXT', 'Text', 'Primitive concept for identifiers and content.'),
    ('BOOLEAN', 'Boolean', 'Primitive true-or-false concept.'),
    ('SUBJECT', 'Subject', 'Simple object class representing a subject.'),
    ('KNOWLEDGE_UNIT', 'Knowledge unit', 'A topic or skill that belongs to a subject.'),
    ('BLOOM_LEVEL', 'Bloom level', 'The five cognitive levels supported by this project.'),
    ('STUDENT', 'Student', 'A person who takes an exam.'),
    ('QUESTION', 'Question', 'Advanced object containing item properties and knowledge-unit links.'),
    ('ANSWER_OPTION', 'Answer option', 'An option in a question answer pool.'),
    ('ABILITY_STATE', 'Ability state', 'Student ability estimated using IRT 3PL.'),
    ('EXAM_SESSION', 'Exam session', 'Composite object linking a student, questions, responses, and ability.'),
    ('is_a', 'is a', 'Relation used by type-1 facts: x:c.'),
    ('belongs_to', 'belongs to', 'A knowledge unit belongs to a subject.'),
    ('measures', 'measures', 'A question measures a topic or skill.'),
    ('prerequisite_of', 'prerequisite of', 'Prerequisite relation between knowledge units.'),
    ('has_bloom_level', 'has Bloom level', 'Cognitive classification of a question.'),
    ('selected_option', 'selected option', 'Fact recording that a student selected an option.'),
    ('unit_accuracy', 'knowledge-unit accuracy', 'Accuracy evidence for a student and knowledge unit.'),
    ('recommended_next', 'recommended next action', 'An inferred learning action.'),
    ('weak_unit', 'weak knowledge unit', 'A unit that should be prioritized for assessment or review.'),
    ('has_mastery', 'has mastery', 'Knowledge-unit mastery state.'),
    ('question_ready', 'question is ready', 'A question that passed deterministic validation.'),
    ('best_option', 'best option', 'The best answer to a question.'),
    ('displayed_options_include', 'displayed options include', 'Answer-option presentation constraint.'),
    ('option_weight', 'option weight', 'Scoring weight assigned to an option.'),
    ('awarded_score', 'awarded score', 'Score inferred from the selected option.'),
    ('has_binary_response', 'has binary response', 'Response evidence used by IRT.'),
    ('has_irt_parameters', 'has IRT parameters', 'IRT parameter tuple a, b, and c.'),
    ('updated_theta', 'updated theta', 'Ability estimate after processing a response.'),
    ('computed_theta', 'computed theta', 'Theta supplied by the IRT module to the inference engine.'),
    ('valid_question_pool', 'valid question pool', 'Question bank eligible for selection.'),
    ('student_theta', 'student theta', 'Ability estimate used as selection input.'),
    ('difficulty_blueprint', 'difficulty blueprint', 'Requested difficulty distribution.'),
    ('exam_generated_with_constraints', 'exam satisfies constraints', 'Goal of fixed-exam generation.'),
    ('subject_has_no_evidence', 'subject has no evidence', 'A subject with no response history.')
) AS english(definition_code, definition_name, description)
WHERE definition.definition_code = english.definition_code;

UPDATE kb_rules AS rule
SET rule_name = english.rule_name,
    explanation_template = english.explanation_template
FROM (VALUES
    ('R_GEN_INCLUDE_BEST', 'Generate a valid option set', 'The displayed option set for {q} must include the best answer {best}.'),
    ('R_SCORE_SELECTED_OPTION', 'Score the selected option', 'Student {student} receives score {w} for question {q}.'),
    ('R_UPDATE_ABILITY_3PL', 'Update ability using IRT 3PL', 'Update {student} theta from binary response {u} using IRT 3PL.'),
    ('R_GEN_IRT_BALANCED', 'Generate an IRT-balanced exam', 'Select questions by difficulty profile, content balance, and Fisher information at the current theta.'),
    ('R_LEARNING_START_SUBJECT', 'Start subject assessment', 'The student has no evidence in {subject} and should complete an initial assessment.'),
    ('R_LEARNING_REMEDIATE', 'Remediate a weak knowledge unit', 'Accuracy in {unit} is below 50%; prioritize foundational review.'),
    ('R_LEARNING_REINFORCE', 'Reinforce a knowledge unit', 'Accuracy in {unit} is between 50% and 75%; continue reinforcement practice.'),
    ('R_LEARNING_ADVANCE', 'Advance a mastered knowledge unit', 'Accuracy in {unit} is at least 75%; advance to higher-order application.')
) AS english(rule_code, rule_name, explanation_template)
WHERE rule.rule_code = english.rule_code;

INSERT INTO kb_rules (
    rule_code, rule_name, rule_type, hypothesis, goal,
    priority, weight, explanation_template, source, provenance, is_active
)
VALUES
    (
        'R_DIFFICULTY_HARD',
        'Classify a hard question',
        'classification',
        '[{"predicate":"difficulty_norm","args":["?question","?value"]},{"operator":"gte","left":"?value","right":0.8}]'::JSONB,
        '[{"predicate":"classified_as","args":["?question","hard"]}]'::JSONB,
        60, 1.0,
        'The question is classified as hard because difficulty_norm is at least 0.80.',
        'course_requirement', '{"language":"en"}'::JSONB, TRUE
    ),
    (
        'R_LOW_TOPIC_INCREASE_FREQUENCY',
        'Increase assessment frequency for a weak unit',
        'recommendation',
        '[{"predicate":"weak_unit","args":["?student","?unit"]}]'::JSONB,
        '[{"predicate":"topic_weight","args":["?student","?unit","increased"]}]'::JSONB,
        55, 1.0,
        'The system increases assessment priority because this knowledge unit is weak.',
        'course_requirement', '{"language":"en"}'::JSONB, TRUE
    )
ON CONFLICT (rule_code) DO UPDATE
SET rule_name = EXCLUDED.rule_name,
    rule_type = EXCLUDED.rule_type,
    hypothesis = EXCLUDED.hypothesis,
    goal = EXCLUDED.goal,
    priority = EXCLUDED.priority,
    weight = EXCLUDED.weight,
    explanation_template = EXCLUDED.explanation_template,
    source = EXCLUDED.source,
    provenance = EXCLUDED.provenance,
    is_active = TRUE;

COMMIT;
