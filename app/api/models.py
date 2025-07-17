from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from enum import Enum


class MessageRole(str, Enum):
    """訊息角色枚舉"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    """訊息模型"""
    role: MessageRole
    content: str
    name: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    """聊天完成請求模型"""
    model: str = Field(
        ...,
        description="模型名稱，使用 'aisales-v1' 來調用 AI Sales 多 Agent 系統",
        example="aisales-v1"
    )
    messages: List[Message] = Field(
        ...,
        description="對話訊息陣列，包含用戶和助手的對話歷史",
        example=[
            {"role": "user", "content": "你好，介紹一下你們的產品"}
        ]
    )
    stream: bool = Field(
        False,
        description="是否啟用串流回應。true=逐字返回，false=完整返回",
        example=False
    )
    temperature: Optional[float] = Field(
        0.7,
        ge=0.0,
        le=1.0,
        description="控制回應創意度。0.0=保守準確，1.0=創意發散。虛擬人模式建議0.8，一般模式建議0.7",
        example=0.7
    )
    max_tokens: Optional[int] = Field(
        None,
        ge=1,
        le=4000,
        description="最大回應長度限制。虛擬人模式建議50-200，一般模式建議100-2000，RAG查詢建議800",
        example=500
    )
    top_p: Optional[float] = Field(
        1.0,
        ge=0.0,
        le=1.0,
        description="核心取樣參數，控制詞彙選擇範圍。1.0=使用所有詞彙，0.1=只使用最可能的詞彙",
        example=1.0
    )
    frequency_penalty: Optional[float] = Field(
        0.0,
        ge=-2.0,
        le=2.0,
        description="頻率懲罰，減少重複用詞。正值=減少重複，負值=增加重複",
        example=0.0
    )
    presence_penalty: Optional[float] = Field(
        0.0,
        ge=-2.0,
        le=2.0,
        description="存在懲罰，鼓勵談論新主題。正值=增加新主題，負值=專注當前主題",
        example=0.0
    )
    user: Optional[str] = Field(
        None,
        max_length=200,
        description="用戶識別碼，用於追蹤對話歷史和個人化回應",
        example="user-123"
    )


class ChatCompletionChoice(BaseModel):
    """聊天完成選項模型"""
    index: int
    message: Message
    finish_reason: str


class Usage(BaseModel):
    """使用情況模型"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """聊天完成回應模型"""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: Usage


class ChatCompletionStreamChoice(BaseModel):
    """串流聊天完成選項模型"""
    index: int
    delta: Dict[str, Any]
    finish_reason: Optional[str] = None


class ChatCompletionStreamResponse(BaseModel):
    """串流聊天完成回應模型"""
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[ChatCompletionStreamChoice]


class Model(BaseModel):
    """模型資訊"""
    id: str
    object: str = "model"
    created: int
    owned_by: str


class ModelsResponse(BaseModel):
    """模型列表回應"""
    object: str = "list"
    data: List[Model]


class ErrorResponse(BaseModel):
    """錯誤回應模型"""
    error: Dict[str, Any]
