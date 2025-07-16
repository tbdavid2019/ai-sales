"""
PDF 文檔處理和向量化腳本
"""

import os
import asyncio
from typing import List, Dict, Any
from pathlib import Path
import hashlib
from datetime import datetime

try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

from app.core.vector_db import vector_db
from app.core.logger import logger


class PDFProcessor:
    """PDF 文檔處理器"""
    
    def __init__(self):
        self.pdf_folder = Path("./documents")
        self.processed_folder = Path("./documents/processed")
        self.chunk_size = 1000  # 每個文檔塊的字符數
        self.chunk_overlap = 200  # 重疊字符數
        
        # 創建資料夾
        self.pdf_folder.mkdir(exist_ok=True)
        self.processed_folder.mkdir(exist_ok=True)
    
    async def process_all_pdfs(self) -> bool:
        """處理所有 PDF 文檔"""
        try:
            pdf_files = list(self.pdf_folder.glob("*.pdf"))
            
            if not pdf_files:
                logger.info("未找到 PDF 文檔")
                return True
            
            logger.info(f"找到 {len(pdf_files)} 個 PDF 文檔")
            
            all_documents = []
            
            for pdf_file in pdf_files:
                # 檢查是否已處理
                if self._is_processed(pdf_file):
                    logger.info(f"跳過已處理的文檔: {pdf_file.name}")
                    continue
                
                logger.info(f"正在處理: {pdf_file.name}")
                
                # 提取文字
                text = await self._extract_text_from_pdf(pdf_file)
                if not text:
                    logger.warning(f"無法提取文字: {pdf_file.name}")
                    continue
                
                # 分塊處理
                chunks = self._split_text_into_chunks(text)
                
                # 轉換為文檔格式
                documents = self._create_documents(chunks, pdf_file)
                all_documents.extend(documents)
                
                # 標記為已處理
                self._mark_as_processed(pdf_file)
                
                logger.info(f"完成處理: {pdf_file.name} -> {len(documents)} 個文檔塊")
            
            # 批量新增到向量資料庫
            if all_documents:
                success = await vector_db.add_documents(all_documents)
                if success:
                    logger.info(f"成功新增 {len(all_documents)} 個文檔到向量資料庫")
                else:
                    logger.error("新增文檔到向量資料庫失敗")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"處理 PDF 失敗: {e}")
            return False
    
    async def _extract_text_from_pdf(self, pdf_path: Path) -> str:
        """從 PDF 提取文字"""
        try:
            text = ""
            
            # 優先使用 PyMuPDF (更好的文字提取)
            if HAS_PYMUPDF:
                text = await self._extract_with_pymupdf(pdf_path)
            elif HAS_PYPDF2:
                text = await self._extract_with_pypdf2(pdf_path)
            else:
                logger.error("沒有安裝 PDF 處理庫 (PyMuPDF 或 PyPDF2)")
                return ""
            
            # 清理文字
            text = self._clean_text(text)
            
            return text
            
        except Exception as e:
            logger.error(f"提取 PDF 文字失敗: {e}")
            return ""
    
    async def _extract_with_pymupdf(self, pdf_path: Path) -> str:
        """使用 PyMuPDF 提取文字"""
        try:
            doc = fitz.open(str(pdf_path))
            text = ""
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text += page.get_text()
            
            doc.close()
            return text
            
        except Exception as e:
            logger.error(f"PyMuPDF 提取失敗: {e}")
            return ""
    
    async def _extract_with_pypdf2(self, pdf_path: Path) -> str:
        """使用 PyPDF2 提取文字"""
        try:
            text = ""
            
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text += page.extract_text()
            
            return text
            
        except Exception as e:
            logger.error(f"PyPDF2 提取失敗: {e}")
            return ""
    
    def _clean_text(self, text: str) -> str:
        """清理文字"""
        # 移除多餘的空白字符
        text = ' '.join(text.split())
        
        # 移除特殊字符
        text = text.replace('\x00', '')
        
        return text.strip()
    
    def _split_text_into_chunks(self, text: str) -> List[str]:
        """將文字分塊"""
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            # 如果不是最後一塊，尋找合適的分割點
            if end < len(text):
                # 尋找最近的句號或換行
                for i in range(end, start, -1):
                    if text[i] in '.。\n':
                        end = i + 1
                        break
            
            chunk = text[start:end]
            chunks.append(chunk)
            
            # 下一塊的開始位置 (考慮重疊)
            start = end - self.chunk_overlap
            
        return chunks
    
    def _create_documents(self, chunks: List[str], pdf_file: Path) -> List[Dict[str, Any]]:
        """創建文檔對象"""
        documents = []
        
        for i, chunk in enumerate(chunks):
            document = {
                "id": f"{pdf_file.stem}_{i}",
                "content": chunk,
                "source": pdf_file.name,
                "title": pdf_file.stem,
                "category": self._determine_category(pdf_file.name),
                "created_at": datetime.now().isoformat(),
                "chunk_index": i,
                "total_chunks": len(chunks)
            }
            documents.append(document)
        
        return documents
    
    def _determine_category(self, filename: str) -> str:
        """根據檔案名稱確定類別"""
        filename_lower = filename.lower()
        
        if any(keyword in filename_lower for keyword in ['product', '產品', 'feature', '功能']):
            return "product"
        elif any(keyword in filename_lower for keyword in ['price', '價格', 'pricing', '定價']):
            return "pricing"
        elif any(keyword in filename_lower for keyword in ['manual', '手冊', 'guide', '指南']):
            return "manual"
        elif any(keyword in filename_lower for keyword in ['faq', '常見問題', 'qa']):
            return "faq"
        else:
            return "general"
    
    def _get_file_hash(self, pdf_file: Path) -> str:
        """獲取文檔的 hash 值"""
        with open(pdf_file, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def _is_processed(self, pdf_file: Path) -> bool:
        """檢查文檔是否已處理"""
        hash_file = self.processed_folder / f"{pdf_file.stem}.hash"
        
        if not hash_file.exists():
            return False
        
        # 比較 hash 值
        current_hash = self._get_file_hash(pdf_file)
        with open(hash_file, 'r') as f:
            stored_hash = f.read().strip()
        
        return current_hash == stored_hash
    
    def _mark_as_processed(self, pdf_file: Path):
        """標記文檔為已處理"""
        hash_file = self.processed_folder / f"{pdf_file.stem}.hash"
        current_hash = self._get_file_hash(pdf_file)
        
        with open(hash_file, 'w') as f:
            f.write(current_hash)
    
    async def reprocess_all(self) -> bool:
        """重新處理所有文檔"""
        logger.info("清理處理記錄...")
        
        # 清空處理記錄
        for hash_file in self.processed_folder.glob("*.hash"):
            hash_file.unlink()
        
        # 重新處理
        return await self.process_all_pdfs()


# 創建全域實例
pdf_processor = PDFProcessor()


async def main():
    """主函數"""
    print("📚 PDF 文檔處理器")
    print("=" * 50)
    
    # 顯示說明
    print(f"📁 PDF 文檔資料夾: {pdf_processor.pdf_folder}")
    print(f"📊 處理記錄資料夾: {pdf_processor.processed_folder}")
    print(f"📏 文檔塊大小: {pdf_processor.chunk_size} 字符")
    print(f"🔄 重疊大小: {pdf_processor.chunk_overlap} 字符")
    print()
    
    # 檢查依賴
    if not HAS_PYMUPDF and not HAS_PYPDF2:
        print("❌ 錯誤：沒有安裝 PDF 處理庫")
        print("請安裝：pip install PyMuPDF 或 pip install PyPDF2")
        return
    
    pdf_lib = "PyMuPDF" if HAS_PYMUPDF else "PyPDF2"
    print(f"📖 使用 PDF 庫: {pdf_lib}")
    print()
    
    # 處理文檔
    success = await pdf_processor.process_all_pdfs()
    
    if success:
        print("✅ PDF 處理完成")
    else:
        print("❌ PDF 處理失敗")


if __name__ == "__main__":
    asyncio.run(main())
