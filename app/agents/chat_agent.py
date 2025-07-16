from typing import Dict, Any
from app.agents.base_agent import BaseAgent
from app.models import LLMFactory
from langchain_core.messages import HumanMessage, SystemMessage


class ChatAgent(BaseAgent):
    """對話 Agent - 處理一般銷售對話"""
    
    def __init__(self):
        super().__init__(
            name="ChatAgent",
            description="AI 銷售助理，專門處理一般對話、產品介紹和銷售互動"
        )
        self.llm = LLMFactory.get_chat_agent_llm()
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """處理一般對話"""
        user_input = input_data.get("user_input", "")
        session_id = input_data.get("session_id", "")
        user_profile = input_data.get("user_profile", {})
        
        # 始終從記憶體中讀取最新的用戶資料
        if session_id:
            memory_profile = self.memory.load_user_profile(session_id) or {}
            # 合併記憶體中的資料和輸入的資料
            user_profile.update(memory_profile)
        
        # 獲取對話歷史
        conversation_history = self.memory.get_conversation_history(session_id, limit=10)
        
        # 構建對話上下文
        context = self._build_conversation_context(user_profile, conversation_history)
        
        # 生成回應
        response = await self._generate_response(
            user_input, 
            context, 
            input_data.get("interaction_mode", "chat"),
            has_user_profile=bool(user_profile)
        )
        
        # 保存對話歷史
        self.memory.add_conversation_history(session_id, "user", user_input)
        self.memory.add_conversation_history(session_id, "assistant", response)
        
        return self.format_response(
            content=response,
            metadata={
                "conversation_length": len(conversation_history),
                "user_profile": user_profile,
                "has_user_data": bool(user_profile)
            }
        )
    
    def _build_conversation_context(self, user_profile: Dict[str, Any], history: list) -> str:
        """構建對話上下文"""
        context_parts = []
        
        # 添加用戶資料
        if user_profile:
            context_parts.append("=== 客戶資料 ===")
            name = user_profile.get("name", "")
            title = user_profile.get("title", "")
            company = user_profile.get("company", "")
            department = user_profile.get("department", "")
            phone = user_profile.get("phone", "")
            email = user_profile.get("email", "")
            
            if name:
                context_parts.append(f"客戶姓名：{name}")
            if title:
                context_parts.append(f"職稱：{title}")
            if company:
                context_parts.append(f"公司：{company}")
            if department:
                context_parts.append(f"部門：{department}")
            if phone:
                context_parts.append(f"電話：{phone}")
            if email:
                context_parts.append(f"Email：{email}")

            # 新增：讀取並加入情緒資料
            emotion = user_profile.get("emotion", "")
            if emotion:
                context_parts.append(f"\\n=== 即時情緒感知 ===")
                context_parts.append(f"系統偵測到客戶目前的情緒為: {emotion}")
            
            # 服務切入點提示
            if company:
                if any(keyword in company.lower() for keyword in ["gov", "gov.tw", "政府", "公所", "局", "處", "院"]):
                    context_parts.append("服務切入點：此為政府或公家單位，可著重於政策推廣、線上服務、地方創生等方案。")
                elif any(keyword in company.lower() for keyword in ["school", "edu", "大學", "中學", "小學", "教育"]):
                    context_parts.append("服務切入點：此為教育機構，可著重於校園商店、活動報名、成果展示等方案。")
                elif any(keyword in company.lower() for keyword in ["org", "協會", "基金會", "非營利"]):
                    context_parts.append("服務切入點：此為非營利組織，可著重於募款、理念宣傳、會員服務等方案。")
                else:
                    context_parts.append("服務切入點：此為一般企業或個人，可著重於產品銷售、品牌建立、市場擴展等方案。")

        # 添加對話歷史
        if history:
            context_parts.append("\\n=== 對話歷史 ===")
            for msg in history[-5:]:  # 最近 5 條訊息
                role = "用戶" if msg["role"] == "user" else "助理"
                context_parts.append(f"{role}: {msg['content']}")
        
        return "\\n".join(context_parts)
    
    async def _generate_response(self, user_input: str, context: str, mode: str = "chat", has_user_profile: bool = False) -> str:
        """生成對話回應"""
        try:
            # 修正：無論如何，只要用戶沒有輸入文字，就返回引導語，避免空請求
            if not user_input.strip():
                if has_user_profile:
                    # 如果有名片資訊，可以根據資訊打招呼
                    return "名片資訊已收到！請問有什麼可以為您服務的嗎？"
                else:
                    # 如果沒有任何資訊（例如，名片辨識失敗後），提供通用引導
                    return "您好！請問有什麼我可以協助您的地方嗎？或者，您可以上傳名片讓我更了解您。";

            # 根據模式獲取提示詞
            system_prompt = self.get_system_prompt(mode)

            # 虛擬人模式的特殊處理：簡化 prompt，強制簡短回應
            if mode == 'virtual_human':
                full_prompt = f"""
{system_prompt}

用戶說："{user_input}"

請嚴格遵守虛擬人互動指南，你的回應必須極度簡短、口語化，只能是一兩句話，並最好以問句結尾。
"""
            else:
                # 一般模式使用完整的上下文
                full_prompt = f"""
{system_prompt}

{context}

用戶問題：{user_input}

請根據上下文提供專業、友善的回應。
"""
            
            # 調用 LLM 生成回應
            from langchain_core.messages import HumanMessage
            
            message = HumanMessage(content=full_prompt)
            response = await self.llm.ainvoke([message])
            
            return response.content.strip()
            
        except Exception as e:
            print(f"生成回應失敗: {e}")
            return "抱歉，我暫時無法回答您的問題，請稍後再試。"
    
    def get_system_prompt(self, mode: str = "chat") -> str:
        """獲取系統提示詞"""
        
        # 虛擬人模式的提示詞
        if mode == 'virtual_human':
            return """
你是一位頂尖的「一站式開店服務平台」顧問，類似於 Shopify 專家。你的使命是協助各類型客戶，包括政府機構、非營利組織、中小企業及個人創業者，輕鬆打造專業且功能強大的線上商店。

# 互動風格：
- 你的回應必須極度簡短、口語化，只能是一兩句話。
- 最好以問句結尾，引導對方繼續對話。
- 絕對禁止任何形式的銷售或產品介紹。
"""

        # 一般對話模式的提示詞 (新增情緒應對指南)
        return """
你是一位頂尖的 Shopify開店平台銷售顧問。你的名字是「AI Sales」，專門協助機構、政府單位、中小企業與個人創業者建立強大的線上商店。

# 你的主要職責：
- **開店諮詢**: 提供從零到一的開店策略、平台功能介紹、金流與物流整合建議。
- **方案推薦**: 根據客戶需求與預算，推薦最適合的開店方案。
- **問題解答**: 回答所有與 Shopify 平台相關的問題，包含技術、行銷、營運等。
- **建立信任**: 以專業、友善、真誠的態度與客戶互動，成為他們值得信賴的夥伴。

# 新增：即時情緒應對指南
你的系統整合了視覺分析功能，能夠感知客戶的即時情緒。請務必善用此資訊，展現你的高情商，並調整互動策略：
- **如果偵測到客戶情緒為 `interested` (感興趣)**: 這表示你的說明正中要點。可以稍微深入介紹相關功能的優點或成功案例，並在結尾開放提問。
- **如果偵測到客戶情緒為 `confused` (困惑)**: 這是一個警訊！你的說明可能太複雜或太快。請立刻停下，並主動關心：「抱歉，是不是我剛才說得太快或不夠清楚？需不需要我換個方式說明？」
- **如果偵測到客戶情緒為 `tired` (疲倦)**: 客戶可能累了。請立刻簡化你的說明，聚焦在最重要的結論上，並主動提議：「我看您可能有些疲憊了，要不我們今天先聊到這？我可以稍後將重點整理成文字檔寄給您參考。」
- **如果偵測到客戶情緒為 `happy` (開心)**: 氣氛正好！保持你友善熱情的風格，可以適時地附和客戶的正面情緒。
- **如果偵測到 `neutral`, `sad`, `angry` 或 `surprised`**: 保持專業和冷靜，專注於解決客戶提出的問題。對於負面情緒，更要展現同理心和耐心。

# 互動風格：
- **專業且自信**: 展現你對開店領域的專業知識。
- **友善且耐心**: 讓客戶感覺像在與一位樂於助人的專家交談。
- **積極主動**: 適時提出問題，引導對話方向，挖掘客戶的深層需求。
- **目標導向**: 始終記得你的目標是協助客戶成功開店，而不僅僅是回答問題。

請根據以上設定，結合提供的「客戶資料」和「對話歷史」，生成你的下一段回應。
"""
