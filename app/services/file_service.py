"""
文件服务层
"""
import hashlib
import json
import asyncio
from typing import Optional, List, Tuple
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import OperationalError, IntegrityError
from fastapi import HTTPException, status
from app.models.file import (
    FileUpload, ChunkInfo, DocumentVector,
    FILE_STATUS_UPLOADING, FILE_STATUS_MERGED, FILE_STATUS_FAILED
)
from app.models.user import User, UserRole
from app.clients.minio_client import minio_client
from app.clients.redis_client import redis_client
from app.clients.kafka_client import kafka_client
from app.clients.elasticsearch_client import es_client
from app.core.config import settings
from app.utils.logger import get_logger
from app.services.permission_service import permission_service

logger = get_logger(__name__)


class FileService:

    @staticmethod
    async def _commit_with_sqlite_retry(
        db: AsyncSession,
        retries: int = 5,
        base_delay: float = 0.2,
    ) -> None:
        """
        SQLite 写锁重试：处理偶发 `database is locked`。
        """
        for attempt in range(1, retries + 1):
            try:
                await db.commit()
                return
            except OperationalError as e:
                message = str(e).lower()
                is_locked = "database is locked" in message
                if not is_locked or attempt >= retries:
                    raise
                await db.rollback()
                await asyncio.sleep(base_delay * attempt)

    @staticmethod
    def calculate_md5(data: bytes) -> str:
        return hashlib.md5(data).hexdigest()

    @staticmethod
    def get_redis_chunk_key(file_md5: str) -> str:
        return f"upload:chunks:{file_md5}"

    @staticmethod
    def get_redis_meta_key(file_md5: str) -> str:
        return f"upload:meta:{file_md5}"

    async def upload_chunk(
        self,
        db: AsyncSession,
        user: User,
        file_md5: str,
        chunk_index: int,
        chunk_data: bytes,
        file_name: str,
        total_size: int,
        total_chunks: Optional[int] = None,
        org_tag: Optional[str] = None,
        is_public: bool = False,
        kb_profile: str = "general",
    ) -> Tuple[List[int], float]:
        """
        上传文件分片
        
        Returns:
            Tuple[List[int], float]: (已上传分片索引列表, 上传进度百分比)
        """
        if chunk_index < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="chunk_index must be >= 0"
            )
        if total_chunks is not None:
            if total_chunks <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="total_chunks must be > 0"
                )
            if chunk_index >= total_chunks:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="chunk_index must be less than total_chunks"
                )

        chunk_md5 = self.calculate_md5(chunk_data)
        
        redis_key = self.get_redis_chunk_key(file_md5)
        is_uploaded = await redis_client.get_bit(redis_key, chunk_index)
        
        existing_chunk_result = await db.execute(
            select(ChunkInfo).where(
                and_(
                    ChunkInfo.file_md5 == file_md5,
                    ChunkInfo.chunk_index == chunk_index
                )
            )
        )
        existing_chunk = existing_chunk_result.scalar_one_or_none()
        
        if is_uploaded == 1 and existing_chunk:
            chunk_path = existing_chunk.storage_path
            if minio_client.file_exists(settings.MINIO_DEFAULT_BUCKET, chunk_path):
                logger.info(f"分片 {chunk_index} 已存在（Redis+DB+MinIO），跳过上传: {file_md5}")
            else:
                logger.warning(f"分片 {chunk_index} 在Redis和DB中存在，但MinIO中不存在，重新上传: {file_md5}")
                chunk_path = minio_client.build_temp_chunk_path(file_md5, chunk_index)
                success = minio_client.upload_bytes(
                    bucket_name=settings.MINIO_DEFAULT_BUCKET,
                    object_name=chunk_path,
                    data=chunk_data
                )
                if not success:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"分片重新上传失败: {file_md5}/{chunk_index}"
                    )
                if existing_chunk.storage_path != chunk_path:
                    existing_chunk.storage_path = chunk_path
                    await db.commit()
                logger.info(f"分片 {chunk_index} 重新上传成功: {file_md5}")
        else:
            if is_uploaded == 1 and not existing_chunk:
                logger.warning(f"分片 {chunk_index} 在Redis中但不在数据库中，尝试修复: {file_md5}")
                chunk_path = minio_client.build_temp_chunk_path(file_md5, chunk_index)
                if not minio_client.file_exists(settings.MINIO_DEFAULT_BUCKET, chunk_path):
                    logger.warning(f"分片 {chunk_index} 在MinIO中也不存在，需要重新上传: {file_md5}")
                    chunk_path = minio_client.build_temp_chunk_path(file_md5, chunk_index)
                    success = minio_client.upload_bytes(
                        bucket_name=settings.MINIO_DEFAULT_BUCKET,
                        object_name=chunk_path,
                        data=chunk_data
                    )
                    if not success:
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"分片上传失败: {file_md5}/{chunk_index}"
                        )
                    await redis_client.set_bit(redis_key, chunk_index, 1)
            else:
                chunk_path = minio_client.build_temp_chunk_path(file_md5, chunk_index)
                success = minio_client.upload_bytes(
                    bucket_name=settings.MINIO_DEFAULT_BUCKET,
                    object_name=chunk_path,
                    data=chunk_data
                )
                
                if not success:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"分片上传失败: {file_md5}/{chunk_index}"
                    )
                
                if not minio_client.file_exists(settings.MINIO_DEFAULT_BUCKET, chunk_path):
                    logger.error(f"分片 {chunk_index} 上传返回成功，但MinIO中不存在，尝试重新上传: {file_md5}")
                    retry_success = minio_client.upload_bytes(
                        bucket_name=settings.MINIO_DEFAULT_BUCKET,
                        object_name=chunk_path,
                        data=chunk_data
                    )
                    if not retry_success or not minio_client.file_exists(settings.MINIO_DEFAULT_BUCKET, chunk_path):
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"分片上传验证失败: {file_md5}/{chunk_index}"
                        )
                    logger.info(f"分片 {chunk_index} 重新上传成功: {file_md5}")
                
                try:
                    await redis_client.set_bit(redis_key, chunk_index, 1)
                except Exception as e:
                    logger.warning(f"Redis更新失败: {e}，将在查询时修复")
            
            if not existing_chunk:
                chunk_info = ChunkInfo(
                    file_md5=file_md5,
                    chunk_index=chunk_index,
                    chunk_md5=chunk_md5,
                    storage_path=chunk_path
                )
                db.add(chunk_info)
        
        file_upload_result = await db.execute(
            select(FileUpload).where(
                and_(
                    FileUpload.file_md5 == file_md5,
                    FileUpload.user_id == user.id
                )
            )
        )
        file_record = file_upload_result.scalar_one_or_none()
        
        if not file_record:
            default_org_tag = org_tag or user.primary_org
            
            file_record = FileUpload(
                file_md5=file_md5,
                file_name=file_name,
                total_size=total_size,
                status=FILE_STATUS_UPLOADING,  # Upload in progress
                user_id=user.id,
                org_tag=default_org_tag,
                is_public=is_public,
                kb_profile=kb_profile,
            )
            db.add(file_record)
            
        else:
            if org_tag:
                file_record.org_tag = org_tag
            if is_public is not None:
                file_record.is_public = is_public
            if kb_profile:
                file_record.kb_profile = kb_profile
        
        meta_key = self.get_redis_meta_key(file_md5)
        known_total_chunks = total_chunks
        try:
            old_meta_raw = await redis_client.get(meta_key)
            if old_meta_raw:
                old_meta = json.loads(old_meta_raw)
                old_total = int(old_meta.get("total_chunks") or 0)
                if old_total > 0:
                    known_total_chunks = max(int(total_chunks or 0), old_total) or old_total
        except Exception:
            pass
        meta_data = {
            "file_md5": file_md5,
            "file_name": file_name,
            "total_size": total_size,
            "total_chunks": known_total_chunks,
            "user_id": user.id
        }
        try:
            await redis_client.set(meta_key, json.dumps(meta_data), expire=3600 * 24)  # 24-hour TTL
        except Exception as e:
            logger.warning(f"Redis元数据保存失败: {e}")

        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            logger.warning(f"分片并发写入冲突，按幂等成功处理: file_md5={file_md5}, chunk={chunk_index}, err={e}")
        except Exception as e:
            await db.rollback()
            logger.error(f"数据库提交失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"数据库写入失败: {str(e)}"
            )
        
        uploaded_chunks = await self.get_uploaded_chunks(file_md5, total_chunks or 0)
        progress = await redis_client.get_bitmap_progress(redis_key, total_chunks or 0)
        
        return uploaded_chunks, progress * 100

    async def get_uploaded_chunks(self, file_md5: str, total_chunks: int) -> List[int]:
        if total_chunks <= 0:
            return []
        
        redis_key = self.get_redis_chunk_key(file_md5)
        uploaded = []
        
        for i in range(total_chunks):
            if await redis_client.get_bit(redis_key, i) == 1:
                uploaded.append(i)
        
        return uploaded

    async def get_upload_status(
        self,
        db: AsyncSession,
        user: User,
        file_md5: str
    ) -> Tuple[List[int], float, int]:
        """
        获取上传状态
        
        Returns:
            Tuple[List[int], float, int]: (已上传分片列表, 进度百分比, 总分片数)
        """
        file_upload_result = await db.execute(
            select(FileUpload).where(
                and_(
                    FileUpload.file_md5 == file_md5,
                    FileUpload.user_id == user.id
                )
            )
        )
        file_record = file_upload_result.scalar_one_or_none()
        
        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Upload record not found"
            )
        
        chunks_result = await db.execute(
            select(ChunkInfo).where(ChunkInfo.file_md5 == file_md5)
        )
        chunks = chunks_result.scalars().all()
        total_chunks = 0
        meta_key = self.get_redis_meta_key(file_md5)
        try:
            meta_raw = await redis_client.get(meta_key)
            if meta_raw:
                meta = json.loads(meta_raw)
                total_chunks = int(meta.get("total_chunks") or 0)
        except Exception:
            total_chunks = 0
        if total_chunks <= 0 and chunks:
            total_chunks = max(int(c.chunk_index) for c in chunks) + 1
        
        redis_key = self.get_redis_chunk_key(file_md5)
        if not await redis_client.exists(redis_key) and chunks:
            logger.info(f"Redis状态丢失，从MySQL重建: {file_md5}")
            for chunk in chunks:
                await redis_client.set_bit(redis_key, chunk.chunk_index, 1)
        
        uploaded_chunks = await self.get_uploaded_chunks(file_md5, total_chunks)
        progress = await redis_client.get_bitmap_progress(redis_key, total_chunks)
        
        return uploaded_chunks, progress * 100, total_chunks

    async def merge_file(
        self,
        db: AsyncSession,
        user: User,
        file_md5: str,
        file_name: str
    ) -> Tuple[str, int]:
        """
        合并文件分片
        
        Returns:
            Tuple[str, int]: (文件访问URL, 文件大小)
        """
        file_upload_result = await db.execute(
            select(FileUpload).where(
                and_(
                    FileUpload.file_md5 == file_md5,
                    FileUpload.user_id == user.id
                )
            )
        )
        file_record = file_upload_result.scalar_one_or_none()
        
        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        chunks_result = await db.execute(
            select(ChunkInfo)
            .where(ChunkInfo.file_md5 == file_md5)
            .order_by(ChunkInfo.chunk_index)
        )
        chunks = chunks_result.scalars().all()
        
        if not chunks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No chunks found"
            )
        
        chunk_by_index = {}
        for chunk in chunks:
            idx = int(chunk.chunk_index)
            if idx < 0:
                continue
            if idx not in chunk_by_index:
                chunk_by_index[idx] = chunk

        if not chunk_by_index:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid chunks found"
            )

        total_chunks = max(chunk_by_index.keys()) + 1
        missing_db_chunks = [i for i in range(total_chunks) if i not in chunk_by_index]
        if missing_db_chunks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing chunk records: {missing_db_chunks[:10]}"
            )
        
        redis_key = self.get_redis_chunk_key(file_md5)
        if not await redis_client.exists(redis_key):
            for idx in chunk_by_index.keys():
                await redis_client.set_bit(redis_key, idx, 1)

        for i in range(total_chunks):
            if await redis_client.get_bit(redis_key, i) == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Not all chunks have been uploaded"
                )
        
        dest_path = minio_client.build_document_path(user.id, file_name)
        success = minio_client.merge_chunks(
            bucket_name=settings.MINIO_DEFAULT_BUCKET,
            file_md5=file_md5,
            total_chunks=total_chunks,
            dest_object=dest_path
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="File merge failed"
            )
        
        temp_prefix = f"temp/{file_md5}/"
        minio_client.delete_prefix(
            bucket_name=settings.MINIO_DEFAULT_BUCKET,
            prefix=temp_prefix
        )
        
        file_record.status = FILE_STATUS_MERGED
        await self._commit_with_sqlite_retry(db)
        
        await redis_client.clear_bitmap(redis_key)
        
        kafka_message = {
            "file_md5": file_md5,
            "file_name": file_name,
            "storage_path": dest_path,
            "user_id": user.id,
            "org_tag": file_record.org_tag,
            "is_public": file_record.is_public,
            "kb_profile": file_record.kb_profile,
        }
        try:
            success = await kafka_client.send_message(
                topic="document_parse",
                value=kafka_message,
                key=file_md5
            )
            if not success:
                logger.warning(f"Kafka消息发送失败（生产者可能未初始化），但文件合并成功")
                file_record.status = FILE_STATUS_FAILED
                await self._commit_with_sqlite_retry(db)
        except Exception as e:
            logger.warning(f"Kafka消息发送失败: {e}，但文件合并成功")
            file_record.status = FILE_STATUS_FAILED
            await self._commit_with_sqlite_retry(db)
        
        file_url = minio_client.get_file_url(
            bucket_name=settings.MINIO_DEFAULT_BUCKET,
            object_name=dest_path
        ) or f"{settings.MINIO_ENDPOINT}/{settings.MINIO_DEFAULT_BUCKET}/{dest_path}"
        
        return file_url, file_record.total_size

    async def delete_file(
        self,
        db: AsyncSession,
        user: User,
        file_md5: str
    ) -> bool:
        """
        删除文件（包括MinIO文件、数据库记录、Elasticsearch向量）
        管理员可以删除任何文件
        
        Returns:
            bool: 是否删除成功
        """
        if user.role == UserRole.ADMIN:
            file_upload_result = await db.execute(
                select(FileUpload).where(FileUpload.file_md5 == file_md5)
            )
        else:
            file_upload_result = await db.execute(
                select(FileUpload).where(
                    and_(
                        FileUpload.file_md5 == file_md5,
                        FileUpload.user_id == user.id
                    )
                )
            )
        file_record = file_upload_result.scalar_one_or_none()
        
        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在"
            )
        
        if file_record.user_id != user.id and user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限删除此文档"
            )
        
        try:
            vectors_result = await db.execute(
                select(DocumentVector).where(DocumentVector.file_md5 == file_md5)
            )
            vectors = vectors_result.scalars().all()
            
            for vector in vectors:
                doc_id = f"{file_md5}_{vector.chunk_id}"
                try:
                    await es_client.delete_document(
                        index=settings.ES_DEFAULT_INDEX,
                        doc_id=doc_id
                    )
                except Exception as e:
                    logger.warning(f"Elasticsearch删除失败: {e}")
            
            if file_record.status >= FILE_STATUS_MERGED:  # Already merged (processing/done/failed included)
                file_path = minio_client.build_document_path(file_record.user_id, file_record.file_name)
                minio_client.delete_file(
                    bucket_name=settings.MINIO_DEFAULT_BUCKET,
                    object_name=file_path
                )
            else:  # File still uploading; remove temporary chunks
                temp_prefix = f"temp/{file_md5}/"
                minio_client.delete_prefix(
                    bucket_name=settings.MINIO_DEFAULT_BUCKET,
                    prefix=temp_prefix
                )
            
            await db.delete(file_record)
            await db.commit()
            
            await redis_client.clear_bitmap(self.get_redis_chunk_key(file_md5))
            await redis_client.delete(self.get_redis_meta_key(file_md5))
            
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error(f"删除文档失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"删除文档失败: {str(e)}"
            )

    async def get_accessible_files(
        self,
        db: AsyncSession,
        user: User,
        kb_profile: Optional[str] = None,
    ) -> List[FileUpload]:
        """
        获取用户可访问的所有文件（包括用户上传的、公开的、所属组织的）
        管理员可以查看所有文件
        """
        if user.role == UserRole.ADMIN:
            stmt = select(FileUpload)
            if kb_profile:
                stmt = stmt.where(FileUpload.kb_profile == kb_profile)
            stmt = stmt.order_by(FileUpload.created_at.desc())
            result = await db.execute(stmt)
            return result.scalars().all()
        
        accessible_tags = await permission_service.get_user_accessible_tags(db, user)
        conditions = permission_service.build_db_file_access_conditions(
            user=user,
            accessible_tags=accessible_tags,
        )
        if not conditions:
            return []
        
        stmt = select(FileUpload).where(or_(*conditions))
        if kb_profile:
            stmt = stmt.where(FileUpload.kb_profile == kb_profile)
        stmt = stmt.order_by(FileUpload.created_at.desc())
        result = await db.execute(stmt)
        
        return result.scalars().all()

    async def get_user_uploaded_files(
        self,
        db: AsyncSession,
        user: User,
        kb_profile: Optional[str] = None,
    ) -> List[FileUpload]:
        stmt = select(FileUpload).where(FileUpload.user_id == user.id)
        if kb_profile:
            stmt = stmt.where(FileUpload.kb_profile == kb_profile)
        stmt = stmt.order_by(FileUpload.created_at.desc())
        result = await db.execute(stmt)
        
        return result.scalars().all()


file_service = FileService()
