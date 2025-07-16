from typing import List, Dict, Any, Optional
import chromadb
from app.config import settings
from app.models import EmbeddingFactory


class VectorDatabase:
    """向量資料庫管理類別"""
    
    def __init__(self):
        self.client = None
        self.collection = None
        self.embedding_model = EmbeddingFactory.get_default_embedding()
        self._init_client()
    
    def _init_client(self):
        """初始化 ChromaDB 客戶端"""
        try:
            if settings.vector_db_type == "chromadb":
                # 設定 ChromaDB 客戶端
                self.client = chromadb.HttpClient(
                    host=settings.chroma_host,
                    port=settings.chroma_port
                )
                
                # 獲取或創建集合
                try:
                    self.collection = self.client.get_collection(
                        name=settings.chroma_collection_name
                    )
                    print(f"✅ 成功連接到現有集合: {settings.chroma_collection_name}")
                except Exception:
                    # 如果集合不存在，創建新的
                    self.collection = self.client.create_collection(
                        name=settings.chroma_collection_name,
                        metadata={"description": "AI Sales knowledge base"}
                    )
                    print(f"✅ 成功創建新集合: {settings.chroma_collection_name}")
                    
            else:
                raise ValueError(f"不支援的向量資料庫類型: {settings.vector_db_type}")
                
        except Exception as e:
            print(f"❌ 向量資料庫初始化失敗: {e}")
            self.client = None
            self.collection = None
    
    async def add_documents(self, documents: List[Dict[str, Any]]) -> bool:
        """新增文檔到向量資料庫"""
        try:
            if not self.collection:
                print("❌ 向量資料庫未初始化")
                return False
            
            # 準備資料
            texts = []
            metadatas = []
            ids = []
            
            for i, doc in enumerate(documents):
                texts.append(doc["content"])
                metadatas.append({
                    "source": doc.get("source", "unknown"),
                    "title": doc.get("title", ""),
                    "category": doc.get("category", "general"),
                    "created_at": doc.get("created_at", ""),
                })
                ids.append(doc.get("id", f"doc_{i}"))
            
            # 生成嵌入向量
            embeddings = await self._generate_embeddings(texts)
            
            # 新增到 ChromaDB
            self.collection.add(
                documents=texts,
                metadatas=metadatas,
                ids=ids,
                embeddings=embeddings
            )
            
            print(f"✅ 成功新增 {len(documents)} 個文檔到向量資料庫")
            return True
            
        except Exception as e:
            print(f"❌ 新增文檔失敗: {e}")
            return False
    
    async def search_similar(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """搜索相似文檔"""
        try:
            if not self.collection:
                print("❌ 向量資料庫未初始化")
                return []
            
            # 生成查詢向量
            query_embedding = await self._generate_embeddings([query])
            
            # 執行搜索
            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=top_k,
                include=["documents", "metadatas", "distances"]
            )
            
            # 格式化結果
            documents = []
            if results["documents"] and len(results["documents"]) > 0:
                for i, doc in enumerate(results["documents"][0]):
                    documents.append({
                        "content": doc,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "score": 1 - results["distances"][0][i] if results["distances"] else 0,  # 轉換為相似度分數
                        "source": results["metadatas"][0][i].get("source", "") if results["metadatas"] else ""
                    })
            
            print(f"✅ 搜索到 {len(documents)} 個相關文檔")
            return documents
            
        except Exception as e:
            print(f"❌ 搜索失敗: {e}")
            return []
    
    async def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """生成文本嵌入向量"""
        try:
            # 使用 LangChain 的嵌入模型
            embeddings = await self.embedding_model.aembed_documents(texts)
            return embeddings
        except Exception as e:
            print(f"❌ 生成嵌入向量失敗: {e}")
            # 返回零向量作為後備方案
            return [[0.0] * 1536 for _ in texts]  # OpenAI embedding 維度為 1536
    
    def get_collection_info(self) -> Dict[str, Any]:
        """獲取集合資訊"""
        try:
            if not self.collection:
                return {"error": "向量資料庫未初始化"}
            
            count = self.collection.count()
            return {
                "collection_name": settings.chroma_collection_name,
                "document_count": count,
                "status": "active"
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def delete_documents(self, ids: List[str]) -> bool:
        """刪除文檔"""
        try:
            if not self.collection:
                return False
            
            self.collection.delete(ids=ids)
            print(f"✅ 成功刪除 {len(ids)} 個文檔")
            return True
            
        except Exception as e:
            print(f"❌ 刪除文檔失敗: {e}")
            return False
    
    async def update_document(self, doc_id: str, content: str, metadata: Dict[str, Any]) -> bool:
        """更新文檔"""
        try:
            if not self.collection:
                return False
            
            # ChromaDB 的更新方式是先刪除再新增
            await self.delete_documents([doc_id])
            
            documents = [{
                "id": doc_id,
                "content": content,
                **metadata
            }]
            
            return await self.add_documents(documents)
            
        except Exception as e:
            print(f"❌ 更新文檔失敗: {e}")
            return False


# 全域向量資料庫實例
vector_db = VectorDatabase()
