from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """系統設定管理"""
    
    # 主控 Agent - Gemini
    gemini_api_key: str
    gemini_base_url: str = "https://generativelanguage.googleapis.com"
    gemini_model_name: str = "gemini-2.0-flash-lite"
    
    # ChatAgent - Gemini
    chat_model_api_key: str
    chat_model_base_url: str = "https://generativelanguage.googleapis.com"
    chat_model_name: str = "gemini-2.0-flash-lite"
    
    # RAG Embedding - OpenAI
    openai_api_key: str
    openai_base_url: str = "https://api.openai.com/v1"
    embedding_model_name: str = "text-embedding-3-large"
    
    # CalendarAgent - OpenAI
    calendar_api_key: str
    calendar_base_url: str = "https://api.openai.com/v1"
    calendar_model_name: str = "gpt-4.1-mini"
    
    # CardAgent - OpenAI
    card_api_key: str
    card_base_url: str = "https://api.openai.com/v1"
    card_model_name: str = "gpt-4o"
    
    # VisionAgent - OpenAI
    vision_api_key: str
    vision_base_url: str = "https://api.openai.com/v1"
    vision_model_name: str = "gpt-4o"
    
    # RAGAgent - Gemini
    rag_model_api_key: str
    rag_model_base_url: str = "https://generativelanguage.googleapis.com"
    rag_model_name: str = "gemini-2.0-flash-lite"
    
    # Google Calendar API 設定
    google_calendar_credentials_file: str = "credentials.json"
    google_calendar_token_file: str = "token.json"
    google_calendar_scopes: str = "https://www.googleapis.com/auth/calendar.readonly,https://www.googleapis.com/auth/calendar.events"
    google_calendar_id: str = "primary"
    
    # 向量資料庫設定
    vector_db_type: str = "chromadb"
    chroma_host: str = "localhost"
    chroma_port: int = 8000
    chroma_collection_name: str = "aisales_knowledge"
    
    # 系統設定
    redis_url: str = "redis://localhost:6379"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # 開發環境設定
    debug: bool = True
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# 全域設定實例
settings = Settings()
