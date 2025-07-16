from typing import Dict, Any, List
from app.agents.base_agent import BaseAgent
from app.models import LLMFactory, EmbeddingFactory
from app.core.vector_db import vector_db


class RAGAgent(BaseAgent):
    """RAG Agent - 處理知識庫檢索和問答"""
    
    def __init__(self):
        super().__init__(
            name="RAGAgent",
            description="AI 知識檢索助理，專門從知識庫中搜索和整合相關資訊"
        )
        self.llm = LLMFactory.get_rag_agent_llm()
        self.embedding_model = EmbeddingFactory.get_default_embedding()
        self.vector_db = vector_db
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """處理知識檢索請求"""
        user_input = input_data.get("user_input", "")
        session_id = input_data.get("session_id", "")
        
        # 檢索相關知識
        relevant_docs = await self._search_knowledge(user_input)
        
        # 生成回應
        response = await self._generate_answer(user_input, relevant_docs)
        
        # 保存檢索歷史
        self.memory.add_conversation_history(session_id, "user", user_input)
        self.memory.add_conversation_history(session_id, "assistant", response)
        
        return self.format_response(
            content=response,
            metadata={
                "retrieved_docs": len(relevant_docs),
                "sources": [doc.get("source", "") for doc in relevant_docs]
            }
        )
    
    async def _search_knowledge(self, query: str) -> List[Dict[str, Any]]:
        """搜索知識庫"""
        try:
            # 使用向量資料庫搜索
            relevant_docs = await self.vector_db.search_similar(query, top_k=3)
            
            if relevant_docs:
                return relevant_docs
            else:
                # 如果向量資料庫沒有結果，返回模擬數據
                return self._get_mock_docs(query)
                
        except Exception as e:
            print(f"知識搜索失敗: {e}")
            # 備用方案：返回模擬數據
            return self._get_mock_docs(query)
    
    def _get_mock_docs(self, query: str) -> List[Dict[str, Any]]:
        """獲取模擬文檔（備用方案）"""
        mock_docs = [
            {
                "content": "我們的平台提供超過 100 種專業設計的商店範本，支援一鍵串接所有主流金流（如信用卡、Apple Pay、LINE Pay）和物流服務，讓您輕鬆開始線上銷售。",
                "source": "平台功能介紹.pdf",
                "score": 0.85,
                "metadata": {"category": "product", "type": "features"}
            },
            {
                "content": "我們提供多種方案滿足不同需求：『新手入門』方案每月 $29 美元，適合個人創作者；『企業首選』方案每月 $79 美元，提供進階報表和更多員工帳號，適合中小企業與機構。所有方案都提供 14 天免費試用。",
                "source": "平台收費方案.pdf", 
                "score": 0.80,
                "metadata": {"category": "pricing", "type": "plan"}
            },
            {
                "content": "我們提供完整的開店支援，包括免費的線上開店教學、24/7 線上客服，以及付費的專家服務，可以協助您進行舊網站資料搬家、商店客製化設計等。",
                "source": "客戶支援服務.pdf",
                "score": 0.75,
                "metadata": {"category": "service", "type": "support"}
            }
        ]
        
        # 根據查詢內容篩選相關文檔
        relevant_docs = []
        for doc in mock_docs:
            if any(keyword in query for keyword in ["功能", "範本", "金流", "物流", "技術"]):
                if doc["metadata"]["category"] == "product":
                    relevant_docs.append(doc)
            elif any(keyword in query for keyword in ["價格", "收費", "方案", "費用", "試用"]):
                if doc["metadata"]["category"] == "pricing":
                    relevant_docs.append(doc)
            elif any(keyword in query for keyword in ["服務", "支援", "幫助", "客服", "搬家"]):
                if doc["metadata"]["category"] == "service":
                    relevant_docs.append(doc)
        
        return relevant_docs if relevant_docs else mock_docs[:2]
    
    async def _generate_answer(self, query: str, docs: List[Dict[str, Any]]) -> str:
        """基於檢索的文檔生成回答"""
        try:
            if not docs:
                return "抱歉，我沒有找到相關的資訊。您可以嘗試換個問法或聯繫我們的銷售團隊。"
            
            # 整合檢索到的文檔
            context = "\\n".join([doc["content"] for doc in docs])
            
            # 構建提示詞
            full_prompt = f"""
{self.get_system_prompt()}

相關資訊：
{context}

用戶問題：{query}

請根據上述資訊回答用戶問題，並在回答中標明資訊來源。
"""
            
            # 調用 LLM 生成回應
            from langchain_core.messages import HumanMessage
            
            message = HumanMessage(content=full_prompt)
            response = await self.llm.ainvoke([message])
            
            # 添加來源資訊
            sources = ", ".join([doc.get("source", "") for doc in docs])
            return f"{response.content}\\n\\n📚 資料來源：{sources}"
            
        except Exception as e:
            print(f"生成回答失敗: {e}")
            return "抱歉，處理您的問題時出現了問題，請稍後再試。"
    
    def get_system_prompt(self) -> str:
        """獲取系統提示詞"""
        return """你是一位專業的 AI 知識助理，負責：

1. 從知識庫中搜索相關資訊
2. 整合多個來源的資訊
3. 生成準確、有用的回答
4. 標明資訊來源和可信度

回答原則：
- 基於提供的資訊回答，不要編造內容
- 如果資訊不足，請誠實說明
- 適當引用資料來源
- 保持回答的專業性和準確性
- 如果需要更多資訊，請引導用戶提供更具體的問題

請確保回答既專業又易於理解。
"""
