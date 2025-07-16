#!/usr/bin/env python3
"""
AI Sales 對話系統 Gradio 介面
"""
import gradio as gr
import asyncio
import os
import sys
import uuid
from typing import List, Tuple, Optional, Dict, Any

# 添加專案根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.logger import logger

# --- Gradio 介面邏輯 ---

async def process_request(
    message: str, 
    image: Optional[Any], 
    history: List[Tuple[str, str]], 
    user_profile: Dict[str, Any],
    interaction_mode: str  # 新增參數
) -> Tuple[List[Tuple[str, str]], Dict[str, Any], str]:
    """
    統一處理後端請求的核心函數
    """
    # 使用統一的核心處理函數
    from app.core.ui_handler import process_user_request
    
    session_id = user_profile.get("session_id", "default_session")
    
    try:
        # 使用統一的核心處理函數
        response_content, updated_profile = await process_user_request(
            message=message,
            image=image,
            user_profile=user_profile,
            interaction_mode=interaction_mode,
            session_id=session_id
        )
        
        # 更新歷史紀錄 - 使用 Gradio 5.x 的 messages 格式
        user_display_message = message if message else "(名片分析)"
        
        # 添加用戶訊息 (如果有的話)
        if message:
            history.append({"role": "user", "content": user_display_message})
        
        # 添加助理回應
        history.append({"role": "assistant", "content": response_content})
        
        return history, updated_profile, ""
        
    except Exception as e:
        logger.error(f"處理請求時發生錯誤: {e}", exc_info=True)
        user_display_message = message if message else "(處理失敗)"
        if message:
            history.append({"role": "user", "content": user_display_message})
        history.append({"role": "assistant", "content": "系統暫時無法處理您的請求，請稍後再試。"})
        return history, user_profile, ""
    if user_display_message.strip():
        history.append({"role": "user", "content": user_display_message})
    
    # 添加助理回應
    history.append({"role": "assistant", "content": response_content})
    
    return history, updated_profile, ""

async def handle_text_submit(
    message: str, 
    history: List[Tuple[str, str]], 
    image: Optional[Any], 
    user_profile: Dict[str, Any],
    interaction_mode: str  # 新增參數
):
    """處理文字輸入和傳送按鈕點擊"""
    if not message:
        return history, user_profile, ""
    
    new_history, new_user_profile, new_msg = await process_request(message, image, history, user_profile, interaction_mode)
    return new_history, new_user_profile, new_msg

async def handle_image_upload(
    image: Optional[Any], 
    history: List[Dict[str, str]], 
    user_profile: Dict[str, Any],
    interaction_mode: str  # 新增參數
):
    """處理圖片上傳事件"""
    if not image:
        return history, user_profile
    
    # 立即給予反饋 - 使用 messages 格式
    history.append({"role": "user", "content": "(名片圖片)"})
    history.append({"role": "assistant", "content": "收到名片，正在為您分析..."})
    
    # 呼叫核心處理函數 (無文字訊息)
    final_history, new_user_profile, _ = await process_request("", image, history, user_profile, interaction_mode)
    
    # 移除"正在分析"的訊息
    # 找到並移除佔位訊息，從後往前找以避免刪錯
    for i in range(len(final_history) - 1, -1, -1):
        if (final_history[i].get("role") == "assistant" and 
            final_history[i].get("content") == "收到名片，正在為您分析..."):
            final_history.pop(i)
            break
            
    return final_history, new_user_profile

def build_ui():
    """建立 Gradio UI"""
    # 定義自訂主題：綠色系、襯線字體、柔和背景
    custom_theme = gr.themes.Soft(
        primary_hue="green",
        secondary_hue="green",
        neutral_hue="stone",
        font=[gr.themes.GoogleFont("Lora"), "Georgia", "serif"]
    ).set(
        body_background_fill="#f5fbf5",  # 使用柔和的淺綠色作為背景
    )

    # 移除外部 JavaScript 檔案載入，直接嵌入代碼
    with gr.Blocks(theme=custom_theme, title="AI Sales 對話系統") as demo:
        # 狀態管理
        session_id = str(uuid.uuid4())
        user_profile = gr.State({"session_id": session_id})

        gr.Markdown("# 🤖 AI Sales 對話系統")
        gr.Markdown("歡迎！您可以直接上傳名片讓我認識您，或在下方輸入文字與我對話。")

        with gr.Row():
            with gr.Column(scale=2):
                chatbot = gr.Chatbot(
                    elem_id="chatbot",
                    height=600,
                    avatar_images=(None, "assets/avatar.png"),
                    type='messages',  # 修正 UserWarning
                    # 設定初始訊息，並符合新版 Gradio 的格式
                    value=[{"role": "assistant", "content": "您好！我是 AI 銷售助理，很高興為您服務。您可以詢問產品、安排會議，或上傳名片讓我更認識您！"}]
                )

            with gr.Column(scale=1):
                with gr.Tab("互動控制"):
                    gr.Markdown("### 模式切換")
                    interaction_mode_selector = gr.Radio(
                        ["一般文字模式 (Chat)", "虛擬人模式 (Virtual Human)"],
                        label="請選擇互動模式",
                        value="一般文字模式 (Chat)",
                        info="切換模式以改變 AI 的回應風格"
                    )

                    gr.Markdown("### 1. 上傳名片 (自動分析)")
                    image_input = gr.Image(
                        label="點擊或拖曳圖片至此",
                        type="pil",
                        sources=["upload", "webcam", "clipboard"]
                    )
                
                with gr.Tab("視覺分析 (Vision)"):
                    gr.Markdown("### 即時情緒感知")
                    # 建立一個隱藏的元件來觸發 JS
                    session_id_html = gr.HTML(f'<span id="session-id" style="display: none;">{session_id}</span>', visible=False)
                    
                    # 攝影機畫面容器
                    video_container = gr.HTML('<div id="video-container" style="width: 100%; min-height: 200px; border: 1px solid #ccc; background: #f0f0f0; display: flex; justify-content: center; align-items: center;"><p style="color:grey;">攝影機已關閉</p></div>')
                    
                    # 狀態顯示
                    vision_status = gr.Textbox(label="視覺分析狀態", value="尚未啟動", interactive=False, elem_id="vision-status-textbox")

                    with gr.Row():
                        start_vision_btn = gr.Button("✅ 開啟鏡頭", elem_id="start-vision-btn")
                        stop_vision_btn = gr.Button("🛑 關閉鏡頭", elem_id="stop-vision-btn")
                    
                    # 使用 gr.HTML 組件，但放在頁面底部以確保載入
                    debug_output = gr.HTML("""
                    <div style="background: #f0f0f0; padding: 10px; margin: 10px; border-radius: 5px;">
                        <h4>除錯資訊:</h4>
                        <div id="debug-info">JavaScript 載入中...</div>
                    </div>
                    """)
                    
                    # 測試按鈕 - 先用簡單的 alert 測試
                    test_btn = gr.Button("🧪 測試按鈕", elem_id="test-btn")
                    
                    # 直接嵌入完整的 JavaScript 代碼
                    gr.HTML(f"""
                    <script>
                    console.log('=== Vision script loading... ===');
                    
                    // 更新除錯資訊
                    function updateDebugInfo(message) {{
                        const debugDiv = document.getElementById('debug-info');
                        if (debugDiv) {{
                            debugDiv.innerHTML += '<br>' + message;
                        }}
                        console.log('DEBUG:', message);
                    }}
                    
                    // 延遲執行以確保 DOM 載入
                    setTimeout(function() {{
                        updateDebugInfo('JavaScript 已載入');
                        
                        // 測試按鈕事件
                        const testBtn = document.getElementById('test-btn');
                        if (testBtn) {{
                            testBtn.addEventListener('click', function() {{
                                alert('測試按鈕運作正常！');
                                updateDebugInfo('測試按鈕點擊成功');
                            }});
                            updateDebugInfo('測試按鈕事件已綁定');
                        }} else {{
                            updateDebugInfo('測試按鈕未找到');
                        }}
                        
                        // 檢查視覺分析按鈕
                        const startBtn = document.getElementById('start-vision-btn');
                        const stopBtn = document.getElementById('stop-vision-btn');
                        
                        updateDebugInfo('開始按鈕: ' + (startBtn ? '找到' : '未找到'));
                        updateDebugInfo('停止按鈕: ' + (stopBtn ? '找到' : '未找到'));
                        
                        // 綁定視覺分析按鈕事件
                        if (startBtn) {{
                            startBtn.addEventListener('click', function() {{
                                updateDebugInfo('開始視覺分析按鈕被點擊');
                                console.log('=== 開始視覺分析 ===');
                                
                                // 請求攝影機權限
                                navigator.mediaDevices.getUserMedia({{ video: true }})
                                    .then(stream => {{
                                        updateDebugInfo('攝影機權限獲取成功');
                                        console.log('攝影機權限獲取成功');
                                        
                                        // 顯示攝影機畫面
                                        const videoContainer = document.getElementById('video-container');
                                        if (videoContainer) {{
                                            const videoElement = document.createElement('video');
                                            videoElement.srcObject = stream;
                                            videoElement.autoplay = true;
                                            videoElement.style.width = '100%';
                                            videoElement.style.transform = 'scaleX(-1)';
                                            videoContainer.innerHTML = '';
                                            videoContainer.appendChild(videoElement);
                                            
                                            // 更新狀態
                                            const statusElement = document.getElementById('vision-status-textbox');
                                            if (statusElement) {{
                                                statusElement.value = '攝影機已啟動';
                                            }}
                                            
                                            updateDebugInfo('攝影機畫面已顯示');
                                        }} else {{
                                            updateDebugInfo('video-container 未找到');
                                        }}
                                    }})
                                    .catch(err => {{
                                        updateDebugInfo('攝影機權限被拒絕: ' + err.message);
                                        console.error('攝影機權限被拒絕:', err);
                                    }});
                            }});
                            updateDebugInfo('開始按鈕事件已綁定');
                        }}
                        
                        if (stopBtn) {{
                            stopBtn.addEventListener('click', function() {{
                                updateDebugInfo('停止視覺分析按鈕被點擊');
                                console.log('=== 停止視覺分析 ===');
                                
                                // 簡單的停止功能
                                const videoContainer = document.getElementById('video-container');
                                if (videoContainer) {{
                                    videoContainer.innerHTML = '<p style="text-align:center; color:grey;">攝影機已關閉</p>';
                                }}
                                
                                const statusElement = document.getElementById('vision-status-textbox');
                                if (statusElement) {{
                                    statusElement.value = '視覺分析已停止';
                                }}
                                
                                updateDebugInfo('視覺分析已停止');
                            }});
                            updateDebugInfo('停止按鈕事件已綁定');
                        }}
                        
                        updateDebugInfo('所有事件綁定完成');
                    }}, 1000);
                    
                    console.log('=== Vision script loaded successfully ===');
                    </script>
                    """, visible=False)

                with gr.Tab("使用者資訊"):
                    gr.Markdown("### 使用者資訊 (自動更新)")
                    user_profile_display = gr.JSON(label="User Profile")

        with gr.Row():
            with gr.Column(scale=12):
                msg_input = gr.Textbox(
                    show_label=False,
                    placeholder="或在這裡輸入您的問題...",
                    container=False,
                )
            with gr.Column(scale=1, min_width=60):
                submit_btn = gr.Button("傳送")

        # --- 動作綁定 ---

        # 圖片上傳和文字提交的事件綁定 (視覺分析按鈕已在 HTML 中處理)
        
        # 1. 圖片上傳時，自動觸發分析
        image_input.upload(
            handle_image_upload,
            [image_input, chatbot, user_profile, interaction_mode_selector],
            [chatbot, user_profile_display],
        )
        
        # 2. 點擊傳送按鈕或按 Enter
        submit_btn.click(
            handle_text_submit,
            [msg_input, chatbot, image_input, user_profile, interaction_mode_selector],
            [chatbot, user_profile_display, msg_input],
        )
        msg_input.submit(
            handle_text_submit,
            [msg_input, chatbot, image_input, user_profile, interaction_mode_selector],
            [chatbot, user_profile_display, msg_input],
        )

    return demo

if __name__ == "__main__":
    # 建立一個 avatar 圖片的目錄
    assets_dir = "assets"
    if not os.path.exists(assets_dir):
        os.makedirs(assets_dir)
    # 提示使用者放置頭像圖片
    avatar_path = os.path.join(assets_dir, "avatar.png")
    if not os.path.exists(avatar_path):
        print(f"提示：請在 {assets_dir} 目錄下放置一張名為 avatar.png 的圖片作為 AI 助理的頭像。")
    
    print("Gradio UI 準備啟動...")
    print("請在瀏覽器中打開 http://127.0.0.1:7860")
    
    ui = build_ui()
    ui.queue()
    ui.launch(server_name="0.0.0.0", server_port=7860)
