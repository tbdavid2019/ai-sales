from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles # 新增這行
from contextlib import asynccontextmanager
from datetime import datetime

from app.api.openai_compatible import api
from app.api.models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ModelsResponse
)
from app.config import settings
from app.routers import vision_router # 新增這行


@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用程式生命週期管理"""
    # 啟動時的初始化
    print("🚀 AI Sales API 啟動中...")
    print(f"📍 API 地址: http://{settings.api_host}:{settings.api_port}")
    print(f"📖 API 文檔: http://{settings.api_host}:{settings.api_port}/docs")
    
    yield
    
    # 關閉時的清理
    print("🔄 AI Sales API 關閉中...")


# 創建 FastAPI 應用
app = FastAPI(
    title="AI Sales Multi-Agent API",
    description="""
    ## 🤖 AI Sales 多 Agent 銷售系統
    
    OpenAI 相容的智能銷售助手 API，支援多種互動模式和參數控制。
    
    ### 🎯 支援的回應模式
    
    - **虛擬人模式** (Virtual Human)：簡短、互動式回應
      - `max_tokens`: 50-200
      - `temperature`: 0.8 (高創意度)
      - 適用於快速對話、即時互動
    
    - **一般文字模式** (General Chat)：詳細、專業回應
      - `max_tokens`: 100-2000
      - `temperature`: 0.7 (平衡創意度)
      - 適用於產品介紹、詳細諮詢
    
    - **RAG 知識查詢** (Knowledge Query)：準確、基於知識庫的回應
      - `max_tokens`: 800
      - `temperature`: 0.5 (低創意度，高準確性)
      - 適用於產品技術問題、資料查詢
    
    ### 🔧 核心功能
    
    - **多 Agent 協作**：智能路由到最適合的 Agent
    - **即時串流**：支援 Server-Sent Events 串流回應
    - **記憶管理**：基於 Redis 的用戶對話歷史
    - **知識檢索**：RAG 技術整合向量資料庫
    - **視覺識別**：名片 OCR 和情緒分析
    - **行事曆整合**：Google Calendar API 支援
    
    ### 📋 使用範例
    
    ```python
    import openai
    
    client = openai.OpenAI(
        base_url="http://localhost:8000/v1",
        api_key="your-api-key"
    )
    
    # 虛擬人模式 - 簡短互動
    response = client.chat.completions.create(
        model="aisales-v1",
        messages=[{"role": "user", "content": "你好"}],
        max_tokens=50,
        temperature=0.8
    )
    
    # 一般模式 - 詳細回應
    response = client.chat.completions.create(
        model="aisales-v1",
        messages=[{"role": "user", "content": "介紹你們的產品"}],
        max_tokens=500,
        temperature=0.7
    )
    ```
    
    ### 🌐 相關連結
    
    - **Streamlit UI**: http://localhost:8501
    - **Gradio UI**: http://localhost:7860
    - **GitHub**: https://github.com/tbdavid2019/ai-sales
    """,
    version="2.0.0",
    lifespan=lifespan,
    contact={
        "name": "AI Sales Team",
        "email": "support@c360company.com"
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT"
    }
)

# 設置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 掛載靜態檔案目錄，讓前端可以存取 vision.js
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 掛載 OpenAI 相容的 API 路由
app.include_router(api.router, prefix="/v1")

# 掛載視覺分析的 WebSocket 路由
app.include_router(vision_router.router, prefix="/vision", tags=["Vision"])


@app.get(
    "/",
    summary="API 根路徑",
    description="""
    ## 🏠 AI Sales API 首頁
    
    返回 API 基本資訊和相關連結。
    
    ### 🔗 重要連結
    
    - **API 文檔**: /docs
    - **OpenAPI 規範**: /openapi.json
    - **Streamlit UI**: http://localhost:8501
    - **Gradio UI**: http://localhost:7860
    """,
    tags=["System"]
)
async def root():
    """根路徑"""
    return {
        "message": "AI Sales Multi-Agent API",
        "version": "2.0.0",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "ui_links": {
            "streamlit": "http://localhost:8501",
            "gradio": "http://localhost:7860"
        }
    }


@app.get(
    "/health",
    summary="健康檢查",
    description="""
    ## 🏥 系統健康檢查
    
    檢查 API 服務狀態和相關元件連線。
    
    ### 📊 檢查項目
    
    - API 服務運行狀態
    - 基本回應時間
    - 系統時間戳記
    """,
    tags=["System"]
)
async def health_check():
    """健康檢查"""
    return {
        "status": "healthy", 
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "components": {
            "api": "running",
            "agents": "ready"
        }
    }


# OpenAI 相容端點
@app.post(
    "/v1/chat/completions", 
    response_model=ChatCompletionResponse,
    summary="聊天完成",
    description="""
    ## 🤖 AI Sales 聊天完成端點
    
    OpenAI 相容的聊天完成 API，支援多種參數控制和回應模式。
    
    ### 📋 參數說明
    
    - **model**: 固定使用 "aisales-v1"
    - **messages**: 對話訊息陣列
    - **stream**: 是否啟用串流回應
    - **temperature**: 回應創意度 (0.0-1.0)
    - **max_tokens**: 最大回應長度
    - **user**: 用戶識別碼（可選）
    
    ### 🎯 建議設定
    
    | 模式 | max_tokens | temperature | 說明 |
    |------|------------|-------------|------|
    | 虛擬人模式 | 50-200 | 0.8 | 簡短互動 |
    | 一般模式 | 100-2000 | 0.7 | 詳細回應 |
    | RAG 查詢 | 800 | 0.5 | 準確回應 |
    
    ### 🔄 回應格式
    
    支援標準 OpenAI 格式回應，包含：
    - 回應內容
    - Token 使用統計
    - 完成原因
    """,
    tags=["Chat Completion"],
    responses={
        200: {"description": "成功回應"},
        400: {"description": "請求參數錯誤"},
        500: {"description": "伺服器內部錯誤"}
    }
)
async def chat_completions(request: ChatCompletionRequest):
    """聊天完成端點"""
    try:
        if request.stream:
            return await api.chat_completions_stream(request)
        else:
            return await api.chat_completions(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/v1/models", 
    response_model=ModelsResponse,
    summary="列出可用模型",
    description="""
    ## 📋 可用模型列表
    
    返回當前系統支援的所有模型。
    
    ### 🤖 模型說明
    
    - **aisales-v1**: AI Sales 多 Agent 系統
      - 整合多個專業 Agent
      - 支援智能路由
      - 適用於銷售對話、知識查詢、名片識別等
    
    ### 🔧 Agent 組成
    
    - **ControlAgent**: 主控制器，負責意圖分析和路由
    - **ChatAgent**: 對話助手，處理一般銷售對話
    - **RAGAgent**: 知識檢索，基於向量資料庫回答
    - **CardAgent**: 名片識別，OCR 和資料提取
    - **CalendarAgent**: 行事曆管理，會議安排
    - **VisionAgent**: 視覺分析，情緒和圖像處理
    """,
    tags=["Models"]
)
async def list_models():
    """列出可用模型"""
    return api.get_models()


@app.post(
    "/v1/models", 
    response_model=ModelsResponse,
    summary="列出可用模型 (POST)",
    description="與 GET /v1/models 相同，提供 POST 方法支援",
    tags=["Models"]
)
async def list_models_post():
    """列出可用模型 (POST 方法)"""
    return api.get_models()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
