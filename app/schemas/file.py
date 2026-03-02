"""
文件相关 Schema
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.schemas.base import BaseResponse


class ChunkUploadResponse(BaseResponse[Dict[str, Any]]):
    code: int = Field(200, description="状态码")
    message: str = Field("分片上传成功", description="提示信息")


class ChunkUploadData(BaseModel):
    uploaded: List[int] = Field(..., description="已上传的分片索引列表")
    progress: float = Field(..., description="上传进度（百分比）")


class UploadStatusResponse(BaseResponse[Dict[str, Any]]):
    code: int = Field(200, description="状态码")
    message: str = Field("Success", description="提示信息")


class UploadStatusData(BaseModel):
    uploaded: List[int] = Field(..., description="已上传的分片索引列表")
    progress: float = Field(..., description="上传进度（百分比）")
    total_chunks: int = Field(..., description="总分片数")


class MergeFileRequest(BaseModel):
    file_md5: str = Field(..., min_length=32, max_length=32, description="文件MD5值")
    file_name: str = Field(..., min_length=1, description="文件名")


class MergeFileResponse(BaseResponse[Dict[str, Any]]):
    code: int = Field(200, description="状态码")
    message: str = Field("File merged successfully", description="提示信息")


class MergeFileData(BaseModel):
    object_url: str = Field(..., description="文件访问URL")
    file_size: int = Field(..., description="文件大小（字节）")


class FileInfo(BaseModel):
    fileMd5: str
    fileName: str
    totalSize: int
    status: int
    userId: str
    orgTag: Optional[str] = None
    kbProfile: Optional[str] = None
    isPublic: bool
    createdAt: datetime
    mergedAt: Optional[datetime] = None


class FileListResponse(BaseResponse[List[FileInfo]]):
    code: int = Field(200, description="状态码")
    message: str = Field("获取文件列表成功", description="提示信息")


class FileUploadInfo(BaseModel):
    fileMd5: str
    fileName: str
    totalSize: int
    status: int
    userId: str
    orgTagName: Optional[str] = None
    kbProfile: Optional[str] = None
    isPublic: bool
    createdAt: datetime
    mergedAt: Optional[datetime] = None
    vectorCount: int = 0
    tableRowCount: int = 0
    imageBlockCount: int = 0
    relationNodeCount: int = 0
    relationEdgeCount: int = 0


class FileUploadListResponse(BaseResponse[List[FileUploadInfo]]):
    code: int = Field(200, description="状态码")
    message: str = Field("获取文件列表成功", description="提示信息")


class EsPreviewItem(BaseModel):
    chunkId: int
    chunkType: Optional[str] = None
    page: Optional[int] = None
    sheet: Optional[str] = None
    textPreview: str
    score: float = 0.0


class EsPreviewResponse(BaseResponse[List[EsPreviewItem]]):
    code: int = Field(200, description="状态码")
    message: str = Field("获取ES文档预览成功", description="提示信息")


class SourceDetailData(BaseModel):
    fileMd5: str
    fileName: str
    objectPath: Optional[str] = None
    originalUrl: Optional[str] = None
    imageUrls: List[str] = Field(default_factory=list)
    previewRows: List[EsPreviewItem] = Field(default_factory=list)


class SourceDetailResponse(BaseResponse[SourceDetailData]):
    code: int = Field(200, description="状态码")
    message: str = Field("获取来源详情成功", description="提示信息")


class DeleteFileResponse(BaseResponse[Optional[Dict[str, Any]]]):
    code: int = Field(200, description="状态码")
    message: str = Field("文档删除成功", description="提示信息")
