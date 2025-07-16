from typing import Dict, List, Optional, Any
import json
import redis
from datetime import datetime, timedelta
from app.config import settings


class MemoryManager:
    """記憶體管理系統"""
    
    def __init__(self):
        self.session_ttl = 3600  # 1小時
        self.memory_ttl = 86400  # 24小時
        
        # 嘗試連接 Redis，如果失敗則使用內建記憶體
        try:
            self.redis_client = redis.from_url(settings.redis_url)
            # 測試連接
            self.redis_client.ping()
            self.use_redis = True
            print("✅ Redis 連接成功")
        except Exception as e:
            print(f"⚠️  Redis 連接失敗，使用內建記憶體: {e}")
            self.redis_client = None
            self.use_redis = False
            # 使用內建字典作為記憶體儲存
            self._memory_store = {}
            self._session_store = {}
            self._profile_store = {}
    
    def _get_session_key(self, session_id: str) -> str:
        """獲取 session 鍵值"""
        return f"session:{session_id}"
    
    def _get_memory_key(self, user_id: str) -> str:
        """獲取記憶體鍵值"""
        return f"memory:{user_id}"
    
    def _get_user_profile_key(self, user_id: str) -> str:
        """獲取用戶資料鍵值"""
        return f"profile:{user_id}"
    
    def save_session(self, session_id: str, conversation_data: Dict[str, Any]) -> bool:
        """儲存會話資料"""
        try:
            if self.use_redis:
                key = self._get_session_key(session_id)
                value = json.dumps(conversation_data, ensure_ascii=False)
                self.redis_client.setex(key, self.session_ttl, value)
            else:
                # 使用內建記憶體儲存
                self._session_store[session_id] = {
                    'data': conversation_data,
                    'timestamp': datetime.now()
                }
            return True
        except Exception as e:
            print(f"儲存會話失敗: {e}")
            return False
    
    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """載入會話資料"""
        try:
            if self.use_redis:
                key = self._get_session_key(session_id)
                data = self.redis_client.get(key)
                if data:
                    return json.loads(data)
            else:
                # 使用內建記憶體儲存
                if session_id in self._session_store:
                    session_data = self._session_store[session_id]
                    # 檢查是否過期
                    if datetime.now() - session_data['timestamp'] < timedelta(seconds=self.session_ttl):
                        return session_data['data']
                    else:
                        # 清除過期資料
                        del self._session_store[session_id]
            return None
        except Exception as e:
            print(f"載入會話失敗: {e}")
            return None
    
    def save_user_profile(self, user_id: str, profile_data: Dict[str, Any]) -> bool:
        """儲存用戶資料"""
        try:
            if self.use_redis:
                key = self._get_user_profile_key(user_id)
                value = json.dumps(profile_data, ensure_ascii=False)
                self.redis_client.setex(key, self.memory_ttl, value)
            else:
                self._profile_store[user_id] = {
                    'data': profile_data,
                    'timestamp': datetime.now()
                }
            return True
        except Exception as e:
            print(f"儲存用戶資料失敗: {e}")
            return False
    
    def load_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """載入用戶資料"""
        try:
            if self.use_redis:
                key = self._get_user_profile_key(user_id)
                data = self.redis_client.get(key)
                if data:
                    return json.loads(data)
            else:
                if user_id in self._profile_store:
                    profile = self._profile_store[user_id]
                    if datetime.now() - profile['timestamp'] < timedelta(seconds=self.memory_ttl):
                        return profile['data']
                    else:
                        del self._profile_store[user_id]
            return None
        except Exception as e:
            print(f"載入用戶資料失敗: {e}")
            return None
    
    def add_conversation_history(self, session_id: str, role: str, content: str) -> bool:
        """新增對話歷史"""
        try:
            session_data = self.load_session(session_id) or {
                "messages": [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            # 新增訊息
            message = {
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat()
            }
            session_data["messages"].append(message)
            session_data["updated_at"] = datetime.now().isoformat()
            
            # 保持最近 20 條訊息
            if len(session_data["messages"]) > 20:
                session_data["messages"] = session_data["messages"][-20:]
            
            return self.save_session(session_id, session_data)
        except Exception as e:
            print(f"新增對話歷史失敗: {e}")
            return False
    
    def get_conversation_history(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """獲取對話歷史"""
        try:
            session_data = self.load_session(session_id)
            if session_data and "messages" in session_data:
                return session_data["messages"][-limit:]
            return []
        except Exception as e:
            print(f"獲取對話歷史失敗: {e}")
            return []
    
    def clear_session(self, session_id: str) -> bool:
        """清除會話資料"""
        try:
            if self.use_redis:
                key = self._get_session_key(session_id)
                self.redis_client.delete(key)
            else:
                if session_id in self._session_store:
                    del self._session_store[session_id]
            return True
        except Exception as e:
            print(f"清除會話失敗: {e}")
            return False
    
    def update_user_profile(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """更新用戶資料"""
        try:
            profile = self.load_user_profile(user_id) or {}
            profile.update(updates)
            profile["updated_at"] = datetime.now().isoformat()
            return self.save_user_profile(user_id, profile)
        except Exception as e:
            print(f"更新用戶資料失敗: {e}")
            return False


# 全域記憶體管理器實例
memory_manager = MemoryManager()
