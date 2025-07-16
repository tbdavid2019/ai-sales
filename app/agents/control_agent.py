from typing import Dict, Any, List, Optional
from app.agents.base_agent import BaseAgent
from app.models import LLMFactory
from app.core.logger import logger
from langchain_core.messages import HumanMessage, SystemMessage
import re
import json


class ControlAgent(BaseAgent):
    """控制 Agent - 決定哪個 Agent 應該處理請求"""
    
    def __init__(self):
        super().__init__(
            name="ControlAgent",
            description="AI 銷售系統的主控制器，負責分析用戶意圖並協調其他 Agent"
        )
        self.llm = LLMFactory.get_control_agent_llm()
        self.intent_patterns = self._load_intent_patterns()
        self.route_map = {
            "chat_agent": {
                "keywords": ["你好", "嗨", "hello", "介紹", "產品", "功能", "價格", "方案", "怎麼賣", "費用", "想了解", "請問", "開店", "電商", "網站"],
                "regex": None
            },
            "rag_agent": {
                "keywords": ["怎麼用", "如何", "教學", "文件", "設定", "串接", "金流", "物流", "訂單", "會員", "SEO", "行銷", "折扣", "庫存"],
                "regex": r"(?i)(how to|what is|explain).*"
            },
            "card_agent": {
                "keywords": ["名片"],
                "regex": None
            },
            # VisionAgent 通常由特定事件觸發，而不是關鍵字，但我們先保留一個位置
            "vision_agent": {
                "keywords": ["表情", "情緒", "攝影機", "鏡頭"],
                "regex": None
            }
        }

    def _load_intent_patterns(self) -> Dict[str, Dict[str, Any]]:
        """載入意圖識別模式"""
        return {
            "card_processing": {
                "keywords": ["名片", "卡片", "聯絡方式", "聯絡資訊", "公司資訊", "職位", "頭銜", "電話", "email"],
                "patterns": [r"這是.*名片", r"掃描.*卡片", r"識別.*資訊"],
                "priority": 10,
                "requires_image": True
            },
            "calendar_management": {
                "keywords": ["會議", "約", "時間", "行事曆", "空檔", "安排", "預約", "約定", "見面", "聚會", "演示", "demo", "簡報", "開店諮詢"],
                "patterns": [r"約.*時間", r"安排.*會議", r"查看.*行事曆", r"有空.*嗎", r"安排.*演示", r"預約.*demo", r"開店諮詢"],
                "priority": 8,
                "requires_image": False
            },
            "product_inquiry": {
                "keywords": ["開店", "商店", "網站", "平台", "功能", "規格", "技術", "服務", "方案", "比較", "優勢", "介紹", "demo", "金流", "物流", "範本", "設計", "APP", "擴充", "SEO"],
                "patterns": [r"平台.*介紹", r"功能.*說明", r"金流.*串接", r"物流.*設定", r"網站.*設計", r"開店.*方案"],
                "priority": 7,
                "requires_image": False
            },
            "personal_info_query": {
                "keywords": ["我叫", "我的名字", "我是誰", "我的資料", "我的資訊", "我的職位", "我的公司", "我的聯絡方式", "個人資訊", "個人資料"],
                "patterns": [r"我叫.*什麼", r"我的.*名字", r"我是.*誰", r"我的.*資料", r"我的.*資訊", r"我的.*職位", r"我的.*公司"],
                "priority": 9,
                "requires_image": False
            },
            "sales_inquiry": {
                "keywords": ["購買", "訂購", "報價", "優惠", "折扣", "方案", "費用", "價錢", "多少錢", "合作", "簽約", "試用", "月費", "年費", "開店成本"],
                "patterns": [r"多少.*錢", r"價格.*如何", r"費用.*是", r"想.*試用", r"方案.*費用", r"有.*優惠"],
                "priority": 8,
                "requires_image": False
            },
            "general_chat": {
                "keywords": ["你好", "謝謝", "再見", "問題", "幫助", "聊天", "閒聊"],
                "patterns": [r"你好", r"謝謝", r"再見", r"問候"],
                "priority": 1,
                "requires_image": False
            }
        }
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """分析用戶意圖並決定路由"""
        user_input = input_data.get("user_input", "")
        has_image = input_data.get("has_image", False)
        session_id = input_data.get("session_id", "")
        
        # 獲取對話歷史
        conversation_history = self.memory.get_conversation_history(session_id, limit=5)
        
        # 進行多層路由決策
        route_decision = await self._enhanced_route_decision(
            user_input, has_image, conversation_history
        )
        
        # 記錄路由決策
        logger.log_agent_action(
            agent_name=self.name,
            action="route_decision",
            session_id=session_id,
            target_agent=route_decision["primary_agent"],
            confidence=route_decision["confidence"],
            reason=route_decision["reason"]
        )
        
        return self.format_response(
            content=f"路由決策: {route_decision['primary_agent']}",
            metadata=route_decision
        )
    
    async def _enhanced_route_decision(
        self, 
        user_input: str, 
        has_image: bool, 
        history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """增強型路由決策"""
        
        # 1. 圖片處理具有最高優先級
        if has_image:
            primary_agent = "card_agent"
            agents = ["card_agent"]
            reason = "偵測到圖片上傳，使用 CardAgent 處理名片識別。"
            confidence = 1.0
            
            # 只有在有明確文字指令時才考慮並行處理
            if user_input.strip() and len(user_input.strip()) > 5:
                # 檢查是否有明確的非名片相關請求
                non_card_keywords = ["產品", "功能", "價格", "會議", "預約", "如何", "怎麼"]
                if any(keyword in user_input for keyword in non_card_keywords):
                    agents.append("chat_agent")
                    reason = "偵測到圖片和明確文字請求，並行處理名片和對話。"
                    execution_mode = "parallel"
                else:
                    execution_mode = "single"
            else:
                execution_mode = "single"

            return {
                "execution_mode": execution_mode,
                "primary_agent": primary_agent,
                "agents": agents,
                "confidence": confidence,
                "reason": reason
            }

        # 2. 基於規則的意圖匹配 (無圖片情況)
        matched_intents = self._match_intent_by_rules(user_input)
        
        # 3. 基於 LLM 的意圖分析
        llm_based_result = await self._llm_based_intent_analysis(user_input, history)
        
        # 4. 結合兩種結果
        final_decision = self._combine_intent_results(matched_intents, llm_based_result)
        
        # 5. 決定是否需要並行處理
        parallel_decision = self._decide_parallel_processing(user_input, final_decision)
        
        return {
            "primary_agent": final_decision["agent"],
            "secondary_agents": parallel_decision.get("secondary_agents", []),
            "execution_mode": "parallel" if parallel_decision.get("use_parallel", False) else "single",
            "reason": final_decision["reason"],
            "confidence": final_decision["confidence"],
            "parallel_processing": parallel_decision.get("use_parallel", False),
            "intent_details": {
                "rule_based": matched_intents,
                "llm_based": llm_based_result,
                "parallel_analysis": parallel_decision
            }
        }
    
    def _match_intent_by_rules(self, user_input: str) -> Dict[str, Any]:
        """基於規則的意圖匹配"""
        user_input_lower = user_input.lower()
        
        best_match = {
            "intent": "general_chat",
            "agent": "chat_agent",
            "confidence": 0.3,
            "matched_keywords": [],
            "matched_patterns": []
        }
        
        for intent, config in self.intent_patterns.items():
            score = 0
            matched_keywords = []
            matched_patterns = []
            
            # 檢查關鍵字
            for keyword in config["keywords"]:
                if keyword in user_input_lower:
                    score += 1
                    matched_keywords.append(keyword)
            
            # 檢查正規表達式
            for pattern in config["patterns"]:
                if re.search(pattern, user_input_lower):
                    score += 2
                    matched_patterns.append(pattern)
            
            # 計算置信度
            if score > 0:
                confidence = min(0.9, score * 0.2 + config["priority"] * 0.05)
                
                if confidence > best_match["confidence"]:
                    agent_mapping = {
                        "card_processing": "card_agent",
                        "calendar_management": "calendar_agent", 
                        "product_inquiry": "rag_agent",
                        "personal_info_query": "chat_agent",
                        "sales_inquiry": "chat_agent",
                        "general_chat": "chat_agent"
                    }
                    
                    best_match = {
                        "intent": intent,
                        "agent": agent_mapping[intent],
                        "confidence": confidence,
                        "matched_keywords": matched_keywords,
                        "matched_patterns": matched_patterns
                    }
        
        return best_match
    
    async def _llm_based_intent_analysis(
        self, 
        user_input: str, 
        history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """基於 LLM 的意圖分析"""
        try:
            # 構建 LLM 分析提示
            system_prompt = """你是一個意圖分析專家，請分析用戶輸入的意圖並決定最適合的處理方式。

可用的 Agent：
1. chat_agent: 一般對話、問候、閒聊、個人資訊查詢、銷售諮詢
2. card_agent: 名片處理、聯絡資訊提取
3. calendar_agent: 行事曆管理、會議安排、時間查詢
4. rag_agent: 產品查詢、技術支援、知識搜尋

特別注意：
- 個人資訊查詢（如「我叫什麼名字」、「我的資料」）應路由到 chat_agent
- 銷售相關問題（價格、購買、合作）應路由到 chat_agent
- 產品技術細節查詢應路由到 rag_agent

請以 JSON 格式回應：
{
    "intent": "意圖類型",
    "agent": "推薦的 agent",
    "confidence": 0.0-1.0,
    "reason": "推薦理由",
    "context_relevant": true/false
}"""
            
            history_context = ""
            if history:
                recent_messages = history[-3:]  # 最近 3 條
                history_context = "\n".join([
                    f"用戶: {msg.get('user_input', '')}"
                    for msg in recent_messages
                ])
            
            user_prompt = f"""
用戶輸入: {user_input}

對話歷史:
{history_context}

請分析用戶的意圖並推薦最適合的 Agent。
"""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # 解析 LLM 回應
            try:
                result = json.loads(response.content)
                return {
                    "intent": result.get("intent", "unknown"),
                    "agent": result.get("agent", "chat_agent"),
                    "confidence": float(result.get("confidence", 0.5)),
                    "reason": result.get("reason", "LLM 分析結果"),
                    "context_relevant": result.get("context_relevant", False)
                }
            except json.JSONDecodeError:
                # 如果 JSON 解析失敗，使用預設值
                return {
                    "intent": "general_chat",
                    "agent": "chat_agent",
                    "confidence": 0.5,
                    "reason": "LLM 回應解析失敗",
                    "context_relevant": False
                }
                
        except Exception as e:
            logger.error("LLM 意圖分析失敗", error=e)
            return {
                "intent": "general_chat",
                "agent": "chat_agent",
                "confidence": 0.3,
                "reason": "LLM 分析失敗，使用預設值",
                "context_relevant": False
            }
    
    def _combine_intent_results(
        self, 
        rule_based: Dict[str, Any], 
        llm_based: Dict[str, Any]
    ) -> Dict[str, Any]:
        """結合規則和 LLM 的分析結果"""
        
        # 如果兩種方法一致，提高置信度
        if rule_based["agent"] == llm_based["agent"]:
            combined_confidence = min(0.95, (rule_based["confidence"] + llm_based["confidence"]) / 2 + 0.1)
            return {
                "agent": rule_based["agent"],
                "confidence": combined_confidence,
                "reason": f"規則和 LLM 分析一致: {rule_based['reason']} & {llm_based['reason']}"
            }
        
        # 如果不一致，選擇置信度較高的
        if rule_based["confidence"] > llm_based["confidence"]:
            return {
                "agent": rule_based["agent"],
                "confidence": rule_based["confidence"],
                "reason": f"規則分析 (置信度: {rule_based['confidence']:.2f}): {rule_based.get('reason', '')}"
            }
        else:
            return {
                "agent": llm_based["agent"],
                "confidence": llm_based["confidence"],
                "reason": f"LLM 分析 (置信度: {llm_based['confidence']:.2f}): {llm_based['reason']}"
            }
    
    def _decide_parallel_processing(self, user_input: str, primary_decision: Dict[str, Any]) -> Dict[str, Any]:
        """決定是否使用並行處理"""
        user_input_lower = user_input.lower()
        
        # 複雜查詢模式
        complex_patterns = [
            r"比較.*產品.*時間",
            r"安排.*會議.*介紹.*產品",
            r"名片.*約.*時間",
            r"聯絡.*資訊.*安排.*會議"
        ]
        
        # 多類別關鍵字
        categories = {
            "time": ["會議", "約", "時間", "行事曆", "空檔", "安排", "預約"],
            "product": ["產品", "功能", "規格", "價格", "技術", "服務", "方案"],
            "contact": ["名片", "聯絡", "資訊", "公司", "職位", "電話", "email"]
        }
        
        matched_categories = []
        for category, keywords in categories.items():
            if any(keyword in user_input_lower for keyword in keywords):
                matched_categories.append(category)
        
        # 判斷是否需要並行處理
        use_parallel = (
            len(matched_categories) > 1 or
            any(re.search(pattern, user_input_lower) for pattern in complex_patterns) or
            len(user_input.split()) > 20  # 長查詢
        )
        
        secondary_agents = []
        if use_parallel:
            primary_agent = primary_decision["agent"]
            
            # 根據匹配的類別添加次要 Agent
            if "time" in matched_categories and primary_agent != "calendar_agent":
                secondary_agents.append("calendar_agent")
            if "product" in matched_categories and primary_agent != "rag_agent":
                secondary_agents.append("rag_agent")
            if "contact" in matched_categories and primary_agent != "card_agent":
                secondary_agents.append("card_agent")
        
        return {
            "use_parallel": use_parallel,
            "secondary_agents": secondary_agents,
            "matched_categories": matched_categories,
            "reason": f"匹配類別: {matched_categories}, 複雜查詢: {len(user_input.split()) > 20}"
        }
    
    def get_system_prompt(self) -> str:
        """獲取系統提示詞"""
        return """你是 AI 銷售系統的主控制器，負責：
1. 分析用戶輸入的意圖和上下文
2. 決定最適合的 Agent 來處理請求
3. 協調多個 Agent 的工作流程
4. 優化整體系統效能

你需要考慮：
- 用戶意圖的複雜程度
- 是否需要多個 Agent 協作
- 對話歷史和上下文
- 處理效率和用戶體驗

請始終以專業、友善的態度與用戶互動，並確保路由決策的準確性。"""
