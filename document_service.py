"""
自動化文檔處理服務
定期掃描和處理新的 PDF 文檔
"""

import asyncio
import schedule
import time
from pathlib import Path
from datetime import datetime
from app.core.logger import logger
from process_pdfs import pdf_processor


class DocumentProcessingService:
    """文檔處理服務"""
    
    def __init__(self):
        self.is_running = False
        self.last_check = None
    
    async def run_processing(self):
        """執行文檔處理"""
        if self.is_running:
            logger.info("文檔處理已在執行中，跳過本次")
            return
        
        self.is_running = True
        
        try:
            logger.info("開始定期文檔處理...")
            
            # 處理 PDF 文檔
            success = await pdf_processor.process_all_pdfs()
            
            if success:
                logger.info("定期文檔處理完成")
            else:
                logger.error("定期文檔處理失敗")
            
            self.last_check = datetime.now()
            
        except Exception as e:
            logger.error(f"文檔處理服務錯誤: {e}")
        finally:
            self.is_running = False
    
    def start_scheduler(self):
        """啟動排程器"""
        # 每小時檢查一次新文檔
        schedule.every().hour.do(
            lambda: asyncio.create_task(self.run_processing())
        )
        
        # 每天午夜重新處理所有文檔
        schedule.every().day.at("00:00").do(
            lambda: asyncio.create_task(pdf_processor.reprocess_all())
        )
        
        logger.info("文檔處理排程器已啟動")
        logger.info("- 每小時檢查新文檔")
        logger.info("- 每天午夜重新處理所有文檔")
        
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分鐘檢查一次排程


# 創建服務實例
document_service = DocumentProcessingService()


async def main():
    """主函數"""
    print("📚 文檔處理服務")
    print("=" * 50)
    
    # 初始處理
    await document_service.run_processing()
    
    # 啟動排程器
    print("🔄 啟動定期處理服務...")
    document_service.start_scheduler()


if __name__ == "__main__":
    asyncio.run(main())
