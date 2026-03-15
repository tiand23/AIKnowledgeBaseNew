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


class StructuredOverviewFileInfo(BaseModel):
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
    documentUnitCount: int = 0
    semanticBlockCount: int = 0
    parentChunkCount: int = 0
    childChunkCount: int = 0
    visualPageCount: int = 0
    visualEmbeddingCount: int = 0
    visualIndexedCount: int = 0
    acceptedBlockCount: int = 0
    weakBlockCount: int = 0
    rejectedBlockCount: int = 0


class StructuredOverviewResponse(BaseResponse[List[StructuredOverviewFileInfo]]):
    code: int = Field(200, description="状态码")
    message: str = Field("获取结构化总览成功", description="提示信息")


class StructuredDocumentUnitItem(BaseModel):
    unitType: str
    unitKey: str
    unitName: Optional[str] = None
    unitOrder: Optional[int] = None
    page: Optional[int] = None
    sheet: Optional[str] = None
    section: Optional[str] = None
    parentUnitKey: Optional[str] = None


class StructuredSemanticBlockItem(BaseModel):
    blockIndex: int
    documentUnitKey: Optional[str] = None
    blockType: str
    sourceParser: Optional[str] = None
    page: Optional[int] = None
    sheet: Optional[str] = None
    section: Optional[str] = None
    rowNo: Optional[int] = None
    qualityScore: int = 0
    qualityStatus: str
    parserConfidence: Optional[int] = None
    validationFlags: List[str] = Field(default_factory=list)
    textPreview: str = ""
    imageUrl: Optional[str] = None


class StructuredParentChunkItem(BaseModel):
    parentChunkId: int
    documentUnitKey: Optional[str] = None
    chunkType: Optional[str] = None
    qualityScore: int = 0
    qualityStatus: str
    textPreview: str = ""


class StructuredChildChunkItem(BaseModel):
    childChunkId: int
    parentChunkId: Optional[int] = None
    documentUnitKey: Optional[str] = None
    chunkType: Optional[str] = None
    qualityScore: int = 0
    qualityStatus: str
    neighborPrevId: Optional[int] = None
    neighborNextId: Optional[int] = None
    textPreview: str = ""


class StructuredImageItem(BaseModel):
    page: Optional[int] = None
    sheet: Optional[str] = None
    sourceParser: Optional[str] = None
    imageUrl: str
    imageWidth: Optional[int] = None
    imageHeight: Optional[int] = None
    matchMode: Optional[str] = None
    matchConfidence: Optional[int] = None


class StructuredVisualPageItem(BaseModel):
    visualPageId: int
    documentUnitId: Optional[int] = None
    unitType: Optional[str] = None
    page: Optional[int] = None
    sheet: Optional[str] = None
    section: Optional[str] = None
    pageLabel: Optional[str] = None
    renderSource: Optional[str] = None
    renderVersion: Optional[str] = None
    qualityStatus: str
    visualEmbeddingStatus: Optional[str] = None
    visualEmbeddingProvider: Optional[str] = None
    visualEmbeddingModel: Optional[str] = None
    visualEmbeddingDim: Optional[int] = None
    visualEmbeddingError: Optional[str] = None
    visualIndexed: bool = False
    visualIndexDocId: Optional[str] = None
    imageUrl: str
    imageWidth: Optional[int] = None
    imageHeight: Optional[int] = None


class StructuredRelationNodeItem(BaseModel):
    nodeId: int
    nodeKey: str
    nodeName: str
    nodeType: Optional[str] = None
    page: Optional[int] = None
    evidenceText: Optional[str] = None


class StructuredRelationEdgeItem(BaseModel):
    edgeId: int
    srcNodeId: int
    srcNodeName: str
    dstNodeId: int
    dstNodeName: str
    relationType: str
    relationText: Optional[str] = None
    page: Optional[int] = None
    evidenceText: Optional[str] = None


class StructuredFileDetailData(BaseModel):
    fileMd5: str
    fileName: str
    originalUrl: Optional[str] = None
    documentUnits: List[StructuredDocumentUnitItem] = Field(default_factory=list)
    semanticBlocks: List[StructuredSemanticBlockItem] = Field(default_factory=list)
    parentChunks: List[StructuredParentChunkItem] = Field(default_factory=list)
    childChunks: List[StructuredChildChunkItem] = Field(default_factory=list)
    images: List[StructuredImageItem] = Field(default_factory=list)
    visualPages: List[StructuredVisualPageItem] = Field(default_factory=list)
    relationNodes: List[StructuredRelationNodeItem] = Field(default_factory=list)
    relationEdges: List[StructuredRelationEdgeItem] = Field(default_factory=list)


class StructuredFileDetailResponse(BaseResponse[StructuredFileDetailData]):
    code: int = Field(200, description="状态码")
    message: str = Field("获取结构化明细成功", description="提示信息")


class DeleteFileResponse(BaseResponse[Optional[Dict[str, Any]]]):
    code: int = Field(200, description="状态码")
    message: str = Field("文档删除成功", description="提示信息")


class VisualIndexRebuildData(BaseModel):
    fileMd5: str
    pages: int = 0
    indexed: int = 0
    esDocs: int = 0
    pending: int = 0
    errors: int = 0


class VisualIndexRebuildResponse(BaseResponse[VisualIndexRebuildData]):
    code: int = Field(200, description="状态码")
    message: str = Field("视觉索引重建成功", description="提示信息")
