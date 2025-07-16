from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import re
import os
from app.agents.base_agent import BaseAgent
from app.models import LLMFactory
from app.core.logger import logger

# 條件性導入 Google Calendar API
try:
    from app.integrations.google_calendar import google_calendar
    HAS_GOOGLE_CALENDAR = True
except ImportError:
    HAS_GOOGLE_CALENDAR = False
    logger.warning("Google Calendar API 不可用，將使用 Mock 模式")


class CalendarAgent(BaseAgent):
    """行事曆 Agent - 處理時間查詢和會議安排"""
    
    def __init__(self):
        super().__init__(
            name="CalendarAgent",
            description="AI 行事曆助理，專門處理時間查詢、空檔查找和會議安排"
        )
        self.llm = LLMFactory.get_calendar_agent_llm()
        self.use_google_calendar = HAS_GOOGLE_CALENDAR and os.getenv("GOOGLE_CALENDAR_CREDENTIALS_FILE")
        
        if self.use_google_calendar:
            logger.info("CalendarAgent 將使用真實的 Google Calendar API")
        else:
            logger.info("CalendarAgent 將使用 Mock 模式")
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """處理行事曆相關請求"""
        user_input = input_data.get("user_input", "")
        session_id = input_data.get("session_id", "")
        user_profile = input_data.get("user_profile", {})
        
        # 解析時間意圖
        time_intent = await self._parse_time_intent(user_input)
        
        if time_intent["action"] == "check_availability":
            return await self._check_availability(time_intent, session_id, user_profile)
        elif time_intent["action"] == "schedule_meeting":
            return await self._schedule_meeting(time_intent, session_id, user_profile)
        elif time_intent["action"] == "query_schedule":
            return await self._query_schedule(time_intent, session_id, user_profile)
        else:
            return await self._general_time_response(user_input, session_id)
    
    async def _parse_time_intent(self, user_input: str) -> Dict[str, Any]:
        """解析時間相關意圖"""
        try:
            # 使用 LLM 解析時間意圖
            prompt = f"""
請分析以下用戶輸入的時間相關意圖，並以 JSON 格式返回：

用戶輸入：{user_input}

請返回：
{{
    "action": "check_availability|schedule_meeting|query_schedule|general",
    "datetime": "YYYY-MM-DD HH:MM",
    "duration": 60,
    "description": "會議描述",
    "participants": ["參與者1", "參與者2"],
    "confidence": 0.85
}}

時間格式：使用 24 小時制
動作類型：
- check_availability: 查詢空檔
- schedule_meeting: 安排會議
- query_schedule: 查詢行程
- general: 一般時間相關問題

只返回 JSON，不要其他說明。
"""
            
            from langchain_core.messages import HumanMessage
            
            message = HumanMessage(content=prompt)
            response = await self.llm.ainvoke([message])
            
            try:
                import json
                intent = json.loads(response.content.strip())
                return intent
            except json.JSONDecodeError:
                # 備用簡單解析
                return self._simple_time_parse(user_input)
                
        except Exception as e:
            print(f"時間意圖解析失敗: {e}")
            return self._simple_time_parse(user_input)
    
    def _simple_time_parse(self, user_input: str) -> Dict[str, Any]:
        """簡單的時間解析（備用方法）"""
        intent = {
            "action": "general",
            "datetime": "",
            "duration": 60,
            "description": "",
            "participants": [],
            "confidence": 0.5
        }
        
        # 檢查關鍵字
        if any(word in user_input for word in ["安排", "約", "會議", "預約"]):
            intent["action"] = "schedule_meeting"
        elif any(word in user_input for word in ["空檔", "有空", "可以"]):
            intent["action"] = "check_availability"
        elif any(word in user_input for word in ["行程", "行事曆", "日程"]):
            intent["action"] = "query_schedule"
        
        # 簡單時間提取
        today = datetime.now()
        if "今天" in user_input:
            intent["datetime"] = today.strftime("%Y-%m-%d 14:00")
        elif "明天" in user_input:
            tomorrow = today + timedelta(days=1)
            intent["datetime"] = tomorrow.strftime("%Y-%m-%d 14:00")
        elif "下週" in user_input:
            next_week = today + timedelta(days=7)
            intent["datetime"] = next_week.strftime("%Y-%m-%d 14:00")
        
        return intent
    
    async def _check_availability(self, intent: Dict[str, Any], session_id: str, user_profile: Dict[str, Any]) -> Dict[str, Any]:
        """查詢時間空檔"""
        try:
            datetime_str = intent.get("datetime", "")
            
            if not datetime_str:
                return self.format_response(
                    content="請指定您想查詢空檔的具體時間，例如：「明天下午有空嗎？」",
                    metadata={"error": "no_datetime_specified"}
                )
            
            # 解析時間
            try:
                target_datetime = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
            except ValueError:
                return self.format_response(
                    content="時間格式錯誤，請使用正確的時間格式",
                    metadata={"error": "invalid_datetime_format"}
                )
            
            # 檢查可用性
            if self.use_google_calendar:
                availability = await self._check_google_calendar(target_datetime, intent.get("duration", 60))
            else:
                availability = await self._mock_check_calendar(datetime_str)
            
            if availability["available"]:
                response = f"好消息！{datetime_str} 這個時間我有空檔。您想安排什麼會議嗎？"
                
                # 如果有找到空閒時間段，提供更詳細的資訊
                if "free_slots" in availability:
                    free_slots = availability["free_slots"][:3]  # 只顯示前3個
                    response += f"\n\n可用時間段：\n"
                    for slot in free_slots:
                        start = datetime.fromisoformat(slot["start"])
                        end = datetime.fromisoformat(slot["end"])
                        response += f"• {start.strftime('%H:%M')} - {end.strftime('%H:%M')} ({slot['duration_minutes']}分鐘)\n"
                        
            else:
                conflicts_info = ""
                if availability.get("conflicts"):
                    conflicts_info = "\n\n現有安排：\n"
                    for conflict in availability["conflicts"][:3]:  # 只顯示前3個衝突
                        conflicts_info += f"• {conflict.get('title', '會議')}\n"
                
                alternative_times = self._suggest_alternative_times(datetime_str)
                response = f"抱歉，{datetime_str} 已經有安排了。{conflicts_info}\n建議的替代時間：{', '.join(alternative_times)}"
            
            return self.format_response(
                content=response,
                metadata={
                    "availability": availability,
                    "requested_time": datetime_str,
                    "google_calendar_used": self.use_google_calendar
                }
            )
            
        except Exception as e:
            logger.error(f"查詢空檔失敗: {e}")
            return self.format_response(
                content="查詢行事曆時發生錯誤，請稍後再試。",
                metadata={"error": str(e)}
            )
    
    async def _schedule_meeting(self, intent: Dict[str, Any], session_id: str, user_profile: Dict[str, Any]) -> Dict[str, Any]:
        """安排會議"""
        try:
            datetime_str = intent.get("datetime", "")
            duration = intent.get("duration", 60)
            description = intent.get("description", "會議")
            
            if not datetime_str:
                return self.format_response(
                    content="請指定會議時間，例如：「明天下午3點安排一個會議」",
                    metadata={"error": "no_datetime_specified"}
                )
            
            # 解析時間
            try:
                start_time = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
                end_time = start_time + timedelta(minutes=duration)
            except ValueError:
                return self.format_response(
                    content="時間格式錯誤，請使用正確的時間格式",
                    metadata={"error": "invalid_datetime_format"}
                )
            
            # 檢查時間是否可用
            if self.use_google_calendar:
                availability = await self._check_google_calendar(start_time, duration)
            else:
                availability = await self._mock_check_calendar(datetime_str)
            
            if availability["available"]:
                # 創建會議
                if self.use_google_calendar:
                    meeting_result = await self._create_google_meeting(
                        start_time, end_time, description, user_profile
                    )
                else:
                    meeting_result = await self._mock_create_meeting(
                        datetime_str, duration, description, user_profile
                    )
                
                if meeting_result.get("success", True):
                    response = f"會議已成功安排！\n時間：{start_time.strftime('%Y-%m-%d %H:%M')}\n時長：{duration}分鐘\n內容：{description}"
                    
                    if user_profile.get("name"):
                        response += f"\n參與者：{user_profile['name']}"
                    
                    if self.use_google_calendar and meeting_result.get("event_link"):
                        response += f"\n會議連結：{meeting_result['event_link']}"
                    
                    return self.format_response(
                        content=response,
                        metadata={
                            "meeting_created": True,
                            "meeting_info": meeting_result,
                            "google_calendar_used": self.use_google_calendar
                        }
                    )
                else:
                    return self.format_response(
                        content=f"會議安排失敗：{meeting_result.get('error', '未知錯誤')}",
                        metadata={"meeting_created": False, "error": meeting_result.get("error")}
                    )
            else:
                alternative_times = self._suggest_alternative_times(datetime_str)
                conflicts_info = ""
                if availability.get("conflicts"):
                    conflicts_info = "\n\n現有安排：\n"
                    for conflict in availability["conflicts"][:3]:
                        conflicts_info += f"• {conflict.get('title', '會議')}\n"
                
                response = f"抱歉，{datetime_str} 已有安排。{conflicts_info}\n建議時間：{', '.join(alternative_times)}"
                
                return self.format_response(
                    content=response,
                    metadata={
                        "meeting_created": False,
                        "alternative_times": alternative_times,
                        "conflicts": availability.get("conflicts", [])
                    }
                )
                
        except Exception as e:
            logger.error(f"安排會議失敗: {e}")
            return self.format_response(
                content="安排會議時發生錯誤，請稍後再試。",
                metadata={"error": str(e)}
            )
    
    async def _query_schedule(self, intent: Dict[str, Any], session_id: str, user_profile: Dict[str, Any]) -> Dict[str, Any]:
        """查詢行程"""
        try:
            datetime_str = intent.get("datetime", "")
            
            # 解析查詢時間範圍
            if datetime_str:
                try:
                    target_date = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
                except ValueError:
                    target_date = datetime.now()
            else:
                target_date = datetime.now()
            
            # 設定查詢範圍 (一天)
            start_time = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = start_time + timedelta(days=1)
            
            # 查詢行程
            if self.use_google_calendar:
                schedule = await self._get_google_schedule(start_time, end_time)
            else:
                schedule = await self._mock_get_schedule(datetime_str)
            
            if schedule:
                response = f"您在 {start_time.strftime('%Y-%m-%d')} 的行程如下：\n"
                for item in schedule:
                    start_time_str = item.get('start', '')
                    if start_time_str:
                        try:
                            start_dt = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                            time_str = start_dt.strftime('%H:%M')
                        except:
                            time_str = item.get('time', '未知時間')
                    else:
                        time_str = item.get('time', '未知時間')
                    
                    title = item.get('title', '無標題')
                    location = item.get('location', '')
                    
                    response += f"• {time_str} - {title}"
                    if location:
                        response += f" ({location})"
                    response += "\n"
            else:
                response = f"您在 {start_time.strftime('%Y-%m-%d')} 沒有安排任何行程。"
            
            return self.format_response(
                content=response,
                metadata={
                    "schedule": schedule,
                    "query_time": datetime_str,
                    "google_calendar_used": self.use_google_calendar
                }
            )
            
        except Exception as e:
            logger.error(f"查詢行程失敗: {e}")
            return self.format_response(
                content="查詢行程時發生錯誤，請稍後再試。",
                metadata={"error": str(e)}
            )
    
    async def _general_time_response(self, user_input: str, session_id: str) -> Dict[str, Any]:
        """一般時間相關回應"""
        response = "我可以幫您查詢空檔、安排會議或查看行程。請告訴我具體的時間需求。"
        
        return self.format_response(
            content=response,
            metadata={"type": "general_time_help"}
        )
    
    # Google Calendar API 方法
    async def _check_google_calendar(self, target_datetime: datetime, duration_minutes: int = 60) -> Dict[str, Any]:
        """檢查 Google Calendar 可用性"""
        try:
            if not HAS_GOOGLE_CALENDAR:
                return await self._mock_check_calendar(target_datetime.isoformat())
            
            # 初始化 Google Calendar API
            if not await google_calendar.initialize():
                logger.warning("Google Calendar API 初始化失敗，使用 Mock 模式")
                return await self._mock_check_calendar(target_datetime.isoformat())
            
            # 檢查指定時間的可用性
            end_time = target_datetime + timedelta(minutes=duration_minutes)
            availability = await google_calendar.check_availability(target_datetime, end_time)
            
            # 如果不可用，嘗試找到附近的空閒時間
            if not availability["available"]:
                # 尋找當天的空閒時間
                day_start = target_datetime.replace(hour=9, minute=0, second=0, microsecond=0)
                day_end = target_datetime.replace(hour=18, minute=0, second=0, microsecond=0)
                
                free_slots = await google_calendar.find_free_time(
                    day_start, day_end, duration_minutes
                )
                availability["free_slots"] = free_slots
            
            return availability
            
        except Exception as e:
            logger.error(f"Google Calendar 檢查失敗: {e}")
            return await self._mock_check_calendar(target_datetime.isoformat())
    
    async def _create_google_meeting(self, start_time: datetime, end_time: datetime, 
                                   description: str, user_profile: Dict[str, Any]) -> Dict[str, Any]:
        """使用 Google Calendar API 創建會議"""
        try:
            if not HAS_GOOGLE_CALENDAR:
                return await self._mock_create_meeting(
                    start_time.isoformat(), 
                    int((end_time - start_time).total_seconds() / 60), 
                    description, 
                    user_profile
                )
            
            # 初始化 Google Calendar API
            if not await google_calendar.initialize():
                logger.warning("Google Calendar API 初始化失敗，使用 Mock 模式")
                return await self._mock_create_meeting(
                    start_time.isoformat(), 
                    int((end_time - start_time).total_seconds() / 60), 
                    description, 
                    user_profile
                )
            
            # 準備參與者列表
            attendees = []
            if user_profile.get("email"):
                attendees.append(user_profile["email"])
            
            # 創建會議
            result = await google_calendar.create_event(
                title=description,
                start_time=start_time,
                end_time=end_time,
                description=f"會議主題：{description}",
                attendees=attendees
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Google Calendar 創建會議失敗: {e}")
            return await self._mock_create_meeting(
                start_time.isoformat(), 
                int((end_time - start_time).total_seconds() / 60), 
                description, 
                user_profile
            )
    
    async def _get_google_schedule(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """從 Google Calendar 獲取行程"""
        try:
            if not HAS_GOOGLE_CALENDAR:
                return await self._mock_get_schedule(start_time.isoformat())
            
            # 初始化 Google Calendar API
            if not await google_calendar.initialize():
                logger.warning("Google Calendar API 初始化失敗，使用 Mock 模式")
                return await self._mock_get_schedule(start_time.isoformat())
            
            # 獲取事件
            events = await google_calendar.get_events(start_time, end_time)
            
            # 轉換格式以匹配現有介面
            formatted_events = []
            for event in events:
                formatted_events.append({
                    'id': event.get('id'),
                    'title': event.get('title'),
                    'start': event.get('start'),
                    'end': event.get('end'),
                    'time': event.get('start', '').split('T')[1][:5] if 'T' in event.get('start', '') else '',
                    'location': event.get('location'),
                    'description': event.get('description')
                })
            
            return formatted_events
            
        except Exception as e:
            logger.error(f"Google Calendar 獲取行程失敗: {e}")
            return await self._mock_get_schedule(start_time.isoformat())
    
    # Mock 方法 (備用)
    
    async def _mock_check_calendar(self, datetime_str: str) -> Dict[str, Any]:
        """模擬行事曆查詢（實際應整合 Google Calendar API）"""
        import random
        
        # 模擬返回可用性
        return {
            "available": random.choice([True, False]),
            "conflicts": [] if random.choice([True, False]) else [
                {"time": "14:00-15:00", "title": "團隊會議"}
            ]
        }
    
    async def _mock_create_meeting(self, datetime_str: str, duration: int, description: str, user_profile: Dict[str, Any]) -> Dict[str, Any]:
        """模擬建立會議"""
        return {
            "id": f"meeting_{datetime.now().timestamp()}",
            "datetime": datetime_str,
            "duration": duration,
            "description": description,
            "attendees": [user_profile.get("name", "客戶")]
        }
    
    async def _mock_get_schedule(self, datetime_str: str) -> List[Dict[str, Any]]:
        """模擬獲取行程"""
        # 模擬返回行程
        return [
            {"time": "09:00", "title": "晨會"},
            {"time": "14:00", "title": "客戶會議"},
            {"time": "16:30", "title": "專案討論"}
        ]
    
    def _suggest_alternative_times(self, original_time: str) -> List[str]:
        """建議替代時間"""
        try:
            # 解析原始時間並建議替代方案
            from datetime import datetime, timedelta
            
            # 簡單的替代時間建議
            alternatives = [
                "明天同一時間",
                "後天下午",
                "下週同一時間"
            ]
            
            return alternatives
            
        except Exception:
            return ["請提供其他可行的時間"]
    
    def get_system_prompt(self) -> str:
        """獲取系統提示詞"""
        return """你是一位專業的行事曆管理助理，具備以下能力：

1. 時間解析：精確理解各種時間表達方式
2. 空檔查詢：快速查找可用的時間段
3. 會議安排：高效安排和管理會議
4. 行程管理：整合和優化日程安排

處理原則：
- 準確理解時間需求
- 提供清晰的可用性資訊
- 主動建議替代方案
- 確認會議細節

請始終以高效、準確的方式處理時間相關需求。
"""
