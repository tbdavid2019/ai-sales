from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.agents.vision_agent import VisionAgent
import json
import asyncio
from typing import Dict, Set

router = APIRouter()

# 連線管理器
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.session_agents: Dict[str, VisionAgent] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        self.session_agents[session_id] = VisionAgent()
        print(f"WebSocket connection established for session: {session_id}")
    
    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        if session_id in self.session_agents:
            del self.session_agents[session_id]
        print(f"WebSocket connection closed for session: {session_id}")
    
    async def send_personal_message(self, message: dict, session_id: str):
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            await websocket.send_json(message)
    
    def get_agent(self, session_id: str) -> VisionAgent:
        return self.session_agents.get(session_id)

# 全域連線管理器
manager = ConnectionManager()

@router.websocket("/ws/vision/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    處理視覺分析的 WebSocket 連線。
    接收來自前端的影像幀，並交由 VisionAgent 處理。
    """
    await manager.connect(websocket, session_id)
    try:
        while True:
            # 接收來自前端的資料
            data = await websocket.receive_text()
            
            # 假設前端傳送的是 JSON 字串，包含 image_data
            try:
                payload = json.loads(data)
                image_data = payload.get("image_data")

                if image_data:
                    # 取得對應的 VisionAgent
                    vision_agent = manager.get_agent(session_id)
                    if vision_agent:
                        # 呼叫 VisionAgent 進行處理
                        result = await vision_agent.process({
                            "image_data": image_data,
                            "session_id": session_id
                        })
                        
                        # 將分析結果傳回前端
                        await manager.send_personal_message({
                            "status": "processed",
                            "emotion": result.get("metadata", {}).get("emotion_analysis", {}),
                            "content": result.get("content", "")
                        }, session_id)
                    else:
                        await manager.send_personal_message({
                            "status": "error", 
                            "message": "VisionAgent not found"
                        }, session_id)

            except json.JSONDecodeError:
                print("Received non-JSON message, ignoring.")
                await manager.send_personal_message({
                    "status": "error", 
                    "message": "Invalid JSON format"
                }, session_id)
            except Exception as e:
                print(f"Error processing message: {e}")
                await manager.send_personal_message({
                    "status": "error", 
                    "message": str(e)
                }, session_id)

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        print(f"An unexpected error occurred in WebSocket for session {session_id}: {e}")
        manager.disconnect(session_id)
        await websocket.close(code=1011)
