-- Migration 0003: recipe pipeline columns + stricter published_recipe view.
-- Apply to existing DBs: psql -d eczema_recipe -f docs/db/migrations/0003_recipe_pipeline.sql
BEGIN;
ALTER TABLE recipe ADD COLUMN IF NOT EXISTS unmatched_ingredients text[] NOT NULL DEFAULT '{}';
ALTER TABLE recipe ADD COLUMN IF NOT EXISTS allergen_hints text[] NOT NULL DEFAULT '{}';
ALTER TABLE recipe ADD COLUMN IF NOT EXISTS content_hash text;
COMMENT ON COLUMN recipe.unmatched_ingredients IS '配對失敗的食材原文（不得丟棄或猜測）；非空時食譜不得公開（見 published_recipe）';
COMMENT ON COLUMN recipe.allergen_hints IS '對全部食材原文（含未配對）做 allergen_keywords 掃描得到的過敏原名稱';
COMMENT ON COLUMN recipe.content_hash IS '內容雜湊：增量更新判斷，未變則跳過';
CREATE OR REPLACE VIEW published_recipe AS
SELECT * FROM recipe
 WHERE status = 'published' AND cardinality(unmatched_ingredients) = 0;
COMMENT ON VIEW published_recipe IS '對外發佈的食譜：status=published 且無未配對食材（安全關鍵：有未識別食材的食譜不公開）';
COMMIT;
