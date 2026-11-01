# deploy.md — 部署執行手冊（寫俾部署電腦上的 AI agent）

> **讀者**：在「實際部署電腦」上執行工作的 AI agent。
> 詳細指令參數不在此重複——本檔只交代**執行順序、閘口與底線**；
> 逐步指令請按需要翻閱 `docs/DEPLOY_LOCAL.md`（本機部署細節）與
> `docs/DEPLOY_PROD.md`（正式參數、Tunnel、檢查表）。
> 專案憲法：`AGENTS.md`；方案書：`docs/PLAN.md`。

## 0. 你要達成的終態

- `docker compose ps`：`db`、`api`、`web` 全部 `healthy/running`；
  tunnel 由既有主機 cloudflared（`pockettcm`）或 dockerized tunnel 提供，視 §3.4 路徑。
- `https://<用戶網域>` 公開可訪問，顯示「濕疹食堂」。
- `http://127.0.0.1:8000/admin` 只能本機進入；**公網訪問必須失敗**。
- 資料庫已有資料（新部署＝種子＋爬蟲匯入；遷移＝舊機 dump 已還原）。
- 每日自動備份排程已建立（需用戶確認後方可註冊）。

## 1. 開工前必須向用戶取得的資料

缺一項就停低問，不要自行假設：

| 資料 | 用途 | 備註 |
|---|---|---|
| 部署目標電腦確認 | 確認你正身處部署機 | Windows 常駐機，見 §2 |
| 公開網域 | `SITE_URL`、Tunnel hostname | 例：`eczema.example.com` |
| Cloudflare 接入方式 | 見 §3.4 三條路 | 本機已有 named tunnel `pockettcm`（PocketTCM）— 首選共用 |
| 資料庫密碼、ADMIN_TOKEN | `.env` | 可主動提議由你產生（`secrets.token_urlsafe(32)`） |
| 是否遷移 | 有冇舊機 `.dump` 備份要還原 | 有 → §3 步驟 4a；冇 → 4b |

## 2. 環境前置檢查（逐項驗證，失敗就報告停低）

```powershell
docker version            # Docker Desktop 必須已運行（WSL2 後端）
docker compose version
python --version          # ≥3.12，匯入器在本機跑
git --version
Get-NetTCPConnection -LocalPort 5432,8000,3000 -State Listen -ErrorAction SilentlyContinue
```

- 5432／8000／3000 被佔用 → 列出 PID 報告用戶，**不要**擅自 `Stop-Process`。
- **本機已知佔用**：`localhost:8081` 係 PocketTCM Flask、`cloudflared` 進程係 PocketTCM tunnel——正常運行中，**唔准停**。
- 未 clone：`git clone https://github.com/HKPPAAUULL/EczemaRecipe`（或用戶提供的 fork）。
- `cd backend && pip install -r requirements.txt`（匯入器依賴，只需一次）。

## 3. 執行順序（每步有閘口，過咗先做下一步）

### 3.1 `.env`

```powershell
copy .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

按 `DEPLOY_PROD.md` §1 檢查表填寫：

- `POSTGRES_PASSWORD` 強密碼；`DATABASE_URL` 密碼一致、host 保持 `db`。
- `ADMIN_TOKEN` ≥16 字元。
- `APP_ENV=production`；`INCLUDE_DRAFTS=false`（prod override 已強制，照填）。
- `SITE_URL=https://<網域>`。
- `CLOUDFLARE_TUNNEL_TOKEN`：token 模式先填；用既有 tunnel（cloudflared 已由其他方式跑）則留空。
- **閘口**：`git status` 確認 `.env` 未被追蹤。

### 3.2 起 DB ＋ 資料

```powershell
docker compose up -d db          # 等 healthy
docker compose exec db psql -U <user> -d <db> -c "\dt"
```

- **4a 遷移**：`.\scripts\restore.ps1 -File <備份.dump>`（主庫還原屬破壞性，腳本會先自動安全備份並要求輸入庫名確認——把確認交給用戶做）。
- **4b 新部署**：按 `DEPLOY_LOCAL.md` §5 依次跑 `import-seed`、`import-nutrition`、`crawl-recipes --source hakka --download`（SSL 失敗的已知問題見 `AGENTS.md`：改用 curl 下載 `data/raw/hakka_recipes.json` 再跑）。
- **閘口**：若資料庫非全新 volume，依序套用未套過的 `docs/db/migrations/*.sql`（冪等，可重跑；全新 volume 跳過）。

### 3.3 起全棧（正式設定）

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose ps                # api/web 應出現 (healthy)
```

**閘口——本機驗證全部通過先繼續**：

| 檢查 | 預期 |
|---|---|
| `http://127.0.0.1:8000/health` | `{"status":"ok","db":true}` |
| `http://127.0.0.1:3000` | 首頁「濕疹食堂」 |
| `/categories` 搜尋「雞」 | 有結果、詳情頁正常 |
| 食譜配對揀食材 → 找食譜 | 有結果＋致敏標示 |
| 未審核/草稿食材詳情 | **404**（`INCLUDE_DRAFTS=false`） |
| `http://127.0.0.1:8000/admin` | 可進入登入頁 |

### 3.4 Cloudflare Tunnel 對外

本機已有一條**本地管理嘅 named tunnel `pockettcm`**（服務 PocketTCM，`tcm.paulli09.xyz`），
config 喺 `C:\Users\pl960\.cloudflared\config.yml`。三條路揀一：

#### 路徑 A（首選）：共用既有 tunnel，加一個 hostname

一個 cloudflared 可以服務多個 hostname。改 `config.yml`，**新規則必須放喺
catch-all `http_status:404` 之前**：

```yaml
ingress:
  - hostname: pocket-tcm.paulli09.xyz
    service: http://localhost:8081
  - hostname: <濕疹食堂網域>            # 例：eczema.paulli09.xyz
    service: http://localhost:3000
  - service: http_status:404
```

然後：

```powershell
cloudflared tunnel route dns pockettcm <濕疹食堂網域>   # 建 DNS CNAME
```

重啟 tunnel 先生效：PocketTCM 嘅 cloudflared 係 `start_local.bat` 開嘅
console 窗口——閂咗「PocketTCM Tunnel」窗再重開（`cloudflared tunnel run pockettcm`），
**會令 PocketTCM 斷幾秒**，做之前同用戶講一聲。

此路徑下：**唔使** `--profile tunnel`、`CLOUDFLARE_TUNNEL_TOKEN` 留空。

#### 路徑 B：Zero Trust 後台加 hostname（dashboard 管理）

若 tunnel 係 dashboard 遠端管理：Zero Trust → Networks → Tunnels → `pockettcm` →
Public Hostnames → 加 `<網域> → http://localhost:3000`，DNS 自動建。

#### 路徑 C：獨立 dockerized tunnel

如要完全分開：新 token tunnel，token 寫 `.env`，
`docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile tunnel up -d`。
多數情況唔使——A 已夠。

**閘口——公網驗證**：
   - `https://<網域>` 回 200，顯示網站。
   - `https://<網域>/admin` 與 `https://<網域>:8000` 之類的 API 路徑**必須 404/被拒**；
     後台程式亦會拒絕帶 `Cf-Connecting-Ip`/`Cf-Ray` 的請求。
   - 用手機數據網絡再驗一次（排除本機 hosts 影響）。

### 3.5 常駐與備份

```powershell
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
```

- Docker Desktop → Settings → 「Start Docker Desktop when you sign in」。
- 備份：`.\scripts\backup.ps1` 先跑一次確認成功（輸出目錄不可在專案內）。
- 每日排程 `Register-ScheduledTask`（範例見 `DEPLOY_LOCAL.md` §10.4）——**需用戶明確同意先至註冊**。

## 4. 硬性規則（任何情況都唔准做）

1. **絕不** `docker compose down -v`（刪除整個資料庫 volume）。
2. **絕不**把 `api:8000` 或 `/admin` 經 Tunnel/公網公開；Public Hostname 只有一條：網域 → `http://web:3000`。
3. **絕不** commit `.env`、密碼、`ADMIN_TOKEN`、Cloudflare token、`.dump` 備份。
4. 還原主庫／任何破壞性 DB 操作前，**必須**先跑 `scripts/backup.ps1`。
5. `APP_ENV=production` 下 `INCLUDE_DRAFTS` 必須 `false`（程式會拒絕啟動，唔好諗住繞過）。
6. 爬蟲/匯入維持既有規矩：開放來源、限速、User-Agent；不爬 AI 生成食譜站。
7. 唔好用 `git checkout` 覆蓋部署機上未提交的改動；有疑問先問。

## 5. 完成後向用戶回報

逐項確認並貼證據（指令輸出摘錄）：

- [ ] `docker compose ps` 全部 healthy/running（含 cloudflared）
- [ ] `https://<網域>` 200 且顯示網站
- [ ] 公網訪問 `/admin` 失敗（404/403）；本機 `127.0.0.1:8000/admin` 可入
- [ ] 食材數／食譜數與預期相符（遷移：同舊機一致）
- [ ] 草稿食材詳情 404
- [ ] `backup.ps1` 至少成功跑過一次，檔案在專案外
- [ ] 睡眠已停用、Docker Desktop 開機自啟已勾
- [ ] 備份排程狀態（已註冊／待用戶決定）
- [ ] 未完成項目及原因

## 6. 出問題時

- 先 `docker compose logs api web` 同 `DEPLOY_LOCAL.md` §11 疑難排解表。
- 回滾：`git checkout <上一個 tag>` → `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`；資料問題用 `scripts/restore.ps1`。
- 連續兩次同一閘口失敗、或涉及用戶帳號/金錢/域名設定 → **停低問用戶**，唔好繼續試。
