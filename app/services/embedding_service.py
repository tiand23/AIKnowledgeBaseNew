"""
向量化服务 - 使用OpenAI API生成文本向量
"""
from typing import List, Optional
import asyncio
from openai import AsyncOpenAI
from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_EMBEDDING_MODEL
        self.dimensions = settings.OPENAI_EMBEDDING_DIMENSIONS
    
    async def embed_text(self, text: str) -> Optional[List[float]]:
        """
        将单个文本转换为向量
        
        Args:
            text: 要向量化的文本
            
        Returns:
            向量列表（1536维），失败返回None
        """
        if not text or not text.strip():
            logger.warning("空文本，无法向量化")
            return None
        
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text.strip(),
                dimensions=self.dimensions
            )
            
            vector = response.data[0].embedding
            logger.debug(f"文本向量化成功，维度: {len(vector)}")
            return vector
            
        except Exception as e:
            logger.error(f"文本向量化失败: {e}", exc_info=True)
            return None
    
    async def embed_batch(self, texts: List[str], batch_size: int = 100) -> List[Optional[List[float]]]:
        """
        批量向量化文本
        
        Args:
            texts: 文本列表
            batch_size: 批次大小（OpenAI API限制最多2048个文本/请求）
            
        Returns:
            向量列表，每个元素对应一个文本的向量（失败则为None）
        """
        if not texts:
            return []
        
        results = []
        total = len(texts)
        
        for i in range(0, total, batch_size):
            batch = texts[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total + batch_size - 1) // batch_size
            
            logger.debug(f"处理批次 {batch_num}/{total_batches}，包含 {len(batch)} 个文本")
            
            try:
                valid_texts = [t.strip() for t in batch if t and t.strip()]
                if not valid_texts:
                    results.extend([None] * len(batch))
                    continue
                
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=valid_texts,
                    dimensions=self.dimensions
                )
                
                valid_results = {item.index: item.embedding for item in response.data}
                
                batch_results = []
                valid_idx = 0
                for text in batch:
                    if text and text.strip():
                        batch_results.append(valid_results.get(valid_idx))
                        valid_idx += 1
                    else:
                        batch_results.append(None)
                
                results.extend(batch_results)
                
            except Exception as e:
                logger.error(f"批量向量化失败（批次 {batch_num}）: {e}", exc_info=True)
                results.extend([None] * len(batch))
            
            if i + batch_size < total:
                await asyncio.sleep(0.1)
        
        success_count = sum(1 for r in results if r is not None)
        logger.info(f"批量向量化完成: 成功 {success_count}/{total}")
        
        return results
    
    async def embed_query(self, query: str) -> Optional[List[float]]:
        """
        向量化查询文本（用于检索）
        
        Args:
            query: 查询文本
            
        Returns:
            查询向量，失败返回None
        """
        if not query or not query.strip():
            logger.warning("查询文本为空")
            return None
        
        return await self.embed_text(query)


embedding_service = EmbeddingService()

