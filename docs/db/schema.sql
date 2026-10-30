-- ============================================================================
-- EczemaRecipe 資料庫結構（PostgreSQL 16）
-- 依據 docs/PLAN.md §5 設計。繁中食材庫、九大過敏原、營養、食譜、爬蟲與審核佇列。
-- 套用方式：psql -d eczema_recipe -f schema.sql
-- ============================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ---------------------------------------------------------------------------
-- ENUM 類型
-- ---------------------------------------------------------------------------
CREATE TYPE eczema_rating AS ENUM ('suitable', 'caution', 'trigger', 'unrated');
CREATE TYPE recipe_status AS ENUM ('draft', 'pending_review', 'published', 'rejected');
CREATE TYPE allergen_type AS ENUM ('major_allergen', 'histamine', 'salicylate', 'nickel', 'other');
CREATE TYPE severity AS ENUM ('low', 'medium', 'high');
CREATE TYPE review_status AS ENUM ('pending', 'approved', 'rejected');
CREATE TYPE crawl_job_status AS ENUM ('pending', 'running', 'succeeded', 'failed', 'cancelled');

COMMENT ON TYPE eczema_rating IS '濕疹適合度：suitable=🟢一般適合、caution=🟡因人而異少量、trigger=🔴常見致敏/誘發、unrated=未評級';
COMMENT ON TYPE recipe_status IS '食譜發佈流程：draft→pending_review→published / rejected';
COMMENT ON TYPE allergen_type IS '過敏原類型：major_allergen=九大過敏原，另組織胺/水楊酸/鎳/other';
COMMENT ON TYPE severity IS '致敏嚴重度（人工標註，供警示排序）';

-- ---------------------------------------------------------------------------
-- updated_at 自動更新觸發器
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- data_source — 外部資料來源登記（PLAN.md §5 無此表；為可追溯來源而加）
-- ---------------------------------------------------------------------------
CREATE TABLE data_source (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        text NOT NULL UNIQUE,
    url         text,
    license     text,
    kind        text NOT NULL CHECK (kind IN ('nutrition', 'recipe', 'evidence', 'allergen', 'manual', 'web')),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE data_source IS '外部資料來源登記（USDA、TFDA、食安中心、Open Food Facts、食譜站、人工輸入等）；license 記錄授權條款，配合 SOURCES.md 使用';
COMMENT ON COLUMN data_source.kind IS 'nutrition=營養資料、recipe=食譜來源、evidence=文獻/證據、allergen=過敏原資料、manual=人工輸入/原創、web=一般網頁來源（匯入器按網域自動建立）';

-- ---------------------------------------------------------------------------
-- food_category — 食材分類（§5）
-- ---------------------------------------------------------------------------
CREATE TABLE food_category (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name_zh     text NOT NULL UNIQUE,
    parent_id   bigint REFERENCES food_category (id) ON DELETE SET NULL,
    sort_order  integer NOT NULL DEFAULT 0,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE food_category IS '食材分類（肉類、蔬菜、水果……），parent_id 支援樹狀子分類，sort_order 控制分類庫頁面排序';

-- ---------------------------------------------------------------------------
-- ingredient — 標準食材主檔（§5）
-- ---------------------------------------------------------------------------
CREATE TABLE ingredient (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name_zh         text NOT NULL UNIQUE,
    name_en         text,
    aliases         text[] NOT NULL DEFAULT '{}',
    category_id     bigint REFERENCES food_category (id) ON DELETE SET NULL,
    eczema_rating   eczema_rating NOT NULL DEFAULT 'unrated',
    rating_reason   text,
    reviewed        boolean NOT NULL DEFAULT false,
    reviewed_at     timestamptz,
    needs_senior_review boolean NOT NULL DEFAULT false,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ingredient_rating_requires_reason CHECK (
        eczema_rating = 'unrated' OR length(btrim(rating_reason)) > 0
    )
);
COMMENT ON TABLE ingredient IS '標準食材主檔：中英文名、別名、分類、濕疹評級與原因。只有 reviewed=true 的列才可對外發佈（見 published_ingredient view）';
COMMENT ON COLUMN ingredient.aliases IS '港/台/英文同義名陣列，供模糊搜尋與食譜食材字串配對';
COMMENT ON COLUMN ingredient.eczema_rating IS 'suitable/caution/trigger 必須填 rating_reason（CHECK 約束）；unrated=未評級';
COMMENT ON COLUMN ingredient.reviewed IS '人工審核通過才可發佈；LLM 生成內容一律 reviewed=false 先入審核佇列';
COMMENT ON COLUMN ingredient.reviewed_at IS '人工審核通過時間';
COMMENT ON COLUMN ingredient.needs_senior_review IS '草稿中標記需資深審核（如證據弱或措辭需謹慎），見 docs/RATING_CRITERIA.md';

-- 名稱模糊搜尋（pg_trgm）
CREATE INDEX ingredient_name_zh_trgm_idx ON ingredient USING gin (name_zh gin_trgm_ops);
-- 別名精確包含搜尋（aliases @> ARRAY[...]）
CREATE INDEX ingredient_aliases_gin_idx ON ingredient USING gin (aliases);
-- 別名模糊搜尋（ILIKE '%...%' 跨陣列元素）
CREATE FUNCTION aliases_text(text[]) RETURNS text
    LANGUAGE sql IMMUTABLE PARALLEL SAFE
    AS $$ SELECT array_to_string($1, ' ') $$;
COMMENT ON FUNCTION aliases_text(text[]) IS 'array_to_string 為 STABLE 不能用於索引；此 IMMUTABLE 包裝供別名 trigram 索引與搜尋查詢共用（text[] 元素為 text 時結果穩定）';
CREATE INDEX ingredient_aliases_trgm_idx ON ingredient USING gin ((aliases_text(aliases)) gin_trgm_ops);
CREATE INDEX ingredient_category_idx ON ingredient (category_id);
CREATE INDEX ingredient_rating_idx ON ingredient (eczema_rating);
CREATE INDEX ingredient_reviewed_idx ON ingredient (reviewed) WHERE reviewed;

-- ---------------------------------------------------------------------------
-- nutrient / ingredient_nutrient — 營養成分（§5）
-- ---------------------------------------------------------------------------
CREATE TABLE nutrient (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        text NOT NULL,
    unit        text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (name, unit)
);
COMMENT ON TABLE nutrient IS '營養素定義（如 protein g、vitamin D µg、omega-3 g），name+unit 唯一';

CREATE TABLE ingredient_nutrient (
    ingredient_id   bigint NOT NULL REFERENCES ingredient (id) ON DELETE CASCADE,
    nutrient_id     bigint NOT NULL REFERENCES nutrient (id) ON DELETE RESTRICT,
    amount_per_100g numeric(10, 3) NOT NULL CHECK (amount_per_100g >= 0),
    source_id       bigint NOT NULL REFERENCES data_source (id) ON DELETE RESTRICT,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (ingredient_id, nutrient_id, source_id)
);
COMMENT ON TABLE ingredient_nutrient IS '每種食材每 100g 的營養含量；同一營養素可保留多個來源的數值（PK 含 source_id）';
COMMENT ON COLUMN ingredient_nutrient.source_id IS '數值出處（USDA/TFDA/食安中心等），可追溯來源';

-- ---------------------------------------------------------------------------
-- allergen / ingredient_allergen — 過敏原（§5）
-- ---------------------------------------------------------------------------
CREATE TABLE allergen (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name_zh     text NOT NULL UNIQUE,
    name_en     text,
    type        allergen_type NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE allergen IS '過敏原主檔：九大過敏原（type=major_allergen）＋組織胺/水楊酸/鎳；種子資料見 seed_categories_allergens.sql';

CREATE TABLE ingredient_allergen (
    ingredient_id   bigint NOT NULL REFERENCES ingredient (id) ON DELETE CASCADE,
    allergen_id     bigint NOT NULL REFERENCES allergen (id) ON DELETE RESTRICT,
    severity        severity,
    note            text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (ingredient_id, allergen_id)
);
COMMENT ON TABLE ingredient_allergen IS '食材↔過敏原對應（含隱藏致敏形式）；severity 可留空待人工標註';
CREATE INDEX ingredient_allergen_allergen_idx ON ingredient_allergen (allergen_id);

-- ---------------------------------------------------------------------------
-- evidence — 評級證據/參考來源（§5）
-- ---------------------------------------------------------------------------
CREATE TABLE evidence (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ingredient_id   bigint NOT NULL REFERENCES ingredient (id) ON DELETE CASCADE,
    title           text NOT NULL,
    url             text,
    summary         text,
    source_type     text NOT NULL DEFAULT 'other' CHECK (length(btrim(source_type)) > 0),
    year            integer CHECK (year IS NULL OR (year >= 1800 AND year <= 2100)),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (ingredient_id, url)
);
COMMENT ON TABLE evidence IS '食材評級的參考證據：PubMed 文獻、官方資料庫條目等；只存標題、摘要與連結';
COMMENT ON COLUMN evidence.source_type IS '建議值：pubmed、usda、cfs、tfda、open_food_facts、guideline、other';
CREATE INDEX evidence_ingredient_idx ON evidence (ingredient_id);

-- ---------------------------------------------------------------------------
-- recipe / recipe_ingredient / recipe_tag — 食譜（§5）
-- ---------------------------------------------------------------------------
CREATE TABLE recipe (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title                   text NOT NULL,
    description             text,
    cook_time               integer CHECK (cook_time IS NULL OR cook_time >= 0),
    servings                integer CHECK (servings IS NULL OR servings > 0),
    image_url               text,
    source_url              text UNIQUE,
    data_source_id          bigint REFERENCES data_source (id) ON DELETE SET NULL,
    status                  recipe_status NOT NULL DEFAULT 'draft',
    eczema_friendly_score   numeric(5, 2) CHECK (eczema_friendly_score IS NULL OR (eczema_friendly_score >= 0 AND eczema_friendly_score <= 100)),
    unmatched_ingredients   text[] NOT NULL DEFAULT '{}',
    unmatched_staples       text[] NOT NULL DEFAULT '{}',
    allergen_hints          text[] NOT NULL DEFAULT '{}',
    content_hash            text,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE recipe IS '食譜：只存標題、簡述、時間份量、原文連結（§4.3 不全文複製）；status=published 才對外顯示（見 published_recipe view）';
COMMENT ON COLUMN recipe.cook_time IS '烹調時間（分鐘）';
COMMENT ON COLUMN recipe.source_url IS '原文連結，UNIQUE 防止重複匯入';
COMMENT ON COLUMN recipe.data_source_id IS '取代 PLAN.md §5 的 source_name 文字欄位，改為指向 data_source';
COMMENT ON COLUMN recipe.eczema_friendly_score IS '濕疹友善分數 0–100，配對排序＝覆蓋率×分數';
COMMENT ON COLUMN recipe.status IS 'draft=自建草擬、pending_review=待人工審核、published=已發佈、rejected=退回';
COMMENT ON COLUMN recipe.unmatched_ingredients IS '配對失敗的食材原文（不得丟棄或猜測）；非空時食譜不得公開（見 published_recipe）';
COMMENT ON COLUMN recipe.unmatched_staples IS '常備調味料中配對失敗的食材原文（不影響 published_recipe；致敏風險由 allergen_hints 關鍵字掃描覆蓋）';
COMMENT ON COLUMN recipe.allergen_hints IS '對全部食材原文（含未配對）做 allergen_keywords 掃描得到的過敏原名稱';
COMMENT ON COLUMN recipe.content_hash IS '內容雜湊：增量更新判斷，未變則跳過';

CREATE INDEX recipe_status_idx ON recipe (status);
CREATE INDEX recipe_title_trgm_idx ON recipe USING gin (title gin_trgm_ops);
CREATE INDEX recipe_data_source_idx ON recipe (data_source_id);

CREATE TABLE recipe_ingredient (
    recipe_id       bigint NOT NULL REFERENCES recipe (id) ON DELETE CASCADE,
    ingredient_id   bigint NOT NULL REFERENCES ingredient (id) ON DELETE RESTRICT,
    raw_text        text NOT NULL,
    qty             numeric(10, 3) CHECK (qty IS NULL OR qty >= 0),
    unit            text,
    is_staple       boolean NOT NULL DEFAULT false,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (recipe_id, ingredient_id)
);
COMMENT ON TABLE recipe_ingredient IS '食譜食材明細：raw_text 保留原文（如「雞胸肉 200g」），qty/unit 為標準化後數值';
COMMENT ON COLUMN recipe_ingredient.is_staple IS '常備調味料（鹽、油等）：計算覆蓋率時不計入食譜食材數（§6）';

-- 食譜配對：由手上食材反查食譜
CREATE INDEX recipe_ingredient_ingredient_idx ON recipe_ingredient (ingredient_id);

CREATE TABLE recipe_tag (
    recipe_id   bigint NOT NULL REFERENCES recipe (id) ON DELETE CASCADE,
    tag         text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (recipe_id, tag)
);
COMMENT ON TABLE recipe_tag IS '食譜標籤（如「清蒸」「低組織胺」「快煮」），供篩選';

-- ---------------------------------------------------------------------------
-- crawl_job / review_queue — 管線與審核（§5）
-- ---------------------------------------------------------------------------
CREATE TABLE crawl_job (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source      text NOT NULL,
    started_at  timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    status      crawl_job_status NOT NULL DEFAULT 'pending',
    stats       jsonb NOT NULL DEFAULT '{}',
    error       text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE crawl_job IS '爬蟲/匯入工作記錄；stats 存 JSON（抓取數、新增數、失敗數、內容 hash 等）';
COMMENT ON COLUMN crawl_job.source IS '來源識別（data_source.name 或網域名）';
CREATE INDEX crawl_job_status_idx ON crawl_job (status);

CREATE TABLE review_queue (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_type     text NOT NULL CHECK (entity_type IN ('ingredient', 'recipe', 'evidence', 'ingredient_allergen', 'recipe_ingredient')),
    entity_id       bigint NOT NULL,
    status          review_status NOT NULL DEFAULT 'pending',
    reviewer_note   text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE review_queue IS '人工審核佇列：LLM 生成或爬蟲標記的內容須審核後才發佈（§4.2）；entity_id 依 entity_type 指向對應表';
CREATE INDEX review_queue_pending_idx ON review_queue (status) WHERE status = 'pending';
CREATE INDEX review_queue_entity_idx ON review_queue (entity_type, entity_id);

-- ---------------------------------------------------------------------------
-- audit_log — 後台審核操作稽核（只追加）
-- ---------------------------------------------------------------------------
CREATE TABLE audit_log (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_type text NOT NULL,
    entity_id   bigint NOT NULL,
    action      text NOT NULL,
    detail      jsonb NOT NULL DEFAULT '{}',
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_log_entity_idx ON audit_log (entity_type, entity_id, id);
COMMENT ON TABLE audit_log IS '後台（/admin）所有食材/食譜改動的追加式稽核記錄；detail 為操作摘要（舊值/新值）';

-- ---------------------------------------------------------------------------
-- updated_at 觸發器
-- ---------------------------------------------------------------------------
CREATE TRIGGER trg_data_source_updated_at        BEFORE UPDATE ON data_source         FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_food_category_updated_at      BEFORE UPDATE ON food_category       FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_ingredient_updated_at         BEFORE UPDATE ON ingredient          FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_nutrient_updated_at           BEFORE UPDATE ON nutrient            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_ingredient_nutrient_updated_at BEFORE UPDATE ON ingredient_nutrient FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_allergen_updated_at           BEFORE UPDATE ON allergen            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_ingredient_allergen_updated_at BEFORE UPDATE ON ingredient_allergen FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_evidence_updated_at           BEFORE UPDATE ON evidence            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_recipe_updated_at             BEFORE UPDATE ON recipe              FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_recipe_ingredient_updated_at  BEFORE UPDATE ON recipe_ingredient   FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_recipe_tag_updated_at         BEFORE UPDATE ON recipe_tag          FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_crawl_job_updated_at          BEFORE UPDATE ON crawl_job           FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_review_queue_updated_at       BEFORE UPDATE ON review_queue        FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- 發佈視圖：只有經人工審核 / published 的內容才對外顯示
-- ---------------------------------------------------------------------------
CREATE VIEW published_ingredient AS
SELECT * FROM ingredient WHERE reviewed = true;
COMMENT ON VIEW published_ingredient IS '對外發佈的食材：display_status 規則＝只顯示 reviewed=true（LLM/爬蟲產生的內容未經人工審核不會出現）';

CREATE VIEW published_recipe AS
SELECT * FROM recipe
 WHERE status = 'published' AND cardinality(unmatched_ingredients) = 0;
COMMENT ON VIEW published_recipe IS '對外發佈的食譜：status=published 且無未配對食材（安全關鍵：有未識別食材的食譜不公開）';

COMMIT;
