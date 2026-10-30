# 本機 Docker 測試部署（DEPLOY_LOCAL）

> 目的：在任何一部新電腦（開發機或日後的常駐機）重現完整測試部署。指令以 PowerShell 為準，路徑相對於專案根目錄。
> 架構與正式部署原則見 `docs/PLAN.md` §8；此檔只記錄「怎樣把整套服務在本機跑起來並驗證」。

## 0. 先看這三點

1. **端口衝突**：Docker 需要 `127.0.0.1` 的 `5432`（db）、`8000`（api）、`3000`（web）。若本機已有 Postgres、uvicorn、`next dev/start` 在跑，要先停掉。
2. **匯入種子與爬蟲在電腦上跑，不在容器內**：`backend` 映像不包含 `data/`，`import-seed`、`import-nutrition`、`crawl-recipes` 從電腦連 `127.0.0.1:5432`（Docker 的 db 已對本機開放此端口）。
3. **schema 只在「全新 volume」自動套用**：`docs/db/schema.sql` 與 `seed_categories_allergens.sql` 只在第一次建立 `pgdata` 時執行。之後 schema 有改動，須手動套用 `docs/db/migrations/*.sql`。

## 1. 前置需求

| 項目 | 要求 |
|---|---|
| Docker Desktop | 已安裝並啟動；Windows 用 WSL2 後端 |
| Python | 3.12 或以上（匯入器與爬蟲在電腦上執行） |
| Git | 已 clone 專案 |

驗證：

```powershell
docker version
docker compose version
python --version
```

安裝 Python 依賴（只需一次）：

```powershell
cd backend
pip install -r requirements.txt
cd ..
```

## 2. 停掉會衝突的程序

```powershell
Get-NetTCPConnection -LocalPort 5432,8000,3000,8010 -State Listen -ErrorAction SilentlyContinue |
  Select-Object LocalPort, OwningProcess
```

有輸出就逐一結束（`Stop-Process -Id <PID>`）。若舊的免安裝 Postgres 在 `.tmp/`：

```powershell
.tmp\pg\pgsql\bin\pg_ctl.exe -D .tmp\pgdata stop
```

停止不會刪資料。

## 3. 建立 `.env`（不入版控）

```powershell
copy .env.example .env
```

編輯 `.env`：

| 變數 | 設定 |
|---|---|
| `POSTGRES_PASSWORD` | 自訂強密碼，不要用範例值 |
| `DATABASE_URL` | `postgresql://<POSTGRES_USER>:<密碼>@db:5432/<POSTGRES_DB>`；密碼須與上面一致，host 保持 `db`（容器內使用） |
| `APP_ENV` | 測試用 `development` |
| `INCLUDE_DRAFTS` | 測試用 `true`（才看到未審核的食材與食譜）；正式必須 `false` |
| `ADMIN_TOKEN` | 要用 `/admin` 就填 16 字元以上隨機字串；留空則 `/admin` 回 404 |

產生隨機 token（可選）：

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

確認 `.env` 沒被追蹤：`git status` 不應出現 `.env`。

## 4. 起服務

```powershell
docker compose up -d db
docker compose ps
```

等 db 顯示 `healthy`，確認表已建立（把 `<user>`、`<db>` 換成 `.env` 的值）：

```powershell
docker compose exec db psql -U <user> -d <db> -c "\dt"
```

應看到 `ingredient`、`recipe`、`audit_log` 等表。再建置並起 API 與網站（首次需數分鐘）：

```powershell
docker compose up -d --build api web
docker compose logs -f api web
```

日誌無錯誤即可（Ctrl+C 離開日誌，不影響服務）。

## 5. 匯入資料（在電腦上跑）

```powershell
cd backend
$env:DATABASE_URL = "postgresql://<user>:<密碼>@127.0.0.1:5432/<db>"
python -m app.cli import-seed --validate-only
python -m app.cli import-seed
python -m app.cli import-nutrition
python -m app.cli crawl-recipes --source hakka --download
cd ..
```

說明：
- `import-seed`：163 種食材草稿（全部 `reviewed=false`）。
- `import-nutrition`：用已入版控的 `data/reference/nutrition_tfda.csv`，不需上網。
- `crawl-recipes --download`：首次下載原始檔到 `data/raw/`（已 gitignore）；之後可省略 `--download`。
- 以上皆冪等，可重跑。

## 6. 驗證清單

| # | 檢查 | 預期 |
|---|---|---|
| 1 | `http://127.0.0.1:8000/health` | `{"status":"ok","db":true}` |
| 2 | `http://127.0.0.1:8000/docs` | API 文件可開啟 |
| 3 | `http://127.0.0.1:3000` | 首頁顯示「濕疹食堂」 |
| 4 | 搜尋「雞」 | 有結果；詳情頁有營養表 |
| 5 | 食材庫、關於頁 | 正常；不存在的食材網址為 404 |
| 6 | 食譜配對：選幾個食材 | 有食譜、有致敏警示 |
| 7 | 忌口設定勾「蛋」後再配對 | 食譜被排除並顯示排除數量 |
| 8 | 買餸清單：加入、勾選、重新整理 | 清單仍在 |

## 7. 後台審核（可選）

`.env` 已設 `ADMIN_TOKEN` 時，開 `http://127.0.0.1:8000/admin`，以 token 登入。

1. 審核 3–5 個食材（標記為已審核）。
2. 處理一道食譜的未配對食材並發佈（發佈條件：無未配對食材、所有食材已審核、至少 1 個非常備食材）。
3. 模擬正式狀態：把 `.env` 的 `INCLUDE_DRAFTS` 改為 `false`，執行 `docker compose up -d api`。公開網站應只顯示已審核食材與已發佈食譜。驗證後可改回 `true` 繼續開發。

> 後台只供本機／內網，**不得**經 Cloudflare Tunnel 公開；程式會拒絕帶 `Cf-Connecting-Ip`／`Cf-Ray` 的請求。

## 8. 重啟與持久化

```powershell
docker compose restart
docker compose down
docker compose up -d
```

資料應保留。**切勿加 `-v`**（`docker compose down -v` 會刪除整個資料庫 volume）。想從頭重來才用，並先備份。

自動開機：Docker Desktop 設定勾選「Start Docker Desktop when you sign in」；服務已設 `restart: unless-stopped`。

## 9. 升級既有資料庫（schema 有改動時）

依檔名順序，只套用尚未套用過的 migration（目前：`0003_recipe_pipeline.sql`、`0004_recipe_unmatched_staples.sql`、`0005_audit_log.sql`）：

```powershell
Get-Content docs\db\migrations\0005_audit_log.sql | docker compose exec -T db psql -U <user> -d <db>
```

全新 volume 不需要，因為 `schema.sql` 已包含所有變更。

## 10. 備份與還原（最基本版）

```powershell
docker compose exec -T db pg_dump -U <user> <db> > backup_$(Get-Date -Format yyyyMMdd).sql
Get-Content backup_YYYYMMDD.sql | docker compose exec -T db psql -U <user> -d <db>
```

備份檔放到另一個磁碟，不要放進專案目錄（含資料，勿入版控）。

## 11. 疑難排解

| 狀況 | 處理 |
|---|---|
| `port is already allocated` | 第 2 步沒停乾淨，再查 5432／8000／3000 |
| api 一直重啟 | `docker compose logs api`；常見：`.env` 缺 `DATABASE_URL`，或 `APP_ENV=production` 配 `INCLUDE_DRAFTS=true`（程式拒絕啟動） |
| 網站顯示後端不可用 | api 未就緒，或 `WEB_API_BASE_URL` 設錯（預設 `http://api:8000`） |
| `/admin` 回 404 | `.env` 未設 `ADMIN_TOKEN`（或少於 16 字元會啟動報錯）；改後須 `docker compose up -d api` |
| 改了 `schema.sql` 資料庫沒變 | 初始化只在新 volume 執行，見第 9 節 |
| 匯入器連不上 DB | 確認 `DATABASE_URL` 用 `127.0.0.1`（不是 `db`），且密碼與 `.env` 一致 |

## 12. 日後正式上線再做（不屬本次測試）

- 每日自動備份到另一磁碟。
- Cloudflare Tunnel：只轉發網站（`web`），不轉發 API 與 `/admin`。
- 電腦停用睡眠；Docker Desktop 開機自啟。
- `APP_ENV=production`、`INCLUDE_DRAFTS=false`、強密碼與 token。
