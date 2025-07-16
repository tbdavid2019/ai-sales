import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
from app.config import settings

try:
    import structlog
    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False


class CustomLogger:
    """自訂日誌系統"""
    
    def __init__(self, name: str = "aisales"):
        self.name = name
        self.logger = self._setup_logger()
    
    def _setup_logger(self):
        """設定日誌"""
        # 創建 logs 目錄
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        if HAS_STRUCTLOG:
            return self._setup_structlog(logs_dir)
        else:
            return self._setup_standard_logging(logs_dir)
    
    def _setup_structlog(self, logs_dir: Path):
        """設定結構化日誌"""
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        
        logging.basicConfig(
            level=getattr(logging, settings.log_level.upper()),
            format="%(message)s",
            handlers=[
                logging.FileHandler(logs_dir / f"{self.name}.log"),
                logging.StreamHandler()
            ]
        )
        
        return structlog.get_logger(self.name)
    
    def _setup_standard_logging(self, logs_dir: Path):
        """設定標準日誌"""
        logger = logging.getLogger(self.name)
        logger.setLevel(getattr(logging, settings.log_level.upper()))
        
        # 防止重複添加 handler
        if not logger.handlers:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            
            # 文件 handler
            file_handler = logging.FileHandler(logs_dir / f"{self.name}.log")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            
            # 控制台 handler
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        
        return logger
    
    def _format_message(self, message: str, **kwargs) -> str:
        """格式化日誌訊息"""
        if kwargs:
            if HAS_STRUCTLOG:
                # structlog 會自動處理 kwargs
                return message
            else:
                # 手動格式化 JSON
                json_data = {
                    "message": message,
                    "timestamp": datetime.now().isoformat(),
                    **kwargs
                }
                return json.dumps(json_data, ensure_ascii=False)
        return message
    
    def info(self, message: str, **kwargs):
        """記錄資訊"""
        if HAS_STRUCTLOG:
            self.logger.info(message, **kwargs)
        else:
            self.logger.info(self._format_message(message, **kwargs))
    
    def warning(self, message: str, **kwargs):
        """記錄警告"""
        if HAS_STRUCTLOG:
            self.logger.warning(message, **kwargs)
        else:
            self.logger.warning(self._format_message(message, **kwargs))
    
    def error(self, message: str, error: Optional[Exception] = None, **kwargs):
        """記錄錯誤"""
        if error:
            kwargs['error'] = str(error)
            kwargs['error_type'] = type(error).__name__
        
        if HAS_STRUCTLOG:
            self.logger.error(message, **kwargs)
        else:
            self.logger.error(self._format_message(message, **kwargs))
    
    def debug(self, message: str, **kwargs):
        """記錄除錯資訊"""
        if HAS_STRUCTLOG:
            self.logger.debug(message, **kwargs)
        else:
            self.logger.debug(self._format_message(message, **kwargs))
    
    def log_api_request(self, request_id: str, method: str, path: str, **kwargs):
        """記錄 API 請求"""
        kwargs.update({
            "request_id": request_id,
            "method": method,
            "path": path,
            "timestamp": datetime.now().isoformat()
        })
        self.info("API Request", **kwargs)
    
    def log_agent_action(self, agent_name: str, action: str, session_id: str, **kwargs):
        """記錄 Agent 動作"""
        kwargs.update({
            "agent": agent_name,
            "action": action,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        })
        self.info("Agent Action", **kwargs)
    
    def log_performance(self, operation: str, duration: float, **kwargs):
        """記錄效能指標"""
        kwargs.update({
            "operation": operation,
            "duration_ms": duration * 1000
        })
        self.info("Performance", **kwargs)


# 全域日誌實例
logger = CustomLogger()
