#!/usr/bin/env python3
"""
綜合測試腳本 - 測試所有 Agent 和 API 功能
"""
import asyncio
import json
import time
from typing import Dict, Any
import sys
import os

# 添加專案根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents import ControlAgent, ChatAgent, RAGAgent, CardAgent, CalendarAgent
from app.core.memory import memory_manager
from app.core.logger import logger
from app.core.tokenizer import get_token_counter
from app.api.openai_compatible import api
from app.api.models import ChatCompletionRequest, Message, MessageRole


class TestRunner:
    """測試執行器"""
    
    def __init__(self):
        self.control_agent = ControlAgent()
        self.chat_agent = ChatAgent()
        self.rag_agent = RAGAgent()
        self.card_agent = CardAgent()
        self.calendar_agent = CalendarAgent()
        self.token_counter = get_token_counter()
        
        self.test_session_id = "test_session_001"
        self.test_results = []
    
    def print_header(self, title: str):
        """打印測試標題"""
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")
    
    def print_test_result(self, test_name: str, success: bool, details: str = ""):
        """打印測試結果"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"   {details}")
        
        self.test_results.append({
            "test_name": test_name,
            "success": success,
            "details": details,
            "timestamp": time.time()
        })
    
    async def test_basic_functionality(self):
        """測試基本功能"""
        self.print_header("基本功能測試")
        
        # 測試日誌系統
        try:
            logger.info("測試日誌系統", test_id="log_test_001")
            logger.error("測試錯誤日誌", error=Exception("測試錯誤"))
            self.print_test_result("日誌系統", True)
        except Exception as e:
            self.print_test_result("日誌系統", False, str(e))
        
        # 測試 Token 計算
        try:
            test_text = "Hello, this is a test message. 你好，這是一個測試訊息。"
            token_count = self.token_counter.count_tokens(test_text)
            self.print_test_result(
                "Token 計算", 
                token_count > 0, 
                f"Token 數量: {token_count}"
            )
        except Exception as e:
            self.print_test_result("Token 計算", False, str(e))
        
        # 測試記憶體管理
        try:
            test_profile = {
                "name": "測試用戶",
                "company": "測試公司",
                "preferences": ["AI", "技術"]
            }
            memory_manager.save_user_profile(self.test_session_id, test_profile)
            loaded_profile = memory_manager.load_user_profile(self.test_session_id)
            
            success = loaded_profile and loaded_profile.get("name") == "測試用戶"
            self.print_test_result(
                "記憶體管理",
                success,
                f"Profile: {loaded_profile}"
            )
        except Exception as e:
            self.print_test_result("記憶體管理", False, str(e))
    
    async def test_agents(self):
        """測試所有 Agent"""
        self.print_header("Agent 功能測試")
        
        test_cases = [
            {
                "agent": self.control_agent,
                "name": "ControlAgent",
                "input": {
                    "user_input": "你好，我想了解你們的產品",
                    "session_id": self.test_session_id,
                    "has_image": False,
                    "user_profile": {}
                }
            },
            {
                "agent": self.chat_agent,
                "name": "ChatAgent",
                "input": {
                    "user_input": "你好，請介紹一下你們的服務",
                    "session_id": self.test_session_id,
                    "has_image": False,
                    "user_profile": {}
                }
            },
            {
                "agent": self.rag_agent,
                "name": "RAGAgent",
                "input": {
                    "user_input": "什麼是人工智慧？",
                    "session_id": self.test_session_id,
                    "has_image": False,
                    "user_profile": {}
                }
            },
            {
                "agent": self.card_agent,
                "name": "CardAgent",
                "input": {
                    "user_input": "請幫我分析這張名片",
                    "session_id": self.test_session_id,
                    "has_image": True,
                    "user_profile": {},
                    "image_data": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD..."
                }
            },
            {
                "agent": self.calendar_agent,
                "name": "CalendarAgent",
                "input": {
                    "user_input": "明天下午有空嗎？",
                    "session_id": self.test_session_id,
                    "has_image": False,
                    "user_profile": {}
                }
            }
        ]
        
        for test_case in test_cases:
            try:
                start_time = time.time()
                result = await test_case["agent"].process(test_case["input"])
                duration = time.time() - start_time
                
                success = (
                    result and 
                    "content" in result and 
                    isinstance(result["content"], str) and
                    len(result["content"]) > 0
                )
                
                details = f"耗時: {duration:.2f}s, 回應長度: {len(result.get('content', ''))}"
                if not success:
                    details += f", 結果: {result}"
                
                self.print_test_result(test_case["name"], success, details)
                
            except Exception as e:
                self.print_test_result(test_case["name"], False, str(e))
    
    async def test_openai_api(self):
        """測試 OpenAI 相容 API"""
        self.print_header("OpenAI API 測試")
        
        # 測試聊天完成
        try:
            request = ChatCompletionRequest(
                model="aisales-v1",
                messages=[
                    Message(role=MessageRole.USER, content="你好，請介紹一下你們的服務")
                ],
                temperature=0.7,
                max_tokens=500,
                stream=False
            )
            
            start_time = time.time()
            response = await api.chat_completions(request)
            duration = time.time() - start_time
            
            success = (
                response and
                response.choices and
                len(response.choices) > 0 and
                response.choices[0].message.content
            )
            
            details = f"耗時: {duration:.2f}s, Response ID: {response.id}"
            if success:
                details += f", Token 使用: {response.usage.total_tokens}"
            
            self.print_test_result("聊天完成 API", success, details)
            
        except Exception as e:
            self.print_test_result("聊天完成 API", False, str(e))
        
        # 測試模型列表
        try:
            models = api.get_models()
            success = models and models.data and len(models.data) > 0
            details = f"模型數量: {len(models.data) if models.data else 0}"
            
            self.print_test_result("模型列表 API", success, details)
            
        except Exception as e:
            self.print_test_result("模型列表 API", False, str(e))
    
    async def test_integration_scenarios(self):
        """測試整合場景"""
        self.print_header("整合場景測試")
        
        scenarios = [
            {
                "name": "完整對話流程",
                "steps": [
                    "你好，我是王小明",
                    "我想了解你們的AI產品",
                    "價格如何？",
                    "下週可以安排會議嗎？"
                ]
            },
            {
                "name": "多輪問答",
                "steps": [
                    "什麼是機器學習？",
                    "深度學習和機器學習有什麼差別？",
                    "如何開始學習AI？"
                ]
            }
        ]
        
        for scenario in scenarios:
            try:
                conversation_success = True
                conversation_details = []
                
                for step_idx, user_input in enumerate(scenario["steps"]):
                    input_data = {
                        "user_input": user_input,
                        "session_id": f"{self.test_session_id}_scenario_{scenario['name']}",
                        "has_image": False,
                        "user_profile": {}
                    }
                    
                    # 使用 ControlAgent 進行路由
                    route_result = await self.control_agent.process(input_data)
                    target_agent = route_result["metadata"]["route_to"]
                    
                    # 根據路由結果調用對應 Agent
                    if target_agent == "chat_agent":
                        result = await self.chat_agent.process(input_data)
                    elif target_agent == "rag_agent":
                        result = await self.rag_agent.process(input_data)
                    elif target_agent == "calendar_agent":
                        result = await self.calendar_agent.process(input_data)
                    else:
                        result = await self.chat_agent.process(input_data)
                    
                    if not result or not result.get("content"):
                        conversation_success = False
                        conversation_details.append(f"步驟 {step_idx + 1} 失敗")
                        break
                    
                    conversation_details.append(f"步驟 {step_idx + 1}: {target_agent}")
                
                self.print_test_result(
                    scenario["name"],
                    conversation_success,
                    " -> ".join(conversation_details)
                )
                
            except Exception as e:
                self.print_test_result(scenario["name"], False, str(e))
    
    async def test_error_handling(self):
        """測試錯誤處理"""
        self.print_header("錯誤處理測試")
        
        # 測試無效輸入
        try:
            result = await self.chat_agent.process({
                "user_input": "",
                "session_id": self.test_session_id,
                "has_image": False,
                "user_profile": {}
            })
            
            # 應該能處理空輸入
            success = result and "content" in result
            self.print_test_result("空輸入處理", success)
            
        except Exception as e:
            self.print_test_result("空輸入處理", False, str(e))
        
        # 測試異常長的輸入
        try:
            long_input = "測試 " * 1000
            result = await self.chat_agent.process({
                "user_input": long_input,
                "session_id": self.test_session_id,
                "has_image": False,
                "user_profile": {}
            })
            
            success = result and "content" in result
            self.print_test_result("長輸入處理", success)
            
        except Exception as e:
            self.print_test_result("長輸入處理", False, str(e))
    
    def print_summary(self):
        """打印測試總結"""
        self.print_header("測試總結")
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"總測試數量: {total_tests}")
        print(f"通過測試: {passed_tests}")
        print(f"失敗測試: {failed_tests}")
        print(f"通過率: {passed_tests/total_tests*100:.1f}%")
        
        if failed_tests > 0:
            print("\n失敗的測試:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  ❌ {result['test_name']}: {result['details']}")
        
        # 儲存測試結果
        with open("test_results.json", "w", encoding="utf-8") as f:
            json.dump(self.test_results, f, ensure_ascii=False, indent=2)
        
        print(f"\n測試結果已儲存至 test_results.json")
    
    async def run_all_tests(self):
        """執行所有測試"""
        print("🚀 開始執行 AI Sales 系統綜合測試...")
        
        await self.test_basic_functionality()
        await self.test_agents()
        await self.test_openai_api()
        await self.test_integration_scenarios()
        await self.test_error_handling()
        
        self.print_summary()


async def main():
    """主函數"""
    runner = TestRunner()
    await runner.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
