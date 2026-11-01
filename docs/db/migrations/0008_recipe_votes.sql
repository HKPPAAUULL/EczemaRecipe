-- 0008_recipe_votes.sql — anonymous recipe like/dislike votes
-- Each voter is identified by a client-generated opaque key stored in
-- localStorage (no login); one vote per (recipe_id, voter_key), re-voting
-- updates the row, vote removed client-side deletes it via the API.

CREATE TABLE IF NOT EXISTS recipe_vote (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    recipe_id   bigint NOT NULL REFERENCES recipe (id) ON DELETE CASCADE,
    voter_key   text NOT NULL,
    vote        smallint NOT NULL CHECK (vote IN (-1, 1)),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (recipe_id, voter_key)
);

CREATE INDEX IF NOT EXISTS recipe_vote_recipe_idx ON recipe_vote (recipe_id);

COMMENT ON TABLE recipe_vote IS '匿名食譜投票：voter_key 為瀏覽器 localStorage 產生的不透明鍵；vote=1 讚好、-1 不讚好';
COMMENT ON COLUMN recipe_vote.voter_key IS '客戶端產生的匿名識別碼（非個人資料），用於去重與改票';
