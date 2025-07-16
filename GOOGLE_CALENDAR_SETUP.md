# Google Calendar API 設定指南

## 1. 獲取 Google Calendar API 憑證

### 步驟 1: 建立 Google Cloud 專案
1. 前往 [Google Cloud Console](https://console.cloud.google.com/)
2. 建立新專案或選擇現有專案
3. 啟用 Google Calendar API

### 步驟 2: 建立 OAuth 2.0 憑證
1. 在 Google Cloud Console 中，前往「APIs & Services」>「Credentials」
2. 點擊「Create Credentials」>「OAuth 2.0 Client IDs」
3. 選擇「Desktop application」
4. 下載 JSON 檔案並重新命名為 `credentials.json`

### 步驟 3: 設定憑證檔案
1. 將 `credentials.json` 放在專案根目錄
2. 確保檔案權限正確 (600)

## 2. 環境變數設定

在 `.env` 檔案中設定：

```bash
# Google Calendar API 設定
GOOGLE_CALENDAR_CREDENTIALS_FILE=credentials.json
GOOGLE_CALENDAR_TOKEN_FILE=token.json
GOOGLE_CALENDAR_SCOPES=https://www.googleapis.com/auth/calendar.readonly,https://www.googleapis.com/auth/calendar.events
GOOGLE_CALENDAR_ID=primary
```

## 3. 初次授權

第一次使用時，系統會：
1. 開啟瀏覽器進行 OAuth 授權
2. 授權後自動產生 `token.json`
3. 後續使用會自動刷新 token

## 4. 權限說明

### 最小權限設定
- `calendar.readonly`: 讀取行事曆
- `calendar.events`: 管理事件

### 完整權限設定
- `calendar`: 完整行事曆管理

## 5. 安全性注意事項

1. **檔案權限**：
   ```bash
   chmod 600 credentials.json
   chmod 600 token.json
   ```

2. **Git 忽略**：
   ```bash
   # 在 .gitignore 中添加
   credentials.json
   token.json
   ```

3. **生產環境**：
   - 使用服務帳戶 (Service Account) 
   - 設定適當的 IAM 角色
   - 使用 Google Cloud Secret Manager

## 6. 測試連接

```python
# 測試 Google Calendar API 連接
python -c "
from app.integrations.google_calendar import google_calendar
import asyncio

async def test():
    success = await google_calendar.initialize()
    print(f'Google Calendar API 連接: {success}')

asyncio.run(test())
"
```

## 7. 常見問題

### Q: 授權失敗
A: 檢查 credentials.json 檔案是否正確，確保 OAuth 2.0 設定正確

### Q: 權限不足
A: 確保 scopes 設定包含所需權限

### Q: Token 過期
A: 系統會自動刷新 token，如果失敗請重新授權

## 8. Docker 部署注意事項

### 問題說明
在 Docker 容器中使用 Google Calendar API 面臨以下挑戰：
- 容器內無法開啟瀏覽器進行 OAuth 授權
- 憑證檔案需要安全地傳遞到容器中
- token.json 需要持久化存儲

### 解決方案

#### 方案 1：本地授權 + Volume 掛載（推薦用於開發）

1. **本地授權**：
   ```bash
   # 建立憑證目錄
   mkdir credentials
   
   # 將憑證檔案放入目錄
   cp credentials.json credentials/
   
   # 本地運行授權
   python -c "
   import asyncio
   from app.integrations.google_calendar import google_calendar
   
   async def setup():
       success = await google_calendar.initialize()
       print(f'授權完成: {success}')
   
   asyncio.run(setup())
   "
   
   # 檢查 token.json 是否生成
   ls -la credentials/
   ```

2. **Docker 部署**：
   ```bash
   # 啟動服務（會自動掛載 credentials 目錄）
   docker-compose up -d
   ```

#### 方案 2：Service Account（推薦用於生產）

1. **建立 Service Account**：
   - 在 Google Cloud Console 建立 Service Account
   - 下載 service-account-key.json
   - 授予 Calendar API 權限

2. **更新配置**：
   ```bash
   # 更新 .env
   GOOGLE_CALENDAR_USE_SERVICE_ACCOUNT=true
   GOOGLE_CALENDAR_SERVICE_ACCOUNT_FILE=/app/credentials/service-account-key.json
   ```

3. **Docker 部署**：
   ```yaml
   # docker-compose.prod.yml
   services:
     aisales-api:
       environment:
         - GOOGLE_CALENDAR_USE_SERVICE_ACCOUNT=true
       volumes:
         - ./credentials/service-account-key.json:/app/credentials/service-account-key.json:ro
   ```

### 安全最佳實踐

1. **憑證檔案權限**：
   ```bash
   chmod 600 credentials/credentials.json
   chmod 600 credentials/token.json
   chmod 600 credentials/service-account-key.json
   ```

2. **Docker 安全掛載**：
   ```yaml
   volumes:
     - ./credentials:/app/credentials:ro  # 只讀掛載
   ```

3. **生產環境使用 Secrets**：
   ```yaml
   # docker-compose.prod.yml
   services:
     aisales-api:
       secrets:
         - google_calendar_credentials
         - google_calendar_token
   
   secrets:
     google_calendar_credentials:
       file: ./credentials/credentials.json
     google_calendar_token:
       file: ./credentials/token.json
   ```

### 故障排除

1. **授權失敗**：
   ```bash
   # 檢查憑證檔案是否存在
   docker-compose exec aisales-api ls -la /app/credentials/
   
   # 檢查環境變數
   docker-compose exec aisales-api env | grep GOOGLE_CALENDAR
   ```

2. **權限問題**：
   ```bash
   # 檢查檔案權限
   docker-compose exec aisales-api stat /app/credentials/credentials.json
   ```

3. **重新授權**：
   ```bash
   # 刪除舊的 token
   rm credentials/token.json
   
   # 重新授權
   python -c "
   import asyncio
   from app.integrations.google_calendar import google_calendar
   asyncio.run(google_calendar.initialize())
   "
   ```

### 降級模式

系統會自動檢測 Google Calendar API 可用性：
- 如果憑證不存在或無效，自動使用 Mock 模式
- 提供基本的行事曆功能模擬
- 確保服務在任何情況下都能正常運行

## 9. 監控和日誌

如果 Google Calendar API 不可用，系統會自動使用 Mock 模式：
- 隨機生成可用性資料
- 模擬會議創建
- 提供基本功能

## 9. 監控和日誌

系統會記錄：
- API 調用成功/失敗
- 授權狀態
- 錯誤資訊

查看日誌：
```bash
grep "google_calendar" logs/aisales.log
```
