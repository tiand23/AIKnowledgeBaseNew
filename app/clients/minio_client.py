"""
MinIO 对象存储客户端
"""
from minio import Minio
from minio.error import S3Error
from minio.commonconfig import ComposeSource
from typing import Optional, BinaryIO
from io import BytesIO
from datetime import timedelta
from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MinioClient:
    
    def __init__(self):
        self.client: Optional[Minio] = None
    
    def connect(self):
        try:
            self.client = Minio(
                endpoint=settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE,
            )
            logger.info(f"MinIO 客户端初始化成功: {settings.MINIO_ENDPOINT}")
        except Exception as e:
            logger.error(f"MinIO 客户端初始化失败: {e}")
            raise
    
    def close(self):
        self.client = None
        logger.info("MinIO 客户端已关闭")
    
    def ensure_bucket(self, bucket_name: str) -> bool:
        """
        确保存储桶存在，如果不存在则创建
        
        Args:
            bucket_name: 存储桶名称
            
        Returns:
            bool: 操作是否成功
        """
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
                logger.info(f"创建存储桶成功: {bucket_name}")
            return True
        except S3Error as e:
            logger.error(f"存储桶操作失败: {e}")
            return False

    @staticmethod
    def build_temp_chunk_path(file_md5: str, chunk_index: int) -> str:
        """
        生成临时分片在 MinIO 中的对象路径。
        约定：/temp/{fileMd5}/{chunkIndex}
        """
        return f"temp/{file_md5}/{chunk_index}"

    @staticmethod
    def build_document_path(user_id: int, file_name: str) -> str:
        """
        生成合并后完整文件在 MinIO 中的对象路径。
        约定：/documents/{userId}/{fileName}
        """
        return f"documents/{user_id}/{file_name}"

    @staticmethod
    def build_document_image_path(
        user_id: int,
        file_md5: str,
        sheet_name: str,
        image_index: int,
        ext: str = "png",
    ) -> str:
        """
        生成文档内嵌图片在 MinIO 中的对象路径。
        约定：/documents/{userId}/images/{fileMd5}/{sheet}_{index}.{ext}
        """
        safe_sheet = (sheet_name or "sheet").replace("/", "_").replace("\\", "_").replace(" ", "_")
        safe_ext = (ext or "png").lower().strip(".")
        return f"documents/{user_id}/images/{file_md5}/{safe_sheet}_{image_index}.{safe_ext}"
    
    def upload_file(
        self,
        bucket_name: str,
        object_name: str,
        file_data: BinaryIO,
        file_size: int,
        content_type: str = "application/octet-stream"
    ) -> bool:
        """
        上传文件到 MinIO
        
        Args:
            bucket_name: 存储桶名称
            object_name: 对象名称（文件路径）
            file_data: 文件数据流
            file_size: 文件大小（字节）
            content_type: 文件类型
            
        Returns:
            bool: 上传是否成功
        """
        try:
            self.ensure_bucket(bucket_name)
            
            self.client.put_object(
                bucket_name=bucket_name,
                object_name=object_name,
                data=file_data,
                length=file_size,
                content_type=content_type
            )
            logger.info(f"文件上传成功: {bucket_name}/{object_name}")
            return True
        except S3Error as e:
            logger.error(f"文件上传失败: {e}")
            return False
    
    def upload_bytes(
        self,
        bucket_name: str,
        object_name: str,
        data: bytes,
        content_type: str = "application/octet-stream"
    ) -> bool:
        """
        上传字节数据到 MinIO
        
        Args:
            bucket_name: 存储桶名称
            object_name: 对象名称（文件路径）
            data: 字节数据
            content_type: 文件类型
            
        Returns:
            bool: 上传是否成功
        """
        try:
            file_data = BytesIO(data)
            return self.upload_file(
                bucket_name=bucket_name,
                object_name=object_name,
                file_data=file_data,
                file_size=len(data),
                content_type=content_type
            )
        except Exception as e:
            logger.error(f"字节数据上传失败: {e}")
            return False
    
    def download_file(self, bucket_name: str, object_name: str) -> Optional[bytes]:
        """
        从 MinIO 下载文件
        
        Args:
            bucket_name: 存储桶名称
            object_name: 对象名称（文件路径）
            
        Returns:
            Optional[bytes]: 文件数据，失败返回 None
        """
        try:
            response = self.client.get_object(bucket_name, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            logger.info(f"文件下载成功: {bucket_name}/{object_name}")
            return data
        except S3Error as e:
            logger.error(f"文件下载失败: {e}")
            return None
    
    def delete_file(self, bucket_name: str, object_name: str) -> bool:
        """
        删除 MinIO 中的文件
        
        Args:
            bucket_name: 存储桶名称
            object_name: 对象名称（文件路径）
            
        Returns:
            bool: 删除是否成功
        """
        try:
            if not self.client:
                logger.warning(f"MinIO 客户端未初始化，无法删除文件: {bucket_name}/{object_name}")
                return False
            self.client.remove_object(bucket_name, object_name)
            logger.info(f"文件删除成功: {bucket_name}/{object_name}")
            return True
        except S3Error as e:
            logger.error(f"文件删除失败: {e}")
            return False
        except AttributeError as e:
            logger.error(f"MinIO 客户端未初始化: {e}")
            return False

    def compose_objects(
        self,
        bucket_name: str,
        dest_object: str,
        source_objects: list
    ) -> bool:
        """
        使用 MinIO 的 composeObject 将多个对象合并为一个对象。

        Args:
            bucket_name: 存储桶名
            dest_object: 目标对象路径
            source_objects: 源对象路径列表（按顺序）
        """
        try:
            self.ensure_bucket(bucket_name)
            sources = [ComposeSource(bucket_name, obj) for obj in source_objects]
            self.client.compose_object(bucket_name, dest_object, sources)
            logger.info(f"对象合并成功: {bucket_name}/{dest_object} <- {len(source_objects)} parts")
            return True
        except S3Error as e:
            logger.error(f"对象合并失败: {e}")
            return False

    def merge_chunks(
        self,
        bucket_name: str,
        file_md5: str,
        total_chunks: int,
        dest_object: str,
        min_chunk_size: int = 5 * 1024 * 1024
    ) -> bool:
        """
        基于既定的临时分片路径规则，将 {0..total_chunks-1} 的分片合并为一个对象。
        
        对于小文件（分片小于5MB），使用下载-合并-上传的方式。
        对于大文件（分片大于等于5MB），使用 MinIO compose API。

        Args:
            bucket_name: 存储桶
            file_md5: 文件 MD5
            total_chunks: 分片总数
            dest_object: 合并后的目标对象路径（通常由 build_document_path 生成）
            min_chunk_size: 使用 compose 的最小分片大小（默认5MB）
        """
        if total_chunks <= 0:
            return False
        
        first_chunk_path = self.build_temp_chunk_path(file_md5, 0)
        try:
            stat = self.client.stat_object(bucket_name, first_chunk_path)
            first_chunk_size = stat.size
            
            if first_chunk_size < min_chunk_size:
                logger.info(f"检测到小文件（分片大小: {first_chunk_size} 字节），使用下载-合并方式")
                return self._merge_small_chunks(bucket_name, file_md5, total_chunks, dest_object)
            else:
                logger.info(f"检测到大文件（分片大小: {first_chunk_size} 字节），使用 compose API")
                sources = [self.build_temp_chunk_path(file_md5, idx) for idx in range(total_chunks)]
                return self.compose_objects(bucket_name, dest_object, sources)
        except S3Error as e:
            logger.error(f"检查分片大小失败: {e}")
            return self._merge_small_chunks(bucket_name, file_md5, total_chunks, dest_object)
    
    def _merge_small_chunks(
        self,
        bucket_name: str,
        file_md5: str,
        total_chunks: int,
        dest_object: str
    ) -> bool:
        """
        对于小文件，下载所有分片到内存，合并后上传。
        
        Args:
            bucket_name: 存储桶
            file_md5: 文件 MD5
            total_chunks: 分片总数
            dest_object: 合并后的目标对象路径
        """
        try:
            self.ensure_bucket(bucket_name)
            
            merged_data = BytesIO()
            total_size = 0
            for idx in range(total_chunks):
                chunk_path = self.build_temp_chunk_path(file_md5, idx)
                chunk_data = self.download_file(bucket_name, chunk_path)
                if chunk_data is None:
                    logger.error(f"下载分片失败: {chunk_path}")
                    return False
                merged_data.write(chunk_data)
                total_size += len(chunk_data)
            
            merged_data.seek(0)
            
            success = self.upload_file(
                bucket_name=bucket_name,
                object_name=dest_object,
                file_data=merged_data,
                file_size=total_size,
                content_type="application/octet-stream"
            )
            
            if success:
                logger.info(f"小文件合并成功: {bucket_name}/{dest_object} <- {total_chunks} parts (总计 {total_size} 字节)")
            return success
            
        except Exception as e:
            logger.error(f"小文件合并失败: {e}")
            return False

    def delete_prefix(self, bucket_name: str, prefix: str) -> int:
        """
        删除指定前缀下的所有对象（用于清理临时分片）。
        返回删除的对象数量。
        """
        try:
            count = 0
            for obj in self.client.list_objects(bucket_name, prefix=prefix, recursive=True):
                self.client.remove_object(bucket_name, obj.object_name)
                count += 1
            logger.info(f"删除前缀对象成功: {bucket_name}/{prefix}，共 {count} 个")
            return count
        except S3Error as e:
            logger.error(f"删除前缀对象失败: {e}")
            return 0
    
    def file_exists(self, bucket_name: str, object_name: str) -> bool:
        """
        检查文件是否存在
        
        Args:
            bucket_name: 存储桶名称
            object_name: 对象名称（文件路径）
            
        Returns:
            bool: 文件是否存在
        """
        try:
            self.client.stat_object(bucket_name, object_name)
            return True
        except S3Error:
            return False
    
    def get_file_url(
        self,
        bucket_name: str,
        object_name: str,
        expires: timedelta = timedelta(hours=1)
    ) -> Optional[str]:
        """
        获取文件的预签名 URL（临时访问链接）
        
        Args:
            bucket_name: 存储桶名称
            object_name: 对象名称（文件路径）
            expires: 过期时间，默认 1 小时
            
        Returns:
            Optional[str]: 预签名 URL，失败返回 None
        """
        try:
            url = self.client.presigned_get_object(
                bucket_name=bucket_name,
                object_name=object_name,
                expires=expires
            )
            return url
        except S3Error as e:
            logger.error(f"获取预签名 URL 失败: {e}")
            return None
    
    def list_files(self, bucket_name: str, prefix: str = "") -> list:
        """
        列出存储桶中的文件
        
        Args:
            bucket_name: 存储桶名称
            prefix: 对象名称前缀（用于过滤）
            
        Returns:
            list: 文件对象列表
        """
        try:
            objects = self.client.list_objects(
                bucket_name=bucket_name,
                prefix=prefix,
                recursive=True
            )
            
            file_list = []
            for obj in objects:
                file_list.append({
                    "name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                    "etag": obj.etag
                })
            
            return file_list
        except S3Error as e:
            logger.error(f"列出文件失败: {e}")
            return []
    
    def get_file_info(self, bucket_name: str, object_name: str) -> Optional[dict]:
        """
        获取文件信息
        
        Args:
            bucket_name: 存储桶名称
            object_name: 对象名称（文件路径）
            
        Returns:
            Optional[dict]: 文件信息，失败返回 None
        """
        try:
            stat = self.client.stat_object(bucket_name, object_name)
            return {
                "name": stat.object_name,
                "size": stat.size,
                "content_type": stat.content_type,
                "last_modified": stat.last_modified.isoformat() if stat.last_modified else None,
                "etag": stat.etag,
                "metadata": stat.metadata
            }
        except S3Error as e:
            logger.error(f"获取文件信息失败: {e}")
            return None
    
    def health_check(self) -> bool:
        try:
            list(self.client.list_buckets())
            return True
        except Exception as e:
            logger.error(f"MinIO 健康检查失败: {e}")
            return False
    
    def get_status(self) -> dict:
        if not self.client:
            return {"error": "MinIO 客户端未初始化"}
        
        try:
            buckets = list(self.client.list_buckets())
            return {
                "状态": "已连接",
                "端点": settings.MINIO_ENDPOINT,
                "安全连接": settings.MINIO_SECURE,
                "存储桶数量": len(buckets),
                "存储桶列表": [bucket.name for bucket in buckets]
            }
        except Exception as e:
            return {
                "状态": "连接失败",
                "错误": str(e)
            }


minio_client = MinioClient()
