```python
class LLMFactory:
    """
    LLM 工廠，根據 Agent 類型提供對應的 LLM 實例。
    這使得更換模型或為不同 Agent 配置不同參數變得容易。
    """
    _llms = {}
    _config = {
        "chat_agent": {"model": "gpt-4o", "temperature": 0.7},
        "rag_agent": {"model": "gpt-4o", "temperature": 0.3},
        "card_agent": {"model": "gpt-4o", "temperature": 0.1},
        "vision_agent": {"model": "gpt-4o", "temperature": 0.2}, # 新增 VisionAgent 的模型配置
        "control_agent": {"model": "gpt-4o", "temperature": 0.0},
    }

    @classmethod
    def _get_llm(cls, agent_name: str):
        # ...existing code...

    @classmethod
    def get_chat_agent_llm(cls):
        return cls._get_llm("chat_agent")

    @classmethod
    def get_rag_agent_llm(cls):
        return cls._get_llm("rag_agent")

    @classmethod
    def get_card_agent_llm(cls):
        return cls._get_llm("card_agent")

    @classmethod
    def get_vision_agent_llm(cls):
        """提供給 VisionAgent 的 LLM，應為多模態模型"""
        return cls._get_llm("vision_agent")

    @classmethod
    def get_control_agent_llm(cls):
        return cls._get_llm("control_agent")
```