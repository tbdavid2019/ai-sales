# AI Sales Multi-Agent 系統

一個基於 FastAPI 的多 Agent AI 銷售系統，提供 OpenAI 相容的 API 接口。

## 🚀 功能特色

- **OpenAI 相容 API**: 完全相容 OpenAI ChatGPT API，支援無縫整合
- **多 Agent 架構**: 智能路由系統，自動選擇最適合的 Agent
- **即時串流回應**: 支援 Server-Sent Events 串流輸出
- **智能記憶管理**: 基於 Redis 的會話記憶和用戶資料管理
- **RAG 知識檢索**: 整合向量資料庫進行知識問答
- **容器化部署**: 使用 Docker Compose 一鍵部署

```
streamlit run app_streamlit.py --server.port 8501 --server.address localhost
```

## 🏗️ 系統架構
```
┌─────────────────────────────────────────────────────────────┐
│                    三個 UI 介面                              │
├─────────────────┬─────────────────┬─────────────────────────┤
│   Gradio UI     │   Streamlit UI  │   FastAPI (port 8000)   │
│   (port 7860)   │   (port 8501)   │   OpenAI Compatible     │
└─────────────────┴─────────────────┴─────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│            統一核心處理 (ui_handler.py)                      │
│         process_user_request() 函數                         │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│               工作流管理 (workflow_manager)                   │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│          各種 Agent (Chat, Card, RAG, Vision, etc.)         │
└─────────────────────────────────────────────────────────────┘

```



```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   LINE Bot      │    │  Telegram Bot   │    │  Web Chat UI    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                 ┌───────────────────────────────┐
                 │     OpenAI Compatible API     │
                 └───────────────────────────────┘
                                 │
                 ┌───────────────────────────────┐
                 │        Control Agent          │
                 └───────────────────────────────┘
                                 │
         ┌───────────────┬───────────────┬───────────────┐
         │               │               │               │
   ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
   │ Chat Agent  │ │ RAG Agent   │ │Card Agent   │ │Calendar     │
   │             │ │             │ │             │ │Agent        │
   └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

## 🛠️ 技術棧

- **API 框架**: FastAPI + Uvicorn
- **LLM 模型**: Gemini 2.0 Flash, GPT-4, Claude 3
- **記憶管理**: Redis
- **向量資料庫**: ChromaDB
- **部署**: Docker + Docker Compose

## 📦 安裝與部署

### 1. 環境準備

```bash
# 複製專案
git clone <repository-url>
cd aisales

# 複製環境變數模板
cp .env.example .env
```

### 2. 配置環境變數

編輯 `.env` 文件，填入您的 API 金鑰：

```bash
# 主控 Agent - Gemini
GEMINI_API_KEY=your_gemini_api_key

# ChatAgent - Gemini  
CHAT_MODEL_API_KEY=your_gemini_api_key

# RAG Embedding - OpenAI
OPENAI_API_KEY=your_openai_api_key

# CalendarAgent - OpenAI
CALENDAR_API_KEY=your_openai_api_key

# CardAgent - OpenAI
VISION_API_KEY=your_openai_api_key

# RAGAgent - Gemini
RAG_MODEL_API_KEY=your_gemini_api_key

# Google Calendar API 設定 (可選)
GOOGLE_CALENDAR_CREDENTIALS_FILE=credentials.json
GOOGLE_CALENDAR_TOKEN_FILE=token.json
GOOGLE_CALENDAR_SCOPES=https://www.googleapis.com/auth/calendar.readonly,https://www.googleapis.com/auth/calendar.events
GOOGLE_CALENDAR_ID=primary
```

### 3. Google Calendar 整合 (可選)

CalendarAgent 支援真實的 Google Calendar API 整合：

1. **獲取 Google Calendar API 憑證**：
   - 前往 [Google Cloud Console](https://console.cloud.google.com/)
   - 建立專案並啟用 Google Calendar API
   - 建立 OAuth 2.0 憑證並下載 `credentials.json`

2. **設定憑證**：
   ```bash
   # 創建憑證資料夾
   mkdir -p ./credentials
   
   # 將憑證檔案放入
   mv ~/Downloads/credentials.json ./credentials/
   chmod 600 ./credentials/credentials.json
   ```

3. **首次授權**：
   - 第一次使用時會開啟瀏覽器進行授權
   - 授權後自動產生 `token.json`

4. **降級模式**：
   - 如果沒有設定 Google Calendar API，會自動使用 Mock 模式
   - 提供基本的行事曆功能模擬

詳細設定請參考：[Google Calendar 設定指南](GOOGLE_CALENDAR_SETUP.md)

### 4. 知識庫文檔處理

RAGAgent 支援自動 PDF 文檔處理和向量化：

1. **放置 PDF 文檔**：
   ```bash
   # 將您的 PDF 文檔放在 documents 資料夾
   cp /path/to/your/document.pdf ./documents/
   ```

2. **處理 PDF 文檔**：
   ```bash
   # 手動處理所有 PDF
   python process_pdfs.py
   
   # 或啟動自動處理服務
   python document_service.py
   ```

3. **支援的文檔類型**：
   - 產品介紹 PDF
   - 定價方案 PDF  
   - 使用手冊 PDF
   - 常見問題 PDF
   - 任何文字型 PDF

4. **自動分類和索引**：
   - 系統會根據檔案名稱自動分類
   - 長文檔會被分割成適當大小的塊
   - 生成向量嵌入並儲存到 ChromaDB
   - 支援增量處理，避免重複處理

5. **文檔更新策略**：
   - 每小時自動檢查新文檔
   - 每天午夜重新處理所有文檔
   - 基於檔案 hash 的智能更新檢測

### 4. 使用 Docker Compose 部署

#### 基本部署

```bash
# 構建和啟動服務
docker-compose up -d

# 查看服務狀態
docker-compose ps

# 查看日誌
docker-compose logs -f aisales-api
```

#### 含 Google Calendar 整合的部署

如果您想使用 Google Calendar 功能，需要額外的設定步驟：

1. **本地授權**（首次設定）：
   ```bash
   # 1. 先在本地完成 Google Calendar 授權
   mkdir credentials
   mv credentials.json credentials/
   
   # 2. 本地運行一次進行授權
   python -c "
   import asyncio
   from app.integrations.google_calendar import google_calendar
   
   async def setup():
       success = await google_calendar.initialize()
       print(f'授權完成: {success}')
   
   asyncio.run(setup())
   "
   
   # 3. 檢查 token.json 是否生成
   ls -la credentials/
   ```

2. **Docker 部署**：
   ```bash
   # 確保憑證目錄存在
   mkdir -p credentials
   
   # 將憑證檔案放入 credentials 目錄
   cp credentials.json credentials/
   # token.json 會在首次授權後自動生成
   
   # 啟動服務
   docker-compose up -d
   ```

3. **驗證部署**：
   ```bash
   # 檢查服務狀態
   docker-compose ps
   
   # 查看日誌確認 Google Calendar 連接狀態
   docker-compose logs -f aisales-api | grep -i "google\|calendar"
   
   # 測試 API
   curl -X POST http://localhost:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{
       "model": "aisales-v1",
       "messages": [{"role": "user", "content": "明天下午有空嗎？"}]
     }'
   ```

#### 生產環境部署建議

對於生產環境，建議使用 Google Cloud Service Account：

1. **建立 Service Account**：
   ```bash
   # 在 Google Cloud Console 建立 Service Account
   # 下載 service-account-key.json
   ```

2. **更新環境變數**：
   ```bash
   # 在 .env 中設定
   GOOGLE_CALENDAR_USE_SERVICE_ACCOUNT=true
   GOOGLE_CALENDAR_SERVICE_ACCOUNT_FILE=/app/credentials/service-account-key.json
   ```

3. **Docker Compose 設定**：
   ```yaml
   # docker-compose.prod.yml
   services:
     aisales-api:
       environment:
         - GOOGLE_CALENDAR_USE_SERVICE_ACCOUNT=true
         - GOOGLE_CALENDAR_SERVICE_ACCOUNT_FILE=/app/credentials/service-account-key.json
       volumes:
         - ./credentials/service-account-key.json:/app/credentials/service-account-key.json:ro
   ```

#### 故障排除

1. **Google Calendar 授權失敗**：
   ```bash
   # 檢查憑證檔案
   ls -la credentials/
   
   # 檢查容器內的憑證
   docker-compose exec aisales-api ls -la /app/credentials/
   
   # 重新授權
   docker-compose exec aisales-api python -c "
   import asyncio
   from app.integrations.google_calendar import google_calendar
   asyncio.run(google_calendar.initialize())
   "
   ```

2. **權限問題**：
   ```bash
   # 確保憑證檔案權限正確
   chmod 600 credentials/credentials.json
   chmod 600 credentials/token.json
   ```

3. **容器內無法授權**：
   - 必須先在本地完成授權
   - 然後將 `token.json` 掛載到容器中
   - 或使用 Service Account 進行授權

### 4. 本地開發環境

```bash
# 安裝依賴
pip install -r requirements.txt

# 啟動開發服務器
python main.py
```

## 🔧 使用方法

### API 端點

- **主要端點**: `http://localhost:8000`
- **📖 Swagger 文檔**: `http://localhost:8000/docs`
- **📋 OpenAPI 規範**: `http://localhost:8000/openapi.json`
- **🏥 健康檢查**: `http://localhost:8000/health`

### 📚 Swagger 文檔特色

我們的 Swagger 文檔包含完整的參數說明和使用範例：

#### 🎯 參數詳細說明
- **模型選擇**: 支援的模型和 Agent 組成
- **回應模式**: 虛擬人模式 vs 一般文字模式的差異
- **參數範圍**: 每個參數的有效範圍和建議值
- **使用場景**: 不同場景下的最佳參數組合

#### 🔧 互動式測試
- **Try it out**: 直接在文檔中測試 API
- **範例請求**: 預設的請求範例
- **回應預覽**: 即時查看 API 回應格式
- **錯誤處理**: 完整的錯誤回應說明

#### 📋 完整的端點說明
- **POST /v1/chat/completions**: 聊天完成端點
- **GET /v1/models**: 模型列表端點
- **GET /health**: 系統健康檢查
- **WebSocket /vision/ws**: 視覺分析端點

要查看完整的 Swagger 文檔，請啟動 API 服務後訪問：
```bash
# 啟動 API 服務
python main.py

# 在瀏覽器中打開 Swagger 文檔
open http://localhost:8000/docs
```

### 📋 API 參數詳細說明

#### OpenAI 相容端點

```bash
# 聊天完成 (非串流)
POST /v1/chat/completions

# 聊天完成 (串流)
POST /v1/chat/completions (with stream=true)

# 模型列表
GET /v1/models
```

#### 💡 核心參數

| 參數名稱 | 類型 | 必填 | 預設值 | 說明 |
|---------|------|------|--------|------|
| `model` | string | ✅ | - | 模型名稱，使用 "aisales-v1" |
| `messages` | array | ✅ | - | 對話訊息陣列 |
| `stream` | boolean | ❌ | false | 是否啟用串流回應 |
| `temperature` | float | ❌ | 0.7 | 回應創意度 (0.0-1.0) |
| `max_tokens` | integer | ❌ | 無限制 | 最大回應長度 |
| `top_p` | float | ❌ | 1.0 | 核心取樣參數 |
| `user` | string | ❌ | - | 用戶識別碼 |

#### 🎯 模式特化參數建議

**虛擬人模式** (簡短互動):
```json
{
  "model": "aisales-v1",
  "messages": [...],
  "max_tokens": 50,
  "temperature": 0.8,
  "stream": false
}
```

**一般文字模式** (詳細回應):
```json
{
  "model": "aisales-v1",
  "messages": [...],
  "max_tokens": 500,
  "temperature": 0.7,
  "stream": false
}
```

**RAG 知識查詢** (準確回應):
```json
{
  "model": "aisales-v1",
  "messages": [...],
  "max_tokens": 800,
  "temperature": 0.5,
  "stream": false
}
```

#### 🔄 訊息格式

```json
{
  "messages": [
    {
      "role": "system",
      "content": "系統提示詞 (可選)"
    },
    {
      "role": "user", 
      "content": "用戶訊息"
    },
    {
      "role": "assistant",
      "content": "AI 回應"
    }
  ]
}
```

#### 📤 回應格式

**非串流回應:**
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "aisales-v1",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "AI 回應內容"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 20,
    "total_tokens": 30
  }
}
```

**串流回應:**
```json
data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1677652288,"model":"aisales-v1","choices":[{"index":0,"delta":{"content":"AI"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1677652288,"model":"aisales-v1","choices":[{"index":0,"delta":{"content":" 回應"},"finish_reason":null}]}

data: [DONE]
```

### Gradio Web UI

除了 API 之外，本專案還提供一個互動式的 Gradio Web UI，方便您直接與 AI Sales 系統對話和測試。

**如何啟動:**

```bash
# 確保您已經安裝了所有依賴
pip install -r requirements.txt

# 啟動 Gradio 應用程式
python app_gradio.py
```

啟動後，您可以在瀏覽器中開啟 `http://localhost:7860` 來使用介面。

**Docker 啟動:**

如果您使用 Docker，Gradio 介面也會自動啟動。請確保 `docker-compose.yml` 中已開放 `7860` 連接埠。

```bash
# 啟動所有服務，包含 Gradio UI
docker-compose up -d

# 在瀏覽器中開啟
http://localhost:7860
```

### OpenAI 相容端點

```bash
# 聊天完成 (非串流)
POST /v1/chat/completions

# 聊天完成 (串流)
POST /v1/chat/completions (with stream=true)

# 模型列表
GET /v1/models
```

### 使用範例

```python
import openai

# 設定 API 基礎 URL
client = openai.OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="your-api-key"
)

# 基本聊天請求
response = client.chat.completions.create(
    model="aisales-v1",
    messages=[
        {"role": "user", "content": "你好，介紹一下你們的產品"}
    ],
    stream=False
)

print(response.choices[0].message.content)

# 使用虛擬人模式 (簡短回應)
response = client.chat.completions.create(
    model="aisales-v1",
    messages=[
        {"role": "user", "content": "你好，介紹一下你們的產品"}
    ],
    max_tokens=50,        # 限制回應長度
    temperature=0.8,      # 提高創意度
    stream=False
)

# 使用一般文字模式 (詳細回應)
response = client.chat.completions.create(
    model="aisales-v1",
    messages=[
        {"role": "user", "content": "你好，介紹一下你們的產品"}
    ],
    max_tokens=500,       # 允許較長回應
    temperature=0.7,      # 平衡創意度
    stream=False
)
```

### 參數說明

#### 🎯 回應模式控制

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `max_tokens` | int | 無限制 | 控制回應的最大長度 |
| `temperature` | float | 0.7 | 控制回應的創意度 (0.0-1.0) |
| `model` | string | "aisales-v1" | 模型名稱 |
| `stream` | boolean | false | 是否使用串流回應 |

#### 📝 建議設定

**虛擬人模式** (簡短、互動式回應):
```python
{
    "max_tokens": 20-200,
    "temperature": 0.8,
    "stream": false
}
```

**一般文字模式** (詳細、專業回應):
```python
{
    "max_tokens": 100-2000,
    "temperature": 0.7,
    "stream": false
}
```

#### 🔧 在 Streamlit UI 中使用

1. **選擇回應模式**：
   - 一般文字模式：提供詳細、專業的回應
   - 虛擬人模式：提供簡短、口語化的互動

2. **調整輸出參數**：
   - 回應長度：控制 AI 輸出的字數
   - 創意度：調整回應的創意程度

3. **即時預覽**：
   - 側邊欄顯示當前所有設定
   - 立即生效，無需重啟

#### 🎨 Gradio UI 中的模式切換

在 Gradio 界面中，您可以：
- 在「互動控制」標籤中選擇回應模式
- 系統會自動調整相應的參數設定
- 支援即時切換，無需重新載入頁面

### 串流使用

```python
# 串流回應
stream = client.chat.completions.create(
    model="aisales-v1",
    messages=[
        {"role": "user", "content": "你好"}
    ],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content is not None:
        print(chunk.choices[0].delta.content, end="")
```

## 🤖 Agent 說明

### ControlAgent (主控制器)
- **功能**: 分析用戶意圖，決定路由策略
- **模型**: Gemini 2.0 Flash Lite
- **職責**: 任務分發、結果整合

### ChatAgent (對話助理)
- **功能**: 處理一般銷售對話
- **模型**: Gemini 2.0 Flash Lite
- **職責**: 銷售話術、客戶互動

### RAGAgent (知識檢索)
- **功能**: 從知識庫檢索相關資訊
- **模型**: Gemini 2.0 Flash Lite
- **職責**: 產品問答、技術支援

### CardAgent (名片識別)
- **功能**: OCR 名片資訊提取
- **模型**: GPT-4 Vision
- **職責**: 圖片分析、客戶資料建檔

### CalendarAgent (行事曆管理)
- **功能**: 行事曆查詢和會議安排
- **模型**: GPT-4.1 Mini
- **整合**: 支援真實 Google Calendar API 或 Mock 模式
- **職責**: 時間管理、約會安排、衝突檢測

## 📊 監控與日誌

```bash
# 查看 API 日誌
docker-compose logs -f aisales-api

# 查看 Redis 狀態
docker-compose exec redis redis-cli ping

# 查看 ChromaDB 狀態
curl http://localhost:8001/api/v1/heartbeat
```

## 🧪 測試

```bash
# 運行測試
pytest tests/

# 測試覆蓋率
pytest --cov=app tests/

# 健康檢查測試
curl http://localhost:8000/health
```

## 🔗 整合範例

### LINE Bot 整合

```python
from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage
import openai

# 設定 OpenAI 客戶端
client = openai.OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="your-api-key"
)

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    # 調用 AI Sales API
    response = client.chat.completions.create(
        model="aisales-v1",
        messages=[
            {"role": "user", "content": event.message.text}
        ],
        user=event.source.user_id
    )
    
    # 回覆用戶
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=response.choices[0].message.content)
    )
```

## 🧠 LangGraph 工作流系統

### 核心功能

本系統採用 LangGraph 框架實現複雜的 Agent 協作和智能路由：

#### 1. 智能路由決策
- **意圖分析**: 自動識別用戶輸入的意圖（問候、產品查詢、預約等）
- **複雜度評估**: 評估查詢的複雜程度，決定單一或並行處理
- **上下文感知**: 基於對話歷史和用戶檔案進行個性化路由

#### 2. 並行 Agent 協作
- **智能 Agent 選擇**: 根據輸入內容自動選擇最合適的 Agent 組合
- **並行執行**: 多個 Agent 同時處理不同方面的查詢
- **結果聚合**: 智能整合多個 Agent 的回應，提供連貫的答案

#### 3. 高級聚合策略
- **主要+上下文**: 突出主要回應，補充相關資訊
- **順序組合**: 按邏輯順序組合多個 Agent 的結果
- **並行合成**: 使用 LLM 智能合成多個回應
- **簡單組合**: 按優先級排序組合結果

#### 4. 效能監控與優化
- **執行時間監控**: 即時監控每個 Agent 的執行效能
- **降級處理**: 當複雜工作流失敗時，自動降級到基本處理
- **效能統計**: 記錄和分析工作流的效能指標

### 工作流測試

系統提供專門的測試腳本來驗證 LangGraph 工作流：

```bash
# 執行 LangGraph 工作流測試
python test_langgraph_workflow.py

# 測試內容包括：
# - 基本工作流功能
# - 並行處理能力
# - 高級路由決策
# - 錯誤處理機制
# - 效能監控
```

### 路由決策示例

```python
# 簡單問候 -> 單一 Agent
用戶輸入: "你好"
路由結果: chat_agent (單一模式)

# 產品查詢 -> 單一 Agent
用戶輸入: "介紹一下你們的AI產品"
路由結果: rag_agent (單一模式)

# 複雜查詢 -> 並行 Agent
用戶輸入: "我想了解產品功能並安排會議"
路由結果: rag_agent + calendar_agent (並行模式)

# 圖片+文字 -> 並行 Agent
用戶輸入: "分析這張名片並介紹相關產品"
路由結果: card_agent + rag_agent (並行模式)
```

## 🛡️ 安全性

- 環境變數管理敏感資訊
- Redis 資料加密
- API 速率限制
- 輸入驗證和清理

## 📈 擴展功能

- [ ] 支援更多 LLM 模型
- [ ] 實時語音對話
- [ ] 多語言支援
- [ ] CRM 系統整合
- [ ] 情緒分析
- [ ] 自定義 Agent 開發

## 🤝 貢獻指南

1. Fork 此專案
2. 創建功能分支
3. 提交變更
4. 發起 Pull Request
