BEGIN;

ALTER TABLE learner_chat_messages
    ADD COLUMN IF NOT EXISTS provider_content TEXT,
    ADD COLUMN IF NOT EXISTS reasoning_details JSONB NOT NULL DEFAULT '[]'::JSONB;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_learner_chat_reasoning_details'
    ) THEN
        ALTER TABLE learner_chat_messages
            ADD CONSTRAINT ck_learner_chat_reasoning_details
            CHECK (jsonb_typeof(reasoning_details) = 'array');
    END IF;
END $$;

INSERT INTO sys_props (prop_key, prop_value, description, is_editable)
VALUES
    ('LLM_MODEL', '"~deepseek/deepseek-v4-flash-latest"'::JSONB,
     'OpenRouter model slug used for LLM operations.', TRUE),
    ('LLM_REASONING_ENABLED', 'true'::JSONB,
     'Request OpenRouter reasoning and preserve private continuation details.', TRUE)
ON CONFLICT (prop_key) DO NOTHING;

UPDATE sys_props
SET prop_value = '"~deepseek/deepseek-v4-flash-latest"'::JSONB,
    description = 'OpenRouter model slug used for LLM operations.',
    updated_at = CURRENT_TIMESTAMP
WHERE prop_key = 'LLM_MODEL'
  AND prop_value #>> '{}' IN ('qwen3.5-4b', 'qwen3-4b');

UPDATE sys_props
SET description = CASE prop_key
        WHEN 'LLM_REASONING_ENABLED'
            THEN 'Request OpenRouter reasoning and preserve private continuation details.'
        ELSE description
    END,
    is_editable = TRUE,
    updated_at = CURRENT_TIMESTAMP
WHERE prop_key IN ('LLM_MODEL', 'LLM_REASONING_ENABLED');

COMMIT;
