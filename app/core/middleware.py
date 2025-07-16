from typing import Callable, Dict, Any
import time
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.logger import logger


class APIMiddleware(BaseHTTPMiddleware):
    """API 中間件 - 處理請求日誌、監控和錯誤"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """處理請求"""
        # 生成請求 ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # 記錄開始時間
        start_time = time.time()
        
        # 記錄請求
        logger.log_api_request(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            query_params=dict(request.query_params),
            headers=dict(request.headers),
            client_ip=request.client.host if request.client else "unknown"
        )
        
        try:
            # 執行請求
            response = await call_next(request)
            
            # 計算處理時間
            process_time = time.time() - start_time
            
            # 記錄回應
            logger.log_performance(
                operation="api_request",
                duration=process_time,
                request_id=request_id,
                status_code=response.status_code,
                method=request.method,
                path=request.url.path
            )
            
            # 添加回應標頭
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.3f}s"
            
            return response
            
        except Exception as e:
            # 記錄錯誤
            process_time = time.time() - start_time
            logger.error(
                "API 請求處理錯誤",
                error=e,
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                process_time=process_time
            )
            
            # 重新拋出錯誤
            raise


class RateLimitMiddleware(BaseHTTPMiddleware):
    """速率限制中間件"""
    
    def __init__(self, app, calls_per_minute: int = 100):
        super().__init__(app)
        self.calls_per_minute = calls_per_minute
        self.requests = {}  # 簡單的記憶體儲存，實際專案建議使用 Redis
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """處理速率限制"""
        # 獲取客戶端 IP
        client_ip = request.client.host if request.client else "unknown"
        
        # 檢查速率限制
        current_time = time.time()
        minute_window = int(current_time // 60)
        
        key = f"{client_ip}:{minute_window}"
        
        if key in self.requests:
            self.requests[key] += 1
        else:
            self.requests[key] = 1
        
        # 清理舊的記錄
        self._cleanup_old_records(minute_window)
        
        # 檢查是否超過限制
        if self.requests[key] > self.calls_per_minute:
            from app.core.error_handler import error_handler
            raise error_handler.handle_rate_limit_error(
                limit=self.calls_per_minute,
                window=60
            )
        
        # 繼續處理請求
        return await call_next(request)
    
    def _cleanup_old_records(self, current_minute: int):
        """清理舊的記錄"""
        # 清理超過 2 分鐘的記錄
        keys_to_remove = []
        for key in self.requests:
            if ":" in key:
                minute = int(key.split(":")[1])
                if current_minute - minute > 2:
                    keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.requests[key]


class CORSMiddleware:
    """自訂 CORS 中間件配置"""
    
    @staticmethod
    def get_cors_config() -> Dict[str, Any]:
        """獲取 CORS 配置"""
        return {
            "allow_origins": ["*"],  # 實際部署時應該限制域名
            "allow_credentials": True,
            "allow_methods": ["*"],
            "allow_headers": ["*"],
            "expose_headers": ["X-Request-ID", "X-Process-Time"]
        }
