from typing import Dict, List, Optional
import re
from app.core.logger import logger

try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False


class TokenCounter:
    """Token 計算工具"""
    
    def __init__(self, model_name: str = "gpt-3.5-turbo"):
        self.model_name = model_name
        self.encoder = None
        
        if HAS_TIKTOKEN:
            try:
                self.encoder = tiktoken.encoding_for_model(model_name)
            except Exception as e:
                logger.warning(f"無法載入 tiktoken 編碼器: {e}")
                self.encoder = None
    
    def count_tokens(self, text: str) -> int:
        """計算文字的 token 數量"""
        if not text:
            return 0
        
        if self.encoder:
            try:
                return len(self.encoder.encode(text))
            except Exception as e:
                logger.warning(f"Token 計算錯誤: {e}")
                return self._approximate_token_count(text)
        else:
            return self._approximate_token_count(text)
    
    def _approximate_token_count(self, text: str) -> int:
        """近似計算 token 數量"""
        # 簡單的近似算法：一般來說，1 token ≈ 0.75 個英文單字 ≈ 2-3 個中文字
        # 這只是一個粗略的估算
        
        # 分別計算英文單字和中文字符
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_words = len(re.findall(r'\b[a-zA-Z]+\b', text))
        other_chars = len(text) - chinese_chars - sum(len(word) for word in re.findall(r'\b[a-zA-Z]+\b', text))
        
        # 近似計算
        tokens = (
            chinese_chars * 0.5 +  # 中文字符
            english_words * 1.3 +  # 英文單字
            other_chars * 0.3      # 其他字符（空格、標點等）
        )
        
        return max(1, int(tokens))
    
    def count_messages_tokens(self, messages: List[Dict]) -> int:
        """計算訊息列表的 token 數量"""
        total_tokens = 0
        
        for message in messages:
            # 計算訊息內容的 token
            content = message.get("content", "")
            role = message.get("role", "")
            
            # 內容 token
            content_tokens = self.count_tokens(content)
            
            # 角色 token
            role_tokens = self.count_tokens(role)
            
            # 訊息格式的額外 token（角色標記、格式字符等）
            format_tokens = 4  # 每個訊息大約 4 個格式 token
            
            total_tokens += content_tokens + role_tokens + format_tokens
        
        return total_tokens
    
    def estimate_response_tokens(self, prompt_tokens: int, max_tokens: Optional[int] = None) -> int:
        """估算回應的 token 數量"""
        if max_tokens:
            return min(max_tokens, prompt_tokens // 2)  # 簡單估算
        else:
            return min(1000, prompt_tokens // 3)  # 預設估算
    
    def is_within_limit(self, text: str, limit: int) -> bool:
        """檢查文字是否在 token 限制內"""
        return self.count_tokens(text) <= limit
    
    def truncate_text(self, text: str, max_tokens: int) -> str:
        """截斷文字以符合 token 限制"""
        if self.is_within_limit(text, max_tokens):
            return text
        
        # 簡單的截斷策略：逐字符截斷直到符合限制
        chars = list(text)
        while len(chars) > 0:
            current_text = ''.join(chars)
            if self.is_within_limit(current_text, max_tokens):
                return current_text
            chars.pop()
        
        return ""
    
    def get_model_limits(self) -> Dict[str, int]:
        """獲取模型的 token 限制"""
        limits = {
            "gpt-3.5-turbo": 4096,
            "gpt-3.5-turbo-16k": 16384,
            "gpt-4": 8192,
            "gpt-4-32k": 32768,
            "gpt-4-turbo": 128000,
            "gemini-pro": 32000,
            "gemini-pro-vision": 16000,
            "claude-3-sonnet": 200000,
            "claude-3-opus": 200000,
            "default": 4096
        }
        
        return limits
    
    def get_context_limit(self) -> int:
        """獲取當前模型的上下文限制"""
        limits = self.get_model_limits()
        return limits.get(self.model_name, limits["default"])


# 全域 token 計算器
def get_token_counter(model_name: str = "gpt-3.5-turbo") -> TokenCounter:
    """獲取 token 計算器實例"""
    return TokenCounter(model_name)
