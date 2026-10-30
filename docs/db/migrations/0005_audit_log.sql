-- Migration 0005: audit_log — append-only audit trail for the /admin backend.
BEGIN;
CREATE TABLE IF NOT EXISTS audit_log (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_type text NOT NULL,
    entity_id   bigint NOT NULL,
    action      text NOT NULL,
    detail      jsonb NOT NULL DEFAULT '{}',
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS audit_log_entity_idx ON audit_log (entity_type, entity_id, id);
COMMENT ON TABLE audit_log IS '後台（/admin）所有食材/食譜改動的追加式稽核記錄；detail 為操作摘要（舊值/新值）';
COMMIT;
