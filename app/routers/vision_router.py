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
                    # 使用統一的工作流管理器
                    from app.core.workflow import workflow_manager
                    from app.core.memory import memory_manager
                    
                    # 載入用戶檔案
                    user_profile = memory_manager.load_user_profile(session_id) or {}
                    
                    # 準備工作流輸入
                    workflow_input = {
                        "user_input": "",  # WebSocket 只傳圖片
                        "session_id": session_id,
                        "has_image": True,
                        "image_data": image_data,
                        "image_source": "websocket_camera",  # 標記為WebSocket攝影機來源
                        "user_profile": user_profile,
                        "response_mode": "websocket"  # WebSocket模式
                    }
                    
                    # 使用修復的工作流管理器
                    workflow_result = await workflow_manager.execute_workflow(workflow_input)
                    
                    if workflow_result.success:
                        # 檢查是否有用戶資料更新
                        if workflow_result.metadata.get("updated_user_profile"):
                            updated_profile = workflow_result.metadata["updated_user_profile"]
                            memory_manager.save_user_profile(session_id, updated_profile)
                        
                        # 將分析結果傳回前端
                        await manager.send_personal_message({
                            "status": "processed",
                            "emotion": workflow_result.metadata.get("emotion_analysis", {}),
                            "content": workflow_result.content,
                            "agents_used": list(workflow_result.agent_results.keys())
                        }, session_id)
                    else:
                        await manager.send_personal_message({
                            "status": "error",
                            "message": "工作流處理失敗"
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
