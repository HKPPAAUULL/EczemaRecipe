# 正式部署（DEPLOY_PROD.md）

前提：已完成 `DEPLOY_LOCAL.md` 的本機部署；Docker Desktop 常駐。審核資料只存在資料庫，**上線／換環境前先用 `scripts/backup.ps1` 備份**。

## 1. 正式 `.env` 檢查表

| 變數 | 要求 |
|---|---|
| `POSTGRES_PASSWORD` / `DATABASE_URL` | 強密碼，兩者一致 |
| `ADMIN_TOKEN` | ≥16 字元隨機值 |
| `APP_ENV` | `production` |
| `INCLUDE_DRAFTS` | `false`（prod override 已強制，.env 設 true 也會被覆蓋） |
| `SITE_URL` | `https://你的網域` |
| `CLOUDFLARE_TUNNEL_TOKEN` | 只在啟用 tunnel 時填；勿提交 |

## 2. 啟動與驗證

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose ps        # api/web 應出現 (healthy)
```

驗證：`/health` ok；草稿食材詳情應 404（`INCLUDE_DRAFTS=false`）；`/admin` 仍只綁 `127.0.0.1:8000`。
回滾：`git checkout <上一個 tag>` → `docker compose up -d --build`；資料問題用 `scripts/restore.ps1` 還原。

## 3. Cloudflare Tunnel

1. Zero Trust 後台 → Networks → Tunnels → 建立 tunnel（token 模式），複製 token 寫入 `.env` 的 `CLOUDFLARE_TUNNEL_TOKEN`。
2. Public Hostname 只設一條：`你的網域` → `http://web:3000`。**不得**新增指向 `api:8000` 或 `/admin` 的 hostname/path。
3. 啟動：`docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile tunnel up -d`（沒有 token 時 cloudflared 會失敗退出，不影響其他服務）。
4. 既有 tunnel：在 Zero Trust 後台為既有 tunnel 新增 Public Hostname `你的網域 → http://web:3000` 即可。

建議設定：SSL/TLS = Full、Always Use HTTPS、Bot Fight Mode 開、Rate Limiting 對 `/api/*` 建議 60 req/min/IP、快取規則靜態資源可快取、`/api/*` 不快取。

## 4. 電腦常駐

```powershell
powercfg /change standby-timeout-ac 0   # 停用睡眠
powercfg /change hibernate-timeout-ac 0
```

Docker Desktop → Settings → 勾選「Start Docker Desktop when you sign in」。Windows 更新重開機後確認 `docker compose ps` 服務運行。

## 5. 備份排程

見 `DEPLOY_LOCAL.md` §10.4（`Register-ScheduledTask` 範例，需用戶自行執行）。

## 6. 上線前檢查表

- [ ] `/privacy` 聯絡方式已填寫（現為「待站長填寫」）
- [ ] `SITE_URL` 填真實網域
- [ ] 以公網 IP/手機網絡訪問 `https://網域/admin` 應 404/403，確認 `/admin` 不可經隧道到達（只綁 127.0.0.1:8000）
- [ ] `.env` 密碼與 `ADMIN_TOKEN` 已輪換為正式值
- [ ] `scripts/backup.ps1` 成功跑過一次且檔案在專案外
- [ ] 每頁有免責聲明；未有療效宣稱
