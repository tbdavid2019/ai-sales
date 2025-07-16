from typing import Optional
from langchain_openai import OpenAIEmbeddings
from app.config import settings


class EmbeddingFactory:
    """向量嵌入模型工廠類別"""
    
    @staticmethod
    def create_openai_embedding(
        api_key: str,
        base_url: str,
        model_name: str,
        **kwargs
    ) -> OpenAIEmbeddings:
        """創建 OpenAI 嵌入模型實例"""
        return OpenAIEmbeddings(
            api_key=api_key,
            base_url=base_url,
            model=model_name,
            **kwargs
        )
    
    @staticmethod
    def get_default_embedding() -> OpenAIEmbeddings:
        """獲取預設的嵌入模型"""
        return EmbeddingFactory.create_openai_embedding(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model_name=settings.embedding_model_name
        )
