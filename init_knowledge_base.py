"""
知識庫初始化腳本
用於初始化向量資料庫並新增基礎知識文檔
"""

import asyncio
from app.core.vector_db import vector_db


async def init_knowledge_base():
    """初始化知識庫"""
    print("🚀 開始初始化知識庫...")
    
    # 基礎知識文檔
    documents = [
        {
            "id": "product_intro_001",
            "content": "我們的 AI Sales 系統是一個多 Agent 架構的智能銷售平台，支援自動客戶互動、名片識別、行事曆管理等功能。系統採用最新的 LLM 技術，提供自然的對話體驗。",
            "source": "產品介紹.pdf",
            "title": "AI Sales 系統介紹",
            "category": "product",
            "created_at": "2024-01-01"
        },
        {
            "id": "pricing_basic_001", 
            "content": "基礎版：每月 $99，包含基本對話功能、名片識別、行事曆整合。支援最多 1000 次對話/月。適合小型企業使用。",
            "source": "定價方案.pdf",
            "title": "基礎版定價",
            "category": "pricing",
            "created_at": "2024-01-01"
        },
        {
            "id": "pricing_pro_001",
            "content": "專業版：每月 $299，包含所有基礎功能，加上 RAG 知識庫、高級分析、API 存取。支援最多 10000 次對話/月。適合中型企業。",
            "source": "定價方案.pdf", 
            "title": "專業版定價",
            "category": "pricing",
            "created_at": "2024-01-01"
        },
        {
            "id": "pricing_enterprise_001",
            "content": "企業版：每月 $999，包含所有功能，無限對話次數、專屬支援、客製化開發、私有部署選項。適合大型企業。",
            "source": "定價方案.pdf",
            "title": "企業版定價", 
            "category": "pricing",
            "created_at": "2024-01-01"
        },
        {
            "id": "features_chat_001",
            "content": "智能對話功能：支援多輪對話、上下文記憶、情緒識別。可以進行自然的銷售對話，理解客戶需求並提供個人化建議。",
            "source": "功能說明.pdf",
            "title": "智能對話功能",
            "category": "features",
            "created_at": "2024-01-01"
        },
        {
            "id": "features_ocr_001",
            "content": "名片 OCR 功能：自動識別名片上的文字資訊，提取姓名、職稱、公司、聯絡方式等，並自動建立客戶檔案。支援多種語言和格式。",
            "source": "功能說明.pdf",
            "title": "名片識別功能",
            "category": "features", 
            "created_at": "2024-01-01"
        },
        {
            "id": "features_calendar_001",
            "content": "行事曆整合：與 Google Calendar 深度整合，自動查詢空檔、安排會議、發送邀請。支援智能時間建議和衝突檢測。",
            "source": "功能說明.pdf",
            "title": "行事曆管理功能",
            "category": "features",
            "created_at": "2024-01-01"
        },
        {
            "id": "support_247_001",
            "content": "我們提供 24/7 技術支援服務，包含線上文檔、影片教學、即時客服和專人技術協助。企業版客戶享有優先支援和專屬客戶經理。",
            "source": "服務說明.pdf",
            "title": "技術支援服務",
            "category": "support",
            "created_at": "2024-01-01"
        },
        {
            "id": "integration_api_001",
            "content": "完整的 API 支援：提供 RESTful API 和 Webhook，支援與 CRM、ERP、行銷自動化工具等第三方系統整合。完整的 OpenAI 相容介面。",
            "source": "技術文檔.pdf",
            "title": "API 整合",
            "category": "technical",
            "created_at": "2024-01-01"
        },
        {
            "id": "security_compliance_001",
            "content": "安全與合規：符合 SOC 2、GDPR、CCPA 等國際標準。資料加密傳輸和儲存，支援私有雲部署，確保客戶資料安全。",
            "source": "安全說明.pdf",
            "title": "安全合規",
            "category": "security",
            "created_at": "2024-01-01"
        }
    ]
    
    # 新增文檔到向量資料庫
    success = await vector_db.add_documents(documents)
    
    if success:
        print(f"✅ 成功初始化 {len(documents)} 個知識文檔")
        
        # 顯示集合資訊
        info = vector_db.get_collection_info()
        print(f"📊 向量資料庫狀態: {info}")
        
        # 測試搜索功能
        print("\\n🔍 測試搜索功能...")
        test_queries = ["產品功能", "價格方案", "技術支援"]
        
        for query in test_queries:
            results = await vector_db.search_similar(query, top_k=2)
            print(f"查詢 '{query}' 找到 {len(results)} 個相關文檔")
            for i, result in enumerate(results[:1], 1):
                print(f"  {i}. {result.get('metadata', {}).get('title', 'Unknown')} (相似度: {result.get('score', 0):.2f})")
    else:
        print("❌ 知識庫初始化失敗")
    
    print("\\n🎉 知識庫初始化完成！")


async def test_rag_functionality():
    """測試 RAG 功能"""
    print("\\n🧪 測試 RAG Agent 功能...")
    
    from app.agents import RAGAgent
    
    rag_agent = RAGAgent()
    
    test_questions = [
        "你們的產品有什麼功能？",
        "基礎版的價格是多少？",
        "支援什麼樣的技術服務？"
    ]
    
    for question in test_questions:
        print(f"\\n❓ 問題: {question}")
        
        input_data = {
            "user_input": question,
            "session_id": "test_session",
        }
        
        response = await rag_agent.process(input_data)
        print(f"💬 回答: {response['content'][:100]}...")


if __name__ == "__main__":
    print("🚀 開始知識庫初始化和測試...")
    
    asyncio.run(init_knowledge_base())
    asyncio.run(test_rag_functionality())
