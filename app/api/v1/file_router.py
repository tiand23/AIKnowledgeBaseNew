"""
文件相关接口路由
"""
import json
import mimetypes
import re
import unicodedata
from urllib.parse import quote

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, get_current_user
from app.clients.elasticsearch_client import es_client
from app.clients.minio_client import minio_client
from app.core.config import settings
from app.models.file import DocumentVector, FileUpload
from app.models.file import (
    RelationNode,
    RelationEdge,
    ImageBlock,
    TableRow,
    ChunkSource,
    DocumentUnit,
    SemanticBlock,
    ParentChunk,
    ChildChunk,
    VisualPage,
    VisualPageEmbedding,
)
from app.models.user import User
from app.schemas.file import (
    ChunkUploadResponse, ChunkUploadData,
    UploadStatusResponse, UploadStatusData,
    MergeFileRequest, MergeFileResponse, MergeFileData,
    DeleteFileResponse,
    FileListResponse, FileInfo,
    FileUploadListResponse, FileUploadInfo,
    EsPreviewResponse, EsPreviewItem,
    SourceDetailResponse, SourceDetailData,
    StructuredOverviewResponse, StructuredOverviewFileInfo,
    StructuredFileDetailResponse, StructuredFileDetailData,
    StructuredDocumentUnitItem, StructuredSemanticBlockItem,
    StructuredParentChunkItem, StructuredChildChunkItem, StructuredImageItem,
    StructuredVisualPageItem,
    StructuredRelationNodeItem, StructuredRelationEdgeItem,
    VisualIndexRebuildResponse, VisualIndexRebuildData,
)
from app.services.file_service import file_service
from app.services.permission_service import permission_service
from app.services.profile_service import profile_service
from app.services.visual_search_service import visual_search_service
from app.utils import jwt_utils
from app.utils.logger import get_logger

logger = get_logger(__name__)

upload_router = APIRouter()


def _clean_source_preview_text(value: str, chunk_type: str | None = None) -> str:
    text = (value or "").strip()
    if not text:
        return ""

    ctype = str(chunk_type or "").lower()
    if "table" not in ctype and "row" not in ctype and "header" not in ctype:
        return text

    text = re.sub(r"(?:(?:^|\||;)\s*col_\d+\s*:?\s*)", " | ", text)
    text = re.sub(r"\|\s*\|+", "|", text)
    text = re.sub(r";\s*;+", ";", text)
    text = re.sub(r"(?:\s*\|\s*){2,}", " | ", text)
    text = re.sub(r"(?:\s*;\s*){2,}", " ; ", text)
    text = re.sub(r"^\s*[\|;:\-]+\s*|\s*[\|;:\-]+\s*$", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not re.search(r"[\u3040-\u30ff\u3400-\u9fffA-Za-z0-9]", text):
        return ""
    return text


def _trim_preview_text(value: str | None, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _safe_json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed if str(item or "").strip()]
    except Exception:
        pass
    return []

@upload_router.post("/chunk", response_model=ChunkUploadResponse)
async def upload_chunk(
    file: UploadFile = File(...),
    fileMd5: str = Form(...),
    chunkIndex: int = Form(...),
    totalSize: int = Form(...),
    fileName: str = Form(...),
    totalChunks: int = Form(None),
    orgTag: str = Form(None),
    isPublic: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    分片上传接口
    
    - 接收文件分片
    - 验证数据完整性
    - 存储到MinIO临时目录
    - 更新Redis BitSet状态
    - 保存分片信息到数据库
    """
    try:
        selected_profile = await profile_service.ensure_profile_selected(db)
        chunk_data = await file.read()
        
        uploaded_chunks, progress = await file_service.upload_chunk(
            db=db,
            user=current_user,
            file_md5=fileMd5,
            chunk_index=chunkIndex,
            chunk_data=chunk_data,
            file_name=fileName,
            total_size=totalSize,
            total_chunks=totalChunks,
            org_tag=orgTag,
            is_public=isPublic,
            kb_profile=selected_profile,
        )
        
        return ChunkUploadResponse(
            code=200,
            message="分片上传成功",
            data=ChunkUploadData(
                uploaded=uploaded_chunks,
                progress=progress
            ).dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分片上传失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"分片上传失败: {str(e)}"
        )


@upload_router.get("/status", response_model=UploadStatusResponse)
async def get_upload_status(
    file_md5: str = Query(..., description="文件MD5值"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    查询上传状态接口
    
    - 查询已上传的分片列表
    - 计算上传进度
    """
    try:
        await profile_service.ensure_profile_selected(db)
        uploaded_chunks, progress, total_chunks = await file_service.get_upload_status(
            db=db,
            user=current_user,
            file_md5=file_md5
        )
        
        return UploadStatusResponse(
            code=200,
            message="Success",
            data=UploadStatusData(
                uploaded=uploaded_chunks,
                progress=progress,
                total_chunks=total_chunks
            ).dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询上传状态失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询上传状态失败: {str(e)}"
        )


@upload_router.post("/merge", response_model=MergeFileResponse)
async def merge_file(
    request: MergeFileRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    文件合并接口
    
    - 验证所有分片已上传
    - 调用MinIO compose API合并分片
    - 清理临时分片
    - 更新文件状态
    - 发送解析任务到Kafka
    """
    try:
        await profile_service.ensure_profile_selected(db)
        object_url, file_size = await file_service.merge_file(
            db=db,
            user=current_user,
            file_md5=request.file_md5,
            file_name=request.file_name
        )
        
        return MergeFileResponse(
            code=200,
            message="File merged successfully",
            data=MergeFileData(
                object_url=object_url,
                file_size=file_size
            ).dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件合并失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件合并失败: {str(e)}"
        )


documents_router = APIRouter()


def _normalize_sheet_name(value: str | None) -> str:
    if not value:
        return ""
    v = unicodedata.normalize("NFKC", str(value))
    v = re.sub(r"\s+", "", v)
    return v.strip()


def _guess_mime_by_name(file_name: str) -> str:
    mime, _ = mimetypes.guess_type(file_name or "")
    return mime or "application/octet-stream"


async def _resolve_user_from_bearer_or_query_token(
    request: Request | None,
    db: AsyncSession,
    token: str | None,
) -> User:
    """
    资源预览场景下，兼容两种鉴权方式：
    1) Authorization: Bearer <token>
    2) query ?token=<token>（用于 img/a 标签直连）
    """
    bearer_token = None
    auth_header = (request.headers.get("authorization", "") if request else "")
    if auth_header.lower().startswith("bearer "):
        bearer_token = auth_header[7:].strip()

    access_token = bearer_token or (token or "").strip()
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    if not await jwt_utils.validate_token(access_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    username = jwt_utils.extract_username(access_token)
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return user

@documents_router.delete("/{file_md5}", response_model=DeleteFileResponse)
async def delete_file(
    file_md5: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    文件删除接口
    
    - 验证权限
    - 删除Elasticsearch中的向量
    - 删除MinIO中的文件
    - 删除数据库记录
    - 清理Redis缓存
    """
    try:
        await file_service.delete_file(
            db=db,
            user=current_user,
            file_md5=file_md5
        )
        
        return DeleteFileResponse(
            code=200,
            message="文档删除成功",
            data=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除文档失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除文档失败: {str(e)}"
        )


@documents_router.get("/accessible", response_model=FileListResponse)
async def get_accessible_files(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取用户可访问的全部文件列表
    
    - 包括用户上传的文件
    - 包括公开文件
    - 包括用户所属组织的文件
    """
    try:
        await profile_service.ensure_profile_selected(db)
        files = await file_service.get_accessible_files(
            db=db,
            user=current_user,
            kb_profile=None,
        )
        
        file_list = [
            FileInfo(
                fileMd5=file.file_md5,
                fileName=file.file_name,
                totalSize=file.total_size,
                status=file.status,
                userId=str(file.user_id),
                orgTag=file.org_tag,
                kbProfile=file.kb_profile,
                isPublic=file.is_public,
                createdAt=file.created_at,
                mergedAt=file.merged_at
            )
            for file in files
        ]
        
        return FileListResponse(
            code=200,
            message="获取文件列表成功",
            data=file_list
        )
        
    except Exception as e:
        logger.error(f"获取文件列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文件列表失败: {str(e)}"
        )


@documents_router.get("/uploads", response_model=FileUploadListResponse)
async def get_user_uploaded_files(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取用户上传的全部文件列表
    """
    try:
        await profile_service.ensure_profile_selected(db)
        files = await file_service.get_user_uploaded_files(
            db=db,
            user=current_user,
            kb_profile=None,
        )

        md5_list = [file.file_md5 for file in files]
        vector_count_map = {}
        table_row_count_map = {}
        image_block_count_map = {}
        relation_node_count_map = {}
        relation_edge_count_map = {}
        if md5_list:
            count_result = await db.execute(
                select(
                    DocumentVector.file_md5,
                    func.count(DocumentVector.vector_id)
                )
                .where(DocumentVector.file_md5.in_(md5_list))
                .group_by(DocumentVector.file_md5)
            )
            vector_count_map = {row[0]: int(row[1]) for row in count_result.all()}
            table_row_count_result = await db.execute(
                select(
                    TableRow.file_md5,
                    func.count(TableRow.id)
                )
                .where(TableRow.file_md5.in_(md5_list))
                .group_by(TableRow.file_md5)
            )
            table_row_count_map = {row[0]: int(row[1]) for row in table_row_count_result.all()}

            node_count_result = await db.execute(
                select(
                    RelationNode.file_md5,
                    func.count(RelationNode.id)
                )
                .where(RelationNode.file_md5.in_(md5_list))
                .group_by(RelationNode.file_md5)
            )
            relation_node_count_map = {row[0]: int(row[1]) for row in node_count_result.all()}

            edge_count_result = await db.execute(
                select(
                    RelationEdge.file_md5,
                    func.count(RelationEdge.id)
                )
                .where(RelationEdge.file_md5.in_(md5_list))
                .group_by(RelationEdge.file_md5)
            )
            relation_edge_count_map = {row[0]: int(row[1]) for row in edge_count_result.all()}
            image_count_result = await db.execute(
                select(
                    ImageBlock.file_md5,
                    func.count(ImageBlock.id)
                )
                .where(ImageBlock.file_md5.in_(md5_list))
                .group_by(ImageBlock.file_md5)
            )
            image_block_count_map = {row[0]: int(row[1]) for row in image_count_result.all()}
        
        file_list = [
            FileUploadInfo(
                fileMd5=file.file_md5,
                fileName=file.file_name,
                totalSize=file.total_size,
                status=file.status,
                userId=str(file.user_id),
                orgTagName=file.org_tag,
                kbProfile=file.kb_profile,
                isPublic=file.is_public,
                createdAt=file.created_at,
                mergedAt=file.merged_at,
                vectorCount=vector_count_map.get(file.file_md5, 0),
                tableRowCount=table_row_count_map.get(file.file_md5, 0),
                imageBlockCount=image_block_count_map.get(file.file_md5, 0),
                relationNodeCount=relation_node_count_map.get(file.file_md5, 0),
                relationEdgeCount=relation_edge_count_map.get(file.file_md5, 0)
            )
            for file in files
        ]
        
        return FileUploadListResponse(
            code=200,
            message="获取文件列表成功",
            data=file_list
        )
        
    except Exception as e:
        logger.error(f"获取文件列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文件列表失败: {str(e)}"
        )




@documents_router.post("/{file_md5}/visual-index/rebuild", response_model=VisualIndexRebuildResponse)
async def rebuild_visual_index(
    file_md5: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    手动重建单个文件的视觉索引。

    用途：
    - 配好 Gemini / Vertex 凭证后，给历史文件补建 visual embeddings
    - 不需要重新上传文件
    """
    file_record = (
        await db.execute(
            select(FileUpload).where(
                FileUpload.file_md5 == file_md5,
                FileUpload.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在或无权限")

    visual_stats = await visual_search_service.rebuild_for_file(
        db=db,
        file_md5=file_md5,
        user_id=current_user.id,
        org_tag=file_record.org_tag or "DEFAULT",
        kb_profile=file_record.kb_profile or "default",
        is_public=bool(file_record.is_public),
    )
    await db.commit()

    return VisualIndexRebuildResponse(
        code=200,
        message="视觉索引重建成功",
        data=VisualIndexRebuildData(
            fileMd5=file_md5,
            pages=visual_stats.get("pages", 0),
            indexed=visual_stats.get("indexed", 0),
            esDocs=visual_stats.get("es_docs", 0),
            pending=visual_stats.get("pending", 0),
            errors=visual_stats.get("errors", 0),
        ).dict(),
    )

@documents_router.get("/structured-overview", response_model=StructuredOverviewResponse)
async def get_structured_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    全体结构化数据页面总览：
    - 返回用户上传文档列表
    - 同时聚合新结构层(document_units / semantic_blocks / parent_chunks / child_chunks)统计
    """
    try:
        await profile_service.ensure_profile_selected(db)
        files = await file_service.get_user_uploaded_files(
            db=db,
            user=current_user,
            kb_profile=None,
        )

        md5_list = [file.file_md5 for file in files]
        vector_count_map: dict[str, int] = {}
        table_row_count_map: dict[str, int] = {}
        image_block_count_map: dict[str, int] = {}
        relation_node_count_map: dict[str, int] = {}
        relation_edge_count_map: dict[str, int] = {}
        document_unit_count_map: dict[str, int] = {}
        semantic_block_count_map: dict[str, int] = {}
        parent_chunk_count_map: dict[str, int] = {}
        child_chunk_count_map: dict[str, int] = {}
        visual_page_count_map: dict[str, int] = {}
        visual_embedding_count_map: dict[str, int] = {}
        visual_indexed_count_map: dict[str, int] = {}
        block_quality_map: dict[str, dict[str, int]] = {}

        if md5_list:
            count_queries = [
                (
                    select(DocumentVector.file_md5, func.count(DocumentVector.vector_id))
                    .where(DocumentVector.file_md5.in_(md5_list))
                    .group_by(DocumentVector.file_md5),
                    vector_count_map,
                ),
                (
                    select(TableRow.file_md5, func.count(TableRow.id))
                    .where(TableRow.file_md5.in_(md5_list))
                    .group_by(TableRow.file_md5),
                    table_row_count_map,
                ),
                (
                    select(ImageBlock.file_md5, func.count(ImageBlock.id))
                    .where(ImageBlock.file_md5.in_(md5_list))
                    .group_by(ImageBlock.file_md5),
                    image_block_count_map,
                ),
                (
                    select(RelationNode.file_md5, func.count(RelationNode.id))
                    .where(RelationNode.file_md5.in_(md5_list))
                    .group_by(RelationNode.file_md5),
                    relation_node_count_map,
                ),
                (
                    select(RelationEdge.file_md5, func.count(RelationEdge.id))
                    .where(RelationEdge.file_md5.in_(md5_list))
                    .group_by(RelationEdge.file_md5),
                    relation_edge_count_map,
                ),
                (
                    select(DocumentUnit.file_md5, func.count(DocumentUnit.id))
                    .where(DocumentUnit.file_md5.in_(md5_list))
                    .group_by(DocumentUnit.file_md5),
                    document_unit_count_map,
                ),
                (
                    select(SemanticBlock.file_md5, func.count(SemanticBlock.id))
                    .where(SemanticBlock.file_md5.in_(md5_list))
                    .group_by(SemanticBlock.file_md5),
                    semantic_block_count_map,
                ),
                (
                    select(ParentChunk.file_md5, func.count(ParentChunk.id))
                    .where(ParentChunk.file_md5.in_(md5_list))
                    .group_by(ParentChunk.file_md5),
                    parent_chunk_count_map,
                ),
                (
                    select(ChildChunk.file_md5, func.count(ChildChunk.id))
                    .where(ChildChunk.file_md5.in_(md5_list))
                    .group_by(ChildChunk.file_md5),
                    child_chunk_count_map,
                ),
                (
                    select(VisualPage.file_md5, func.count(VisualPage.id))
                    .where(VisualPage.file_md5.in_(md5_list))
                    .group_by(VisualPage.file_md5),
                    visual_page_count_map,
                ),
                (
                    select(VisualPageEmbedding.file_md5, func.count(VisualPageEmbedding.id))
                    .where(VisualPageEmbedding.file_md5.in_(md5_list))
                    .group_by(VisualPageEmbedding.file_md5),
                    visual_embedding_count_map,
                ),
                (
                    select(VisualPageEmbedding.file_md5, func.count(VisualPageEmbedding.id))
                    .where(
                        VisualPageEmbedding.file_md5.in_(md5_list),
                        VisualPageEmbedding.es_doc_id.isnot(None),
                    )
                    .group_by(VisualPageEmbedding.file_md5),
                    visual_indexed_count_map,
                ),
            ]
            for stmt, target_map in count_queries:
                result = await db.execute(stmt)
                target_map.update({row[0]: int(row[1]) for row in result.all()})

            quality_result = await db.execute(
                select(
                    SemanticBlock.file_md5,
                    func.sum(case((SemanticBlock.quality_status == "accepted", 1), else_=0)),
                    func.sum(case((SemanticBlock.quality_status == "weak", 1), else_=0)),
                    func.sum(case((SemanticBlock.quality_status == "rejected", 1), else_=0)),
                )
                .where(SemanticBlock.file_md5.in_(md5_list))
                .group_by(SemanticBlock.file_md5)
            )
            for file_md5, accepted_count, weak_count, rejected_count in quality_result.all():
                block_quality_map[str(file_md5)] = {
                    "accepted": int(accepted_count or 0),
                    "weak": int(weak_count or 0),
                    "rejected": int(rejected_count or 0),
                }

        file_list = [
            StructuredOverviewFileInfo(
                fileMd5=file.file_md5,
                fileName=file.file_name,
                totalSize=file.total_size,
                status=file.status,
                userId=str(file.user_id),
                orgTagName=file.org_tag,
                kbProfile=file.kb_profile,
                isPublic=file.is_public,
                createdAt=file.created_at,
                mergedAt=file.merged_at,
                vectorCount=vector_count_map.get(file.file_md5, 0),
                tableRowCount=table_row_count_map.get(file.file_md5, 0),
                imageBlockCount=image_block_count_map.get(file.file_md5, 0),
                relationNodeCount=relation_node_count_map.get(file.file_md5, 0),
                relationEdgeCount=relation_edge_count_map.get(file.file_md5, 0),
                documentUnitCount=document_unit_count_map.get(file.file_md5, 0),
                semanticBlockCount=semantic_block_count_map.get(file.file_md5, 0),
                parentChunkCount=parent_chunk_count_map.get(file.file_md5, 0),
                childChunkCount=child_chunk_count_map.get(file.file_md5, 0),
                visualPageCount=visual_page_count_map.get(file.file_md5, 0),
                visualEmbeddingCount=visual_embedding_count_map.get(file.file_md5, 0),
                visualIndexedCount=visual_indexed_count_map.get(file.file_md5, 0),
                acceptedBlockCount=block_quality_map.get(file.file_md5, {}).get("accepted", 0),
                weakBlockCount=block_quality_map.get(file.file_md5, {}).get("weak", 0),
                rejectedBlockCount=block_quality_map.get(file.file_md5, {}).get("rejected", 0),
            )
            for file in files
        ]

        return StructuredOverviewResponse(
            code=200,
            message="获取结构化总览成功",
            data=file_list,
        )
    except Exception as e:
        logger.error(f"获取结构化总览失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取结构化总览失败: {str(e)}"
        )


@documents_router.get("/structured-detail", response_model=StructuredFileDetailResponse)
async def get_structured_detail(
    file_md5: str = Query(..., description="文件MD5值"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    单文件结构化明细：
    - document_units
    - semantic_blocks
    - parent_chunks
    - child_chunks
    - image blocks
    """
    try:
        await profile_service.ensure_profile_selected(db)
        file_result = await db.execute(
            select(FileUpload).where(FileUpload.file_md5 == file_md5)
        )
        file_record = file_result.scalar_one_or_none()
        if not file_record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")

        has_permission = await permission_service.check_file_access_permission(
            db=db,
            user=current_user,
            file_user_id=file_record.user_id,
            file_org_tag=file_record.org_tag,
            file_is_public=file_record.is_public,
        )
        if not has_permission:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问该文档")

        units = (
            await db.execute(
                select(DocumentUnit)
                .where(DocumentUnit.file_md5 == file_md5)
                .order_by(DocumentUnit.unit_order.asc().nulls_last(), DocumentUnit.id.asc())
            )
        ).scalars().all()
        blocks = (
            await db.execute(
                select(SemanticBlock)
                .where(SemanticBlock.file_md5 == file_md5)
                .order_by(SemanticBlock.block_index.asc())
            )
        ).scalars().all()
        parent_chunks = (
            await db.execute(
                select(ParentChunk)
                .where(ParentChunk.file_md5 == file_md5)
                .order_by(ParentChunk.parent_chunk_id.asc())
            )
        ).scalars().all()
        child_chunks = (
            await db.execute(
                select(ChildChunk)
                .where(ChildChunk.file_md5 == file_md5)
                .order_by(ChildChunk.child_chunk_id.asc())
            )
        ).scalars().all()
        relation_nodes = (
            await db.execute(
                select(RelationNode)
                .where(RelationNode.file_md5 == file_md5)
                .order_by(RelationNode.page.asc().nulls_last(), RelationNode.node_name.asc(), RelationNode.id.asc())
            )
        ).scalars().all()
        relation_edges = (
            await db.execute(
                select(RelationEdge)
                .where(RelationEdge.file_md5 == file_md5)
                .order_by(RelationEdge.page.asc().nulls_last(), RelationEdge.id.asc())
            )
        ).scalars().all()
        images = (
            await db.execute(
                select(ImageBlock)
                .where(ImageBlock.file_md5 == file_md5)
                .order_by(ImageBlock.page.asc().nulls_last(), ImageBlock.id.asc())
            )
        ).scalars().all()
        visual_pages = (
            await db.execute(
                select(VisualPage)
                .where(VisualPage.file_md5 == file_md5)
                .order_by(VisualPage.page.asc().nulls_last(), VisualPage.sheet.asc().nulls_last(), VisualPage.id.asc())
            )
        ).scalars().all()
        visual_embeddings = (
            await db.execute(
                select(VisualPageEmbedding)
                .where(VisualPageEmbedding.file_md5 == file_md5)
                .order_by(VisualPageEmbedding.visual_page_id.asc(), VisualPageEmbedding.id.desc())
            )
        ).scalars().all()
        visual_embedding_map: dict[int, VisualPageEmbedding] = {}
        for row in visual_embeddings:
            visual_embedding_map.setdefault(int(row.visual_page_id), row)

        image_url_map: dict[str, str] = {}
        image_items: list[StructuredImageItem] = []
        for img in images:
            storage_path = (img.storage_path or "").strip()
            if not storage_path:
                continue
            image_url = (
                "/api/v1/documents/source-image"
                f"?file_md5={file_md5}"
                f"&image_path={quote(storage_path, safe='')}"
            )
            image_url_map[storage_path] = image_url
            image_items.append(
                StructuredImageItem(
                    page=img.page,
                    sheet=img.sheet,
                    sourceParser=img.source_parser,
                    imageUrl=image_url,
                    imageWidth=img.image_width,
                    imageHeight=img.image_height,
                    matchMode=img.match_mode,
                    matchConfidence=img.match_confidence,
                )
            )

        return StructuredFileDetailResponse(
            code=200,
            message="获取结构化明细成功",
            data=StructuredFileDetailData(
                fileMd5=file_record.file_md5,
                fileName=file_record.file_name,
                originalUrl=f"/api/v1/documents/source-file?file_md5={file_md5}",
                documentUnits=[
                    StructuredDocumentUnitItem(
                        unitType=row.unit_type,
                        unitKey=row.unit_key,
                        unitName=row.unit_name,
                        unitOrder=row.unit_order,
                        page=row.page,
                        sheet=row.sheet,
                        section=row.section,
                        parentUnitKey=row.parent_unit_key,
                    )
                    for row in units
                ],
                semanticBlocks=[
                    StructuredSemanticBlockItem(
                        blockIndex=row.block_index,
                        documentUnitKey=row.document_unit_key,
                        blockType=row.block_type,
                        sourceParser=row.source_parser,
                        page=row.page,
                        sheet=row.sheet,
                        section=row.section,
                        rowNo=row.row_no,
                        qualityScore=int(row.quality_score or 0),
                        qualityStatus=row.quality_status or "weak",
                        parserConfidence=row.parser_confidence,
                        validationFlags=_safe_json_list(row.validation_flags),
                        textPreview=_trim_preview_text(row.normalized_text or row.raw_text),
                        imageUrl=image_url_map.get((row.image_path or "").strip()) if row.image_path else None,
                    )
                    for row in blocks
                ],
                parentChunks=[
                    StructuredParentChunkItem(
                        parentChunkId=row.parent_chunk_id,
                        documentUnitKey=row.document_unit_key,
                        chunkType=row.chunk_type,
                        qualityScore=int(row.quality_score or 0),
                        qualityStatus=row.quality_status or "weak",
                        textPreview=_trim_preview_text(row.text_content, 300),
                    )
                    for row in parent_chunks
                ],
                childChunks=[
                    StructuredChildChunkItem(
                        childChunkId=row.child_chunk_id,
                        parentChunkId=row.parent_chunk_id,
                        documentUnitKey=row.document_unit_key,
                        chunkType=row.chunk_type,
                        qualityScore=int(row.quality_score or 0),
                        qualityStatus=row.quality_status or "weak",
                        neighborPrevId=row.neighbor_prev_id,
                        neighborNextId=row.neighbor_next_id,
                        textPreview=_trim_preview_text(row.text_content, 220),
                    )
                    for row in child_chunks
                ],
                images=image_items,
                visualPages=[
                    StructuredVisualPageItem(
                        visualPageId=row.id,
                        documentUnitId=row.document_unit_id,
                        unitType=row.unit_type,
                        page=row.page,
                        sheet=row.sheet,
                        section=row.section,
                        pageLabel=row.page_label,
                        renderSource=row.render_source,
                        renderVersion=row.render_version,
                        qualityStatus=row.quality_status or "accepted",
                        visualEmbeddingStatus=visual_embedding_map.get(row.id).status if visual_embedding_map.get(row.id) else None,
                        visualEmbeddingProvider=visual_embedding_map.get(row.id).provider if visual_embedding_map.get(row.id) else None,
                        visualEmbeddingModel=visual_embedding_map.get(row.id).model_name if visual_embedding_map.get(row.id) else None,
                        visualEmbeddingDim=visual_embedding_map.get(row.id).embedding_dim if visual_embedding_map.get(row.id) else None,
                        visualEmbeddingError=visual_embedding_map.get(row.id).error_message if visual_embedding_map.get(row.id) else None,
                        visualIndexed=bool(visual_embedding_map.get(row.id).es_doc_id) if visual_embedding_map.get(row.id) else False,
                        visualIndexDocId=visual_embedding_map.get(row.id).es_doc_id if visual_embedding_map.get(row.id) else None,
                        imageUrl=image_url_map.get((row.image_path or "").strip())
                        or (
                            "/api/v1/documents/source-image"
                            f"?file_md5={file_md5}"
                            f"&image_path={quote((row.image_path or '').strip(), safe='')}"
                        ),
                        imageWidth=row.image_width,
                        imageHeight=row.image_height,
                    )
                    for row in visual_pages
                    if str(row.image_path or "").strip()
                ],
                relationNodes=[
                    StructuredRelationNodeItem(
                        nodeId=row.id,
                        nodeKey=row.node_key,
                        nodeName=row.node_name,
                        nodeType=row.node_type,
                        page=row.page,
                        evidenceText=_trim_preview_text(row.evidence_text, 220) if row.evidence_text else None,
                    )
                    for row in relation_nodes
                ],
                relationEdges=[
                    StructuredRelationEdgeItem(
                        edgeId=row.id,
                        srcNodeId=row.src_node_id,
                        srcNodeName=row.src_node.node_name if row.src_node else str(row.src_node_id),
                        dstNodeId=row.dst_node_id,
                        dstNodeName=row.dst_node.node_name if row.dst_node else str(row.dst_node_id),
                        relationType=row.relation_type,
                        relationText=row.relation_text,
                        page=row.page,
                        evidenceText=_trim_preview_text(row.evidence_text, 220) if row.evidence_text else None,
                    )
                    for row in relation_edges
                ],
            )
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取结构化明细失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取结构化明细失败: {str(e)}"
        )


@documents_router.get("/es-preview", response_model=EsPreviewResponse)
async def get_es_preview(
    file_md5: str = Query(..., description="文件MD5值"),
    size: int = Query(5, ge=1, le=20, description="返回文档块数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    查看指定文件在 Elasticsearch 中的文档预览
    """
    try:
        await profile_service.ensure_profile_selected(db)
        file_result = await db.execute(
            select(FileUpload).where(FileUpload.file_md5 == file_md5)
        )
        file_record = file_result.scalar_one_or_none()
        if not file_record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")

        has_permission = await permission_service.check_file_access_permission(
            db=db,
            user=current_user,
            file_user_id=file_record.user_id,
            file_org_tag=file_record.org_tag,
            file_is_public=file_record.is_public
        )
        if not has_permission:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问该文档")
        es_result = await es_client.search(
            index=settings.ES_DEFAULT_INDEX,
            query={"term": {"file_md5": file_md5}},
            size=size
        )
        if not es_result:
            return EsPreviewResponse(code=200, message="ES中暂无数据", data=[])

        hits = es_result.get("hits", {}).get("hits", [])
        data = []
        for hit in hits:
            source = hit.get("_source", {})
            text = str(source.get("text_content", "") or "")
            data.append(
                EsPreviewItem(
                    chunkId=int(source.get("chunk_id", 0) or 0),
                    chunkType=source.get("chunk_type"),
                    page=source.get("page"),
                    sheet=source.get("sheet"),
                    textPreview=(text[:200] + "...") if len(text) > 200 else text,
                    score=float(hit.get("_score", 0.0) or 0.0)
                )
            )

        return EsPreviewResponse(code=200, message="获取ES文档预览成功", data=data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取ES文档预览失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取ES文档预览失败: {str(e)}"
        )


@documents_router.get("/source-detail", response_model=SourceDetailResponse)
async def get_source_detail(
    file_md5: str = Query(..., description="文件MD5值"),
    chunk_id: int | None = Query(None, ge=0, description="优先定位的 chunk_id"),
    page: int | None = Query(None, ge=1, description="可选页码过滤"),
    sheet: str | None = Query(None, description="可选sheet过滤"),
    size: int = Query(10, ge=1, le=30, description="返回文档块数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    聊天来源详情：
    - 返回指定来源的精确片段（按 chunk/page/sheet 过滤）
    - 返回原始源文件的访问链接（MinIO 预签名）
    """
    try:
        await profile_service.ensure_profile_selected(db)
        file_result = await db.execute(
            select(FileUpload).where(FileUpload.file_md5 == file_md5)
        )
        file_record = file_result.scalar_one_or_none()
        if not file_record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")

        has_permission = await permission_service.check_file_access_permission(
            db=db,
            user=current_user,
            file_user_id=file_record.user_id,
            file_org_tag=file_record.org_tag,
            file_is_public=file_record.is_public
        )
        if not has_permission:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问该文档")

        rows: list[EsPreviewItem] = []
        image_urls: list[str] = []
        object_path = minio_client.build_document_path(file_record.user_id, file_record.file_name)
        original_url = f"/api/v1/documents/source-file?file_md5={file_md5}"

        if chunk_id is not None:
            mapped_stmt = (
                select(ChunkSource)
                .where(
                    ChunkSource.file_md5 == file_md5,
                    ChunkSource.chunk_id == int(chunk_id),
                )
                .order_by(ChunkSource.source_order.asc())
            )
            mapped_rows = (await db.execute(mapped_stmt)).scalars().all()
            sheet_counter: dict[str, int] = {}
            page_counter: dict[int, int] = {}
            for mr in mapped_rows:
                s = (mr.sheet or "").strip()
                if s:
                    sheet_counter[s] = sheet_counter.get(s, 0) + 1
                if mr.page is not None:
                    try:
                        p = int(mr.page)
                        page_counter[p] = page_counter.get(p, 0) + 1
                    except Exception:
                        pass
            target_sheet = (sheet or "").strip() or (sorted(sheet_counter.items(), key=lambda x: x[1], reverse=True)[0][0] if sheet_counter else "")
            target_page = sorted(page_counter.items(), key=lambda x: x[1], reverse=True)[0][0] if page_counter else None

            scoped_rows = []
            for mr in mapped_rows:
                if target_sheet and (mr.sheet or "").strip() not in {"", target_sheet}:
                    continue
                if target_page is not None and mr.page is not None:
                    try:
                        if int(mr.page) != int(target_page):
                            continue
                    except Exception:
                        pass
                scoped_rows.append(mr)
            preview_rows = scoped_rows if scoped_rows else mapped_rows
            for mr in preview_rows:
                text = _clean_source_preview_text(str(mr.text_preview or ""), mr.source_type)
                if not text:
                    continue
                rows.append(
                    EsPreviewItem(
                        chunkId=int(chunk_id),
                        chunkType=mr.source_type,
                        page=mr.page,
                        sheet=mr.sheet,
                        textPreview=text,
                        score=1.0,
                    )
                )
                if len(rows) >= size:
                    break

            direct_image_paths: list[str] = []
            seen_paths: set[str] = set()
            for mr in preview_rows:
                p = (mr.image_path or "").strip()
                if not p or p in seen_paths:
                    continue
                seen_paths.add(p)
                direct_image_paths.append(p)

            if not direct_image_paths:
                for mr in mapped_rows:
                    p = (mr.image_path or "").strip()
                    if not p or p in seen_paths:
                        continue
                    seen_paths.add(p)
                    direct_image_paths.append(p)

            if not direct_image_paths:
                img_stmt = select(ImageBlock).where(ImageBlock.file_md5 == file_md5)
                if target_sheet:
                    img_stmt = img_stmt.where(ImageBlock.sheet == target_sheet)
                if target_page is not None:
                    img_stmt = img_stmt.where(ImageBlock.page == target_page)
                img_stmt = img_stmt.order_by(ImageBlock.id.asc()).limit(6)
                img_rows = (await db.execute(img_stmt)).scalars().all()
                for img in img_rows:
                    p = (img.storage_path or "").strip()
                    if not p or p in seen_paths:
                        continue
                    seen_paths.add(p)
                    direct_image_paths.append(p)
            for p in direct_image_paths:
                image_urls.append(
                    "/api/v1/documents/source-image"
                    f"?file_md5={file_md5}"
                    f"&image_path={quote(p, safe='')}"
                )
                if len(image_urls) >= 3:
                    break

        else:
            must_filters: list[dict] = [{"term": {"file_md5": file_md5}}]
            if page is not None:
                must_filters.append({"term": {"page": page}})
            if sheet:
                must_filters.append({"term": {"sheet": sheet}})
            try:
                es_result = await es_client.search(
                    index=settings.ES_DEFAULT_INDEX,
                    query={"bool": {"must": must_filters}},
                    size=size
                )
                hits = (es_result or {}).get("hits", {}).get("hits", [])
                for hit in hits:
                    source = hit.get("_source", {})
                    text = str(source.get("text_content", "") or "")
                    rows.append(
                        EsPreviewItem(
                            chunkId=int(source.get("chunk_id", 0) or 0),
                            chunkType=source.get("chunk_type"),
                            page=source.get("page"),
                            sheet=source.get("sheet"),
                            textPreview=(text[:500] + "...") if len(text) > 500 else text,
                            score=float(hit.get("_score", 0.0) or 0.0),
                        )
                    )
            except Exception as es_err:
                logger.warning(f"source-detail ES fallback failed for file_md5={file_md5}: {es_err}")
            img_stmt = select(ImageBlock).where(ImageBlock.file_md5 == file_md5)
            if sheet:
                img_stmt = img_stmt.where(ImageBlock.sheet == sheet)
            if page is not None:
                img_stmt = img_stmt.where(ImageBlock.page == page)
            img_stmt = img_stmt.order_by(ImageBlock.id.asc()).limit(12)
            img_rows = (await db.execute(img_stmt)).scalars().all()
            for img in img_rows:
                p = (img.storage_path or "").strip()
                if not p:
                    continue
                image_urls.append(
                    "/api/v1/documents/source-image"
                    f"?file_md5={file_md5}"
                    f"&image_path={quote(p, safe='')}"
                )

        return SourceDetailResponse(
            code=200,
            message="获取来源详情成功",
            data=SourceDetailData(
                fileMd5=file_record.file_md5,
                fileName=file_record.file_name,
                objectPath=object_path,
                originalUrl=original_url,
                imageUrls=image_urls,
                previewRows=rows,
            )
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取来源详情失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取来源详情失败: {str(e)}"
        )


@documents_router.get("/source-file")
async def get_source_file(
    file_md5: str = Query(..., description="文件MD5"),
    token: str | None = Query(None, description="可选访问 token（用于浏览器直连）"),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """
    通过后端代理返回原始文件，避免前端直接访问 MinIO 不可达。
    """
    try:
        current_user = await _resolve_user_from_bearer_or_query_token(request, db, token)
        file_result = await db.execute(
            select(FileUpload).where(FileUpload.file_md5 == file_md5)
        )
        file_record = file_result.scalar_one_or_none()
        if not file_record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")

        has_permission = await permission_service.check_file_access_permission(
            db=db,
            user=current_user,
            file_user_id=file_record.user_id,
            file_org_tag=file_record.org_tag,
            file_is_public=file_record.is_public
        )
        if not has_permission:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问该文档")

        object_path = minio_client.build_document_path(file_record.user_id, file_record.file_name)
        raw = minio_client.download_file(
            bucket_name=settings.MINIO_DEFAULT_BUCKET,
            object_name=object_path,
        )
        if not raw:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="原文件不存在")

        return StreamingResponse(
            iter([raw]),
            media_type=_guess_mime_by_name(file_record.file_name),
            headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(file_record.file_name)}"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取原文件失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取原文件失败")


@documents_router.get("/source-image")
async def get_source_image(
    file_md5: str = Query(..., description="文件MD5"),
    image_path: str = Query(..., description="图片对象路径"),
    token: str | None = Query(None, description="可选访问 token（用于浏览器直连）"),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """
    通过后端代理返回来源图片，确保浏览器可显示。
    """
    try:
        current_user = await _resolve_user_from_bearer_or_query_token(request, db, token)
        file_result = await db.execute(
            select(FileUpload).where(FileUpload.file_md5 == file_md5)
        )
        file_record = file_result.scalar_one_or_none()
        if not file_record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")

        has_permission = await permission_service.check_file_access_permission(
            db=db,
            user=current_user,
            file_user_id=file_record.user_id,
            file_org_tag=file_record.org_tag,
            file_is_public=file_record.is_public
        )
        if not has_permission:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问该文档")

        img_result = await db.execute(
            select(ImageBlock).where(
                ImageBlock.file_md5 == file_md5,
                ImageBlock.storage_path == image_path,
            )
        )
        img = img_result.scalar_one_or_none()
        if not img:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图片不存在")

        raw = minio_client.download_file(
            bucket_name=settings.MINIO_DEFAULT_BUCKET,
            object_name=image_path,
        )
        if not raw:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图片对象不存在")

        media_type = img.content_type or _guess_mime_by_name(image_path)
        return StreamingResponse(iter([raw]), media_type=media_type)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取来源图片失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取来源图片失败")
