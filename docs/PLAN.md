# 濕疹食譜一站式網站 — 方案書

> 版本：v0.1（規劃階段）｜語言：繁體中文｜狀態：尚未開始開發
> 本文件為開發的唯一依據。方案有變更時必須更新本文件並在「變更記錄」留底。

## 1. 產品定位

濕疹人士的「食材查詢 + 煮餸靈感 + 買餸分類庫」工具，免登入版本優先。

### 核心功能
1. **食材查詢**：搜尋指定食材是否適合濕疹人士食用，顯示營養成分、評級原因與參考來源。
2. **食譜配對**：選擇手上已有的多項食材，推薦對濕疹有益的食譜；若食材有致敏機會，須明確警示。
3. **食材分類庫**：按食物種類（肉類、蔬菜、水果、海鮮、穀物、奶蛋、豆類等）列出食材，供買餸用。
4. （附加）買餸清單，存於瀏覽器 localStorage。

### 醫療免責與評級原則
- 網站只提供參考資訊，不作診斷；每頁顯示免責聲明，建議嚴重者諮詢醫生或營養師。
- 評級分三級，不下絕對結論，並必須附原因與來源：
  - 🟢 一般適合 ／ 🟡 因人而異、少量 ／ 🔴 常見致敏或誘發
- 評級維度：九大過敏原、組織胺、水楊酸、鎳、促炎／抗炎營養（Omega-3、維他命D、鋅等）、交叉過敏。
- 任何由 LLM 生成的醫療相關文字必須經人工審核才可發佈。

## 2. 已確認的條件與限制

| 項目 | 內容 |
|---|---|
| 語言 | 繁體中文為主 |
| 預算 | 免費起步 |
| 已有資源 | 自有 domain 並已設定 Cloudflare Tunnel；Google Gemini Pro；GitHub Copilot Pro；一部長期開機電腦（Windows）作 server |
| 食譜來源 | 香港、台灣食譜網站 |
| 用戶系統 | 第一版免登入 |
| UI 初稿 | Google Stitch，須響應式（手機＋電腦） |

## 3. 系統架構

```
[爬蟲/資料管線] → [PostgreSQL] ← [FastAPI 後端] ← [Next.js 前端]
   排程執行          資料庫          API              響應式網站
                                          ↑
                         Cloudflare Tunnel → 自有 domain
```

全部服務以 **Docker Compose** 部署在自有常駐電腦，經 Cloudflare Tunnel 對外，無需開 port、無主機費用。

### 技術選型
| 層 | 技術 | 備註 |
|---|---|---|
| 前端 | Next.js + TypeScript + Tailwind CSS | SSR/SSG 利於 SEO；Mobile-first |
| 後端 | Python FastAPI | 與爬蟲共用語言與模型 |
| 資料庫 | PostgreSQL（`pg_trgm` 模糊搜尋、JSONB 存原始資料） | 繁中搜尋需配合別名表；日後可評估 `pg_bigm`/zhparser |
| 爬蟲 | Scrapy + Playwright + `extruct`（schema.org/Recipe JSON-LD） | 優先解析結構化資料 |
| 排程 | 起步：Windows 工作排程器或 Docker 內 cron/APScheduler | 日後需要再上 Celery + Redis |
| LLM 輔助 | Google Gemini API（用現有方案／免費額度） | 用於食材抽取、摘要、原因草稿；須人工審核 |
| 對外 | Cloudflare Tunnel（已具備） | 可加 Cloudflare 快取與 WAF |
| 版本控制 | GitHub（Copilot Pro 輔助開發）、GitHub Actions 做 CI | |
| 備份 | 每日 `pg_dump` 到本機另一磁碟，可選同步雲端 | |

## 4. 爬蟲與資料來源

### 4.1 資料來源（優先官方 API，其次爬網頁）
1. **營養**：USDA FoodData Central API、Open Food Facts、香港食安中心食物成分資料庫（本地食材）、台灣食品營養成分資料庫（衛福部 TFDA，開放資料）。
2. **濕疹與食物證據**：PubMed E-utilities API（只存標題、摘要、連結）。
3. **食譜**：香港、台灣食譜站（候選站點待逐一檢查 robots.txt、服務條款與 JSON-LD 支援後定案，見 §10）。另自建一批原創食譜作核心內容。
4. **本地化**：食材繁中名、粵語／台灣用語、英文名對照表（自建，列入 `ingredient.aliases`）。

### 4.2 管線
```
抓取 → 清洗/標準化 → 食材配對 → 過敏原自動標記 → 人工審核佇列 → 發佈
```
- 食材標準化：「雞胸肉 200g」拆為食材/數量/單位，配對標準食材表（規則＋同義詞表，Gemini 輔助處理疑難）。
- 過敏原關鍵字表自動標記食譜致敏標籤。
- 增量更新（內容 hash 比對）、失敗重試、結構變更告警。

### 4.3 合規規則（強制）
- 遵守 robots.txt 與各站服務條款；限速 1–2 秒/請求；明確 User-Agent。
- 食譜只存標題、食材清單、簡短摘要與**原文連結**，不全文複製步驟；圖片不轉存（除非有授權）。
- 記錄來源 URL 與抓取時間。
- 若某站條款禁止爬取，改為不爬或聯絡授權。

### 4.4 來源可信度規則（用戶要求）
- **排除 AI 生成內容的網站**（資料不可信）：如內容農場、自動生成食譜／營養文章的站點。
- 優先：有真實作者／編輯團隊、有註明來源、營養資料引用官方資料庫的網站；官方／學術／政府機構資料優先於食譜部落格。
- 入選前人工抽查：作者署名、發佈歷史、食譜是否有實拍成品與合理份量、有無「AI 生成」跡象；結果記錄於 `docs/SOURCES.md`。
- 營養與濕疹相關結論只可引用官方資料庫與學術文獻（USDA、食安中心、TFDA、PubMed），食譜站只作食譜來源。

## 5. 資料庫設計（核心表）

```
ingredient(id, name_zh, name_en, aliases[], category_id, eczema_rating,
           rating_reason, reviewed, updated_at)
food_category(id, name_zh, parent_id, sort_order)
nutrient(id, name, unit)
ingredient_nutrient(ingredient_id, nutrient_id, amount_per_100g, source_id)
allergen(id, name, type)                     -- 九大過敏原/組織胺/水楊酸/鎳
ingredient_allergen(ingredient_id, allergen_id, severity, note)
evidence(id, ingredient_id, title, url, summary, source_type, year)
recipe(id, title, description, cook_time, servings, image_url,
       source_url, source_name, status, eczema_friendly_score)
recipe_ingredient(recipe_id, ingredient_id, raw_text, qty, unit, is_staple)
recipe_tag(recipe_id, tag)
crawl_job(id, source, started_at, status, stats)
review_queue(id, entity_type, entity_id, status, reviewer_note)
```

## 6. API 設計

- `GET /ingredients/search?q=` 模糊搜尋（含別名）
- `GET /ingredients/{id}` 詳情：評級、原因、營養、致敏原、證據
- `GET /categories`、`GET /categories/{id}/ingredients`
- `POST /recipes/suggest` — `{ingredient_ids, exclude_allergens}` → 食譜＋警示
- `GET /recipes/{id}`
- `GET /allergens`

### 食譜配對演算法
1. 覆蓋率 = 命中食材數 / 食譜食材數（常備調味料 `is_staple` 不計）。
2. 排除或降權含用家忌口過敏原的食譜。
3. **警示**：用家所選食材本身為 🔴 或含過敏原時，結果頂部顯示警示橫幅；食譜卡片顯示過敏原標籤。
4. 排序：覆蓋率 × 濕疹友善分數。
5. 此邏輯為安全關鍵功能，必須有單元測試。

## 7. 介面設計

### 7.1 頁面
1. 首頁：大搜尋框＋三個入口＋免責聲明
2. 食材查詢頁／食材詳情
3. 食譜配對頁：多選食材 chips＋忌口設定 → 食譜卡片（致敏警示、缺少食材、烹飪時間）
4. 食材分類庫：按種類、可篩選評級、可加入買餸清單
5. 食譜詳情：致敏食材高亮、來源連結
6. 買餸清單（localStorage）
7. 關於／資料來源／免責聲明

### 7.2 響應式
- Mobile-first；手機底部導航列、單欄、點擊區域 ≥ 44px；電腦頂部導航、多欄網格。
- 評級以顏色＋圖示＋文字三重表達（無障礙）。
- 柔和低刺激配色（淺綠／米白）。字體：繁中使用 Noto Sans TC。

### 7.3 Google Stitch 工作流
1. 用 `docs/STITCH_PROMPTS.md` 生成各頁（手機＋桌面）。
2. 迭代至風格統一，匯出 HTML/CSS 或 Figma。
3. 抽取設計 token 寫入 `tailwind.config`。
4. 以 Stitch 輸出作參考，重寫為 React 元件，不直接照搬。
5. 元件庫：`RatingBadge`、`IngredientChip`、`RecipeCard`、`AllergenTag`、`NutrientTable`、`WarningBanner`。

## 8. 部署（自有電腦）

- Docker Compose 服務：`db`（Postgres）、`api`、`web`、`crawler`（按需/排程）、`cloudflared`（或沿用現有 tunnel 設定）。
- Windows 注意：設定 Docker Desktop 開機自啟、電腦停用睡眠、備份目錄放另一磁碟。
- 對外只經 Cloudflare Tunnel；DB 不對外暴露；密鑰放 `.env`（不入版控）。

## 9. 開發階段

| 階段 | 內容 | 狀態 |
|---|---|---|
| 0. 準備 | 方案書、agents.md、Stitch 設計稿、確定來源站點合規清單 | 完成（授權徵詢信待寄） |
| 1. 資料基礎 | DB schema、營養資料匯入、約 150 種常見食材人工評級種子資料 | 進行中（v0.1.0：專案骨架、Docker Compose、種子匯入器、CI；營養資料匯入待做） |
| 2. 後端 API | 搜尋、詳情、分類、食譜配對 | 進行中（v0.2.0：食材搜尋／詳情／分類／過敏原 API 已完成；食譜配對待階段 4） |
| 3. 前端 MVP | 首頁、食材查詢、分類庫（功能 1、3） | 未開始 |
| 4. 食譜 | 爬蟲＋標準化＋配對＋警示（功能 2） | 未開始 |
| 5. 審核與品質 | 簡易審核介面、爬蟲監控、測試 | 未開始 |
| 6. 上線 | 部署、Tunnel、SEO、備份、免責/隱私頁 | 未開始 |

## 10. 待辦與未決事項

- [x] 來源條款第一輪核實完成（`docs/SOURCES.md`）：台灣政府開放資料與 TFDA 可用；Cookpad／iCook／香港政府網站需授權；CookWhatHK 不可用
- [ ] 寫信徵詢授權：衞生署長者健康服務（ehsenq@dh.gov.hk）／衞生防護中心（可否擷取食材清單並附原文連結）、Cookpad（info-tw@cookpad.com）、愛料理、國民健康署
- [ ] 補查未核實項目：國民健康署與 fae.moa.gov.tw 的 robots／條款、USDA 與 Open Food Facts 條款、醫院管理局食譜頁
- [ ] 食譜庫起步內容決定：自建原創食譜為主（客家委員會資料集多為重油傳統菜，不適合作濕疹飲食主力）
- [ ] 人工審核 `data/seed/ingredients_draft.csv`（163 項草稿，71 項標 needs_senior_review，22 項 unrated）
- [ ] 以真實 Postgres 16 驗證 `docs/db/schema.sql`（目前只用 pglast 驗證語法）
- [ ] 若日後有商業用途（廣告、會員），須重新檢視所有「非商業限定」來源
- [x] Stitch 設計稿已匯出（`stitch_eczema_kitchen/`），審查結果見 `docs/DESIGN_REVIEW.md`；design token 於開始製作前端時抽取
- [ ] 設計傳統說法（中醫）資料表與「資料不足」「傳統說法」元件設計
- [ ] 決定繁中全文搜尋方案（別名表 + pg_trgm 是否足夠）
- [ ] 決定審核介面形式（簡易後台頁 vs 直接改資料庫）

## 11. 風險

| 風險 | 對策 |
|---|---|
| 健康資訊錯誤 | 保守分級、附來源、人工審核、免責 |
| 爬蟲被封／違反條款 | 優先 API、限速、只存摘要與連結 |
| 版權 | 不全文複製，自建原創食譜 |
| 食材配對不準 | 同義詞表＋審核佇列＋持續修正 |
| 自架 server 停電/斷網 | 每日備份、自動重啟、Cloudflare 靜態快取 |

## 12. 版本與發佈規範

- 採語意化版本（`v0.1.0`…），每個可用版本：更新 `CHANGELOG.md` → commit → 打 tag → push 到 GitHub。
- Commit 訊息採 Conventional Commits（`feat:`、`fix:`、`docs:`、`chore:`）。

## 13. 變更記錄（方案書）

| 日期 | 版本 | 內容 |
|---|---|---|
| 2026-10-29 | v0.1 | 初版：整合預算、自架部署、Gemini、香港/台灣食譜來源、免登入版本 |
| 2026-10-29 | v0.1.1 | 新增 §4.4 來源可信度規則（排除 AI 生成網站）；設定 GitHub repo |
| 2026-10-29 | v0.1.6 | v0.2.0 唯讀 API：食材搜尋、詳情、分類庫、過敏原；以 INCLUDE_DRAFTS 控制草稿可見性（預設只顯示已審核；production 禁止開啟） |
| 2026-10-29 | v0.1.5 | 進入開發階段；v0.1.0 完成專案骨架（FastAPI、Postgres Docker Compose、種子匯入器、GitHub Actions CI）；schema 新增 needs_senior_review、evidence 唯一約束、data_source.kind='web'、allergen『花粉交叉』 |
| 2026-10-29 | v0.1.4 | 收到 Stitch 設計稿；新增 `docs/DESIGN_REVIEW.md`。品牌定名「濕疹食堂 Eczema Kitchen」；中醫內容以「傳統說法」獨立標示且不影響評級；第一版只做核心功能；記錄設計稿須修正項目（捏造文獻、療效宣稱、Level 分級等） |
| 2026-10-29 | v0.1.3 | 新增 `docs/RATING_CRITERIA.md` 評級準則、`docs/db/` schema 草稿、`data/seed/` 食材種子草稿、`data/reference/` 過敏原關鍵字與同義詞表；`docs/SOURCES.md` 完成條款核實 |
| 2026-10-29 | v0.1.2 | 新增 `docs/SOURCES.md` 來源初步評估；食譜策略改為「政府開放資料＋自建原創食譜」優先，社群平台後置 |
