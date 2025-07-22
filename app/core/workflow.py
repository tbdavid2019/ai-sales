from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

from app.core.logger import logger
from app.core.error_handler import error_handler
from app.core.memory import memory_manager
from app.agents import ControlAgent, ChatAgent, RAGAgent, CardAgent, CalendarAgent
from app.agents.rag_agent import RAGAgent
from app.agents.card_agent import CardAgent
from app.agents.chat_agent import ChatAgent
from app.agents.vision_agent import VisionAgent # 新增這行

try:
    from langgraph.graph import StateGraph, END
    from langgraph.prebuilt import ToolExecutor
    HAS_LANGGRAPH = True
except ImportError:
    HAS_LANGGRAPH = False


class WorkflowState(Enum):
    """工作流狀態"""
    PENDING = "pending"
    ROUTING = "routing"
    PROCESSING = "processing"
    PARALLEL_PROCESSING = "parallel_processing"
    AGGREGATING = "aggregating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentTask:
    """Agent 任務"""
    agent_name: str
    task_data: Dict[str, Any]
    priority: int = 1
    dependencies: List[str] = None
    timeout: int = 30
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


@dataclass
class WorkflowResult:
    """工作流結果"""
    success: bool
    content: str
    metadata: Dict[str, Any]
    agent_results: Dict[str, Any]
    execution_time: float
    error: Optional[Exception] = None


class LangGraphWorkflowManager:
    """LangGraph 工作流管理器"""
    
    # 循環檢測和安全控制
    MAX_WORKFLOW_ITERATIONS = 5  # 最大工作流迭代次數
    MAX_AGENT_CALLS_PER_SESSION = 20  # 每個 session 最大 Agent 調用次數
    
    def __init__(self):
        self.agents = {
            "control_agent": ControlAgent(),
            "chat_agent": ChatAgent(),
            "rag_agent": RAGAgent(),
            "card_agent": CardAgent(),
            "calendar_agent": CalendarAgent(),
            "vision_agent": VisionAgent()  # 新增 VisionAgent
        }
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.workflow_graph = None
        self.parallel_executors = {}
        
        if HAS_LANGGRAPH:
            self._setup_langgraph()
        else:
            logger.warning("LangGraph 不可用，使用自定義工作流")
    
    def _setup_langgraph(self):
        """設置 LangGraph 工作流"""
        try:
            # 創建狀態圖
            self.workflow_graph = StateGraph(dict)
            
            # 添加節點
            self.workflow_graph.add_node("route_decision", self._route_decision_node)
            self.workflow_graph.add_node("single_agent", self._single_agent_node)
            self.workflow_graph.add_node("parallel_agents", self._parallel_agents_node)
            self.workflow_graph.add_node("aggregate_results", self._aggregate_results_node)
            self.workflow_graph.add_node("safety_check", self._safety_check_node)
            
            # 設置條件邊 - 防止無限循環
            self.workflow_graph.add_conditional_edges(
                "route_decision",
                self._routing_condition,
                {
                    "single": "single_agent",
                    "parallel": "parallel_agents",
                    "error": "safety_check"
                }
            )
            
            # 設置直接邊
            self.workflow_graph.add_edge("single_agent", "safety_check")
            self.workflow_graph.add_edge("parallel_agents", "safety_check")
            
            # 安全檢查後的條件邊
            self.workflow_graph.add_conditional_edges(
                "safety_check",
                self._safety_condition,
                {
                    "complete": "aggregate_results",
                    "retry": "route_decision",
                    "fail": END
                }
            )
            
            self.workflow_graph.add_edge("aggregate_results", END)
            
            # 設置入口點
            self.workflow_graph.set_entry_point("route_decision")
            
            # 編譯圖
            self.workflow_graph = self.workflow_graph.compile()
            
            logger.info("LangGraph 工作流設置完成")
            
        except Exception as e:
            logger.error("LangGraph 設置失敗", error=e)
            self.workflow_graph = None
    
    async def execute_workflow(self, input_data: Dict[str, Any]) -> WorkflowResult:
        """執行工作流 - 帶有循環檢測和安全控制"""
        start_time = time.time()
        session_id = input_data.get("session_id", "unknown")
        
        try:
            # 初始化 session 狀態
            session_state = self._init_session_state(session_id)
            
            # 預先安全檢查
            initial_safety = self._check_loop_safety(session_id, [])
            if not initial_safety["safe"]:
                logger.warning(
                    f"Session {session_id} 初始安全檢查失敗: {initial_safety['reason']}",
                    session_id=session_id
                )
                return await self._handle_workflow_failure(
                    Exception(f"Session safety violation: {initial_safety['reason']}"),
                    input_data
                )
            
            logger.log_agent_action(
                agent_name="workflow_manager",
                action="start_workflow_with_safety",
                session_id=session_id,
                input_keys=list(input_data.keys()),
                iteration=session_state["iteration_count"]
            )
            
            # 執行工作流
            if HAS_LANGGRAPH and self.workflow_graph:
                result = await self._execute_langgraph_workflow_safe(input_data)
            else:
                result = await self._execute_custom_workflow_safe(input_data)
            
            # 設置執行時間
            result.execution_time = time.time() - start_time
            
            # 監控效能
            await self._monitor_workflow_performance(start_time, input_data, result)
            
            logger.log_performance(
                operation="workflow_execution_safe",
                duration=result.execution_time,
                session_id=session_id,
                success=result.success,
                agents_used=list(result.agent_results.keys()),
                iteration=session_state["iteration_count"]
            )
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error("安全工作流執行失敗", error=e, session_id=session_id)
            
            # 嘗試降級處理
            fallback_result = await self._handle_workflow_failure(e, input_data)
            fallback_result.execution_time = execution_time
            
            return fallback_result
    
    async def _execute_langgraph_workflow(self, input_data: Dict[str, Any]) -> WorkflowResult:
        """執行 LangGraph 工作流"""
        try:
            # 準備初始狀態
            initial_state = {
                "input_data": input_data,
                "routing_result": None,
                "agent_results": {},
                "final_result": None,
                "execution_mode": "single"  # single 或 parallel
            }
            
            # 執行工作流
            final_state = await self.workflow_graph.ainvoke(initial_state)
            
            return WorkflowResult(
                success=True,
                content=final_state.get("final_result", {}).get("content", ""),
                metadata=final_state.get("final_result", {}).get("metadata", {}),
                agent_results=final_state.get("agent_results", {}),
                execution_time=0  # 會在外層計算
            )
            
        except Exception as e:
            logger.error("LangGraph 工作流執行錯誤", error=e)
            raise
    
    async def _execute_custom_workflow(self, input_data: Dict[str, Any]) -> WorkflowResult:
        """執行自定義工作流"""
        try:
            # 1. 路由決策
            routing_result = await self._route_decision(input_data)
            
            # 2. 根據路由結果執行
            if routing_result.get("execution_mode") == "parallel":
                agent_results = await self._execute_parallel_agents(
                    input_data, 
                    routing_result.get("agents", [])
                )
            else:
                agent_results = await self._execute_single_agent(
                    input_data,
                    routing_result.get("primary_agent", "chat_agent")
                )
            
            # 3. 聚合結果
            final_result = await self._aggregate_results(input_data, agent_results)
            
            return WorkflowResult(
                success=True,
                content=final_result.get("content", ""),
                metadata=final_result.get("metadata", {}),
                agent_results=agent_results,
                execution_time=0
            )
            
        except Exception as e:
            logger.error("自定義工作流執行錯誤", error=e)
            raise
    
    async def _route_decision(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """路由決策 - 使用高級路由系統"""
        try:
            # 使用高級路由決策
            return await self._advanced_route_decision(input_data)
        except Exception as e:
            logger.warning("高級路由決策失敗，使用基本路由", error=e)
            return await self._basic_route_decision(input_data)
    
    async def _basic_route_decision(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """基本路由決策 - 備用方案"""
        user_input = input_data.get("user_input", "")
        has_image = input_data.get("has_image", False)
        session_id = input_data.get("session_id", "")
        
        logger.info(f"路由決策: user_input='{user_input}', has_image={has_image}")
        
        # 特殊情況：純圖片上傳（名片識別）
        if has_image and not user_input.strip():
            logger.info("純圖片上傳，使用 card_agent")
            return {
                "execution_mode": "single",
                "primary_agent": "card_agent",
                "agents": ["card_agent"],
                "reason": "名片圖片識別"
            }
        
        # 使用 ControlAgent 進行基本路由決策
        control_result = await self.agents["control_agent"].process(input_data)
        primary_agent = control_result["metadata"]["route_to"]
        
        # 判斷是否需要並行處理
        needs_parallel = self._should_use_parallel_processing(user_input, has_image)
        
        if needs_parallel:
            parallel_agents = self._determine_parallel_agents(user_input, has_image, primary_agent)
            return {
                "execution_mode": "parallel",
                "primary_agent": primary_agent,
                "agents": parallel_agents,
                "reason": "需要多個 Agent 協作處理"
            }
        else:
            return {
                "execution_mode": "single",
                "primary_agent": primary_agent,
                "agents": [primary_agent],
                "reason": control_result["metadata"]["reason"]
            }
    
    async def _advanced_route_decision(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """高級路由決策系統"""
        user_input = input_data.get("user_input", "")
        has_image = input_data.get("has_image", False)
        session_id = input_data.get("session_id", "")
        user_profile = input_data.get("user_profile", {})
        
        # 分析用戶輸入的意圖
        intent_analysis = self._analyze_user_intent(user_input)
        
        # 分析對話歷史
        conversation_context = self._analyze_conversation_context(session_id)
        
        # 決定執行模式
        execution_mode = self._determine_execution_mode(
            intent_analysis, has_image, conversation_context
        )
        
        # 選擇 Agent 組合
        agent_combination = self._select_agent_combination(
            intent_analysis, execution_mode, has_image, user_profile, user_input
        )
        
        # 生成路由結果
        routing_result = {
            "execution_mode": execution_mode,
            "primary_agent": agent_combination["primary"],
            "agents": agent_combination["agents"],
            "intent_analysis": intent_analysis,
            "conversation_context": conversation_context,
            "confidence": agent_combination["confidence"],
            "reason": agent_combination["reason"]
        }
        
        logger.log_agent_action(
            agent_name="workflow_manager",
            action="advanced_routing_decision",
            session_id=session_id,
            routing_result=routing_result
        )
        
        return routing_result
    
    def _analyze_user_intent(self, user_input: str) -> Dict[str, Any]:
        """分析用戶意圖"""
        intents = {
            "greeting": ["你好", "哈囉", "hi", "hello", "早安", "午安", "晚安"],
            "product_inquiry": ["產品", "服務", "功能", "特色", "規格", "價格", "費用"],
            "appointment": ["會議", "約", "預約", "安排", "時間", "日程"],
            "card_processing": ["名片", "聯絡", "資訊", "公司", "職位"],
            "knowledge_query": ["什麼", "如何", "為什麼", "怎麼", "介紹", "說明"],
            "comparison": ["比較", "對比", "差別", "區別", "優缺點"],
            "complaint": ["問題", "錯誤", "故障", "不滿", "抱怨"],
            "goodbye": ["再見", "拜拜", "bye", "goodbye", "結束"]
        }
        
        intent_scores = {}
        for intent, keywords in intents.items():
            score = sum(1 for keyword in keywords if keyword in user_input)
            if score > 0:
                intent_scores[intent] = score / len(keywords)
        
        # 找出最高分數的意圖
        primary_intent = max(intent_scores, key=intent_scores.get) if intent_scores else "general"
        
        return {
            "primary_intent": primary_intent,
            "intent_scores": intent_scores,
            "complexity": self._calculate_complexity(user_input),
            "emotional_tone": self._detect_emotional_tone(user_input)
        }
    
    def _calculate_complexity(self, user_input: str) -> str:
        """計算查詢複雜度"""
        complexity_indicators = {
            "simple": len(user_input) < 20,
            "medium": 20 <= len(user_input) < 100,
            "complex": len(user_input) >= 100 or user_input.count("？") > 1 or user_input.count("?") > 1
        }
        
        for level, condition in complexity_indicators.items():
            if condition:
                return level
        
        return "medium"
    
    def _detect_emotional_tone(self, user_input: str) -> str:
        """檢測情感語調"""
        positive_words = ["好", "棒", "讚", "滿意", "喜歡", "感謝", "謝謝"]
        negative_words = ["不好", "差", "爛", "不滿", "討厭", "問題", "錯誤"]
        neutral_words = ["一般", "還可以", "普通", "不錯"]
        
        positive_score = sum(1 for word in positive_words if word in user_input)
        negative_score = sum(1 for word in negative_words if word in user_input)
        neutral_score = sum(1 for word in neutral_words if word in user_input)
        
        if positive_score > negative_score and positive_score > neutral_score:
            return "positive"
        elif negative_score > positive_score and negative_score > neutral_score:
            return "negative"
        else:
            return "neutral"
    
    def _analyze_conversation_context(self, session_id: str) -> Dict[str, Any]:
        """分析對話上下文"""
        # 從記憶體獲取對話歷史
        conversation_history = memory_manager.get_conversation_history(session_id)
        
        if not conversation_history:
            return {
                "is_new_conversation": True,
                "previous_topics": [],
                "conversation_stage": "initial"
            }
        
        # 分析對話階段
        conversation_stage = self._determine_conversation_stage(conversation_history)
        
        # 提取之前的主題
        previous_topics = self._extract_previous_topics(conversation_history)
        
        return {
            "is_new_conversation": False,
            "previous_topics": previous_topics,
            "conversation_stage": conversation_stage,
            "message_count": len(conversation_history)
        }
    
    def _determine_conversation_stage(self, history: List[Dict]) -> str:
        """確定對話階段"""
        if len(history) <= 2:
            return "initial"
        elif len(history) <= 5:
            return "exploration"
        elif len(history) <= 10:
            return "engagement"
        else:
            return "advanced"
    
    def _extract_previous_topics(self, history: List[Dict]) -> List[str]:
        """提取之前的對話主題"""
        topics = []
        topic_keywords = {
            "product": ["產品", "服務", "功能"],
            "appointment": ["會議", "約", "時間"],
            "card": ["名片", "聯絡"],
            "technical": ["技術", "規格", "實現"]
        }
        
        for message in history[-5:]:  # 只看最近5條消息
            content = message.get("content", "")
            for topic, keywords in topic_keywords.items():
                if any(keyword in content for keyword in keywords):
                    if topic not in topics:
                        topics.append(topic)
        
        return topics
    
    def _determine_execution_mode(self, intent_analysis: Dict, has_image: bool, 
                                 conversation_context: Dict) -> str:
        """確定執行模式"""
        # 複雜度高或有圖片 -> 並行處理
        if intent_analysis["complexity"] == "complex" or has_image:
            return "parallel"
        
        # 比較類查詢 -> 並行處理
        if intent_analysis["primary_intent"] == "comparison":
            return "parallel"
        
        # 新對話且是簡單查詢 -> 單一處理
        if conversation_context["is_new_conversation"] and intent_analysis["complexity"] == "simple":
            return "single"
        
        # 進階對話階段 -> 考慮並行
        if conversation_context["conversation_stage"] == "advanced":
            return "parallel"
        
        # 預設單一處理
        return "single"
    
    def _select_agent_combination(self, intent_analysis: Dict, execution_mode: str, 
                                 has_image: bool, user_profile: Dict, user_input: str = "") -> Dict[str, Any]:
        """選擇 Agent 組合"""
        primary_intent = intent_analysis["primary_intent"]
        
        # 基於意圖的 Agent 選擇
        intent_to_agent = {
            "greeting": "chat_agent",
            "product_inquiry": "rag_agent",
            "appointment": "calendar_agent",
            "card_processing": "card_agent",
            "knowledge_query": "rag_agent",
            "comparison": "rag_agent",
            "complaint": "chat_agent",
            "goodbye": "chat_agent"
        }
        
        primary_agent = intent_to_agent.get(primary_intent, "chat_agent")
        
        if execution_mode == "single":
            return {
                "primary": primary_agent,
                "agents": [primary_agent],
                "confidence": 0.9,
                "reason": f"單一 Agent 處理 {primary_intent}"
            }
        
        # 並行模式的 Agent 選擇
        agents = [primary_agent]
        
        # 智能判斷圖片類型並添加相應 Agent
        if has_image:
            # 判斷是否為名片掃描還是攝影機影像
            card_keywords = ["名片", "卡片", "聯絡", "資訊", "掃描", "識別", "上傳"]
            has_card_keywords = any(keyword in user_input for keyword in card_keywords)
            
            # 對話關鍵字表示這是攝影機影像
            chat_keywords = ["你好", "哈囉", "hi", "hello", "謝謝", "再見", "問候", "聊天"]
            has_chat_keywords = any(keyword in user_input.lower() for keyword in chat_keywords)
            
            # 如果有名片關鍵字，或者純圖片上傳（很少文字），添加 card_agent
            if has_card_keywords or (len(user_input.strip()) < 10 and not has_chat_keywords):
                if "card_agent" not in agents:
                    agents.append("card_agent")
                    logger.info(f"添加 card_agent 因為有名片關鍵字或純圖片上傳")
            
            # 如果有明確的對話意圖，添加 vision_agent 用於情緒分析
            if has_chat_keywords or len(user_input.strip()) >= 10:
                if "vision_agent" not in agents:
                    agents.append("vision_agent")
                    logger.info(f"添加 vision_agent 因為有對話意圖")
        
        # 對於視覺相關的問題，添加 VisionAgent
        vision_keywords = ["看", "視覺", "攝影機", "鏡頭", "表情", "情緒", "外觀", "穿", "顏色", "男生", "女生"]
        if any(keyword in user_input for keyword in vision_keywords):
            if "vision_agent" not in agents:
                agents.append("vision_agent")
                logger.info(f"添加 vision_agent 因為包含關鍵字: {[k for k in vision_keywords if k in user_input]}")
        
        if primary_intent == "comparison" and "rag_agent" not in agents:
            agents.append("rag_agent")
        
        if primary_intent == "product_inquiry" and "chat_agent" not in agents:
            agents.append("chat_agent")
        
        # 基於用戶檔案的個性化選擇
        if user_profile.get("preferences", {}).get("detailed_info", False):
            if "rag_agent" not in agents:
                agents.append("rag_agent")
        
        return {
            "primary": primary_agent,
            "agents": agents,
            "confidence": 0.8,
            "reason": f"並行處理 {primary_intent}，使用 {len(agents)} 個 Agent"
        }
    
    async def _execute_single_agent(self, input_data: Dict[str, Any], agent_name: str) -> Dict[str, Any]:
        """執行單個 Agent"""
        if agent_name not in self.agents:
            raise ValueError(f"未知的 Agent: {agent_name}")
        
        agent = self.agents[agent_name]
        result = await agent.process(input_data)
        
        return {agent_name: result}
    
    async def _execute_parallel_agents(self, input_data: Dict[str, Any], agents: List[str]) -> Dict[str, Any]:
        """並行執行多個 Agent"""
        session_id = input_data.get("session_id", "unknown")
        
        # 創建並行任務
        tasks = []
        agent_contexts = {}
        
        for agent_name in agents:
            if agent_name in self.agents:
                # 為每個 Agent 準備特定的上下文
                agent_context = self._prepare_agent_context(agent_name, input_data)
                agent_contexts[agent_name] = agent_context
                
                # 創建帶有上下文的任務
                task = asyncio.create_task(
                    self._execute_agent_with_timeout(agent_name, agent_context),
                    name=f"agent_{agent_name}_{session_id}"
                )
                tasks.append((agent_name, task))
        
        logger.log_agent_action(
            agent_name="workflow_manager",
            action="start_parallel_execution",
            session_id=session_id,
            agents=agents,
            task_count=len(tasks)
        )
        
        # 並行執行所有任務
        results = {}
        completed_tasks = 0
        
        # 使用 asyncio.gather 進行並行執行，但要處理個別錯誤
        async def execute_single_task(agent_name: str, task: asyncio.Task):
            try:
                start_time = time.time()
                result = await task
                execution_time = time.time() - start_time
                
                logger.log_performance(
                    operation=f"agent_{agent_name}_execution",
                    duration=execution_time,
                    session_id=session_id,
                    success=True
                )
                
                return agent_name, result
                
            except asyncio.TimeoutError:
                logger.warning(f"Agent {agent_name} 執行超時", session_id=session_id)
                return agent_name, {
                    "error": True,
                    "content": f"Agent {agent_name} 執行超時，請稍後重試",
                    "metadata": {"timeout": True, "agent": agent_name}
                }
            except Exception as e:
                logger.error(f"Agent {agent_name} 執行錯誤", error=e, session_id=session_id)
                return agent_name, error_handler.handle_agent_error(e, agent_name, session_id)
        
        # 並行執行所有任務
        task_results = await asyncio.gather(
            *[execute_single_task(agent_name, task) for agent_name, task in tasks],
            return_exceptions=True
        )
        
        # 處理結果
        for result in task_results:
            if isinstance(result, Exception):
                logger.error("並行任務執行異常", error=result, session_id=session_id)
                continue
                
            agent_name, agent_result = result
            results[agent_name] = agent_result
            completed_tasks += 1
        
        logger.log_agent_action(
            agent_name="workflow_manager",
            action="complete_parallel_execution",
            session_id=session_id,
            completed_tasks=completed_tasks,
            total_tasks=len(tasks),
            success_rate=completed_tasks / len(tasks) if tasks else 0
        )
        
        return results
    
    async def _execute_agent_with_timeout(self, agent_name: str, input_data: Dict[str, Any], timeout: int = 30):
        """帶超時的 Agent 執行"""
        agent = self.agents[agent_name]
        
        try:
            result = await asyncio.wait_for(
                agent.process(input_data),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            logger.warning(f"Agent {agent_name} 執行超時")
            raise
    
    async def _aggregate_results(self, input_data: Dict[str, Any], agent_results: Dict[str, Any]) -> Dict[str, Any]:
        """聚合多個 Agent 的結果"""
        if len(agent_results) == 1:
            # 單個 Agent 結果直接返回
            return list(agent_results.values())[0]
        
        # 多個 Agent 結果需要智能聚合
        session_id = input_data.get("session_id", "")
        user_input = input_data.get("user_input", "")
        
        # 過濾錯誤結果
        valid_results = {
            name: result for name, result in agent_results.items() 
            if not result.get("error", False)
        }
        
        if not valid_results:
            logger.warning("所有 Agent 都返回錯誤結果", session_id=session_id)
            return {
                "content": "抱歉，處理您的請求時遇到了問題，請稍後重試。",
                "metadata": {"error": "all_agents_failed", "agent_count": len(agent_results)}
            }
        
        # 智能聚合策略
        aggregation_strategy = self._determine_aggregation_strategy(user_input, valid_results)
        
        if aggregation_strategy == "primary_with_context":
            return await self._aggregate_primary_with_context(valid_results, user_input)
        elif aggregation_strategy == "sequential_combination":
            return await self._aggregate_sequential_combination(valid_results, user_input)
        elif aggregation_strategy == "parallel_synthesis":
            return await self._aggregate_parallel_synthesis(valid_results, user_input)
        else:
            return await self._aggregate_simple_combination(valid_results, user_input)
    
    def _determine_aggregation_strategy(self, user_input: str, results: Dict[str, Any]) -> str:
        """決定聚合策略"""
        result_types = set(results.keys())
        
        # 如果有 CardAgent 結果，使用主要+上下文聚合
        if "card_agent" in result_types:
            return "primary_with_context"
        
        # 如果有名片和行事曆結果，使用順序組合
        if "calendar_agent" in result_types:
            return "sequential_combination"
        
        # 如果有知識查詢和對話結果，使用並行合成
        if "rag_agent" in result_types and "chat_agent" in result_types:
            return "parallel_synthesis"
        
        # 如果有明確的主要代理，使用主要+上下文
        if any(keyword in user_input for keyword in ["主要", "重點", "核心"]):
            return "primary_with_context"
        
        # 預設使用簡單組合
        return "simple_combination"
    
    async def _aggregate_primary_with_context(self, results: Dict[str, Any], user_input: str) -> Dict[str, Any]:
        """主要結果+上下文聚合"""
        # 確定主要 Agent - CardAgent 具有最高優先級
        agent_priority = {
            "card_agent": 1,
            "calendar_agent": 2,
            "rag_agent": 3,
            "chat_agent": 4
        }
        
        primary_agent = min(results.keys(), key=lambda x: agent_priority.get(x, 10))
        primary_result = results[primary_agent]
        
        # 特殊處理：如果主要 Agent 是 card_agent，只使用其結果
        if primary_agent == "card_agent":
            return {
                "content": primary_result.get("content", ""),
                "metadata": {
                    "primary_agent": primary_agent,
                    "context_agents": [],
                    "aggregation_strategy": "card_agent_only",
                    "updated_user_profile": primary_result.get("metadata", {}).get("updated_user_profile", {})
                }
            }
        
        # 構建上下文資訊
        context_info = []
        for agent_name, result in results.items():
            if agent_name != primary_agent:
                content = result.get("content", "")
                if content and len(content) > 10:
                    context_info.append(f"【{agent_name}】{content[:100]}...")
        
        # 組合最終內容
        final_content = primary_result.get("content", "")
        if context_info:
            final_content += f"\n\n補充資訊：\n" + "\n".join(context_info)
        
        return {
            "content": final_content,
            "metadata": {
                "primary_agent": primary_agent,
                "context_agents": [name for name in results.keys() if name != primary_agent],
                "aggregation_strategy": "primary_with_context"
            }
        }
    
    async def _aggregate_sequential_combination(self, results: Dict[str, Any], user_input: str) -> Dict[str, Any]:
        """順序組合聚合"""
        # 按邏輯順序組合結果
        sequence_order = ["card_agent", "rag_agent", "calendar_agent", "chat_agent"]
        
        combined_content = []
        used_agents = []
        
        for agent_name in sequence_order:
            if agent_name in results:
                content = results[agent_name].get("content", "")
                if content:
                    combined_content.append(content)
                    used_agents.append(agent_name)
        
        # 使用智能連接詞
        if len(combined_content) > 1:
            connectors = ["首先，", "接著，", "另外，", "最後，"]
            final_parts = []
            for i, content in enumerate(combined_content):
                if i < len(connectors):
                    final_parts.append(f"{connectors[i]}{content}")
                else:
                    final_parts.append(content)
            final_content = "\n\n".join(final_parts)
        else:
            final_content = combined_content[0] if combined_content else ""
        
        return {
            "content": final_content,
            "metadata": {
                "used_agents": used_agents,
                "aggregation_strategy": "sequential_combination"
            }
        }
    
    async def _aggregate_parallel_synthesis(self, results: Dict[str, Any], user_input: str) -> Dict[str, Any]:
        """並行合成聚合"""
        # 使用 LLM 對多個結果進行智能合成
        synthesis_prompt = f"""
        用戶問題：{user_input}
        
        多個 AI 代理的回答：
        """
        
        agent_responses = []
        for agent_name, result in results.items():
            content = result.get("content", "")
            if content:
                agent_responses.append(f"【{agent_name}】{content}")
        
        synthesis_prompt += "\n".join(agent_responses)
        synthesis_prompt += "\n\n請將以上回答整合成一個連貫、完整的回應："
        
        # 這裡可以調用 LLM 進行合成，暫時使用簡單合成
        synthesized_content = self._simple_synthesize(agent_responses, user_input)
        
        return {
            "content": synthesized_content,
            "metadata": {
                "synthesis_agents": list(results.keys()),
                "aggregation_strategy": "parallel_synthesis"
            }
        }
    
    async def _aggregate_simple_combination(self, results: Dict[str, Any], user_input: str) -> Dict[str, Any]:
        """簡單組合聚合"""
        # 按優先級排序
        agent_priority = {
            "control_agent": 1,
            "card_agent": 2,
            "calendar_agent": 3,
            "rag_agent": 4,
            "chat_agent": 5
        }
        
        sorted_results = sorted(
            results.items(),
            key=lambda x: agent_priority.get(x[0], 10)
        )
        
        primary_content = ""
        secondary_contents = []
        
        for agent_name, result in sorted_results:
            content = result.get("content", "")
            if content:
                if not primary_content and agent_name != "control_agent":
                    primary_content = content
                elif agent_name != "control_agent":
                    secondary_contents.append(f"【{agent_name}】{content}")
        
        # 組合最終內容
        final_content = primary_content
        if secondary_contents:
            final_content += "\n\n" + "\n".join(secondary_contents)
        
        return {
            "content": final_content or "處理完成",
            "metadata": {
                "agents_used": list(results.keys()),
                "aggregation_strategy": "simple_combination"
            }
        }
    
    def _simple_synthesize(self, agent_responses: List[str], user_input: str) -> str:
        """簡單的回應合成"""
        if not agent_responses:
            return "抱歉，沒有找到相關資訊。"
        
        if len(agent_responses) == 1:
            return agent_responses[0]
        
        # 提取關鍵資訊
        combined_info = []
        for response in agent_responses:
            if "【" in response and "】" in response:
                agent_name = response.split("【")[1].split("】")[0]
                content = response.split("】")[1].strip()
                if content:
                    combined_info.append(f"關於 {agent_name}：{content}")
        
        if combined_info:
            return "根據您的問題，我為您整理了以下資訊：\n\n" + "\n\n".join(combined_info)
        else:
            return "\n\n".join(agent_responses)
    
    def _prepare_agent_context(self, agent_name: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """為特定 Agent 準備上下文"""
        base_context = input_data.copy()
        
        # 確保用戶資料被傳遞到所有 Agent
        session_id = input_data.get("session_id")
        if session_id and not base_context.get("user_profile"):
            from app.core.memory import memory_manager
            user_profile = memory_manager.load_user_profile(session_id)
            if user_profile:
                base_context["user_profile"] = user_profile
                logger.info(f"為 {agent_name} 載入用戶資料: {user_profile.get('name', 'Unknown')}")
        
        # 根據 Agent 類型添加特定上下文
        if agent_name == "card_agent":
            base_context.update({
                "focus": "名片資訊提取",
                "expected_output": "結構化的聯絡資訊",
                "processing_mode": "ocr_analysis"
            })
        elif agent_name == "calendar_agent":
            base_context.update({
                "focus": "時間和行事曆管理",
                "expected_output": "可用時間或會議安排",
                "processing_mode": "time_analysis"
            })
        elif agent_name == "rag_agent":
            base_context.update({
                "focus": "知識查詢和產品資訊",
                "expected_output": "詳細的產品或技術資訊",
                "processing_mode": "knowledge_search"
            })
        elif agent_name == "chat_agent":
            base_context.update({
                "focus": "一般對話和客戶服務",
                "expected_output": "友好的對話回應",
                "processing_mode": "conversational"
            })
        elif agent_name == "vision_agent":
            base_context.update({
                "focus": "即時影像情緒分析",
                "expected_output": "情緒識別結果",
                "processing_mode": "emotion_analysis"
            })
        
        return base_context
    
    async def _execute_agent_with_dependency_check(self, agent_name: str, input_data: Dict[str, Any], 
                                                  dependencies: List[str] = None) -> Dict[str, Any]:
        """執行帶有依賴檢查的 Agent"""
        dependencies = dependencies or []
        
        # 檢查依賴是否滿足
        for dep in dependencies:
            if dep not in input_data.get("completed_agents", []):
                raise ValueError(f"Agent {agent_name} 依賴 {dep} 尚未完成")
        
        # 執行 Agent
        return await self._execute_agent_with_timeout(agent_name, input_data)
    
    async def _execute_sequential_workflow(self, input_data: Dict[str, Any], 
                                          workflow_steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """執行順序工作流"""
        results = {}
        completed_agents = []
        
        for step in workflow_steps:
            agent_name = step["agent"]
            dependencies = step.get("dependencies", [])
            
            # 檢查依賴
            missing_deps = [dep for dep in dependencies if dep not in completed_agents]
            if missing_deps:
                logger.warning(f"Agent {agent_name} 缺少依賴: {missing_deps}")
                continue
            
            # 執行 Agent
            try:
                step_input = input_data.copy()
                step_input["completed_agents"] = completed_agents
                step_input["previous_results"] = results
                
                result = await self._execute_agent_with_timeout(agent_name, step_input)
                results[agent_name] = result
                completed_agents.append(agent_name)
                
                logger.log_agent_action(
                    agent_name=agent_name,
                    action="sequential_step_completed",
                    session_id=input_data.get("session_id", ""),
                    step_number=len(completed_agents)
                )
                
            except Exception as e:
                logger.error(f"順序執行 Agent {agent_name} 失敗", error=e)
                results[agent_name] = error_handler.handle_agent_error(
                    e, agent_name, input_data.get("session_id", "")
                )
        
        return results
    
    async def _monitor_workflow_performance(self, start_time: float, input_data: Dict[str, Any], 
                                           result: WorkflowResult) -> None:
        """監控工作流效能"""
        total_time = time.time() - start_time
        session_id = input_data.get("session_id", "")
        
        # 記錄效能指標
        performance_metrics = {
            "total_execution_time": total_time,
            "success": result.success,
            "agent_count": len(result.agent_results),
            "content_length": len(result.content) if result.content else 0,
            "error_occurred": result.error is not None
        }
        
        # 判斷效能級別
        if total_time < 2.0:
            performance_level = "excellent"
        elif total_time < 5.0:
            performance_level = "good"
        elif total_time < 10.0:
            performance_level = "acceptable"
        else:
            performance_level = "poor"
        
        performance_metrics["performance_level"] = performance_level
        
        logger.log_performance(
            operation="workflow_total_execution",
            duration=total_time,
            session_id=session_id,
            **performance_metrics
        )
        
        # 如果效能不佳，記錄詳細資訊
        if performance_level in ["acceptable", "poor"]:
            logger.warning(
                f"工作流效能 {performance_level}",
                session_id=session_id,
                execution_time=total_time,
                agent_results=list(result.agent_results.keys())
            )
    
    def _optimize_agent_selection(self, agent_combination: Dict[str, Any], 
                                 performance_history: List[Dict]) -> Dict[str, Any]:
        """基於歷史效能優化 Agent 選擇"""
        if not performance_history:
            return agent_combination
        
        # 分析歷史效能
        avg_performance = {}
        for record in performance_history[-10:]:  # 只看最近10次
            agents = record.get("agents_used", [])
            execution_time = record.get("execution_time", 0)
            success = record.get("success", False)
            
            for agent in agents:
                if agent not in avg_performance:
                    avg_performance[agent] = {"times": [], "success_rate": 0}
                avg_performance[agent]["times"].append(execution_time)
                avg_performance[agent]["success_rate"] += 1 if success else 0
        
        # 計算平均效能
        for agent in avg_performance:
            times = avg_performance[agent]["times"]
            avg_performance[agent]["avg_time"] = sum(times) / len(times)
            avg_performance[agent]["success_rate"] = avg_performance[agent]["success_rate"] / len(times)
        
        # 基於效能調整 Agent 選擇
        optimized_agents = []
        for agent in agent_combination["agents"]:
            if agent in avg_performance:
                perf = avg_performance[agent]
                if perf["success_rate"] > 0.8 and perf["avg_time"] < 5.0:
                    optimized_agents.append(agent)
            else:
                optimized_agents.append(agent)  # 新 Agent 給予機會
        
        if optimized_agents:
            agent_combination["agents"] = optimized_agents
            agent_combination["optimized"] = True
        
        return agent_combination
    
    async def _handle_workflow_failure(self, error: Exception, input_data: Dict[str, Any]) -> WorkflowResult:
        """處理工作流失敗"""
        session_id = input_data.get("session_id", "")
        
        # 嘗試降級處理
        fallback_result = await self._execute_fallback_workflow(input_data)
        
        if fallback_result.success:
            logger.info(
                "工作流降級處理成功",
                session_id=session_id,
                original_error=str(error)
            )
            return fallback_result
        
        # 完全失敗，返回友好錯誤訊息
        logger.error(
            "工作流完全失敗",
            error=error,
            session_id=session_id
        )
        
        return WorkflowResult(
            success=False,
            content="抱歉，系統暫時遇到問題，請稍後再試。",
            metadata={"error": "workflow_failure", "fallback_attempted": True},
            agent_results={},
            execution_time=0,
            error=error
        )
    
    async def _execute_fallback_workflow(self, input_data: Dict[str, Any]) -> WorkflowResult:
        """執行降級工作流"""
        try:
            # 僅使用 ChatAgent 進行基本回應
            result = await self.agents["chat_agent"].process(input_data)
            
            return WorkflowResult(
                success=True,
                content=result.get("content", "我正在為您處理，請稍等。"),
                metadata={"fallback": True, "agent": "chat_agent"},
                agent_results={"chat_agent": result},
                execution_time=0
            )
        except Exception as e:
            return WorkflowResult(
                success=False,
                content="",
                metadata={"fallback_failed": True},
                agent_results={},
                execution_time=0,
                error=e
            )
    
    def get_workflow_statistics(self) -> Dict[str, Any]:
        """獲取工作流統計資訊"""
        # 這裡可以實現統計資訊的獲取
        return {
            "total_workflows": 0,
            "success_rate": 0.0,
            "avg_execution_time": 0.0,
            "most_used_agents": [],
            "performance_trends": []
        }
    
    def _init_session_state(self, session_id: str) -> Dict[str, Any]:
        """初始化 session 狀態"""
        if not hasattr(self, 'session_states'):
            self.session_states = {}
        
        if session_id not in self.session_states:
            self.session_states[session_id] = {
                "iteration_count": 0,
                "agent_call_count": 0,
                "call_history": [],
                "last_agents": [],
                "start_time": time.time(),
                "timeout_occurred": False
            }
        else:
            # 如果 session 已存在，檢查是否需要重置
            current_time = time.time()
            last_start_time = self.session_states[session_id]["start_time"]
            
            # 如果上次執行超過 5 分鐘，重置 session 狀態
            if current_time - last_start_time > 300:  # 5分鐘
                logger.info(f"Session {session_id} 已超時，重置狀態")
                self.session_states[session_id] = {
                    "iteration_count": 0,
                    "agent_call_count": 0,
                    "call_history": [],
                    "last_agents": [],
                    "start_time": current_time,
                    "timeout_occurred": False
                }
        
        return self.session_states[session_id]
    
    def _check_loop_safety(self, session_id: str, current_agents: List[str]) -> Dict[str, Any]:
        """檢查循環安全性"""
        state = self._init_session_state(session_id)
        
        # 檢查迭代次數
        if state["iteration_count"] >= self.MAX_WORKFLOW_ITERATIONS:
            return {
                "safe": False,
                "reason": "max_iterations_exceeded",
                "action": "terminate"
            }
        
        # 檢查總調用次數
        if state["agent_call_count"] >= self.MAX_AGENT_CALLS_PER_SESSION:
            return {
                "safe": False,
                "reason": "max_calls_exceeded", 
                "action": "terminate"
            }
        
        # 檢查執行時間 - 放寬超時限制
        current_execution_time = time.time() - state["start_time"]
        if current_execution_time > 120:  # 2分鐘超時，更寬容
            state["timeout_occurred"] = True
            logger.warning(f"Session {session_id} 執行時間超過限制: {current_execution_time:.2f}秒")
            return {
                "safe": False,
                "reason": "timeout",
                "action": "terminate"
            }
        
        # 檢查 Agent 循環調用
        if len(state["last_agents"]) >= 3:
            # 檢查最近3次是否是相同的 Agent 組合
            recent_agents = state["last_agents"][-3:]
            if all(set(agents) == set(current_agents) for agents in recent_agents):
                return {
                    "safe": False,
                    "reason": "agent_loop_detected",
                    "action": "fallback"
                }
        
        return {
            "safe": True,
            "reason": "normal",
            "action": "continue"
        }
    
    def _update_session_state(self, session_id: str, agents_used: List[str]):
        """更新 session 狀態"""
        state = self._init_session_state(session_id)
        
        state["iteration_count"] += 1
        state["agent_call_count"] += len(agents_used)
        state["call_history"].append({
            "timestamp": time.time(),
            "agents": agents_used.copy(),
            "iteration": state["iteration_count"]
        })
        state["last_agents"].append(agents_used.copy())
        
        # 保持最近5次記錄
        if len(state["last_agents"]) > 5:
            state["last_agents"] = state["last_agents"][-5:]
        
        # 清理超過1小時的 session
        if time.time() - state["start_time"] > 3600:
            del self.session_states[session_id]
    
    def _routing_condition(self, state: Dict[str, Any]) -> str:
        """路由條件判斷"""
        routing_result = state.get("routing_result", {})
        execution_mode = routing_result.get("execution_mode", "single")
        
        # 安全檢查
        session_id = state["input_data"].get("session_id", "")
        agents = routing_result.get("agents", [])
        safety_check = self._check_loop_safety(session_id, agents)
        
        if not safety_check["safe"]:
            state["safety_issue"] = safety_check
            return "error"
        
        return execution_mode
    
    def _safety_condition(self, state: Dict[str, Any]) -> str:
        """安全條件判斷"""
        safety_result = state.get("safety_result", {})
        
        if safety_result.get("action") == "terminate":
            return "fail"
        elif safety_result.get("action") == "retry" and safety_result.get("safe"):
            return "retry"
        else:
            return "complete"
    
    async def _route_decision_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """路由決策節點"""
        input_data = state["input_data"]
        session_id = input_data.get("session_id", "")
        
        try:
            # 進行路由決策
            routing_result = await self._route_decision(input_data)
            state["routing_result"] = routing_result
            
            # 確定執行模式
            state["execution_mode"] = routing_result.get("execution_mode", "single")
            
            logger.log_agent_action(
                agent_name="workflow_manager",
                action="route_decision_node",
                session_id=session_id,
                routing_result=routing_result
            )
            
            return state
            
        except Exception as e:
            logger.error("路由決策節點錯誤", error=e, session_id=session_id)
            state["routing_result"] = {
                "execution_mode": "single",
                "primary_agent": "chat_agent",
                "agents": ["chat_agent"],
                "error": True,
                "reason": f"路由決策失敗: {str(e)}"
            }
            state["execution_mode"] = "single"
            return state
    
    async def _single_agent_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """單一 Agent 節點"""
        input_data = state["input_data"]
        routing_result = state.get("routing_result", {})
        session_id = input_data.get("session_id", "")
        
        try:
            primary_agent = routing_result.get("primary_agent", "chat_agent")
            
            # 執行單一 Agent
            agent_results = await self._execute_single_agent_safe(input_data, primary_agent)
            state["agent_results"] = agent_results
            
            logger.log_agent_action(
                agent_name="workflow_manager",
                action="single_agent_node",
                session_id=session_id,
                primary_agent=primary_agent,
                success=True
            )
            
            return state
            
        except Exception as e:
            logger.error("單一 Agent 節點錯誤", error=e, session_id=session_id)
            state["agent_results"] = {
                "error": {
                    "error": True,
                    "content": "單一 Agent 處理失敗",
                    "metadata": {"node_error": True}
                }
            }
            return state
    
    async def _parallel_agents_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """並行 Agent 節點"""
        input_data = state["input_data"]
        routing_result = state.get("routing_result", {})
        session_id = input_data.get("session_id", "")
        
        try:
            agents = routing_result.get("agents", ["chat_agent"])
            
            # 執行並行 Agent
            agent_results = await self._execute_parallel_agents_safe(input_data, agents)
            state["agent_results"] = agent_results
            
            logger.log_agent_action(
                agent_name="workflow_manager",
                action="parallel_agents_node",
                session_id=session_id,
                agents=agents,
                results_count=len(agent_results)
            )
            
            return state
            
        except Exception as e:
            logger.error("並行 Agent 節點錯誤", error=e, session_id=session_id)
            state["agent_results"] = {
                "error": {
                    "error": True,
                    "content": "並行 Agent 處理失敗",
                    "metadata": {"node_error": True}
                }
            }
            return state
    
    async def _aggregate_results_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """結果聚合節點"""
        input_data = state["input_data"]
        agent_results = state.get("agent_results", {})
        session_id = input_data.get("session_id", "")
        
        try:
            # 聚合結果
            final_result = await self._aggregate_results(input_data, agent_results)
            state["final_result"] = final_result
            
            logger.log_agent_action(
                agent_name="workflow_manager",
                action="aggregate_results_node",
                session_id=session_id,
                agent_count=len(agent_results),
                final_content_length=len(final_result.get("content", ""))
            )
            
            return state
            
        except Exception as e:
            logger.error("結果聚合節點錯誤", error=e, session_id=session_id)
            state["final_result"] = {
                "content": "結果聚合失敗，請稍後重試",
                "metadata": {"aggregation_error": True}
            }
            return state
    
    async def _safety_check_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """安全檢查節點"""
        session_id = state["input_data"].get("session_id", "")
        agents_used = list(state.get("agent_results", {}).keys())
        
        # 更新 session 狀態
        self._update_session_state(session_id, agents_used)
        
        # 進行安全檢查
        safety_check = self._check_loop_safety(session_id, agents_used)
        
        # 記錄安全檢查結果
        logger.log_agent_action(
            agent_name="workflow_manager",
            action="safety_check",
            session_id=session_id,
            safety_result=safety_check,
            agents_used=agents_used
        )
        
        state["safety_result"] = safety_check
        
        # 如果檢測到循環，強制終止
        if not safety_check["safe"]:
            if safety_check["reason"] == "agent_loop_detected":
                logger.warning(
                    "檢測到 Agent 循環調用",
                    session_id=session_id,
                    agents_used=agents_used
                )
                # 使用降級處理
                fallback_result = await self._execute_fallback_workflow(state["input_data"])
                state["agent_results"] = {"fallback": fallback_result}
            else:
                logger.error(
                    f"工作流安全檢查失敗: {safety_check['reason']}",
                    session_id=session_id
                )
        
        return state
    
    async def _execute_langgraph_workflow_safe(self, input_data: Dict[str, Any]) -> WorkflowResult:
        """執行 LangGraph 工作流 - 安全版本"""
        try:
            # 準備初始狀態，加入安全控制
            initial_state = {
                "input_data": input_data,
                "routing_result": None,
                "agent_results": {},
                "final_result": None,
                "execution_mode": "single",
                "safety_result": None,
                "iteration_count": 0
            }
            
            # 使用超時控制執行工作流
            final_state = await asyncio.wait_for(
                self.workflow_graph.ainvoke(initial_state),
                timeout=60.0  # 60秒超時
            )
            
            return WorkflowResult(
                success=True,
                content=final_state.get("final_result", {}).get("content", ""),
                metadata=final_state.get("final_result", {}).get("metadata", {}),
                agent_results=final_state.get("agent_results", {}),
                execution_time=0  # 會在外層計算
            )
            
        except asyncio.TimeoutError:
            logger.error("LangGraph 工作流執行超時")
            raise Exception("工作流執行超時")
        except Exception as e:
            logger.error("LangGraph 安全工作流執行錯誤", error=e)
            raise
    
    async def _execute_custom_workflow_safe(self, input_data: Dict[str, Any]) -> WorkflowResult:
        """執行自定義工作流 - 安全版本"""
        session_id = input_data.get("session_id", "")
        max_retries = 3
        retry_count = 0
        
        # 確保載入用戶資料
        if session_id:
            from app.core.memory import memory_manager
            user_profile = memory_manager.load_user_profile(session_id)
            if user_profile:
                input_data["user_profile"] = user_profile
                logger.info(f"已載入用戶資料: {user_profile.get('name', 'Unknown')}")
            else:
                logger.info("未找到用戶資料")
        
        while retry_count < max_retries:
            try:
                # 安全檢查
                safety_check = self._check_loop_safety(session_id, [])
                if not safety_check["safe"]:
                    logger.warning(f"自定義工作流安全檢查失敗: {safety_check['reason']}")
                    break
                
                # 1. 路由決策
                routing_result = await self._route_decision(input_data)
                
                # 2. 再次安全檢查
                agents_to_use = routing_result.get("agents", [])
                safety_check = self._check_loop_safety(session_id, agents_to_use)
                if not safety_check["safe"]:
                    if safety_check["action"] == "fallback":
                        logger.info("檢測到循環，使用降級處理")
                        return await self._execute_fallback_workflow(input_data)
                    else:
                        raise Exception(f"安全檢查失敗: {safety_check['reason']}")
                
                # 3. 根據路由結果執行
                if routing_result.get("execution_mode") == "parallel":
                    agent_results = await self._execute_parallel_agents_safe(
                        input_data, 
                        routing_result.get("agents", [])
                    )
                else:
                    agent_results = await self._execute_single_agent_safe(
                        input_data,
                        routing_result.get("primary_agent", "chat_agent")
                    )
                
                # 4. 更新 session 狀態
                self._update_session_state(session_id, list(agent_results.keys()))
                
                # 5. 聚合結果
                final_result = await self._aggregate_results(input_data, agent_results)
                
                return WorkflowResult(
                    success=True,
                    content=final_result.get("content", ""),
                    metadata=final_result.get("metadata", {}),
                    agent_results=agent_results,
                    execution_time=0
                )
                
            except Exception as e:
                retry_count += 1
                logger.warning(f"自定義工作流執行失敗，重試 {retry_count}/{max_retries}", error=e)
                
                if retry_count >= max_retries:
                    logger.error("自定義安全工作流重試次數超限", error=e)
                    raise
                
                # 等待一下再重試
                await asyncio.sleep(0.5)
        
        # 如果循環退出但沒有成功，使用降級處理
        return await self._execute_fallback_workflow(input_data)
    
    async def _execute_single_agent_safe(self, input_data: Dict[str, Any], agent_name: str) -> Dict[str, Any]:
        """安全執行單個 Agent"""
        if agent_name not in self.agents:
            logger.warning(f"未知的 Agent: {agent_name}，使用 chat_agent")
            agent_name = "chat_agent"
        
        try:
            # 使用超時控制
            agent = self.agents[agent_name]
            result = await asyncio.wait_for(
                agent.process(input_data),
                timeout=30.0  # 30秒超時
            )
            
            return {agent_name: result}
            
        except asyncio.TimeoutError:
            logger.warning(f"Agent {agent_name} 執行超時")
            return {agent_name: {
                "error": True,
                "content": f"Agent {agent_name} 執行超時",
                "metadata": {"timeout": True}
            }}
        except Exception as e:
            logger.error(f"Agent {agent_name} 執行錯誤", error=e)
            return {agent_name: error_handler.handle_agent_error(
                e, agent_name, input_data.get("session_id", "")
            )}
    
    async def _execute_parallel_agents_safe(self, input_data: Dict[str, Any], agents: List[str]) -> Dict[str, Any]:
        """安全並行執行多個 Agent"""
        session_id = input_data.get("session_id", "unknown")
        
        # 限制並行 Agent 數量
        max_parallel = 4
        if len(agents) > max_parallel:
            logger.warning(f"並行 Agent 數量超限 ({len(agents)} > {max_parallel})，截取前 {max_parallel} 個")
            agents = agents[:max_parallel]
        
        # 創建帶超時的並行任務
        async def execute_single_task_with_timeout(agent_name: str):
            try:
                if agent_name not in self.agents:
                    return agent_name, {
                        "error": True,
                        "content": f"未知的 Agent: {agent_name}",
                        "metadata": {"unknown_agent": True}
                    }
                
                agent_context = self._prepare_agent_context(agent_name, input_data)
                result = await asyncio.wait_for(
                    self.agents[agent_name].process(agent_context),
                    timeout=30.0
                )
                
                return agent_name, result
                
            except asyncio.TimeoutError:
                logger.warning(f"並行 Agent {agent_name} 執行超時", session_id=session_id)
                return agent_name, {
                    "error": True,
                    "content": f"Agent {agent_name} 執行超時",
                    "metadata": {"timeout": True}
                }
            except Exception as e:
                logger.error(f"並行 Agent {agent_name} 執行錯誤", error=e, session_id=session_id)
                return agent_name, error_handler.handle_agent_error(e, agent_name, session_id)
        
        # 並行執行所有任務，總超時60秒
        try:
            task_results = await asyncio.wait_for(
                asyncio.gather(
                    *[execute_single_task_with_timeout(agent) for agent in agents],
                    return_exceptions=True
                ),
                timeout=60.0
            )
            
            # 處理結果
            results = {}
            for result in task_results:
                if isinstance(result, Exception):
                    logger.error("並行任務異常", error=result, session_id=session_id)
                    continue
                    
                agent_name, agent_result = result
                results[agent_name] = agent_result
            
            return results
            
        except asyncio.TimeoutError:
            logger.error("並行 Agent 執行總超時", session_id=session_id)
            return {
                "timeout_error": {
                    "error": True,
                    "content": "並行處理超時，請稍後重試",
                    "metadata": {"total_timeout": True}
                }
            }
    
    def _should_use_parallel_processing(self, user_input: str, has_image: bool) -> bool:
        """判斷是否需要並行處理"""
        # 如果只有圖片沒有文字，通常是名片上傳，使用單一 Agent
        if has_image and not user_input.strip():
            return False
        
        # 如果有圖片且有文字，可能需要並行處理
        if has_image and user_input.strip():
            return True
        
        # 複雜查詢關鍵字
        parallel_keywords = [
            "並且", "同時", "還有", "以及", "另外", "順便", "會議", "預約", "安排", "時間"
        ]
        
        # 檢查是否包含需要並行處理的關鍵字
        for keyword in parallel_keywords:
            if keyword in user_input:
                return True
        
        return False
    
    def _determine_parallel_agents(self, user_input: str, has_image: bool, primary_agent: str) -> List[str]:
        """決定需要並行處理的 Agent 組合"""
        agents = [primary_agent]
        
        # 如果有圖片，添加 card_agent
        if has_image:
            if "card_agent" not in agents:
                agents.append("card_agent")
        
        # 對於視覺相關的問題，添加 VisionAgent
        vision_keywords = ["看", "視覺", "攝影機", "鏡頭", "表情", "情緒", "外觀", "穿", "顏色", "男生", "女生"]
        if has_image or any(keyword in user_input for keyword in vision_keywords):
            if "vision_agent" not in agents:
                agents.append("vision_agent")
        
        # 根據關鍵字決定額外的 Agent
        if any(keyword in user_input for keyword in ["會議", "預約", "安排", "時間"]):
            if "calendar_agent" not in agents:
                agents.append("calendar_agent")
        
        if any(keyword in user_input for keyword in ["產品", "功能", "價格", "方案"]):
            if "rag_agent" not in agents:
                agents.append("rag_agent")
        return agents
    
    def _is_card_upload(self, user_input: str, input_data: Dict[str, Any]) -> bool:
        """判斷是否為名片上傳而非攝影機即時影像"""
        # 檢查是否有明確的名片相關關鍵字
        card_keywords = ["名片", "卡片", "聯絡", "資訊", "掃描", "識別", "上傳"]
        has_card_keywords = any(keyword in user_input for keyword in card_keywords)
        
        # 檢查圖片來源類型（如果有的話）
        image_source = input_data.get("image_source", "")
        is_upload = image_source in ["upload", "file", "drag_drop"]
        
        # 檢查是否為純圖片上傳（無文字或很少文字）
        is_minimal_text = len(user_input.strip()) < 10
        
        # 如果有名片關鍵字，或者是上傳且文字很少，認為是名片掃描
        if has_card_keywords or (is_upload and is_minimal_text):
            return True
            
        # 如果有明確的對話意圖，認為是攝影機影像
        chat_keywords = ["你好", "哈囉", "hi", "hello", "謝謝", "再見", "問候", "聊天"]
        has_chat_keywords = any(keyword in user_input.lower() for keyword in chat_keywords)
        
        if has_chat_keywords:
            return False
            
        # 預設：如果文字很少且沒有明確指示，認為是名片掃描
        return is_minimal_text



# 創建全域工作流管理器實例
workflow_manager = LangGraphWorkflowManager()

# 匯出主要物件
__all__ = ["workflow_manager", "LangGraphWorkflowManager", "WorkflowState", "AgentTask", "WorkflowResult"]
