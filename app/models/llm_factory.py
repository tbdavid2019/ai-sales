from typing import Any, Dict, Optional
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models import BaseLanguageModel
from app.config import settings


class LLMFactory:
    """LLM 模型工廠類別"""
    
    @staticmethod
    def create_gemini_llm(
        api_key: str,
        model_name: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> ChatGoogleGenerativeAI:
        """創建 Gemini 模型實例"""
        return ChatGoogleGenerativeAI(
            google_api_key=api_key,
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
    
    @staticmethod
    def create_openai_llm(
        api_key: str,
        base_url: str,
        model_name: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> ChatOpenAI:
        """創建 OpenAI 相容的模型實例"""
        return ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
    
    @staticmethod
    def get_control_agent_llm() -> BaseLanguageModel:
        """獲取主控 Agent 的 LLM"""
        return LLMFactory.create_gemini_llm(
            api_key=settings.gemini_api_key,
            model_name=settings.gemini_model_name,
            temperature=0.3  # 較低溫度以確保路由決策的準確性
        )
    
    @staticmethod
    def get_chat_agent_llm() -> BaseLanguageModel:
        """獲取對話 Agent 的 LLM"""
        return LLMFactory.create_gemini_llm(
            api_key=settings.chat_model_api_key,
            model_name=settings.chat_model_name,
            temperature=0.7
        )
    
    @staticmethod
    def get_rag_agent_llm() -> BaseLanguageModel:
        """獲取 RAG Agent 的 LLM"""
        return LLMFactory.create_gemini_llm(
            api_key=settings.rag_model_api_key,
            model_name=settings.rag_model_name,
            temperature=0.5  # 中等溫度平衡創意與準確性
        )
    
    @staticmethod
    def get_calendar_agent_llm() -> BaseLanguageModel:
        """獲取行事曆 Agent 的 LLM"""
        return LLMFactory.create_openai_llm(
            api_key=settings.calendar_api_key,
            base_url=settings.calendar_base_url,
            model_name=settings.calendar_model_name,
            temperature=0.1  # 極低溫度確保結構化任務的準確性
        )
    
    @staticmethod
    def get_card_agent_llm() -> BaseLanguageModel:
        """獲取名片 Agent 的 LLM"""
        return LLMFactory.create_openai_llm(
            api_key=settings.card_api_key,
            base_url=settings.card_base_url,
            model_name=settings.card_model_name,
            temperature=0.2  # 低溫度確保 OCR 準確性
        )

    @staticmethod
    def get_vision_agent_llm() -> BaseLanguageModel:
        """獲取視覺 Agent 的 LLM - 支援多模態輸入"""
        return LLMFactory.create_openai_llm(
            api_key=settings.vision_api_key,
            base_url=settings.vision_base_url,
            model_name=settings.vision_model_name,
            temperature=0.3  # 較低溫度確保情緒識別的準確性
        )
