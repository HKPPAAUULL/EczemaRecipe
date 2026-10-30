-- Migration 0004: recipe.unmatched_staples — unmatched items whose parsed name
-- is a staple condiment; they must NOT block published_recipe visibility.
BEGIN;
ALTER TABLE recipe ADD COLUMN IF NOT EXISTS unmatched_staples text[] NOT NULL DEFAULT '{}';
COMMENT ON COLUMN recipe.unmatched_staples IS '常備調味料中配對失敗的食材原文（不影響 published_recipe；致敏風險由 allergen_hints 關鍵字掃描覆蓋）';
COMMIT;
