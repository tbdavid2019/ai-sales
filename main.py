from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles # 新增這行
from contextlib import asynccontextmanager

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
    description="OpenAI 相容的多 Agent AI 銷售系統",
    version="1.0.0",
    lifespan=lifespan
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


@app.get("/")
async def root():
    """根路徑"""
    return {
        "message": "AI Sales Multi-Agent API",
        "version": "1.0.0",
        "docs": "/docs",
        "openapi": "/openapi.json"
    }


@app.get("/health")
async def health_check():
    """健康檢查"""
    return {"status": "healthy", "timestamp": "2024-01-01T00:00:00Z"}


# OpenAI 相容端點
@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest):
    """聊天完成端點"""
    try:
        if request.stream:
            return await api.chat_completions_stream(request)
        else:
            return await api.chat_completions(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/models", response_model=ModelsResponse)
async def list_models():
    """列出可用模型"""
    return api.get_models()


@app.post("/v1/models", response_model=ModelsResponse)
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
