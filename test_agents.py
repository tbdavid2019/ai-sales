"""
AI Sales 系統測試腳本
測試各個 Agent 的功能
"""

import asyncio
import json
from datetime import datetime


async def test_chat_agent():
    """測試 ChatAgent"""
    print("🤖 測試 ChatAgent...")
    
    from app.agents import ChatAgent
    
    chat_agent = ChatAgent()
    
    test_cases = [
        {
            "user_input": "你好，我想了解你們的服務",
            "session_id": "test_chat_001",
            "user_profile": {}
        },
        {
            "user_input": "我是一家科技公司的CTO，想找AI解決方案",
            "session_id": "test_chat_002", 
            "user_profile": {"name": "張總監", "title": "CTO", "company": "科技公司"}
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\\n測試案例 {i}:")
        print(f"輸入: {test_case['user_input']}")
        
        response = await chat_agent.process(test_case)
        print(f"回應: {response['content']}")
        print(f"元資料: {response['metadata']}")


async def test_rag_agent():
    """測試 RAGAgent"""
    print("\\n🔍 測試 RAGAgent...")
    
    from app.agents import RAGAgent
    
    rag_agent = RAGAgent()
    
    test_cases = [
        {
            "user_input": "你們的產品有哪些功能？",
            "session_id": "test_rag_001"
        },
        {
            "user_input": "專業版的價格是多少？",
            "session_id": "test_rag_002"
        },
        {
            "user_input": "支援什麼樣的技術整合？",
            "session_id": "test_rag_003"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\\n測試案例 {i}:")
        print(f"輸入: {test_case['user_input']}")
        
        response = await rag_agent.process(test_case)
        print(f"回應: {response['content']}")
        print(f"檢索到的文檔數: {response['metadata'].get('retrieved_docs', 0)}")


async def test_card_agent():
    """測試 CardAgent"""
    print("\\n🃏 測試 CardAgent...")
    
    from app.agents import CardAgent
    
    card_agent = CardAgent()
    
    # 模擬名片圖片（這裡用文字描述代替實際圖片）
    test_cases = [
        {
            "image_url": "https://example.com/business_card.jpg",
            "session_id": "test_card_001"
        },
        {
            "image_data": "base64_encoded_image_data_here",
            "session_id": "test_card_002"
        },
        {
            # 沒有圖片的測試案例
            "session_id": "test_card_003"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\\n測試案例 {i}:")
        print(f"輸入: {test_case}")
        
        response = await card_agent.process(test_case)
        print(f"回應: {response['content']}")
        print(f"元資料: {response['metadata']}")


async def test_calendar_agent():
    """測試 CalendarAgent"""
    print("\\n📅 測試 CalendarAgent...")
    
    from app.agents import CalendarAgent
    
    calendar_agent = CalendarAgent()
    
    test_cases = [
        {
            "user_input": "明天下午有空嗎？",
            "session_id": "test_calendar_001",
            "user_profile": {"name": "王經理"}
        },
        {
            "user_input": "安排下週三下午3點的會議",
            "session_id": "test_calendar_002",
            "user_profile": {"name": "李總監", "company": "ABC公司"}
        },
        {
            "user_input": "查看我今天的行程",
            "session_id": "test_calendar_003",
            "user_profile": {"name": "張主任"}
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\\n測試案例 {i}:")
        print(f"輸入: {test_case['user_input']}")
        
        response = await calendar_agent.process(test_case)
        print(f"回應: {response['content']}")
        print(f"元資料: {response['metadata']}")


async def test_control_agent():
    """測試 ControlAgent 路由功能"""
    print("\\n🎛️ 測試 ControlAgent...")
    
    from app.agents import ControlAgent
    
    control_agent = ControlAgent()
    
    test_cases = [
        {
            "user_input": "你好",
            "session_id": "test_control_001",
            "has_image": False
        },
        {
            "user_input": "這是我的名片",
            "session_id": "test_control_002", 
            "has_image": True
        },
        {
            "user_input": "明天下午有空嗎？",
            "session_id": "test_control_003",
            "has_image": False
        },
        {
            "user_input": "你們的產品價格如何？",
            "session_id": "test_control_004",
            "has_image": False
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\\n測試案例 {i}:")
        print(f"輸入: {test_case['user_input']}")
        print(f"有圖片: {test_case['has_image']}")
        
        response = await control_agent.process(test_case)
        print(f"路由決策: {response['metadata']['route_to']}")
        print(f"原因: {response['metadata']['reason']}")
        print(f"信心度: {response['metadata']['confidence']}")


async def test_memory_manager():
    """測試記憶體管理"""
    print("\\n🧠 測試記憶體管理...")
    
    from app.core.memory import memory_manager
    
    # 測試會話記憶
    session_id = "test_memory_001"
    
    # 新增對話歷史
    memory_manager.add_conversation_history(session_id, "user", "你好")
    memory_manager.add_conversation_history(session_id, "assistant", "您好！有什麼可以幫您的嗎？")
    memory_manager.add_conversation_history(session_id, "user", "我想了解產品價格")
    
    # 獲取對話歷史
    history = memory_manager.get_conversation_history(session_id)
    print(f"對話歷史 ({len(history)} 條):")
    for msg in history:
        print(f"  {msg['role']}: {msg['content']}")
    
    # 測試用戶資料
    user_profile = {
        "name": "測試用戶",
        "title": "產品經理",
        "company": "測試公司",
        "phone": "0912345678"
    }
    
    memory_manager.save_user_profile(session_id, user_profile)
    loaded_profile = memory_manager.load_user_profile(session_id)
    print(f"\\n用戶資料: {loaded_profile}")


async def test_vector_db():
    """測試向量資料庫"""
    print("\\n🗃️ 測試向量資料庫...")
    
    from app.core.vector_db import vector_db
    
    # 獲取集合資訊
    info = vector_db.get_collection_info()
    print(f"資料庫資訊: {info}")
    
    # 測試搜索
    search_queries = [
        "產品功能",
        "價格方案", 
        "技術支援",
        "API 整合"
    ]
    
    for query in search_queries:
        print(f"\\n搜索: '{query}'")
        results = await vector_db.search_similar(query, top_k=2)
        
        for i, result in enumerate(results, 1):
            title = result.get('metadata', {}).get('title', 'Unknown')
            score = result.get('score', 0)
            print(f"  {i}. {title} (相似度: {score:.2f})")


async def main():
    """主測試函數"""
    print("🚀 開始 AI Sales 系統測試\\n")
    print("=" * 50)
    
    # 按順序執行測試
    await test_memory_manager()
    await test_vector_db()
    await test_control_agent()
    await test_chat_agent()
    await test_rag_agent()
    await test_card_agent()
    await test_calendar_agent()
    
    print("\\n" + "=" * 50)
    print("🎉 所有測試完成！")


if __name__ == "__main__":
    asyncio.run(main())
