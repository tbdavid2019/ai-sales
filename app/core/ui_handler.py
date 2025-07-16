"""
統一的核心處理邏輯
供 Gradio 和 Streamlit 版本共同使用
"""
import base64
import io
import logging
from typing import Dict, Any, Optional, Tuple
from PIL import Image

logger = logging.getLogger(__name__)

async def process_user_request(
    message: str,
    image: Optional[Any],
    user_profile: Dict[str, Any],
    interaction_mode: str,
    session_id: str = "default_session"
) -> Tuple[str, Dict[str, Any]]:
    """
    統一處理用戶請求的核心函數
    
    Args:
        message: 用戶文字訊息
        image: 圖片 (PIL Image 或 base64 字串)
        user_profile: 用戶檔案
        interaction_mode: 互動模式 (sales, support, consultation)
        session_id: 會話ID
        
    Returns:
        Tuple[回應內容, 更新後的用戶檔案]
    """
    # 延遲匯入避免循環依賴
    from app.core.workflow import workflow_manager
    
    # 1. 處理圖片
    image_data = None
    if image:
        try:
            if isinstance(image, str):
                # 已經是 base64 字串
                image_data = image
            else:
                # PIL Image，需要轉換
                buffer = io.BytesIO()
                image.save(buffer, format='JPEG')
                image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
            logger.info("圖片已成功轉換為 base64")
        except Exception as e:
            logger.error(f"圖片處理失敗: {e}")
            return "圖片處理失敗，請重新上傳。", user_profile

    # 2. 準備工作流輸入
    has_image = image is not None and image_data is not None
    workflow_input = {
        "user_input": message,
        "session_id": session_id,
        "has_image": has_image,
        "image_data": image_data,
        "user_profile": user_profile,
        "interaction_mode": interaction_mode
    }
    logger.info(f"工作流輸入: user_input='{message}', has_image={has_image}, session_id={session_id}")
    if has_image:
        logger.info(f"偵測到圖片，image_data 長度: {len(image_data) if image_data else 0}")
    else:
        logger.info(f"未偵測到圖片，image 是否為 None: {image is None}, image_data 是否為 None: {image_data is None}")

    # 3. 執行工作流
    response_content = "系統發生未預期的錯誤，請稍後再試。"
    updated_profile = user_profile.copy()

    try:
        result = await workflow_manager.execute_workflow(workflow_input)
        if result.success:
            response_content = result.content
            
            # 從 agent_results 中提取用戶檔案更新
            if hasattr(result, 'agent_results') and result.agent_results:
                for agent_name, agent_result in result.agent_results.items():
                    if isinstance(agent_result, dict) and 'metadata' in agent_result:
                        metadata = agent_result['metadata']
                        if 'updated_user_profile' in metadata:
                            updated_profile.update(metadata['updated_user_profile'])
                            logger.info(f"從 {agent_name} 更新用戶檔案: {metadata['updated_user_profile']}")
            
            # 檢查 metadata 中是否有用戶檔案更新
            if hasattr(result, 'metadata') and result.metadata:
                if 'updated_user_profile' in result.metadata:
                    updated_profile.update(result.metadata['updated_user_profile'])
                    logger.info(f"從 workflow metadata 更新用戶檔案: {result.metadata['updated_user_profile']}")
        else:
            response_content = f"處理時發生錯誤: {result.content}"
            logger.error(f"工作流執行失敗: {result.content}")
    except Exception as e:
        logger.error(f"執行工作流時發生未預期錯誤: {e}", exc_info=True)
        response_content = "系統暫時無法處理您的請求，請稍後再試。"

    return response_content, updated_profile
