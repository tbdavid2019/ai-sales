#!/usr/bin/env python3
"""
LangGraph 工作流測試腳本
"""
import asyncio
import json
import time
from typing import Dict, Any
import sys
import os

# 添加專案根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.workflow import workflow_manager
from app.core.logger import logger


class LangGraphWorkflowTest:
    """LangGraph 工作流測試類"""
    
    def __init__(self):
        self.test_results = []
        self.workflow_manager = workflow_manager
    
    def print_header(self, title: str):
        """打印測試標題"""
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")
    
    def print_test_result(self, test_name: str, success: bool, details: str = "", duration: float = 0):
        """打印測試結果"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name} ({duration:.2f}s)")
        if details:
            print(f"   {details}")
        
        self.test_results.append({
            "test_name": test_name,
            "success": success,
            "details": details,
            "duration": duration,
            "timestamp": time.time()
        })
    
    async def test_basic_workflow(self):
        """測試基本工作流"""
        self.print_header("基本工作流測試")
        
        test_cases = [
            {
                "name": "簡單問候",
                "input": {
                    "user_input": "你好",
                    "session_id": "test_basic_001",
                    "has_image": False,
                    "user_profile": {}
                },
                "expected_mode": "single"
            },
            {
                "name": "產品查詢",
                "input": {
                    "user_input": "請介紹一下你們的AI產品功能",
                    "session_id": "test_basic_002",
                    "has_image": False,
                    "user_profile": {}
                },
                "expected_mode": "single"
            },
            {
                "name": "複雜查詢",
                "input": {
                    "user_input": "我想了解AI產品的功能，並且想安排一個會議討論",
                    "session_id": "test_basic_003",
                    "has_image": False,
                    "user_profile": {}
                },
                "expected_mode": "parallel"
            }
        ]
        
        for case in test_cases:
            try:
                start_time = time.time()
                result = await self.workflow_manager.execute_workflow(case["input"])
                duration = time.time() - start_time
                
                success = (
                    result.success and 
                    result.content and 
                    len(result.content) > 0
                )
                
                details = f"內容長度: {len(result.content)}, Agents: {list(result.agent_results.keys())}"
                
                self.print_test_result(case["name"], success, details, duration)
                
            except Exception as e:
                self.print_test_result(case["name"], False, f"錯誤: {str(e)}", 0)
    
    async def test_parallel_processing(self):
        """測試並行處理"""
        self.print_header("並行處理測試")
        
        parallel_test_cases = [
            {
                "name": "圖片+文字查詢",
                "input": {
                    "user_input": "請幫我分析這張名片並介紹相關產品",
                    "session_id": "test_parallel_001",
                    "has_image": True,
                    "image_data": "mock_image_data",
                    "user_profile": {}
                }
            },
            {
                "name": "產品比較查詢",
                "input": {
                    "user_input": "請比較不同AI產品的特色和優勢",
                    "session_id": "test_parallel_002",
                    "has_image": False,
                    "user_profile": {}
                }
            },
            {
                "name": "綜合業務查詢",
                "input": {
                    "user_input": "我需要了解產品功能、價格，並且希望安排demo會議",
                    "session_id": "test_parallel_003",
                    "has_image": False,
                    "user_profile": {}
                }
            }
        ]
        
        for case in parallel_test_cases:
            try:
                start_time = time.time()
                result = await self.workflow_manager.execute_workflow(case["input"])
                duration = time.time() - start_time
                
                success = (
                    result.success and 
                    result.content and 
                    len(result.agent_results) > 1  # 應該有多個 Agent 參與
                )
                
                details = f"Agents: {list(result.agent_results.keys())}, 聚合: {result.metadata.get('aggregated', False)}"
                
                self.print_test_result(case["name"], success, details, duration)
                
            except Exception as e:
                self.print_test_result(case["name"], False, f"錯誤: {str(e)}", 0)
    
    async def test_advanced_routing(self):
        """測試高級路由"""
        self.print_header("高級路由測試")
        
        routing_test_cases = [
            {
                "name": "意圖分析 - 問候",
                "input": {
                    "user_input": "你好，很高興認識你",
                    "session_id": "test_routing_001",
                    "has_image": False,
                    "user_profile": {}
                },
                "expected_intent": "greeting"
            },
            {
                "name": "意圖分析 - 產品查詢",
                "input": {
                    "user_input": "請問你們的產品有什麼特色功能？",
                    "session_id": "test_routing_002",
                    "has_image": False,
                    "user_profile": {}
                },
                "expected_intent": "product_inquiry"
            },
            {
                "name": "意圖分析 - 預約會議",
                "input": {
                    "user_input": "我想安排一個會議討論合作事宜",
                    "session_id": "test_routing_003",
                    "has_image": False,
                    "user_profile": {}
                },
                "expected_intent": "appointment"
            }
        ]
        
        for case in routing_test_cases:
            try:
                start_time = time.time()
                
                # 測試路由決策
                routing_result = await self.workflow_manager._route_decision(case["input"])
                duration = time.time() - start_time
                
                success = (
                    routing_result and 
                    "execution_mode" in routing_result and
                    "primary_agent" in routing_result
                )
                
                details = f"模式: {routing_result.get('execution_mode')}, 主要Agent: {routing_result.get('primary_agent')}"
                
                self.print_test_result(case["name"], success, details, duration)
                
            except Exception as e:
                self.print_test_result(case["name"], False, f"錯誤: {str(e)}", 0)
    
    async def test_error_handling(self):
        """測試錯誤處理"""
        self.print_header("錯誤處理測試")
        
        error_test_cases = [
            {
                "name": "空輸入處理",
                "input": {
                    "user_input": "",
                    "session_id": "test_error_001",
                    "has_image": False,
                    "user_profile": {}
                }
            },
            {
                "name": "異常長輸入",
                "input": {
                    "user_input": "測試內容 " * 500,
                    "session_id": "test_error_002",
                    "has_image": False,
                    "user_profile": {}
                }
            },
            {
                "name": "缺少必要欄位",
                "input": {
                    "user_input": "測試輸入",
                    # 缺少 session_id
                    "has_image": False,
                    "user_profile": {}
                }
            }
        ]
        
        for case in error_test_cases:
            try:
                start_time = time.time()
                result = await self.workflow_manager.execute_workflow(case["input"])
                duration = time.time() - start_time
                
                # 錯誤處理測試的成功標準：系統能正常回應，不崩潰
                success = (
                    result is not None and 
                    hasattr(result, 'content') and
                    isinstance(result.content, str)
                )
                
                details = f"成功: {result.success}, 內容: {result.content[:50]}..."
                
                self.print_test_result(case["name"], success, details, duration)
                
            except Exception as e:
                self.print_test_result(case["name"], False, f"錯誤: {str(e)}", 0)
    
    async def test_performance_monitoring(self):
        """測試效能監控"""
        self.print_header("效能監控測試")
        
        performance_test_cases = [
            {
                "name": "快速查詢效能",
                "input": {
                    "user_input": "你好",
                    "session_id": "test_perf_001",
                    "has_image": False,
                    "user_profile": {}
                },
                "expected_time": 2.0  # 期望在2秒內完成
            },
            {
                "name": "並行查詢效能",
                "input": {
                    "user_input": "請比較產品功能並安排會議",
                    "session_id": "test_perf_002",
                    "has_image": False,
                    "user_profile": {}
                },
                "expected_time": 10.0  # 期望在10秒內完成
            }
        ]
        
        for case in performance_test_cases:
            try:
                start_time = time.time()
                result = await self.workflow_manager.execute_workflow(case["input"])
                duration = time.time() - start_time
                
                success = (
                    result.success and 
                    duration < case["expected_time"]
                )
                
                details = f"執行時間: {duration:.2f}s, 期望: <{case['expected_time']}s"
                
                self.print_test_result(case["name"], success, details, duration)
                
            except Exception as e:
                self.print_test_result(case["name"], False, f"錯誤: {str(e)}", 0)
    
    def print_summary(self):
        """打印測試總結"""
        self.print_header("測試總結")
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        
        avg_duration = sum(result["duration"] for result in self.test_results) / total_tests if total_tests > 0 else 0
        
        print(f"總測試數量: {total_tests}")
        print(f"通過測試: {passed_tests}")
        print(f"失敗測試: {failed_tests}")
        print(f"通過率: {passed_tests/total_tests*100:.1f}%")
        print(f"平均執行時間: {avg_duration:.2f}s")
        
        if failed_tests > 0:
            print("\n失敗的測試:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  ❌ {result['test_name']}: {result['details']}")
        
        # 儲存測試結果
        with open("langgraph_test_results.json", "w", encoding="utf-8") as f:
            json.dump(self.test_results, f, ensure_ascii=False, indent=2)
        
        print(f"\n測試結果已儲存至 langgraph_test_results.json")
    
    async def run_all_tests(self):
        """執行所有測試"""
        print("🚀 開始執行 LangGraph 工作流測試...")
        
        await self.test_basic_workflow()
        await self.test_parallel_processing()
        await self.test_advanced_routing()
        await self.test_error_handling()
        await self.test_performance_monitoring()
        
        self.print_summary()


async def main():
    """主函數"""
    test_runner = LangGraphWorkflowTest()
    await test_runner.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
