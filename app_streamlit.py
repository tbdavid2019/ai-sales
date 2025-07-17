import streamlit as st
import asyncio
import cv2
import numpy as np
import base64
import json
import io
from PIL import Image
import threading
import time
from datetime import datetime
import sys
import os
import logging
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import contextlib
import gc

# 添加專案路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 上下文管理器，確保資源正確清理
@contextlib.asynccontextmanager
async def safe_async_context():
    """確保異步操作的資源正確清理"""
    try:
        yield
    finally:
        # 更積極的資源清理
        try:
            # 等待所有掛起的 gRPC 調用完成
            await asyncio.sleep(0.2)
            
            # 強制進行垃圾回收，清理未完成的 gRPC 調用
            gc.collect()
            
            # 再次等待，確保清理完成
            await asyncio.sleep(0.1)
        except Exception as cleanup_error:
            logger.warning(f"資源清理過程中出現警告: {cleanup_error}")
            # 不重新拋出異常，因為這只是清理過程的警告

# 安全的異步運行函數
def safe_run_async(coro):
    """安全地運行異步函數，避免 event loop 衝突"""
    try:
        # 嘗試獲取現有的 event loop
        loop = asyncio.get_running_loop()
        if loop.is_running():
            # 如果 loop 正在運行，創建一個新的線程來運行協程
            import concurrent.futures
            import threading
            
            def run_coro():
                # 在新線程中創建新的 event loop
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    # 包裝協程以確保資源清理
                    async def wrapped_coro():
                        async with safe_async_context():
                            return await coro
                    return new_loop.run_until_complete(wrapped_coro())
                finally:
                    new_loop.close()
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_coro)
                return future.result(timeout=60)  # 設置超時
        else:
            return asyncio.run(coro)
    except RuntimeError as e:
        if "cannot be called from a running event loop" in str(e):
            # 如果是 event loop 衝突，使用線程池執行
            import concurrent.futures
            import threading
            
            def run_coro():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    async def wrapped_coro():
                        async with safe_async_context():
                            return await coro
                    return new_loop.run_until_complete(wrapped_coro())
                finally:
                    new_loop.close()
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_coro)
                return future.result(timeout=60)
        else:
            # 其他 RuntimeError，直接運行
            return asyncio.run(coro)
    except Exception as e:
        logger.error(f"safe_run_async 執行失敗: {e}")
        raise

# 導入核心模組
try:
    from app.core.workflow import workflow_manager
    from app.core.ui_handler import process_user_request  # 使用統一處理函數
    from app.agents.vision_agent import VisionAgent
    from app.models.llm_factory import LLMFactory
    from app.config import settings
    logger.info("所有模組載入成功")
except ImportError as e:
    logger.error(f"模組載入失敗: {e}")
    st.error(f"系統載入失敗: {e}")
    st.stop()

# 設定頁面配置
st.set_page_config(
    page_title="AI Sales 智能銷售助手",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自訂 CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .chat-container {
        max-height: 500px;
        overflow-y: auto;
        padding: 1rem;
        background-color: #f8f9fa;
        border-radius: 10px;
        margin-bottom: 1rem;
    }
    .user-message {
        background-color: #e3f2fd;
        padding: 0.5rem 1rem;
        margin: 0.5rem 0;
        border-radius: 15px;
        text-align: right;
    }
    .assistant-message {
        background-color: #f5f5f5;
        padding: 0.5rem 1rem;
        margin: 0.5rem 0;
        border-radius: 15px;
        text-align: left;
    }
    .emotion-display {
        background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 1rem 0;
    }
    .camera-container {
        border: 2px solid #ddd;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# 初始化 session state
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
    # AI 主動打招呼
    greeting_message = "您好！我是 AI 銷售助理，很高興為您服務。您可以詢問產品、安排會議，或上傳名片讓我更認識您！"
    st.session_state.chat_history.append(("", greeting_message))
    
if 'user_profile' not in st.session_state:
    st.session_state.user_profile = {}
if 'vision_agent' not in st.session_state:
    st.session_state.vision_agent = VisionAgent()
if 'current_emotion' not in st.session_state:
    st.session_state.current_emotion = None
if 'camera_active' not in st.session_state:
    st.session_state.camera_active = False
if 'current_camera_image' not in st.session_state:
    st.session_state.current_camera_image = None
if 'emotion_history' not in st.session_state:
    st.session_state.emotion_history = []

# 主標題
st.markdown("""
<div class="main-header">
    <h1>🤖 AI Sales 智能銷售助手</h1>
    <p>支援即時攝影機情緒分析的多代理人銷售系統</p>
</div>
""", unsafe_allow_html=True)

# 側邊欄
with st.sidebar:
    st.header("🔧 系統設定")
    
    # 互動模式選擇
    interaction_mode = st.selectbox(
        "互動模式",
        ["sales", "support", "consultation"],
        index=0,
        help="選擇 AI 助理的互動風格"
    )
    
    # 虛擬人與文字 UI 模式選擇
    st.subheader("🤖 回應模式")
    response_mode = st.selectbox(
        "回應模式",
        ["一般文字模式 (Chat)", "虛擬人模式 (Virtual Human)"],
        index=0,
        help="選擇 AI 的回應風格：一般模式提供詳細回答，虛擬人模式提供簡短互動"
    )
    
    # LLM 輸出參數控制
    st.subheader("📝 輸出參數")
    if "虛擬人" in response_mode:
        max_tokens = st.slider("回應長度 (字數)", 20, 200, 50, 10, help="虛擬人模式建議使用較短的回應")
        temperature = st.slider("回應創意度", 0.1, 1.0, 0.8, 0.1, help="虛擬人模式建議使用較高的創意度")
    else:
        max_tokens = st.slider("回應長度 (字數)", 100, 2000, 500, 50, help="一般模式可以使用較長的回應")
        temperature = st.slider("回應創意度", 0.1, 1.0, 0.7, 0.1, help="一般模式建議使用中等創意度")
    
    # 視覺分析設定
    st.subheader("👁️ 視覺分析")
    vision_enabled = st.checkbox("啟用情緒分析", value=True)
    emotion_sensitivity = st.slider("情緒敏感度", 0.1, 1.0, 0.7, 0.1)
    
    # 系統狀態
    st.subheader("📊 系統狀態")
    st.success("✅ 核心系統已載入")
    if st.session_state.camera_active:
        st.success("✅ 攝影機已啟動")
        # 顯示攝影機圖片狀態
        if 'current_camera_image' in st.session_state and st.session_state.current_camera_image:
            st.info(f"📸 攝影機圖片已保存 ({len(st.session_state.current_camera_image)} 字元)")
        else:
            st.warning("📸 尚未拍照")
    else:
        st.info("📷 攝影機待機中")
    
    # 當前設定顯示
    st.subheader("⚙️ 當前設定")
    st.write(f"**互動模式**: {interaction_mode}")
    st.write(f"**回應模式**: {response_mode}")
    st.write(f"**最大回應長度**: {max_tokens} 字")
    st.write(f"**創意度**: {temperature}")
    if vision_enabled:
        st.write(f"**情緒敏感度**: {emotion_sensitivity}")
    else:
        st.write("**情緒分析**: 已停用")
    
    # 用戶檔案
    st.subheader("👤 用戶檔案")
    if st.session_state.user_profile:
        for key, value in st.session_state.user_profile.items():
            st.write(f"**{key}**: {value}")
    else:
        st.write("尚未建立用戶檔案")

# 主要內容區域
col1, col2 = st.columns([2, 1])

with col1:
    st.header("💬 對話區域")
    
    # 聊天歷史顯示
    chat_container = st.container()
    with chat_container:
        for i, (user_msg, assistant_msg) in enumerate(st.session_state.chat_history):
            if user_msg:
                st.markdown(f'<div class="user-message">👤 {user_msg}</div>', unsafe_allow_html=True)
            if assistant_msg:
                st.markdown(f'<div class="assistant-message">🤖 {assistant_msg}</div>', unsafe_allow_html=True)
    
    # 輸入區域
    st.subheader("✍️ 輸入訊息")
    
    # 使用表單來處理輸入
    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_input("請輸入您的問題...", key="user_message")
        submitted = st.form_submit_button("💬 發送訊息", type="primary")
        
        if submitted and user_input:
            # 處理用戶訊息
            with st.spinner("AI 正在思考..."):
                try:
                    # 檢查是否有攝影機圖片
                    camera_image = None
                    if st.session_state.camera_active and 'current_camera_image' in st.session_state:
                        camera_image = st.session_state.current_camera_image
                        logger.info(f"使用攝影機圖片，長度: {len(camera_image) if camera_image else 0}")
                    
                    # 添加更多debug信息
                    logger.info(f"攝影機狀態: {st.session_state.camera_active}")
                    logger.info(f"攝影機圖片存在: {'current_camera_image' in st.session_state}")
                    logger.info(f"攝影機圖片內容: {camera_image is not None}")
                    
                    # 確定模式參數
                    mode = "virtual_human" if "虛擬人" in response_mode else "chat"
                    
                    # 使用統一的核心處理函數
                    response_text, updated_profile = safe_run_async(process_user_request(
                        message=user_input,
                        image=camera_image,
                        user_profile=st.session_state.user_profile,
                        interaction_mode=interaction_mode,
                        session_id="streamlit_session",
                        response_mode=mode,
                        max_tokens=max_tokens,
                        temperature=temperature
                    ))
                    
                    # 更新聊天歷史
                    st.session_state.chat_history.append((user_input, response_text))
                    
                    # 更新用戶檔案
                    st.session_state.user_profile = updated_profile
                    
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"處理訊息時出錯: {e}")
                    logger.error(f"Message processing error: {e}")
    
    # 按鈕區域
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        if st.button("🗑️ 清除對話"):
            st.session_state.chat_history = []
            st.session_state.user_profile = {}
            # 重新添加打招呼訊息
            greeting_message = "您好！我是 AI 銷售助理，很高興為您服務。您可以詢問產品、安排會議，或上傳名片讓我更認識您！"
            st.session_state.chat_history.append(("", greeting_message))
            st.rerun()
    
    with col_btn2:
        if st.button("📋 匯出對話"):
            if st.session_state.chat_history:
                export_data = {
                    "timestamp": datetime.now().isoformat(),
                    "chat_history": st.session_state.chat_history,
                    "user_profile": st.session_state.user_profile,
                    "emotion_history": st.session_state.emotion_history
                }
                st.download_button(
                    label="下載 JSON",
                    data=json.dumps(export_data, ensure_ascii=False, indent=2),
                    file_name=f"chat_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )

with col2:
    st.header("👁️ 視覺分析")
    
    # 攝影機控制
    st.subheader("📷 攝影機控制")
    
    # 攝影機啟動按鈕
    if not st.session_state.camera_active:
        if st.button("📹 啟動攝影機", type="primary"):
            st.session_state.camera_active = True
            st.success("攝影機已啟動！")
            st.rerun()
    else:
        if st.button("⏹️ 停止攝影機", type="secondary"):
            st.session_state.camera_active = False
            st.session_state.current_emotion = None
            st.info("攝影機已停止")
            st.rerun()
    
    # 攝影機畫面
    camera_placeholder = st.empty()
    
    # 情緒顯示
    emotion_placeholder = st.empty()
    
    # 圖片上傳
    st.subheader("📸 圖片上傳")
    uploaded_file = st.file_uploader(
        "上傳名片或圖片",
        type=['png', 'jpg', 'jpeg'],
        help="支援 PNG、JPG、JPEG 格式"
    )
    
    if uploaded_file is not None:
        # 顯示上傳的圖片
        image = Image.open(uploaded_file)
        st.image(image, caption="上傳的圖片", use_column_width=True)
        
        # 處理圖片
        if st.button("🔍 分析圖片"):
            with st.spinner("正在分析圖片..."):
                try:
                    # 確定模式參數
                    mode = "virtual_human" if "虛擬人" in response_mode else "chat"
                    
                    # 使用統一的核心處理函數
                    response_text, updated_profile = safe_run_async(process_user_request(
                        message="",
                        image=image,  # 直接傳遞 PIL Image
                        user_profile=st.session_state.user_profile,
                        interaction_mode=interaction_mode,
                        session_id="streamlit_session",
                        response_mode=mode,
                        max_tokens=max_tokens,
                        temperature=temperature
                    ))
                    
                    # 更新聊天歷史
                    st.session_state.chat_history.append(("(圖片分析)", response_text))
                    
                    # 更新用戶檔案
                    st.session_state.user_profile = updated_profile
                    
                    st.success("圖片分析完成！")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"圖片分析失敗: {e}")
                    logger.error(f"Image analysis error: {e}")

# 攝影機處理函數
def process_camera():
    """處理攝影機畫面和情緒分析"""
    if not st.session_state.camera_active or not vision_enabled:
        return
    
    try:
        # 使用 Streamlit 的攝影機輸入
        camera_input = st.camera_input("攝影機畫面", key="camera")
        
        if camera_input is not None:
            # 轉換圖片格式
            image = Image.open(camera_input)
            
            # 儲存攝影機圖片供聊天系統使用
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            st.session_state.current_camera_image = img_str
            logger.info(f"攝影機圖片已保存，長度: {len(img_str)}")
            
            # 進行情緒分析
            try:
                # 使用 VisionAgent 分析情緒
                emotion_result = safe_run_async(
                    st.session_state.vision_agent.analyze_emotion(img_str)
                )
                
                logger.info(f"情緒分析結果: {emotion_result}")
                
                if emotion_result:
                    st.session_state.current_emotion = emotion_result
                    st.session_state.emotion_history.append({
                        "timestamp": datetime.now().isoformat(),
                        "emotion": emotion_result
                    })
                    
                    # 顯示情緒分析結果
                    with emotion_placeholder.container():
                        emotion_data = emotion_result
                        st.markdown(f"""
                        <div class="emotion-display">
                            <h3>當前情緒: {emotion_data.get('emotion', 'Unknown')}</h3>
                            <p>信心度: {emotion_data.get('confidence', 0):.2f}</p>
                            <p>建議: {emotion_data.get('suggestion', '')}</p>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.warning("未能分析出情緒")
                        
            except Exception as e:
                logger.error(f"Emotion analysis error: {e}")
                st.error(f"情緒分析失敗: {e}")
                
    except Exception as e:
        logger.error(f"Camera processing error: {e}")
        st.error(f"攝影機處理失敗: {e}")

# 攝影機處理
if st.session_state.camera_active and vision_enabled:
    with camera_placeholder:
        process_camera()

# 情緒歷史
if st.session_state.emotion_history:
    with st.expander("📊 情緒歷史"):
        for record in st.session_state.emotion_history[-10:]:  # 顯示最近10筆
            st.write(f"**{record['timestamp']}**: {record['emotion'].get('emotion', 'Unknown')} ({record['emotion'].get('confidence', 0):.2f})")

# 頁腳
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; margin-top: 2rem;">
    <p>🤖 AI Sales 智能銷售助手 v2.0 | 支援即時情緒分析</p>
    <p>Built with Streamlit | © 2024 C360 Company</p>
</div>
""", unsafe_allow_html=True)
