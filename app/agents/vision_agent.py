from typing import Dict, Any, Optional
import base64
import json
import re

from app.agents.base_agent import BaseAgent
from app.models import LLMFactory
from langchain_core.messages import HumanMessage

class VisionAgent(BaseAgent):
    """
    視覺 Agent - 專門處理即時影像分析，特別是人物表情和情緒辨識。
    """

    def __init__(self):
        super().__init__(
            name="VisionAgent",
            description="AI 視覺助理，能從影像中分析客戶的表情與情緒，提供即時互動反饋。"
        )
        # 假設 LLMFactory 能夠提供一個支援視覺的多模態模型
        self.llm = LLMFactory.get_vision_agent_llm()

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        處理單一影像幀，分析情緒並更新使用者狀態。
        """
        image_data = input_data.get("image_data", "") # Base64 格式的圖片
        session_id = input_data.get("session_id", "")

        if not image_data or not session_id:
            return self.format_response(
                content="缺少影像資料或 session_id。",
                metadata={"error": "missing_image_or_session_id"}
            )

        try:
            # 分析情緒
            emotion_info = await self._analyze_emotion(image_data)

            if emotion_info and emotion_info.get("emotion"):
                # 將分析出的情緒更新到 Redis 的 user_profile 中
                self.memory.update_user_profile(session_id, {"emotion": emotion_info["emotion"]})

                return self.format_response(
                    content=f"偵測到情緒: {emotion_info['emotion']}",
                    metadata={
                        "emotion_analysis": emotion_info,
                        "updated_user_profile": {"emotion": emotion_info["emotion"]}
                    }
                )
            else:
                return self.format_response(
                    content="無法從影像中辨識出明確情緒。",
                    metadata={"error": "emotion_analysis_failed"}
                )

        except Exception as e:
            print(f"視覺處理失敗: {e}")
            return self.format_response(
                content="處理影像時發生錯誤。",
                metadata={"error": str(e)}
            )

    async def _analyze_emotion(self, image_data: str) -> Optional[Dict[str, Any]]:
        """
        使用多模態 LLM 分析單一影像幀中的情緒。
        """
        try:
            print(f"開始情緒分析，圖片資料長度: {len(image_data) if image_data else 0}")
            
            image_content = {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_data}"
                }
            }

            prompt = self.get_system_prompt()
            print(f"使用提示詞: {prompt[:100]}...")

            message = HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    image_content
                ]
            )

            print("調用 LLM 進行情緒分析...")
            response = await self.llm.ainvoke([message])
            print(f"LLM 原始回應: {response.content}")
            
            # 清理並解析 LLM 的回應
            cleaned_content = response.content.strip()
            
            # 移除 markdown 代碼塊標記
            if cleaned_content.startswith("```json"):
                cleaned_content = cleaned_content[7:]  # 移除 ```json
            if cleaned_content.startswith("```"):
                cleaned_content = cleaned_content[3:]   # 移除 ```
            if cleaned_content.endswith("```"):
                cleaned_content = cleaned_content[:-3]  # 移除結尾的 ```
            
            # 移除開頭的 "json" 字串（如果存在）
            if cleaned_content.strip().startswith("json"):
                cleaned_content = cleaned_content.strip()[4:].strip()
            
            print(f"清理後的內容: {cleaned_content}")
            
            emotion_info = json.loads(cleaned_content)
            print(f"解析後的情緒資訊: {emotion_info}")
            return emotion_info

        except json.JSONDecodeError as e:
            print(f"JSON 解析失敗: {e}")
            print(f"無法解析的內容: {cleaned_content}")
            return None
        except Exception as e:
            print(f"情緒分析時發生錯誤: {e}")
            return None

    async def analyze_emotion(self, image_data: str) -> Optional[Dict[str, Any]]:
        """
        公開的情緒分析方法，供外部調用。
        """
        return await self._analyze_emotion(image_data)

    def get_system_prompt(self) -> str:
        """
        獲取指導 LLM 進行情緒分析的系統提示詞。
        """
        return """
請你扮演一位專業的心理學家和表情分析專家。
你的任務是分析這張圖片中人物的臉部表情，並判斷其最主要的情緒。

請從以下情緒類別中選擇一個最符合的：
- `neutral` (中性/無明顯情緒)
- `happy` (開心/微笑)
- `sad` (悲傷/沮喪)
- `angry` (生氣/憤怒)
- `surprised` (驚訝)
- `confused` (困惑/不解)
- `interested` (感興趣/專注)
- `tired` (疲倦/厭煩)

重要指示：
1. 你必須始終回應 JSON 格式，包含三個欄位：emotion、confidence、suggestion
2. 如果圖片中沒有人物臉部，請使用 emotion: "neutral", confidence: 0.1
3. 如果圖片中有人物但表情不清楚，請使用 emotion: "neutral", confidence: 0.3
4. 絕對不要拒絕分析圖片，總是提供 JSON 回應

你的回應必須是純 JSON 格式，包含三個欄位：`emotion`、`confidence` 和 `suggestion`。
- `emotion`: 你判斷出的情緒類別 (必須是上述列表之一)。
- `confidence`: 你對此判斷的信心分數 (0.0 到 1.0)。
- `suggestion`: 針對此情緒的簡短建議或互動提示。

範例回應:
{
    "emotion": "interested",
    "confidence": 0.85,
    "suggestion": "客戶看起來很感興趣，可以提供更多詳細資訊"
}

請務必只返回 JSON 物件，不要包含任何其他文字、解釋或 markdown 標籤。
"""

    async def analyze_image_content(self, image_data: str, question: str) -> Optional[Dict[str, Any]]:
        """
        分析圖片內容並回答特定問題（如顏色、服裝等）
        """
        try:
            print(f"開始圖片內容分析，問題: {question}")
            print(f"圖片資料長度: {len(image_data) if image_data else 0}")
            
            image_content = {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_data}"
                }
            }

            # 針對視覺問題的提示詞
            visual_prompt = f"""
你是一位專業的視覺分析師。請仔細分析這張圖片並回答以下問題：

問題：{question}

請詳細描述你在圖片中看到的內容，並針對問題提供具體的答案。

如果圖片中沒有相關內容，請說明你看到了什麼，並解釋為什麼無法回答該問題。

請用繁體中文回答。
"""

            message = HumanMessage(
                content=[
                    {"type": "text", "text": visual_prompt},
                    image_content
                ]
            )

            print("調用 LLM 進行視覺分析...")
            response = await self.llm.ainvoke([message])
            print(f"LLM 視覺分析回應: {response.content}")
            
            return {
                "content": response.content,
                "question": question,
                "success": True
            }

        except Exception as e:
            print(f"視覺分析時發生錯誤: {e}")
            return {
                "content": f"抱歉，分析圖片時發生錯誤：{str(e)}",
                "question": question,
                "success": False
            }
