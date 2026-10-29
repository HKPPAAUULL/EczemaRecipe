-- ============================================================================
-- 種子資料：food_category（食材分類）與 allergen（九大過敏原＋組織胺/水楊酸/鎳）
-- 在 schema.sql 之後執行：psql -d eczema_recipe -f seed_categories_allergens.sql
-- 可重複執行（ON CONFLICT DO NOTHING）
-- ============================================================================

BEGIN;

INSERT INTO food_category (name_zh, sort_order) VALUES
    ('肉類',         10),
    ('海鮮',         20),
    ('蔬菜',         30),
    ('水果',         40),
    ('穀物主食',     50),
    ('蛋奶',         60),
    ('豆類及豆製品', 70),
    ('堅果種子',     80),
    ('調味料',       90),
    ('油脂',        100),
    ('飲品',        110),
    ('其他',        120)
ON CONFLICT (name_zh) DO NOTHING;

INSERT INTO allergen (name_zh, name_en, type) VALUES
    ('蛋',           'egg',          'major_allergen'),
    ('奶',           'milk',         'major_allergen'),
    ('花生',         'peanut',       'major_allergen'),
    ('堅果(樹堅果)', 'tree nuts',    'major_allergen'),
    ('大豆',         'soy',          'major_allergen'),
    ('小麥',         'wheat',        'major_allergen'),
    ('魚',           'fish',         'major_allergen'),
    ('甲殼類',       'crustacean',   'major_allergen'),
    ('芝麻',         'sesame',       'major_allergen'),
    ('組織胺',       'histamine',    'histamine'),
    ('水楊酸',       'salicylate',   'salicylate'),
    ('鎳',           'nickel',       'nickel')
ON CONFLICT (name_zh) DO NOTHING;

COMMIT;
