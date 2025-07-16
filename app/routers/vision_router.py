from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.workflow import VisionAgent, AgentFactory
import json

router = APIRouter()

# 實例化 VisionAgent
# 在實際應用中，你可能會希望透過依賴注入來管理 Agent 的生命週期
vision_agent = AgentFactory.create_agent("vision_agent")

@router.websocket("/ws/vision/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    處理視覺分析的 WebSocket 連線。
    接收來自前端的影像幀，並交由 VisionAgent 處理。
    """
    await websocket.accept()
    print(f"WebSocket connection established for session: {session_id}")
    try:
        while True:
            # 接收來自前端的資料
            data = await websocket.receive_text()
            
            # 假設前端傳送的是 JSON 字串，包含 image_data
            try:
                payload = json.loads(data)
                image_data = payload.get("image_data")

                if image_data:
                    # 呼叫 VisionAgent 進行處理
                    # 我們以非同步方式執行，避免阻塞 WebSocket
                    result = await vision_agent.process({
                        "image_data": image_data,
                        "session_id": session_id
                    })
                    
                    # (可選) 將分析結果傳回前端，用於調試或顯示
                    await websocket.send_json({
                        "status": "processed",
                        "emotion": result.get("metadata", {}).get("emotion_analysis", {})
                    })

            except json.JSONDecodeError:
                print("Received non-JSON message, ignoring.")
            except Exception as e:
                print(f"Error processing message: {e}")
                # 可以考慮將錯誤訊息傳回前端
                await websocket.send_json({"status": "error", "message": str(e)})

    except WebSocketDisconnect:
        print(f"WebSocket connection closed for session: {session_id}")
    except Exception as e:
        print(f"An unexpected error occurred in WebSocket for session {session_id}: {e}")
        await websocket.close(code=1011)
