from typing import Dict, Any, Optional
from fastapi import HTTPException
from fastapi.responses import JSONResponse
import traceback
import time
from app.core.logger import logger


class ErrorHandler:
    """統一錯誤處理類別"""
    
    @staticmethod
    def handle_agent_error(error: Exception, agent_name: str, session_id: str) -> Dict[str, Any]:
        """處理 Agent 錯誤"""
        error_id = f"agent_error_{int(time.time())}"
        
        logger.error(
            f"Agent {agent_name} 處理錯誤",
            error=error,
            agent=agent_name,
            session_id=session_id,
            error_id=error_id,
            traceback=traceback.format_exc()
        )
        
        return {
            "error": True,
            "error_id": error_id,
            "error_type": type(error).__name__,
            "message": "Agent 處理過程中發生錯誤，請稍後重試",
            "details": str(error) if hasattr(error, '__str__') else "未知錯誤"
        }
    
    @staticmethod
    def handle_llm_error(error: Exception, model_name: str, session_id: str) -> Dict[str, Any]:
        """處理 LLM 錯誤"""
        error_id = f"llm_error_{int(time.time())}"
        
        logger.error(
            f"LLM {model_name} 調用錯誤",
            error=error,
            model=model_name,
            session_id=session_id,
            error_id=error_id,
            traceback=traceback.format_exc()
        )
        
        return {
            "error": True,
            "error_id": error_id,
            "error_type": type(error).__name__,
            "message": "AI 模型調用失敗，請稍後重試",
            "details": str(error)
        }
    
    @staticmethod
    def handle_vector_db_error(error: Exception, operation: str, session_id: str) -> Dict[str, Any]:
        """處理向量資料庫錯誤"""
        error_id = f"vector_db_error_{int(time.time())}"
        
        logger.error(
            f"向量資料庫 {operation} 操作錯誤",
            error=error,
            operation=operation,
            session_id=session_id,
            error_id=error_id,
            traceback=traceback.format_exc()
        )
        
        return {
            "error": True,
            "error_id": error_id,
            "error_type": type(error).__name__,
            "message": "知識庫查詢失敗，將使用預設回應",
            "details": str(error)
        }
    
    @staticmethod
    def handle_memory_error(error: Exception, operation: str, session_id: str) -> Dict[str, Any]:
        """處理記憶體錯誤"""
        error_id = f"memory_error_{int(time.time())}"
        
        logger.error(
            f"記憶體 {operation} 操作錯誤",
            error=error,
            operation=operation,
            session_id=session_id,
            error_id=error_id,
            traceback=traceback.format_exc()
        )
        
        return {
            "error": True,
            "error_id": error_id,
            "error_type": type(error).__name__,
            "message": "記憶體操作失敗，對話記憶可能受影響",
            "details": str(error)
        }
    
    @staticmethod
    def create_openai_error_response(
        error_type: str, 
        message: str, 
        status_code: int = 500,
        param: Optional[str] = None,
        code: Optional[str] = None
    ) -> HTTPException:
        """建立 OpenAI 相容的錯誤回應"""
        error_detail = {
            "error": {
                "message": message,
                "type": error_type,
                "param": param,
                "code": code
            }
        }
        
        return HTTPException(
            status_code=status_code,
            detail=error_detail
        )
    
    @staticmethod
    def handle_validation_error(error: Exception, field: str) -> HTTPException:
        """處理驗證錯誤"""
        logger.warning(
            f"驗證錯誤: {field}",
            error=error,
            field=field
        )
        
        return ErrorHandler.create_openai_error_response(
            error_type="invalid_request_error",
            message=f"欄位 '{field}' 驗證失敗: {str(error)}",
            status_code=400,
            param=field
        )
    
    @staticmethod
    def handle_rate_limit_error(limit: int, window: int) -> HTTPException:
        """處理速率限制錯誤"""
        logger.warning(
            "速率限制觸發",
            limit=limit,
            window=window
        )
        
        return ErrorHandler.create_openai_error_response(
            error_type="rate_limit_error",
            message=f"請求過於頻繁，每 {window} 秒限制 {limit} 次請求",
            status_code=429,
            code="rate_limit_exceeded"
        )
    
    @staticmethod
    def handle_authentication_error(message: str = "無效的 API 金鑰") -> HTTPException:
        """處理身份驗證錯誤"""
        logger.warning("身份驗證失敗", message=message)
        
        return ErrorHandler.create_openai_error_response(
            error_type="authentication_error",
            message=message,
            status_code=401,
            code="invalid_api_key"
        )
    
    @staticmethod
    def handle_internal_error(error: Exception, context: str = "") -> HTTPException:
        """處理內部錯誤"""
        error_id = f"internal_error_{int(time.time())}"
        
        logger.error(
            "內部錯誤",
            error=error,
            context=context,
            error_id=error_id,
            traceback=traceback.format_exc()
        )
        
        return ErrorHandler.create_openai_error_response(
            error_type="internal_error",
            message=f"伺服器內部錯誤 (錯誤 ID: {error_id})",
            status_code=500,
            code="internal_error"
        )


# 全域錯誤處理器實例
error_handler = ErrorHandler()
