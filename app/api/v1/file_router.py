"""
文件相关接口路由
"""
import mimetypes
import re
import unicodedata
from urllib.parse import quote

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, get_current_user
from app.clients.elasticsearch_client import es_client
from app.clients.minio_client import minio_client
from app.core.config import settings
from app.models.file import DocumentVector, FileUpload
from app.models.file import RelationNode, RelationEdge, ImageBlock, TableRow, ChunkSource
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
)
from app.services.file_service import file_service
from app.services.permission_service import permission_service
from app.services.profile_service import profile_service
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
