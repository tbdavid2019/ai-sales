#!/usr/bin/env python3
"""
測試UI參數功能
"""
import asyncio
from app.core.ui_handler import process_user_request

async def test_ui_parameters():
    """測試UI參數功能"""
    
    # 測試一般文字模式
    print("=== 測試一般文字模式 ===")
    result_chat, profile = await process_user_request(
        message="你好，我想了解你們的產品",
        image=None,
        user_profile={},
        interaction_mode="sales",
        response_mode="chat",
        max_tokens=200,
        temperature=0.7
    )
    print(f"一般模式回應: {result_chat}")
    print(f"回應長度: {len(result_chat)}")
    
    # 測試虛擬人模式
    print("\n=== 測試虛擬人模式 ===")
    result_virtual, profile = await process_user_request(
        message="你好，我想了解你們的產品",
        image=None,
        user_profile={},
        interaction_mode="sales",
        response_mode="virtual_human",
        max_tokens=50,
        temperature=0.8
    )
    print(f"虛擬人模式回應: {result_virtual}")
    print(f"回應長度: {len(result_virtual)}")
    
    # 比較回應長度
    print(f"\n=== 比較結果 ===")
    print(f"一般模式長度: {len(result_chat)} 字")
    print(f"虛擬人模式長度: {len(result_virtual)} 字")
    print(f"長度差異: {len(result_chat) - len(result_virtual)} 字")

if __name__ == "__main__":
    asyncio.run(test_ui_parameters())
