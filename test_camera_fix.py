#!/usr/bin/env python3
"""
測試攝影機修復效果
"""

import asyncio
import sys
sys.path.append('.')

from app.core.workflow import workflow_manager
from app.core.memory import memory_manager

async def test_camera_fix():
    """測試攝影機修復效果"""
    
    print("=== 測試攝影機修復效果 ===\n")
    
    # 測試案例1：先掃描名片
    print("1. 測試名片掃描...")
    card_input = {
        "user_input": "",  # 純圖片上傳
        "has_image": True,
        "image_source": "upload",
        "session_id": "test_session_001"
    }
    
    card_result = await workflow_manager.execute_workflow(card_input)
    print(f"名片掃描結果: {card_result.success}")
    print(f"使用的 Agent: {list(card_result.agent_results.keys())}")
    print(f"回應內容: {card_result.content[:100]}...")
    
    # 模擬名片資訊被儲存
    mock_card_info = {
        "name": "王大偉",
        "company": "國立臺灣科技大學",
        "title": "教授",
        "phone": "02-1234-5678",
        "email": "wang@ntust.edu.tw"
    }
    memory_manager.update_user_profile("test_session_001", mock_card_info)
    
    print("\n" + "="*50 + "\n")
    
    # 測試案例2：啟動攝影機後對話
    print("2. 測試攝影機對話...")
    camera_input = {
        "user_input": "你好啊",
        "has_image": True,
        "image_source": "camera",  # 攝影機來源
        "session_id": "test_session_001"
    }
    
    camera_result = await workflow_manager.execute_workflow(camera_input)
    print(f"攝影機對話結果: {camera_result.success}")
    print(f"使用的 Agent: {list(camera_result.agent_results.keys())}")
    print(f"回應內容: {camera_result.content[:200]}...")
    
    # 檢查是否正確識別了用戶資料
    if "王大偉" in camera_result.content:
        print("✅ 成功識別用戶資料！")
    else:
        print("❌ 未能正確識別用戶資料")
    
    # 檢查是否使用了正確的 Agent 組合
    expected_agents = {"chat_agent", "vision_agent"}
    actual_agents = set(camera_result.agent_results.keys())
    
    if expected_agents.issubset(actual_agents):
        print("✅ Agent 路由正確！")
    else:
        print(f"❌ Agent 路由有誤。期望: {expected_agents}, 實際: {actual_agents}")
    
    print("\n" + "="*50 + "\n")
    
    # 測試案例3：測試錯誤情況
    print("3. 測試錯誤情況修復...")
    error_input = {
        "user_input": "抱歉，無法清楚識別名片內容。請確保圖片清晰且包含完整的名片資訊。",
        "has_image": True,
        "image_source": "camera",
        "session_id": "test_session_001"
    }
    
    error_result = await workflow_manager.execute_workflow(error_input)
    print(f"錯誤情況處理結果: {error_result.success}")
    print(f"使用的 Agent: {list(error_result.agent_results.keys())}")
    print(f"回應內容: {error_result.content[:200]}...")
    
    # 檢查是否正確處理了錯誤情況
    if "card_agent" not in error_result.agent_results:
        print("✅ 正確避免了錯誤的名片處理！")
    else:
        print("❌ 仍然錯誤地嘗試處理名片")

if __name__ == "__main__":
    asyncio.run(test_camera_fix())