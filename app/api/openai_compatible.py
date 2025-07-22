from typing import Dict, Any, AsyncGenerator
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse
import json
import time
import uuid
from datetime import datetime

from app.api.models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionStreamResponse,
    ChatCompletionChoice,
    ChatCompletionStreamChoice,
    Usage,
    Message,
    MessageRole,
    ModelsResponse,
    Model,
    ErrorResponse
)
from app.agents import ControlAgent, ChatAgent, RAGAgent, CardAgent, CalendarAgent
from app.core.memory import memory_manager
from app.core.logger import logger
from app.core.error_handler import error_handler
from app.core.tokenizer import get_token_counter


class OpenAICompatibleAPI:
    """OpenAI 相容 API 實現"""
    
    def __init__(self):
        self.control_agent = ControlAgent()
        self.chat_agent = ChatAgent()
        self.rag_agent = RAGAgent()
        self.card_agent = CardAgent()
        self.calendar_agent = CalendarAgent()
        self.agents = {
            "control_agent": self.control_agent,
            "chat_agent": self.chat_agent,
            "rag_agent": self.rag_agent,
            "card_agent": self.card_agent,
            "calendar_agent": self.calendar_agent
        }
        self.token_counter = get_token_counter()
    
    async def chat_completions(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """處理聊天完成請求 - 使用修復的工作流管理器"""
        # 使用修復的工作流管理器
        from app.core.workflow import workflow_manager

        request_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
        session_id = request.user or f"session-{uuid.uuid4().hex[:8]}"
        start_time = time.time()
        
        try:
            # 記錄請求
            logger.log_api_request(
                request_id=request_id,
                method="POST",
                path="/v1/chat/completions",
                session_id=session_id,
                model=request.model,
                stream=request.stream
            )
            
            # 提取用戶輸入
            user_message = self._extract_user_message(request.messages)
            
            # 內容安全檢查
            from app.core.security import security_middleware
            if not security_middleware.check_content_safety(user_message):
                logger.warning("危險內容檢測", content=user_message[:100])
                raise error_handler.create_openai_error_response(
                    error_type="content_policy_violation",
                    message="輸入內容不符合安全政策",
                    status_code=400
                )
            
            # 載入用戶檔案
            user_profile = memory_manager.load_user_profile(session_id) or {}
            
            # 檢查是否有圖片內容
            image_content = self._extract_image_content(request.messages)
            
            # 準備工作流輸入 - 包含修復的參數
            workflow_input = {
                "user_input": user_message,
                "session_id": session_id,
                "has_image": bool(image_content),
                "image_data": image_content,
                "image_source": "api",  # 標記為API來源
                "user_profile": user_profile,
                "request_id": request_id,
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
                "response_mode": "api"  # API模式
            }
            
            # 使用修復的工作流管理器
            workflow_result = await workflow_manager.execute_workflow(workflow_input)
            
            if not workflow_result.success:
                logger.error(
                    "工作流執行失敗",
                    error=workflow_result.error,
                    request_id=request_id,
                    session_id=session_id
                )
                raise error_handler.handle_internal_error(
                    workflow_result.error or Exception("工作流執行失敗"),
                    "workflow_execution"
                )
            
            response_content = workflow_result.content
            
            # 檢查是否有用戶資料更新
            if workflow_result.metadata.get("updated_user_profile"):
                updated_profile = workflow_result.metadata["updated_user_profile"]
                memory_manager.save_user_profile(session_id, updated_profile)
            
            # 計算 token 使用量
            self.token_counter.model_name = request.model
            prompt_tokens = self.token_counter.count_messages_tokens(request.messages)
            completion_tokens = self.token_counter.count_tokens(response_content)
            
            # 構建回應
            response = ChatCompletionResponse(
                id=request_id,
                created=int(time.time()),
                model=request.model,
                choices=[
                    ChatCompletionChoice(
                        index=0,
                        message=Message(
                            role=MessageRole.ASSISTANT,
                            content=response_content
                        ),
                        finish_reason="stop"
                    )
                ],
                usage=Usage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens
                )
            )
            
            # 記錄成功回應
            total_duration = time.time() - start_time
            logger.log_performance(
                operation="chat_completion_total",
                duration=total_duration,
                request_id=request_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                agents_used=list(workflow_result.agent_results.keys())
            )
            
            return response
            
        except Exception as e:
            logger.error(
                "API 請求處理失敗",
                error=str(e),
                request_id=request_id,
                session_id=session_id
            )
            raise error_handler.handle_internal_error(e, "api_request")
    
    def _extract_image_content(self, messages: list) -> str:
        """提取訊息中的圖片內容"""
        for message in messages:
            if hasattr(message, 'content') and isinstance(message.content, list):
                for content_item in message.content:
                    if content_item.get('type') == 'image_url':
                        image_url = content_item.get('image_url', {}).get('url', '')
                        if image_url.startswith('data:image/'):
                            # 提取 base64 部分
                            return image_url.split(',')[1] if ',' in image_url else image_url
        return None

    async def chat_completions_stream(
        self, request: ChatCompletionRequest
    ) -> StreamingResponse:
        """處理流式聊天完成請求"""
        # 延遲匯入以避免循環依賴
        from app.core.workflow import workflow_manager
        
        async def generate_stream():
            try:
                # 生成請求 ID
                request_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
                
                # 提取用戶輸入
                user_message = self._extract_user_message(request.messages)
                session_id = request.user or f"session-{uuid.uuid4().hex[:8]}"
                
                # 載入用戶檔案
                user_profile = memory_manager.load_user_profile(session_id) or {}
                
                # 檢查是否有圖片內容
                image_content = self._extract_image_content(request.messages)
                
                # 準備工作流輸入 - 包含修復的參數
                input_data = {
                    "user_input": user_message,
                    "session_id": session_id,
                    "has_image": bool(image_content),
                    "image_data": image_content,
                    "image_source": "api_stream",  # 標記為API串流來源
                    "user_profile": user_profile,
                    "request_id": request_id,
                    "max_tokens": request.max_tokens,
                    "temperature": request.temperature,
                    "response_mode": "api_stream"  # API串流模式
                }
                
                # 使用 LangGraph 工作流管理器處理請求
                workflow_result = await workflow_manager.execute_workflow(input_data)

                if not workflow_result.success:
                    logger.error(
                        "工作流執行失敗",
                        error=workflow_result.error,
                        request_id=request_id
                    )
                    # 在流式回應中發送錯誤
                    error_chunk = self._create_error_chunk(
                        request_id,
                        "工作流執行失敗",
                        "internal_error"
                    )
                    yield f"data: {json.dumps(error_chunk)}\\n\\n"
                    yield "data: [DONE]\\n\\n"
                    return

                response_content = workflow_result.content
                
                # 檢查是否有用戶資料更新
                if workflow_result.metadata.get("updated_user_profile"):
                    updated_profile = workflow_result.metadata["updated_user_profile"]
                    memory_manager.save_user_profile(session_id, updated_profile)
                
                # 模擬流式輸出
                words = response_content.split()
                for i, word in enumerate(words):
                    chunk = ChatCompletionStreamResponse(
                        id=request_id,
                        created=int(time.time()),
                        model=request.model,
                        choices=[
                            ChatCompletionStreamChoice(
                                index=0,
                                delta={"content": word + " " if i < len(words) - 1 else word},
                                finish_reason=None
                            )
                        ]
                    )
                    
                    yield f"data: {chunk.json()}\\n\\n"
                
                # 結束標記
                final_chunk = ChatCompletionStreamResponse(
                    id=request_id,
                    created=int(time.time()),
                    model=request.model,
                    choices=[
                        ChatCompletionStreamChoice(
                            index=0,
                            delta={},
                            finish_reason="stop"
                        )
                    ]
                )
                
                yield f"data: {final_chunk.json()}\\n\\n"
                yield "data: [DONE]\\n\\n"
                
            except Exception as e:
                error_chunk = {
                    "error": {
                        "message": str(e),
                        "type": "internal_error"
                    }
                }
                yield f"data: {json.dumps(error_chunk)}\\n\\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream"
            }
        )
    
    def get_models(self) -> ModelsResponse:
        """獲取可用模型列表"""
        return ModelsResponse(
            data=[
                Model(
                    id="aisales-v1",
                    created=int(time.time()),
                    owned_by="aisales"
                )
            ]
        )
    
    def _extract_user_message(self, messages: list) -> str:
        """提取用戶訊息"""
        for message in reversed(messages):
            if message.role == MessageRole.USER:
                return message.content
        return ""
    
    def _has_image_content(self, messages: list) -> bool:
        """檢查是否包含圖片內容"""
        for message in messages:
            if hasattr(message, 'content') and isinstance(message.content, list):
                for content_part in message.content:
                    if isinstance(content_part, dict) and content_part.get('type') == 'image_url':
                        return True
        return False
    
    def _extract_image_data(self, messages: list) -> list:
        """提取圖片資料"""
        images = []
        for message in messages:
            if hasattr(message, 'content') and isinstance(message.content, list):
                for content_part in message.content:
                    if isinstance(content_part, dict) and content_part.get('type') == 'image_url':
                        images.append(content_part.get('image_url', {}).get('url'))
        return images
    
    def _validate_request(self, request: ChatCompletionRequest) -> None:
        """驗證請求參數"""
        if not request.messages:
            raise error_handler.create_openai_error_response(
                error_type="invalid_request_error",
                message="messages 參數為必填項",
                status_code=400,
                param="messages"
            )
        
        if request.max_tokens and request.max_tokens < 1:
            raise error_handler.create_openai_error_response(
                error_type="invalid_request_error",
                message="max_tokens 必須大於 0",
                status_code=400,
                param="max_tokens"
            )
        
        if request.temperature and (request.temperature < 0 or request.temperature > 2):
            raise error_handler.create_openai_error_response(
                error_type="invalid_request_error",
                message="temperature 必須在 0 到 2 之間",
                status_code=400,
                param="temperature"
            )
    
    def _prepare_agent_context(self, request: ChatCompletionRequest, session_id: str) -> dict:
        """準備 Agent 上下文"""
        context = {
            "model": request.model,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
            "frequency_penalty": request.frequency_penalty,
            "presence_penalty": request.presence_penalty,
            "session_id": session_id,
            "conversation_history": request.messages[:-1] if len(request.messages) > 1 else []
        }
        
        return context

    def _create_error_chunk(self, request_id: str, message: str, error_type: str):
        """創建錯誤區塊"""
        return {
            "id": request_id,
            "created": int(time.time()),
            "model": "error-model",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "content": f"錯誤: {message}"
                    },
                    "finish_reason": "stop"
                }
            ],
            "error": {
                "message": message,
                "type": error_type
            }
        }


# 創建 API 實例
api = OpenAICompatibleAPI()
