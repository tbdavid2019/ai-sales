from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from app.models import LLMFactory
from app.core.memory import memory_manager


class BaseAgent(ABC):
    """基礎 Agent 抽象類別"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.llm = None
        self.memory = memory_manager
    
    @abstractmethod
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """處理輸入並返回結果"""
        pass
    
    def get_system_prompt(self) -> str:
        """獲取系統提示詞"""
        return f"你是 {self.name}，{self.description}"
    
    def format_response(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """格式化回應"""
        import time
        timestamp = None
        try:
            if self.memory.use_redis and self.memory.redis_client:
                timestamp = self.memory.redis_client.time()[0]
            else:
                timestamp = int(time.time())
        except Exception:
            timestamp = int(time.time())
        
        return {
            "agent": self.name,
            "content": content,
            "metadata": metadata or {},
            "timestamp": timestamp
        }
