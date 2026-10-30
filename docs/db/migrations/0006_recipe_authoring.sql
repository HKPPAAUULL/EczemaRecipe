-- Migration 0006: recipe authoring — steps/notes/is_original/external_key
-- plus CREATE OR REPLACE VIEW so published_recipe exposes the new columns
-- (the view is SELECT * FROM recipe; column list is fixed at creation).
BEGIN;
ALTER TABLE recipe ADD COLUMN IF NOT EXISTS steps text[] NOT NULL DEFAULT '{}';
ALTER TABLE recipe ADD COLUMN IF NOT EXISTS notes text;
ALTER TABLE recipe ADD COLUMN IF NOT EXISTS is_original boolean NOT NULL DEFAULT false;
ALTER TABLE recipe ADD COLUMN IF NOT EXISTS external_key text;
CREATE UNIQUE INDEX IF NOT EXISTS recipe_external_key_key ON recipe (external_key) WHERE external_key IS NOT NULL;
COMMENT ON COLUMN recipe.steps IS '烹調步驟（逐項）；原創食譜才有內容';
COMMENT ON COLUMN recipe.notes IS '備註（原創食譜）';
COMMENT ON COLUMN recipe.is_original IS '站方原創食譜（後台建立/CSV 匯入；爬蟲食譜為 false）';
COMMENT ON COLUMN recipe.external_key IS '匯入用穩定鍵（CSV recipe_id）；同 key 的後續匯入為更新而非新增';
CREATE OR REPLACE VIEW published_recipe AS
SELECT * FROM recipe
 WHERE status = 'published' AND cardinality(unmatched_ingredients) = 0;
COMMENT ON VIEW published_recipe IS '對外發佈的食譜：status=published 且無未配對食材（安全關鍵：有未識別食材的食譜不公開）';
COMMIT;
