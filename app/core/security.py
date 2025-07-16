from typing import Optional, List
import hashlib
import hmac
import time
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings
from app.core.logger import logger
from app.core.error_handler import error_handler


class APIKeyValidator:
    """API 金鑰驗證器"""
    
    def __init__(self):
        self.valid_keys = self._load_api_keys()
    
    def _load_api_keys(self) -> List[str]:
        """載入有效的 API 金鑰"""
        # 從環境變數或設定檔載入
        api_keys = []
        
        # 從環境變數載入
        if hasattr(settings, 'api_keys') and settings.api_keys:
            api_keys.extend(settings.api_keys.split(','))
        
        # 預設測試金鑰（僅在開發環境）
        if settings.debug:
            api_keys.extend([
                "sk-test-aisales-dev-key-001",
                "sk-test-aisales-dev-key-002"
            ])
        
        return [key.strip() for key in api_keys if key.strip()]
    
    def validate_key(self, api_key: str) -> bool:
        """驗證 API 金鑰"""
        if not api_key:
            return False
        
        # 檢查是否在有效金鑰列表中
        if api_key in self.valid_keys:
            return True
        
        # 如果是開發模式，允許所有以 sk-test- 開頭的金鑰
        if settings.debug and api_key.startswith("sk-test-"):
            return True
        
        return False
    
    def get_key_info(self, api_key: str) -> Optional[dict]:
        """獲取 API 金鑰資訊"""
        if not self.validate_key(api_key):
            return None
        
        # 返回金鑰資訊
        return {
            "key_id": hashlib.md5(api_key.encode()).hexdigest()[:8],
            "is_test": api_key.startswith("sk-test-"),
            "created_at": time.time()
        }


class SecurityMiddleware:
    """安全性中間件"""
    
    def __init__(self):
        self.api_key_validator = APIKeyValidator()
        self.bearer_scheme = HTTPBearer(auto_error=False)
    
    async def validate_api_key(
        self, 
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
    ) -> str:
        """驗證 API 金鑰"""
        # 嘗試從 Authorization header 獲取
        api_key = None
        
        if credentials:
            api_key = credentials.credentials
        else:
            # 嘗試從 query 參數獲取
            api_key = request.query_params.get('api_key')
            
            # 嘗試從 headers 獲取
            if not api_key:
                api_key = request.headers.get('X-API-Key')
        
        # 如果沒有 API 金鑰
        if not api_key:
            logger.warning("API 請求缺少 API 金鑰", path=request.url.path)
            raise error_handler.handle_authentication_error("缺少 API 金鑰")
        
        # 驗證 API 金鑰
        if not self.api_key_validator.validate_key(api_key):
            logger.warning("無效的 API 金鑰", api_key_prefix=api_key[:10])
            raise error_handler.handle_authentication_error("無效的 API 金鑰")
        
        # 記錄驗證成功
        key_info = self.api_key_validator.get_key_info(api_key)
        logger.info(
            "API 金鑰驗證成功",
            key_id=key_info["key_id"],
            is_test=key_info["is_test"],
            path=request.url.path
        )
        
        return api_key
    
    def validate_request_signature(self, request: Request, secret_key: str) -> bool:
        """驗證請求簽名（可選的額外安全層）"""
        # 獲取簽名相關的 headers
        timestamp = request.headers.get('X-Timestamp')
        signature = request.headers.get('X-Signature')
        
        if not timestamp or not signature:
            return False
        
        # 檢查時間戳（防止重放攻擊）
        current_time = int(time.time())
        request_time = int(timestamp)
        
        if abs(current_time - request_time) > 300:  # 5 分鐘內有效
            return False
        
        # 構建簽名字符串
        method = request.method
        path = request.url.path
        query = str(request.query_params)
        
        signature_string = f"{method}{path}{query}{timestamp}"
        
        # 計算期望的簽名
        expected_signature = hmac.new(
            secret_key.encode(),
            signature_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # 比較簽名
        return hmac.compare_digest(signature, expected_signature)
    
    def sanitize_input(self, data: str) -> str:
        """清理輸入資料"""
        if not data:
            return ""
        
        # 移除危險字符
        dangerous_chars = ['<', '>', '"', "'", '&', '\x00']
        for char in dangerous_chars:
            data = data.replace(char, '')
        
        # 限制長度
        max_length = 10000
        if len(data) > max_length:
            data = data[:max_length]
        
        return data.strip()
    
    def check_content_safety(self, content: str) -> bool:
        """檢查內容安全性"""
        # 簡單的內容安全檢查
        dangerous_patterns = [
            r'javascript:',
            r'<script',
            r'</script>',
            r'eval\(',
            r'exec\(',
            r'__import__',
            r'subprocess',
            r'os\.system'
        ]
        
        import re
        content_lower = content.lower()
        
        for pattern in dangerous_patterns:
            if re.search(pattern, content_lower):
                return False
        
        return True


# 全域安全性中間件實例
security_middleware = SecurityMiddleware()


# 依賴注入函數
async def get_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> str:
    """獲取並驗證 API 金鑰的依賴注入函數"""
    return await security_middleware.validate_api_key(request, credentials)


def require_api_key(func):
    """需要 API 金鑰的裝飾器"""
    async def wrapper(*args, **kwargs):
        # 這個裝飾器在 FastAPI 中需要與 Depends 一起使用
        return await func(*args, **kwargs)
    return wrapper
