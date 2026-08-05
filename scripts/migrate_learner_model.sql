BEGIN;

CREATE TABLE IF NOT EXISTS assessment_criteria (
    criterion_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_id          BIGINT NOT NULL REFERENCES subjects(subject_id),
    knowledge_unit_id   BIGINT NOT NULL UNIQUE REFERENCES knowledge_units(unit_id),
    criterion_code      VARCHAR(100) NOT NULL UNIQUE,
    criterion_name      VARCHAR(255) NOT NULL,
    learning_objective  TEXT NOT NULL,
    success_statement   TEXT NOT NULL,
    mastery_threshold   NUMERIC(5,4) NOT NULL DEFAULT 0.75,
    importance_weight   NUMERIC(6,3) NOT NULL DEFAULT 1,
    display_order       INTEGER NOT NULL DEFAULT 0,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    reviewed_by         VARCHAR(100),
    reviewed_at         TIMESTAMPTZ,
    provenance          JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_assessment_criteria_subject_code
        UNIQUE (subject_id, criterion_code),
    CONSTRAINT ck_assessment_criteria_mastery
        CHECK (mastery_threshold > 0 AND mastery_threshold <= 1),
    CONSTRAINT ck_assessment_criteria_weight CHECK (importance_weight > 0),
    CONSTRAINT ck_assessment_criteria_order CHECK (display_order >= 0),
    CONSTRAINT ck_assessment_criteria_provenance
        CHECK (jsonb_typeof(provenance) = 'object')
);

INSERT INTO assessment_criteria (
    subject_id, knowledge_unit_id, criterion_code, criterion_name,
    learning_objective, success_statement, display_order, provenance
)
SELECT
    unit.subject_id,
    unit.unit_id,
    unit.unit_code,
    unit.unit_name,
    COALESCE(
        NULLIF(unit.description, ''),
        'Explain and apply ' || unit.unit_name || ' in representative problems.'
    ),
    'The learner can identify, explain, and correctly apply ' ||
        unit.unit_name || ' in assessment questions.',
    ROW_NUMBER() OVER (
        PARTITION BY unit.subject_id
        ORDER BY parent.unit_name NULLS FIRST, unit.unit_name
    ),
    jsonb_build_object(
        'source', 'existing_skill_knowledge_unit',
        'migration', 'migrate_learner_model.sql'
    )
FROM knowledge_units unit
LEFT JOIN knowledge_units parent ON parent.unit_id = unit.parent_unit_id
WHERE unit.unit_type = 'skill'
ON CONFLICT (knowledge_unit_id) DO UPDATE SET
    criterion_code = EXCLUDED.criterion_code,
    criterion_name = EXCLUDED.criterion_name,
    learning_objective = EXCLUDED.learning_objective,
    success_statement = EXCLUDED.success_statement,
    display_order = EXCLUDED.display_order,
    updated_at = CURRENT_TIMESTAMP;

UPDATE assessment_criteria criterion
SET is_active = EXISTS (
        SELECT 1
        FROM question_knowledge_units link
        JOIN questions question ON question.question_id = link.question_id
        WHERE link.unit_id = criterion.knowledge_unit_id
          AND link.unit_role IN ('primary_skill', 'supporting_skill')
          AND question.status IN ('active', 'reviewed')
    ),
    updated_at = CURRENT_TIMESTAMP;

CREATE INDEX IF NOT EXISTS ix_assessment_criteria_subject
    ON assessment_criteria(subject_id, is_active, display_order);

CREATE TABLE IF NOT EXISTS student_ability_snapshots (
    snapshot_id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id              BIGINT NOT NULL REFERENCES exam_sessions(session_id) ON DELETE CASCADE,
    student_id              BIGINT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    subject_id              BIGINT NOT NULL REFERENCES subjects(subject_id),
    criterion_id            BIGINT REFERENCES assessment_criteria(criterion_id),
    theta                   NUMERIC(9,6) NOT NULL,
    standard_error          NUMERIC(9,6) NOT NULL,
    mastery_probability     NUMERIC(8,5),
    accuracy_percent        NUMERIC(7,3),
    evidence_count          INTEGER NOT NULL DEFAULT 0,
    previous_theta          NUMERIC(9,6),
    previous_mastery        NUMERIC(8,5),
    theta_delta             NUMERIC(9,6),
    mastery_delta           NUMERIC(9,6),
    model_version           VARCHAR(50) NOT NULL DEFAULT 'IRT-3PL-EAP-v1',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_ability_snapshots_theta CHECK (theta BETWEEN -6 AND 6),
    CONSTRAINT ck_ability_snapshots_se CHECK (standard_error > 0),
    CONSTRAINT ck_ability_snapshots_mastery CHECK (
        mastery_probability IS NULL OR mastery_probability BETWEEN 0 AND 1
    ),
    CONSTRAINT ck_ability_snapshots_accuracy CHECK (
        accuracy_percent IS NULL OR accuracy_percent BETWEEN 0 AND 100
    ),
    CONSTRAINT ck_ability_snapshots_evidence CHECK (evidence_count >= 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_student_ability_snapshot_scope
    ON student_ability_snapshots(session_id, criterion_id) NULLS NOT DISTINCT;

CREATE INDEX IF NOT EXISTS ix_student_ability_snapshots_history
    ON student_ability_snapshots(student_id, subject_id, criterion_id, created_at DESC);

CREATE TABLE IF NOT EXISTS subject_knowledge_documents (
    document_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_id      BIGINT NOT NULL REFERENCES subjects(subject_id) ON DELETE CASCADE,
    document_code   VARCHAR(100) NOT NULL,
    title           VARCHAR(255) NOT NULL,
    content         TEXT NOT NULL,
    keywords        JSONB NOT NULL DEFAULT '[]'::JSONB,
    source          VARCHAR(255) NOT NULL DEFAULT 'curated_course_knowledge',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_subject_knowledge_document UNIQUE (subject_id, document_code),
    CONSTRAINT ck_subject_knowledge_keywords CHECK (jsonb_typeof(keywords) = 'array')
);

CREATE INDEX IF NOT EXISTS ix_subject_knowledge_documents_subject
    ON subject_knowledge_documents(subject_id, is_active, document_code);

INSERT INTO subject_knowledge_documents (
    subject_id, document_code, title, content, keywords
)
SELECT subject.subject_id, seed.document_code, seed.title, seed.content,
       seed.keywords::JSONB
FROM (
    VALUES
        ('DATABASE', 'DB_RELATIONAL_MODEL', 'Relational model, keys, and integrity',
         'Cơ sở dữ liệu quan hệ lưu dữ liệu trong các bảng, trong đó hàng biểu diễn bản ghi và cột biểu diễn thuộc tính. Khóa chính định danh duy nhất từng hàng; khóa ngoại tham chiếu khóa của bảng liên quan và bảo đảm toàn vẹn tham chiếu. Thiết kế tốt chọn khóa ổn định, khai báo rõ NULL và ràng buộc, đồng thời dùng bảng nối cho quan hệ nhiều-nhiều.',
         '["relational model","primary key","foreign key","junction table","integrity"]'),
        ('DATABASE', 'DB_SQL_QUERYING', 'SQL filtering, grouping, and joins',
         'SQL tạo kết quả từ nguồn FROM và JOIN, lọc hàng bằng WHERE, gom nhóm bằng GROUP BY, lọc nhóm bằng HAVING và sắp xếp bằng ORDER BY. INNER JOIN chỉ giữ các hàng khớp; LEFT JOIN giữ mọi hàng bên trái và điền NULL khi bên phải không khớp. Hàm cửa sổ tính toán trên các hàng liên quan mà không gộp chúng thành một hàng cho mỗi nhóm.',
         '["SQL","WHERE","HAVING","JOIN","LEFT JOIN","GROUP BY","window function"]'),
        ('DATABASE', 'DB_NORMALIZATION', 'Functional dependencies and normalization',
         'Chuẩn hóa giảm bất thường khi cập nhật bằng cách phân rã quan hệ theo phụ thuộc hàm. Dạng chuẩn một yêu cầu giá trị nguyên tử; dạng chuẩn hai loại phụ thuộc bộ phận vào một phần khóa ghép; dạng chuẩn ba loại phụ thuộc bắc cầu của thuộc tính không khóa. Phép phân rã phải bảo toàn thông tin và nên bảo toàn các phụ thuộc quan trọng.',
         '["normalization","functional dependency","1NF","2NF","3NF","anomaly"]'),
        ('DATABASE', 'DB_INDEXING', 'Database indexes and query access paths',
         'Chỉ mục là cấu trúc truy cập phụ giúp tăng tốc đọc nhưng tốn dung lượng và chi phí bảo trì khi ghi. Chỉ mục B-tree hỗ trợ tìm bằng, tìm theo khoảng và truy cập có thứ tự. Hiệu quả của chỉ mục ghép phụ thuộc thứ tự cột và điều kiện trên các cột đầu; chỉ mục bao phủ chứa đủ cột mà truy vấn cần. Độ chọn lọc, tải công việc và kế hoạch thực thi phải định hướng thiết kế chỉ mục.',
         '["index","B-tree","composite index","covering index","selectivity","query plan"]'),
        ('DATABASE', 'DB_TRANSACTIONS', 'Transactions, isolation, and MVCC',
         'Giao dịch gom các thao tác thành một đơn vị logic với tính nguyên tử, nhất quán, cô lập và bền vững. Mức cô lập kiểm soát tác động đồng thời nào được nhìn thấy và ngăn các bất thường như đọc bẩn, đọc không lặp lại và phantom. MVCC giữ nhiều phiên bản của hàng để đọc và ghi thường có thể diễn ra ít chặn nhau hơn, nhưng quy tắc xung đột vẫn quyết định việc commit.',
         '["transaction","ACID","isolation","dirty read","phantom","MVCC","concurrency"]'),
        ('DATABASE', 'DB_RECOVERY', 'Write-ahead logging and recovery',
         'Write-ahead logging ghi thay đổi vào log bền vững trước khi trang dữ liệu tương ứng được ghi. Sau sự cố, phục hồi dùng log và checkpoint để thực hiện lại thay đổi đã commit và hoàn tác phần chưa hoàn tất khi thuật toán yêu cầu. Tính bền vững, đúng thứ tự và khả năng lặp lại an toàn của thao tác phục hồi là các ý chính.',
         '["write-ahead logging","WAL","recovery","checkpoint","redo","undo","durability"]'),
        ('DATABASE', 'DB_SCALE_SECURITY', 'Partitioning, replication, and database security',
         'Phân vùng chia một bảng logic thành các phần được quản lý theo khóa phân vùng; sao chép duy trì nhiều bản dữ liệu để tăng khả dụng hoặc năng lực đọc. Hai kỹ thuật này không tự thay thế thiết kế chỉ mục hay nhất quán. Bảo mật đặc quyền tối thiểu chỉ cấp cho mỗi vai trò quyền thật sự cần, tách trách nhiệm và ghi vết thao tác nhạy cảm.',
         '["partitioning","replication","availability","least privilege","role","audit"]'),
        ('NETWORK', 'NET_MODELS', 'Network layers and encapsulation',
         'Mô hình mạng phân tầng tách các trách nhiệm. Giao thức ứng dụng dùng dịch vụ vận chuyển; tầng vận chuyển chia dữ liệu; tầng mạng định tuyến gói giữa các mạng; tầng liên kết chuyển frame trên môi trường cục bộ. Đóng gói thêm header tại từng tầng và phía nhận tháo chúng theo thứ tự ngược lại.',
         '["OSI","TCP/IP","layer","encapsulation","frame","packet","segment"]'),
        ('NETWORK', 'NET_ADDRESSING', 'IPv4 addressing, subnet masks, and CIDR',
         'Tiền tố IPv4 chia địa chỉ thành phần mạng và phần host. Ký hiệu CIDR /n cho biết số bit mạng; subnet mask có n bit 1 liên tiếp ở đầu. Thiết bị so sánh tiền tố để biết đích nằm cục bộ hay phải qua router. Kích thước subnet, địa chỉ mạng, địa chỉ broadcast và dải host dùng được đều suy ra từ độ dài tiền tố.',
         '["IPv4","subnet mask","CIDR","prefix","network address","broadcast"]'),
        ('NETWORK', 'NET_LOCAL_DELIVERY', 'ARP, switching, VLANs, and NAT',
         'ARP phân giải địa chỉ IPv4 thành địa chỉ tầng liên kết trong mạng cục bộ. Switch Ethernet chuyển frame theo bảng địa chỉ MAC đã học; VLAN tạo các miền broadcast logic riêng. NAT viết lại thông tin địa chỉ giữa các vùng mạng; PAT còn phân biệt luồng bằng cổng vận chuyển để nhiều host riêng có thể dùng chung một địa chỉ công cộng.',
         '["ARP","MAC","switch","VLAN","NAT","PAT","broadcast domain"]'),
        ('NETWORK', 'NET_ROUTING', 'Routing and forwarding',
         'Forwarding chuyển từng gói theo tuyến khớp tốt nhất, thường dùng nguyên tắc tiền tố dài nhất. Giao thức định tuyến trao đổi thông tin để router xây dựng các tuyến. Tuyến tĩnh được cấu hình thủ công; giao thức động phản ứng với thay đổi topology bằng metric và quy tắc hội tụ. Tuyến mặc định được dùng khi không có tiền tố cụ thể hơn khớp.',
         '["routing","forwarding","longest prefix match","static route","dynamic routing","default route"]'),
        ('NETWORK', 'NET_TRANSPORT', 'TCP, UDP, and congestion control',
         'UDP chuyển thông điệp với chi phí vận chuyển thấp và không có độ tin cậy tích hợp. TCP thiết lập kết nối, đánh số byte, xác nhận dữ liệu, truyền lại khi mất, điều khiển luồng phía nhận và điều chỉnh tốc độ khi tắc nghẽn. Điều khiển tắc nghẽn bảo vệ mạng bằng cách thay đổi congestion window theo tín hiệu như mất gói hoặc độ trễ.',
         '["TCP","UDP","reliability","flow control","congestion control","window"]'),
        ('NETWORK', 'NET_SERVICES', 'DNS and DHCP services',
         'DNS là hệ thống đặt tên phân tán ánh xạ tên sang các bản ghi như địa chỉ IP, máy chủ thư hoặc bí danh, đồng thời dùng cache và cơ chế ủy quyền. DHCP tự động cấu hình host qua quá trình cấp lease, có thể cung cấp địa chỉ, subnet mask, default gateway, DNS server và thời hạn thuê.',
         '["DNS","DHCP","name resolution","cache","lease","default gateway"]'),
        ('NETWORK', 'NET_QOS', 'Quality of Service policy',
         'Chính sách Quality of Service quản lý các luồng lưu lượng cạnh tranh theo nhu cầu của ứng dụng và tổ chức. Nó thường phân loại và đánh dấu lưu lượng, đưa gói vào hàng đợi, lập lịch theo ưu tiên hoặc trọng số, đồng thời có thể policing hay shaping tốc độ. Mục tiêu là kiểm soát băng thông, độ trễ, jitter và mất gói cho luồng quan trọng khi tắc nghẽn; QoS không tạo thêm băng thông và cần được áp dụng nhất quán trên đường đi.',
         '["QoS","quality of service","classification","marking","queue","scheduling","policing","shaping","latency","jitter"]'),
        ('NETWORK', 'NET_SECURITY', 'Network security controls',
         'Bảo mật mạng kết hợp phân đoạn, đặc quyền tối thiểu, quản trị có xác thực, mã hóa, lọc, giám sát và vá lỗi kịp thời. Firewall đánh giá lưu lượng theo chính sách; hệ thống phát hiện xâm nhập tìm hành vi đáng ngờ. Phòng thủ nhiều lớp giả định một biện pháp có thể thất bại và giới hạn phạm vi ảnh hưởng.',
         '["network security","firewall","segmentation","encryption","monitoring","defense in depth"]')
) AS seed(subject_code, document_code, title, content, keywords)
JOIN subjects subject ON subject.subject_code = seed.subject_code
ON CONFLICT (subject_id, document_code) DO UPDATE SET
    title = EXCLUDED.title,
    content = EXCLUDED.content,
    keywords = EXCLUDED.keywords,
    is_active = TRUE,
    updated_at = CURRENT_TIMESTAMP;

WITH subject_history AS (
    SELECT exam.session_id, exam.student_id, exam.subject_id,
           exam.theta_current AS theta,
           exam.standard_error_current AS standard_error,
           1.0 / (1.0 + EXP(-exam.theta_current)) AS mastery,
           CASE WHEN exam.max_score > 0
                THEN 100 * exam.total_score / exam.max_score ELSE 0 END AS accuracy,
           COUNT(item.exam_item_id) FILTER (WHERE item.answered_at IS NOT NULL)
               AS evidence_count,
           exam.finished_at,
           LAG(exam.theta_current) OVER (
               PARTITION BY exam.student_id, exam.subject_id
               ORDER BY exam.finished_at, exam.session_id
           ) AS previous_theta,
           LAG(1.0 / (1.0 + EXP(-exam.theta_current))) OVER (
               PARTITION BY exam.student_id, exam.subject_id
               ORDER BY exam.finished_at, exam.session_id
           ) AS previous_mastery
    FROM exam_sessions exam
    LEFT JOIN exam_items item ON item.session_id = exam.session_id
    WHERE exam.status = 'completed'
    GROUP BY exam.session_id
)
INSERT INTO student_ability_snapshots (
    session_id, student_id, subject_id, criterion_id, theta,
    standard_error, mastery_probability, accuracy_percent, evidence_count,
    previous_theta, previous_mastery, theta_delta, mastery_delta,
    model_version, created_at
)
SELECT session_id, student_id, subject_id, NULL, theta,
       standard_error, mastery, accuracy, evidence_count,
       previous_theta, previous_mastery,
       theta - previous_theta, mastery - previous_mastery,
       'historical-session-backfill-v1', finished_at
FROM subject_history
ON CONFLICT (session_id, criterion_id) DO NOTHING;

WITH criterion_base AS (
    SELECT exam.session_id, exam.student_id, exam.subject_id,
           criterion.criterion_id, exam.theta_current AS theta,
           exam.standard_error_current AS standard_error,
           AVG(CASE WHEN item.is_correct THEN 1.0 ELSE 0.0 END) AS mastery,
           100 * AVG(CASE WHEN item.is_correct THEN 1.0 ELSE 0.0 END) AS accuracy,
           COUNT(item.exam_item_id) AS evidence_count,
           exam.finished_at
    FROM exam_sessions exam
    JOIN exam_items item ON item.session_id = exam.session_id
    JOIN question_knowledge_units link
      ON link.question_id = item.question_id
     AND link.unit_role IN ('primary_skill', 'supporting_skill')
    JOIN assessment_criteria criterion
      ON criterion.knowledge_unit_id = link.unit_id
    WHERE exam.status = 'completed' AND item.answered_at IS NOT NULL
    GROUP BY exam.session_id, criterion.criterion_id
), criterion_history AS (
    SELECT base.*,
           LAG(theta) OVER (
               PARTITION BY student_id, subject_id, criterion_id
               ORDER BY finished_at, session_id
           ) AS previous_theta,
           LAG(mastery) OVER (
               PARTITION BY student_id, subject_id, criterion_id
               ORDER BY finished_at, session_id
           ) AS previous_mastery
    FROM criterion_base base
)
INSERT INTO student_ability_snapshots (
    session_id, student_id, subject_id, criterion_id, theta,
    standard_error, mastery_probability, accuracy_percent, evidence_count,
    previous_theta, previous_mastery, theta_delta, mastery_delta,
    model_version, created_at
)
SELECT session_id, student_id, subject_id, criterion_id, theta,
       standard_error, mastery, accuracy, evidence_count,
       previous_theta, previous_mastery,
       theta - previous_theta, mastery - previous_mastery,
       'historical-criterion-accuracy-backfill-v1', finished_at
FROM criterion_history
ON CONFLICT (session_id, criterion_id) DO NOTHING;

ALTER TABLE exam_sessions
    ADD COLUMN IF NOT EXISTS assessment_purpose VARCHAR(20) NOT NULL DEFAULT 'practice';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_exam_sessions_assessment_purpose'
    ) THEN
        ALTER TABLE exam_sessions
            ADD CONSTRAINT ck_exam_sessions_assessment_purpose
            CHECK (assessment_purpose IN ('placement', 'practice', 'progress'));
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS learner_chat_threads (
    thread_id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id          BIGINT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    subject_id          BIGINT REFERENCES subjects(subject_id),
    title               VARCHAR(255) NOT NULL DEFAULT 'Learning assistant',
    status              VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_learner_chat_thread_status CHECK (status IN ('active', 'archived'))
);

CREATE INDEX IF NOT EXISTS ix_learner_chat_threads_student
    ON learner_chat_threads(student_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS learner_chat_messages (
    message_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    thread_id           BIGINT NOT NULL REFERENCES learner_chat_threads(thread_id) ON DELETE CASCADE,
    role                VARCHAR(20) NOT NULL,
    content             TEXT NOT NULL,
    intent              VARCHAR(40),
    session_id          BIGINT REFERENCES exam_sessions(session_id) ON DELETE SET NULL,
    question_id         BIGINT REFERENCES questions(question_id) ON DELETE SET NULL,
    evidence            JSONB NOT NULL DEFAULT '[]'::JSONB,
    limitations         JSONB NOT NULL DEFAULT '[]'::JSONB,
    model               VARCHAR(100),
    used_llm            BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_learner_chat_message_role CHECK (role IN ('user', 'assistant')),
    CONSTRAINT ck_learner_chat_message_evidence CHECK (jsonb_typeof(evidence) = 'array'),
    CONSTRAINT ck_learner_chat_message_limitations CHECK (jsonb_typeof(limitations) = 'array')
);

CREATE INDEX IF NOT EXISTS ix_learner_chat_messages_thread
    ON learner_chat_messages(thread_id, created_at, message_id);

INSERT INTO sys_props (prop_key, prop_value, description, is_editable)
VALUES
    ('PLACEMENT_QUESTION_COUNT', '20'::JSONB,
     'Number of questions in a subject placement assessment.', TRUE),
    ('PLACEMENT_DIFFICULTY_DISTRIBUTION',
     '{"easy":0.4,"medium":0.4,"hard":0.2}'::JSONB,
     'Difficulty blueprint for placement assessments.', TRUE),
    ('CAT_CRITERION_COVERAGE_WEIGHT', '0.3'::JSONB,
     'CAT weight for criteria with little or no learner evidence.', TRUE),
    ('PROFILE_IMPROVEMENT_DELTA', '0.05'::JSONB,
     'Mastery delta used to classify improvement or regression.', TRUE),
    ('PROFILE_GRAPH_MIN_TESTS', '3'::JSONB,
     'Completed subject tests required before graph edges assert a mastery state.', TRUE),
    ('PROFILE_NEEDS_REVIEW_THRESHOLD', '0.45'::JSONB,
     'Mastery below this value is labeled Needs review.', TRUE),
    ('PROFILE_DEVELOPING_THRESHOLD', '0.60'::JSONB,
     'Mastery below this value is labeled Developing after sufficient evidence.', TRUE),
    ('PROFILE_MASTERY_THRESHOLD', '0.75'::JSONB,
     'Mastery at or above this value is labeled Mastered or Proficient.', TRUE),
    ('LLM_CHAT_MAX_TOKENS', '450'::JSONB,
     'Maximum completion tokens for one learner-chat response.', TRUE),
    ('LLM_CHAT_HISTORY_LIMIT', '10'::JSONB,
     'Maximum prior chat messages included in grounded context.', TRUE),
    ('LLM_CHAT_RETRIEVAL_LIMIT', '200'::JSONB,
     'Maximum completed responses searched for natural learner-chat grounding.', TRUE),
    ('LLM_CHAT_KNOWLEDGE_LIMIT', '300'::JSONB,
     'Maximum sanitized subject, criterion, knowledge-unit, and question resources searched for learner-chat grounding.', TRUE),
    ('LLM_CHAT_WEB_SEARCH_ENABLED', 'false'::JSONB,
     'Allow OpenRouter web search for general educational questions. Disabled by default to control cost.', TRUE),
    ('LLM_CHAT_WEB_SEARCH_MAX_RESULTS', '3'::JSONB,
     'Maximum OpenRouter web-search results for one eligible learner-chat turn.', TRUE),
    ('LLM_CHAT_TOOL_ROUNDS', '4'::JSONB,
     'Maximum MCP tool-call rounds before a learner-chat response must finish.', TRUE)
ON CONFLICT (prop_key) DO UPDATE SET
    description = EXCLUDED.description,
    is_editable = EXCLUDED.is_editable;

INSERT INTO kb_definitions (
    definition_code, definition_name, definition_type, concept_level,
    attributes_schema, description, source
)
VALUES
    ('AssessmentCriterion', 'assessment criterion', 'concept', 1,
     '{"criterion_code":"string","learning_objective":"string","success_statement":"string","mastery_threshold":"number"}'::JSONB,
     'An observable subject requirement measured by mapped questions.',
     'learner_model_extension'),
    ('AbilitySnapshot', 'ability snapshot', 'concept', 2,
     '{"session_id":"integer","mastery":"number","delta":"number","evidence_count":"integer"}'::JSONB,
     'An immutable learner-state observation associated with one completed assessment.',
     'learner_model_extension'),
    ('LearnerConversation', 'learner conversation', 'concept', 3,
     '{"thread_id":"integer","messages":"array","grounding":"object"}'::JSONB,
     'A persisted grounded conversation about improvement and answer rationale.',
     'learner_model_extension')
ON CONFLICT (definition_code) DO UPDATE SET
    definition_name = EXCLUDED.definition_name,
    attributes_schema = EXCLUDED.attributes_schema,
    description = EXCLUDED.description,
    source = EXCLUDED.source,
    is_active = TRUE;

INSERT INTO kb_definitions (
    definition_code, definition_name, definition_type, concept_level,
    attributes_schema, description, source
)
VALUES
    ('criterion_mastery', 'criterion mastery', 'relation', NULL,
     '{"student":"string","criterion":"string","mastery":"number"}'::JSONB,
     'The current IRT-derived mastery probability for one learner and assessment criterion.',
     'learner_model_extension')
ON CONFLICT (definition_code) DO UPDATE SET
    definition_name = EXCLUDED.definition_name,
    attributes_schema = EXCLUDED.attributes_schema,
    description = EXCLUDED.description,
    source = EXCLUDED.source,
    is_active = TRUE;

INSERT INTO kb_rules (
    rule_code, rule_name, rule_type, hypothesis, goal,
    priority, weight, explanation_template, source
)
VALUES
    (
        'R_CRITERION_REMEDIATE', 'Remediate a weak assessment criterion',
        'recommendation',
        '[{"predicate":"criterion_mastery","args":["?student","?criterion","?mastery"]},{"operator":"lt","left":"?mastery","right":0.45}]'::JSONB,
        '[{"predicate":"recommended_next","args":["?student","?criterion","remediate"]}]'::JSONB,
        20, 1,
        'Criterion mastery is below 45%; prioritize prerequisite review.',
        'learner_model_extension'
    ),
    (
        'R_CRITERION_DEVELOP', 'Develop an assessment criterion',
        'recommendation',
        '[{"predicate":"criterion_mastery","args":["?student","?criterion","?mastery"]},{"operator":"gte","left":"?mastery","right":0.45},{"operator":"lt","left":"?mastery","right":0.60}]'::JSONB,
        '[{"predicate":"recommended_next","args":["?student","?criterion","develop"]}]'::JSONB,
        30, 1,
        'Criterion mastery is between 45% and 60%; use guided practice.',
        'learner_model_extension'
    ),
    (
        'R_CRITERION_REINFORCE', 'Reinforce an understood assessment criterion',
        'recommendation',
        '[{"predicate":"criterion_mastery","args":["?student","?criterion","?mastery"]},{"operator":"gte","left":"?mastery","right":0.60},{"operator":"lt","left":"?mastery","right":0.75}]'::JSONB,
        '[{"predicate":"recommended_next","args":["?student","?criterion","reinforce"]}]'::JSONB,
        40, 1,
        'Criterion mastery is between 60% and 75%; consolidate understanding before mastery.',
        'learner_model_extension'
    )
ON CONFLICT (rule_code) DO UPDATE SET
    rule_name = EXCLUDED.rule_name,
    rule_type = EXCLUDED.rule_type,
    hypothesis = EXCLUDED.hypothesis,
    goal = EXCLUDED.goal,
    priority = EXCLUDED.priority,
    weight = EXCLUDED.weight,
    explanation_template = EXCLUDED.explanation_template,
    source = EXCLUDED.source,
    is_active = TRUE;

COMMIT;
