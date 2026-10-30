# AGENTS.md — 濕疹食譜網站

## 專案概述
一站式濕疹食譜網站（繁體中文）：食材適合度查詢、按手上食材配對食譜並提示致敏、食材分類庫。含爬蟲資料管線。免登入版本優先。

## 最高原則
1. **一律按 `docs/PLAN.md`（方案書）開發。** 開工前先讀方案書；不得偏離。
2. **方案有變更時，必須同步更新 `docs/PLAN.md`**：修改相關章節、更新階段狀態（§9）、並在 §13 變更記錄加一行（日期、版本、內容）。重大方向改變先詢問用戶。
3. UI 設計初稿來自 Google Stitch（提示詞在 `docs/STITCH_PROMPTS.md`）；以設計 token 與元件重寫，不直接照搬輸出。
4. 與用戶溝通使用繁體中文（香港用語習慣）。

## 版本控制與發佈（強制）
- 開始實際製作網站後，**每完成一個版本（可運作的里程碑）必須自動 commit 並 push 到 GitHub**，不需再逐次詢問。
- 每個版本須：
  1. 更新 `CHANGELOG.md`（Keep a Changelog 格式：版本、日期、Added/Changed/Fixed）。
  2. 以 Conventional Commits 撰寫 commit 訊息（`feat:`、`fix:`、`docs:`、`chore:`），內文簡述更新內容。
  3. 打語意化版本 tag（如 `v0.2.0`）並 push tag。
  4. 如 PLAN.md 階段狀態有變，一併更新。
- 絕不 commit 密鑰（`.env`、API key、Cloudflare token）；確保 `.gitignore` 涵蓋。
- 不 force-push、不改寫歷史。若 remote 尚未設定，先詢問用戶 GitHub repo 網址。
- 2026-10-29 用戶已確認「開始製作」：進入開發階段，按方案書 §9 階段推進；每個版本完成並驗證後自動 commit、更新 CHANGELOG、打 tag 並 push。
- 2026-10-30 用戶決定：**不寄授權信**；需授權的來源一律不爬，只用開放授權／明確允許的來源，並持續尋找更多（見 PLAN §4.5）。
- 範圍：第一版只做核心功能（見 `docs/DESIGN_REVIEW.md`）；中醫內容只可作「傳統說法」，不影響評級。

## 技術棧（摘要，詳見方案書）
- 前端：Next.js + TypeScript + Tailwind（Mobile-first 響應式）
- 後端：Python FastAPI
- 資料庫：PostgreSQL
- 爬蟲：Scrapy + Playwright + extruct；LLM 輔助用 Google Gemini API
- 部署：Docker Compose，跑在用戶自有 Windows 常駐電腦，經 Cloudflare Tunnel 對外
- 預算：免費優先，不引入付費服務

## 安全與合規規則
- 健康內容保守表達：評級為 🟢/🟡/🔴，必附原因與來源；不作診斷；每頁有免責聲明。
- LLM 生成的醫療相關內容必須標為待審核，人工確認後才發佈。
- 爬蟲來源不得為 AI 生成內容的網站；入選來源須記錄於 `docs/SOURCES.md`（見方案書 §4.4）。
- GitHub repo：https://github.com/HKPPAAUULL/EczemaRecipe
- 爬蟲：遵守 robots.txt 與服務條款，限速，設 User-Agent；只存標題、食材、簡短摘要與原文連結，不全文複製。
- 食譜配對與致敏警示邏輯屬安全關鍵，必須有單元測試。

## 開發慣例
- 完成後驗證（lint、typecheck、測試、必要時實際啟動）再 commit。
- 優先沿用既有檔案與模式；不寫多餘文件（本檔、PLAN.md、CHANGELOG.md、STITCH_PROMPTS.md 除外）。
- 驗證指令在建立專案後補充於此處：
  - Lint：`ruff check backend`
  - 單元測試：`python -m pytest backend/tests -q`（整合測試需設 `TEST_DATABASE_URL`，見 `.env.example`）
  - 種子驗證（免 DB）：`cd backend && python -m app.cli import-seed --validate-only`
  - 營養資料（TFDA）：`cd backend && python -m app.cli import-nutrition --download`（原始檔→`data/raw/`，不入版控）→ `--build`（產生 `data/reference/nutrition_tfda.csv`＋配對報告）→ `--validate-only` 驗證 → `python -m app.cli import-nutrition` 匯入（設 `DATABASE_URL`；`--dry-run` 試跑）
  - 起 DB：`docker compose up -d db`（首次自動執行 `docs/db/*.sql`）；停：`docker compose down`（保留 volume）
  - 匯入種子：`cd backend && python -m app.cli import-seed`（先設 `DATABASE_URL` 指向 `127.0.0.1`；`--dry-run` 試跑）
  - 後台：設 `ADMIN_TOKEN`（≥16 字元）才啟用 `/admin`（僅限本機，不得經 Cloudflare Tunnel 公開）；`cd backend && ADMIN_TOKEN=... uvicorn app.main:app --port 8010`；既有 DB 升級用 `docs/db/migrations/0005_audit_log.sql`
  - 前端 BFF：`/api/ingredients/search`、`/api/recipes/suggest`；localStorage key：`ek:v1:allergen-exclusions`、`ek:v1:shopping-list`
  - 啟動 API：`cd backend && uvicorn app.main:app --reload`（env：`DATABASE_URL` 必需；`APP_ENV`、`INCLUDE_DRAFTS`、`CORS_ORIGINS` 見 `.env.example`；production 下 `INCLUDE_DRAFTS` 必須為 false）
  - 食譜爬蟲：`cd backend && python -m app.cli crawl-recipes --source hakka [--download] [--limit N] [--dry-run] [--validate-only]`（設 `DATABASE_URL`；報告寫 `data/reference/recipe_match_report_hakka.md`）
  - 前端：`cd frontend`；`npm run lint`（eslint）、`npm run typecheck`（tsc --noEmit）、`npm test`（vitest）、`npm run build`、`npm run dev`/`npm start`（env：`API_BASE_URL`，預設 `http://127.0.0.1:8000`）

## 文件索引
- `docs/PLAN.md` — 方案書（開發依據）
- `docs/STITCH_PROMPTS.md` — Google Stitch 提示詞
- `docs/DESIGN_REVIEW.md` — Stitch 設計稿審查：可用部分、必須修正項、用戶決定（品牌名「濕疹食堂」、第一版範圍）
- `stitch_eczema_kitchen/` — Stitch 匯出（參考用；其中示意文獻、療效宣稱與 Level 分級不得直接採用）
- `docs/SOURCES.md` — 食譜／資料來源與條款核實
- `docs/RATING_CRITERIA.md` — 食材濕疹評級準則（評級唯一標準）
- `docs/DEPLOY_LOCAL.md` — 本機 Docker 測試部署步驟（可在新機重現）
- `docs/db/` — PostgreSQL schema 與初始資料
- `data/seed/`、`data/reference/` — 食材種子草稿、過敏原關鍵字、同義詞表（草稿須人工審核）
- `CHANGELOG.md` — 版本更新記錄（開始建站時建立）
