-- Migration 0007: ingredient_tradition_note — 傳統說法（中醫）
-- DESIGN_REVIEW.md §4：獨立卡片、標示「傳統說法（非實證）」、不影響評級、
-- 每條須有來源、reviewed=true 才對外顯示。
BEGIN;
CREATE TABLE IF NOT EXISTS ingredient_tradition_note (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ingredient_id  bigint NOT NULL REFERENCES ingredient (id) ON DELETE CASCADE,
    tag            text NOT NULL DEFAULT 'other'
                   CHECK (tag IN ('fawu', 'sticky', 'warm_hot', 'cool', 'neutral', 'other')),
    note           text NOT NULL CHECK (length(btrim(note)) > 0),
    source_title   text,
    source_url     text,
    reviewed       boolean NOT NULL DEFAULT false,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    CHECK (source_title IS NOT NULL OR source_url IS NOT NULL),
    UNIQUE (ingredient_id, note)
);
COMMENT ON TABLE ingredient_tradition_note IS '傳統說法（中醫觀點）：非實證內容，獨立顯示且不影響評級；每條須有來源（書名或網址），reviewed=true 才對外顯示';
CREATE INDEX IF NOT EXISTS itn_ingredient_idx ON ingredient_tradition_note (ingredient_id);
CREATE INDEX IF NOT EXISTS itn_reviewed_idx ON ingredient_tradition_note (ingredient_id) WHERE reviewed;
DROP TRIGGER IF EXISTS trg_itn_updated_at ON ingredient_tradition_note;
CREATE TRIGGER trg_itn_updated_at BEFORE UPDATE ON ingredient_tradition_note
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
COMMIT;
