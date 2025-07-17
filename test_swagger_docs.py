#!/usr/bin/env python3
"""
測試 Swagger 文檔功能
"""

import requests
import json

def test_swagger_docs():
    """測試 Swagger 文檔功能"""
    base_url = "http://localhost:8000"
    
    print("=== 測試 AI Sales API Swagger 文檔 ===\n")
    
    # 1. 測試根路徑
    print("1. 測試根路徑 (/)")
    try:
        response = requests.get(f"{base_url}/")
        print(f"   狀態碼: {response.status_code}")
        print(f"   回應: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"   錯誤: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # 2. 測試健康檢查
    print("2. 測試健康檢查 (/health)")
    try:
        response = requests.get(f"{base_url}/health")
        print(f"   狀態碼: {response.status_code}")
        print(f"   回應: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"   錯誤: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # 3. 測試模型列表
    print("3. 測試模型列表 (/v1/models)")
    try:
        response = requests.get(f"{base_url}/v1/models")
        print(f"   狀態碼: {response.status_code}")
        print(f"   回應: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"   錯誤: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # 4. 測試聊天完成 - 虛擬人模式
    print("4. 測試聊天完成 - 虛擬人模式")
    try:
        payload = {
            "model": "aisales-v1",
            "messages": [
                {"role": "user", "content": "你好，介紹一下你們的產品"}
            ],
            "max_tokens": 50,
            "temperature": 0.8,
            "stream": False
        }
        
        response = requests.post(
            f"{base_url}/v1/chat/completions",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"   狀態碼: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"   回應內容: {result['choices'][0]['message']['content']}")
            print(f"   Token 使用: {result['usage']}")
        else:
            print(f"   錯誤: {response.text}")
    except Exception as e:
        print(f"   錯誤: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # 5. 測試聊天完成 - 一般模式
    print("5. 測試聊天完成 - 一般模式")
    try:
        payload = {
            "model": "aisales-v1",
            "messages": [
                {"role": "user", "content": "詳細介紹一下你們的產品特色"}
            ],
            "max_tokens": 500,
            "temperature": 0.7,
            "stream": False
        }
        
        response = requests.post(
            f"{base_url}/v1/chat/completions",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"   狀態碼: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"   回應內容: {result['choices'][0]['message']['content']}")
            print(f"   Token 使用: {result['usage']}")
        else:
            print(f"   錯誤: {response.text}")
    except Exception as e:
        print(f"   錯誤: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # 6. 顯示 Swagger 文檔連結
    print("6. Swagger 文檔連結")
    print(f"   📖 API 文檔: {base_url}/docs")
    print(f"   📋 OpenAPI 規範: {base_url}/openapi.json")
    print(f"   🎨 Streamlit UI: http://localhost:8501")
    print(f"   🎮 Gradio UI: http://localhost:7860")
    
    print("\n" + "="*50 + "\n")
    
    # 7. 參數說明
    print("7. 參數使用建議")
    print("   虛擬人模式 (簡短互動):")
    print("   - max_tokens: 50-200")
    print("   - temperature: 0.8")
    print("   - 適用: 快速對話、即時互動")
    print()
    print("   一般文字模式 (詳細回應):")
    print("   - max_tokens: 100-2000")
    print("   - temperature: 0.7")
    print("   - 適用: 產品介紹、詳細諮詢")
    print()
    print("   RAG 知識查詢 (準確回應):")
    print("   - max_tokens: 800")
    print("   - temperature: 0.5")
    print("   - 適用: 技術問題、資料查詢")

if __name__ == "__main__":
    test_swagger_docs()
