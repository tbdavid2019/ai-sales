"""
Google Calendar API 整合模組
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import os
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.logger import logger


class GoogleCalendarIntegration:
    """Google Calendar API 整合"""
    
    def __init__(self):
        self.credentials_file = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_FILE", "credentials.json")
        self.token_file = os.getenv("GOOGLE_CALENDAR_TOKEN_FILE", "token.json")
        self.scopes = os.getenv("GOOGLE_CALENDAR_SCOPES", "").split(",")
        self.calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
        self.service = None
        
        # 默認 scopes
        if not self.scopes or self.scopes == [""]:
            self.scopes = [
                'https://www.googleapis.com/auth/calendar.readonly',
                'https://www.googleapis.com/auth/calendar.events'
            ]
    
    async def initialize(self) -> bool:
        """初始化 Google Calendar API"""
        try:
            creds = None
            
            # 檢查是否有有效的 token
            if os.path.exists(self.token_file):
                creds = Credentials.from_authorized_user_file(self.token_file, self.scopes)
            
            # 如果沒有有效的憑證，需要重新授權
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                    except Exception as e:
                        logger.warning(f"Token 刷新失敗: {e}")
                        creds = None
                
                if not creds:
                    if not os.path.exists(self.credentials_file):
                        logger.error(f"Google Calendar 憑證文件不存在: {self.credentials_file}")
                        return False
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, self.scopes)
                    creds = flow.run_local_server(port=0)
                
                # 保存憑證
                with open(self.token_file, 'w') as token:
                    token.write(creds.to_json())
            
            # 建立 API 服務
            self.service = build('calendar', 'v3', credentials=creds)
            logger.info("Google Calendar API 初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"Google Calendar API 初始化失敗: {e}")
            return False
    
    async def check_availability(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """檢查指定時間段的可用性"""
        try:
            if not self.service:
                if not await self.initialize():
                    raise Exception("Google Calendar API 未初始化")
            
            # 轉換時間格式
            start_time_str = start_time.isoformat()
            end_time_str = end_time.isoformat()
            
            # 查詢事件
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=start_time_str,
                timeMax=end_time_str,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # 檢查衝突
            conflicts = []
            for event in events:
                if event.get('status') == 'cancelled':
                    continue
                    
                event_start = event['start'].get('dateTime', event['start'].get('date'))
                event_end = event['end'].get('dateTime', event['end'].get('date'))
                
                conflicts.append({
                    'id': event.get('id'),
                    'title': event.get('summary', '無標題'),
                    'start': event_start,
                    'end': event_end,
                    'location': event.get('location'),
                    'description': event.get('description')
                })
            
            is_available = len(conflicts) == 0
            
            return {
                'available': is_available,
                'conflicts': conflicts,
                'checked_period': {
                    'start': start_time_str,
                    'end': end_time_str
                }
            }
            
        except HttpError as e:
            logger.error(f"Google Calendar API 錯誤: {e}")
            return {
                'available': False,
                'conflicts': [],
                'error': f"API 錯誤: {e}"
            }
        except Exception as e:
            logger.error(f"檢查可用性失敗: {e}")
            return {
                'available': False,
                'conflicts': [],
                'error': str(e)
            }
    
    async def create_event(self, title: str, start_time: datetime, end_time: datetime, 
                          description: str = "", location: str = "", 
                          attendees: List[str] = None) -> Dict[str, Any]:
        """創建日曆事件"""
        try:
            if not self.service:
                if not await self.initialize():
                    raise Exception("Google Calendar API 未初始化")
            
            # 構建事件資料
            event = {
                'summary': title,
                'location': location,
                'description': description,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'Asia/Taipei',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'Asia/Taipei',
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},
                        {'method': 'popup', 'minutes': 10},
                    ],
                },
            }
            
            # 添加參與者
            if attendees:
                event['attendees'] = [{'email': email} for email in attendees]
            
            # 創建事件
            created_event = self.service.events().insert(
                calendarId=self.calendar_id,
                body=event
            ).execute()
            
            logger.info(f"成功創建日曆事件: {created_event.get('id')}")
            
            return {
                'success': True,
                'event_id': created_event.get('id'),
                'event_link': created_event.get('htmlLink'),
                'created_event': created_event
            }
            
        except HttpError as e:
            logger.error(f"創建事件失敗 (API 錯誤): {e}")
            return {
                'success': False,
                'error': f"API 錯誤: {e}"
            }
        except Exception as e:
            logger.error(f"創建事件失敗: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_events(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """獲取指定時間範圍的事件"""
        try:
            if not self.service:
                if not await self.initialize():
                    raise Exception("Google Calendar API 未初始化")
            
            # 查詢事件
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=start_time.isoformat(),
                timeMax=end_time.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # 格式化事件資料
            formatted_events = []
            for event in events:
                if event.get('status') == 'cancelled':
                    continue
                
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                
                formatted_events.append({
                    'id': event.get('id'),
                    'title': event.get('summary', '無標題'),
                    'start': start,
                    'end': end,
                    'location': event.get('location'),
                    'description': event.get('description'),
                    'status': event.get('status'),
                    'created': event.get('created'),
                    'updated': event.get('updated')
                })
            
            return formatted_events
            
        except HttpError as e:
            logger.error(f"獲取事件失敗 (API 錯誤): {e}")
            return []
        except Exception as e:
            logger.error(f"獲取事件失敗: {e}")
            return []
    
    async def update_event(self, event_id: str, **kwargs) -> Dict[str, Any]:
        """更新事件"""
        try:
            if not self.service:
                if not await self.initialize():
                    raise Exception("Google Calendar API 未初始化")
            
            # 獲取現有事件
            event = self.service.events().get(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            
            # 更新事件資料
            if 'title' in kwargs:
                event['summary'] = kwargs['title']
            if 'description' in kwargs:
                event['description'] = kwargs['description']
            if 'location' in kwargs:
                event['location'] = kwargs['location']
            if 'start_time' in kwargs:
                event['start']['dateTime'] = kwargs['start_time'].isoformat()
            if 'end_time' in kwargs:
                event['end']['dateTime'] = kwargs['end_time'].isoformat()
            
            # 更新事件
            updated_event = self.service.events().update(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=event
            ).execute()
            
            logger.info(f"成功更新事件: {event_id}")
            
            return {
                'success': True,
                'event_id': updated_event.get('id'),
                'updated_event': updated_event
            }
            
        except HttpError as e:
            logger.error(f"更新事件失敗 (API 錯誤): {e}")
            return {
                'success': False,
                'error': f"API 錯誤: {e}"
            }
        except Exception as e:
            logger.error(f"更新事件失敗: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def delete_event(self, event_id: str) -> Dict[str, Any]:
        """刪除事件"""
        try:
            if not self.service:
                if not await self.initialize():
                    raise Exception("Google Calendar API 未初始化")
            
            self.service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            
            logger.info(f"成功刪除事件: {event_id}")
            
            return {
                'success': True,
                'event_id': event_id
            }
            
        except HttpError as e:
            logger.error(f"刪除事件失敗 (API 錯誤): {e}")
            return {
                'success': False,
                'error': f"API 錯誤: {e}"
            }
        except Exception as e:
            logger.error(f"刪除事件失敗: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def find_free_time(self, start_date: datetime, end_date: datetime, 
                           duration_minutes: int = 60) -> List[Dict[str, Any]]:
        """尋找空閒時間段"""
        try:
            # 獲取指定範圍內的所有事件
            events = await self.get_events(start_date, end_date)
            
            # 工作時間設定 (9:00 - 18:00)
            work_start_hour = 9
            work_end_hour = 18
            
            free_slots = []
            current_day = start_date.date()
            end_day = end_date.date()
            
            while current_day <= end_day:
                # 每天的工作時間
                day_start = datetime.combine(current_day, datetime.min.time().replace(hour=work_start_hour))
                day_end = datetime.combine(current_day, datetime.min.time().replace(hour=work_end_hour))
                
                # 獲取當天的事件
                day_events = [
                    event for event in events
                    if datetime.fromisoformat(event['start'].replace('Z', '+00:00')).date() == current_day
                ]
                
                # 排序事件
                day_events.sort(key=lambda x: x['start'])
                
                # 尋找空閒時間段
                current_time = day_start
                
                for event in day_events:
                    event_start = datetime.fromisoformat(event['start'].replace('Z', '+00:00'))
                    event_end = datetime.fromisoformat(event['end'].replace('Z', '+00:00'))
                    
                    # 檢查是否有足夠的空閒時間
                    if (event_start - current_time).total_seconds() >= duration_minutes * 60:
                        free_slots.append({
                            'start': current_time.isoformat(),
                            'end': event_start.isoformat(),
                            'duration_minutes': int((event_start - current_time).total_seconds() / 60)
                        })
                    
                    current_time = max(current_time, event_end)
                
                # 檢查最後一個事件後的時間
                if (day_end - current_time).total_seconds() >= duration_minutes * 60:
                    free_slots.append({
                        'start': current_time.isoformat(),
                        'end': day_end.isoformat(),
                        'duration_minutes': int((day_end - current_time).total_seconds() / 60)
                    })
                
                current_day += timedelta(days=1)
            
            return free_slots
            
        except Exception as e:
            logger.error(f"尋找空閒時間失敗: {e}")
            return []


# 全域實例
google_calendar = GoogleCalendarIntegration()
