#!/usr/bin/env python3
"""
VisionAgent 診斷測試
"""
import sys
import os
import asyncio
import base64
from PIL import Image
import io

# 添加專案路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.agents.vision_agent import VisionAgent
from app.config.settings import settings

async def test_vision_agent():
    """測試 VisionAgent 的基本功能"""
    print("=== VisionAgent 診斷測試 ===")
    
    # 1. 測試 settings 配置
    print(f"VISION_API_KEY: {settings.vision_api_key[:10]}...")
    print(f"VISION_BASE_URL: {settings.vision_base_url}")
    print(f"VISION_MODEL_NAME: {settings.vision_model_name}")
    
    # 2. 創建 VisionAgent
    try:
        agent = VisionAgent()
        print("✅ VisionAgent 創建成功")
    except Exception as e:
        print(f"❌ VisionAgent 創建失敗: {e}")
        return
    
    # 3. 測試 LLM 初始化
    try:
        llm = agent.llm
        print(f"✅ LLM 初始化成功: {type(llm)}")
    except Exception as e:
        print(f"❌ LLM 初始化失敗: {e}")
        return
    
    # 4. 創建一個簡單的測試圖片
    try:
        # 創建一個簡單的紅色方塊圖片
        img = Image.new('RGB', (100, 100), color='red')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
        print(f"✅ 測試圖片創建成功，大小: {len(image_data)} 字元")
    except Exception as e:
        print(f"❌ 測試圖片創建失敗: {e}")
        return
    
    # 5. 測試情緒分析
    try:
        print("🔍 開始情緒分析測試...")
        result = await agent.analyze_emotion(image_data)
        print(f"✅ 情緒分析完成: {result}")
    except Exception as e:
        print(f"❌ 情緒分析失敗: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_vision_agent())
