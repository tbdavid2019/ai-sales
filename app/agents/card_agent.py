from typing import Dict, Any, Optional
from app.agents.base_agent import BaseAgent
from app.models import LLMFactory
from langchain_core.messages import HumanMessage
import base64
import json
import re


class CardAgent(BaseAgent):
    """名片 Agent - 處理名片 OCR 和資訊提取"""
    
    def __init__(self):
        super().__init__(
            name="CardAgent",
            description="AI 名片識別助理，專門處理名片圖片分析和客戶資訊提取"
        )
        self.llm = LLMFactory.get_card_agent_llm()
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """處理名片 OCR 請求"""
        image_data = input_data.get("image_data", "")
        image_url = input_data.get("image_url", "")
        session_id = input_data.get("session_id", "")
        
        if not image_data and not image_url:
            return self.format_response(
                content="請提供名片圖片以進行識別。",
                metadata={"error": "no_image_provided"}
            )
        
        try:
            # 分析名片
            card_info = await self._analyze_business_card(image_data, image_url)
            
            if card_info:
                # 更新用戶資料
                if session_id:
                    self.memory.update_user_profile(session_id, card_info)
                
                # 生成友善回應
                response = self._generate_greeting(card_info)
                
                return self.format_response(
                    content=response,
                    metadata={
                        "extracted_info": card_info,
                        "confidence": card_info.get("confidence", 0.8),
                        "updated_user_profile": card_info  # 添加這行讓 app_gradio.py 能同步更新
                    }
                )
            else:
                return self.format_response(
                    content="抱歉，無法清楚識別名片內容。請確保圖片清晰且包含完整的名片資訊。",
                    metadata={"error": "ocr_failed"}
                )
                
        except Exception as e:
            print(f"名片處理失敗: {e}")
            return self.format_response(
                content="處理名片時發生錯誤，請稍後再試。",
                metadata={"error": str(e)}
            )
    
    async def _analyze_business_card(self, image_data: str, image_url: str) -> Optional[Dict[str, Any]]:
        """分析名片圖片"""
        try:
            # 構建圖片訊息
            if image_data:
                # Base64 編碼的圖片
                image_content = {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_data}"
                    }
                }
            elif image_url:
                # URL 圖片
                image_content = {
                    "type": "image_url",
                    "image_url": {
                        "url": image_url
                    }
                }
            else:
                return None
            
            # 構建提示詞
            prompt = self.get_system_prompt()
            
            # 調用 LLM 分析
            message = HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    image_content
                ]
            )
            
            response = await self.llm.ainvoke([message])
            
            # 清理回應內容，移除可能的 markdown 標記
            cleaned_content = re.sub(r"```json\\n|```", "", response.content.strip())
            
            # 解析 JSON
            card_info = json.loads(cleaned_content)
            return card_info
            
        except json.JSONDecodeError:
            print(f"JSON 解析失敗，嘗試備用提取方案。原始回應: {response.content}")
            # 如果解析失敗，嘗試從原始文本中提取關鍵資訊作為備用方案
            return self._fallback_extraction(response.content)
        except Exception as e:
            print(f"分析名片時發生錯誤: {e}")
            return None

    def _fallback_extraction(self, raw_text: str) -> Optional[Dict[str, Any]]:
        """在 JSON 解析失敗時，從原始文本中提取資訊的備用方法"""
        try:
            print("執行備用提取方案...")
            # 嘗試用正則表達式找到看起來像 JSON 的物件
            match = re.search(r'{\s*".*?"\s*:\s*".*?"\s*[,}]', raw_text, re.DOTALL)
            if match:
                # 找到開頭後，再找對應的結尾
                start_index = match.start()
                open_braces = 0
                for i, char in enumerate(raw_text[start_index:]):
                    if char == '{':
                        open_braces += 1
                    elif char == '}':
                        open_braces -= 1
                        if open_braces == 0:
                            end_index = start_index + i + 1
                            json_str = raw_text[start_index:end_index]
                            card_info = json.loads(json_str)
                            print("備用提取成功！")
                            return card_info
            print("備用提取方案未找到有效的 JSON 物件。")
            return None
        except Exception as e:
            print(f"備用提取方案失敗: {e}")
            return None

    def _generate_greeting(self, card_info: Dict[str, Any]) -> str:
        """根據提取的資訊生成問候語"""
        name = card_info.get("name", "您")
        company = card_info.get("company", "")
        
        greeting = f"{name} 您好！很高興認識您。"
        if company:
            greeting += f" 我看到您來自「{company}」。"
            
        greeting += " 您的聯絡資訊我已經記錄下來了。"
        greeting += " 作為您的一站式開店顧問，我非常樂意協助貴公司或您的業務打造專業的線上商店。"
        greeting += " 不知道您目前是否有線上銷售的需求，或是對我們的平台有任何想了解的地方呢？"
        
        return greeting

    def _parse_llm_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """解析 LLM 返回的 JSON 字串"""
        try:
            # 提取 JSON 部分
            json_match = re.search(r"```json\\n(.*?)\\n```", response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                return json.loads(json_str)
            else:
                # 如果沒有找到 markdown 格式，嘗試直接解析
                return json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"JSON 解析失敗: {e}")
            print(f"原始回應: {response_text}")
            return None
        except Exception as e:
            print(f"處理回應時發生未知錯誤: {e}")
            return None

    def get_system_prompt(self) -> str:
        """獲取系統提示詞"""
        return """
請分析這張名片圖片，提取以下資訊並以 JSON 格式返回。請務必只返回 JSON 物件，不要包含任何其他文字或說明。

```json
{
    "name": "姓名",
    "title": "職稱",
    "company": "公司名稱",
    "department": "部門",
    "phone": "電話號碼",
    "email": "電子郵件",
    "address": "地址",
    "website": "網站",
    "confidence": 0.85
}
```

- `name`: 姓名，如果無法識別則留空。
- `title`: 職稱，如果無法識別則留空。
- `company`: 公司或組織名稱，如果無法識別則留空。
- `department`: 部門，如果沒有則留空。
- `phone`: 電話或手機號碼，優先提取手機。
- `email`: 電子郵件地址。
- `address`: 公司地址。
- `website`: 公司網站。
- `confidence`: 你對提取資訊準確度的信心分數 (0.0 到 1.0)。
"""
