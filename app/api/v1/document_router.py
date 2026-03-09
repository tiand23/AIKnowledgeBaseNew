"""
文档检索和管理接口
"""
import json
import re

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, get_current_user
from app.models.file import TableRow, FileUpload
from app.models.user import User
from app.services.search_service import search_service
from app.services.relation_search_service import relation_search_service
from app.services.query_understanding_service import query_understanding_service
from app.services.profile_service import profile_service
from app.schemas.search import (
    HybridSearchRequest,
    HybridSearchResponse,
    SearchResultItem,
    ScheduleDebugItem,
    ScheduleDebugResponse,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/ping")
async def document_ping():
    return {
        "code": 200,
        "message": "文档模块正常",
        "data": {"module": "document", "status": "ok"}
    }


@router.get("/hybrid", response_model=HybridSearchResponse, summary="混合检索接口")
async def hybrid_search(
    query: str = Query(..., description="搜索查询字符串", min_length=1, max_length=500),
    topK: int = Query(default=10, description="返回结果数量", ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    混合检索接口
    
    - 结合语义检索（向量相似度）和关键词检索（全文搜索）
    - 自动应用权限过滤（用户只能看到有权限的文档）
    - 支持指定返回结果数量
    
    Args:
        query: 搜索查询字符串
        topK: 返回结果数量（默认10，最大100）
        db: 数据库会话
        current_user: 当前登录用户
        
    Returns:
        检索结果列表，包含：
        - file_md5: 文件MD5
        - chunk_id: 分块ID
        - text_content: 文本内容
        - score: 相关性分数
        - file_name: 文件名
    """
    try:
        logger.info(f"用户 {current_user.id} 执行混合检索: query='{query[:50]}...', topK={topK}")

        selected_profile = await profile_service.get_selected_profile(db)
        profile_strategy = profile_service.get_strategy(selected_profile)
        understood = query_understanding_service.understand(
            query=query,
            profile_terms=profile_strategy.query_expand_terms
        )

        results = await search_service.hybrid_search(
            db=db,
            user=current_user,
            query_text=str(understood.get("rewritten_query") or query),
            top_k=topK,
            entities=understood.get("entities") or [],
            selected_profile=selected_profile,
        )
        
        result_items = [
            SearchResultItem(
                file_md5=item["file_md5"],
                chunk_id=item["chunk_id"],
                text_content=item["text_content"],
                score=item["score"],
                file_name=item["file_name"]
            )
            for item in results
        ]
        
        return HybridSearchResponse(
            code=200,
            message="检索成功",
            data=result_items
        )
        
    except Exception as e:
        logger.error(f"混合检索失败: {e}", exc_info=True)
        error_msg = str(e)
        if "Elasticsearch" in error_msg or "search" in error_msg.lower():
            detail_msg = f"搜索服务错误: {error_msg[:200]}。请检查Elasticsearch是否正常运行，以及索引中是否有数据。"
        elif "向量" in error_msg or "embedding" in error_msg.lower():
            detail_msg = f"向量化服务错误: {error_msg[:200]}。请检查向量化服务是否正常运行。"
        else:
            detail_msg = f"检索失败: {error_msg[:200]}"
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail_msg
        )


@router.get("/flow", response_model=HybridSearchResponse, summary="流程关系检索接口")
async def flow_search(
    query: str = Query(..., description="流程查询字符串", min_length=1, max_length=500),
    topK: int = Query(default=10, description="返回结果数量", ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    流程关系检索：
    - 优先命中关系索引（nodes/edges）
    - 若关系检索为空，自动回退混合检索
    """
    try:
        logger.info(f"用户 {current_user.id} 执行流程检索: query='{query[:50]}...', topK={topK}")
        selected_profile = await profile_service.get_selected_profile(db)
        profile_strategy = profile_service.get_strategy(selected_profile)
        understood = query_understanding_service.understand(
            query=query,
            profile_terms=profile_strategy.query_expand_terms
        )
        rewritten_query = str(understood.get("rewritten_query") or query)
        entities = understood.get("entities") or []

        results = await relation_search_service.search_relations(
            db=db,
            user=current_user,
            query_text=rewritten_query,
            top_k=topK
        )
        if not results:
            logger.info("流程检索为空，回退混合检索")
            results = await search_service.hybrid_search(
                db=db,
                user=current_user,
                query_text=rewritten_query,
                top_k=topK,
                entities=entities,
                selected_profile=selected_profile,
            )

        result_items = [
            SearchResultItem(
                file_md5=item.get("file_md5", ""),
                chunk_id=int(item.get("chunk_id", 0) or 0),
                text_content=item.get("text_content", ""),
                score=float(item.get("score", 0.0) or 0.0),
                file_name=item.get("file_name", "未知文件")
            )
            for item in results
        ]

        return HybridSearchResponse(code=200, message="检索成功", data=result_items)
    except Exception as e:
        logger.error(f"流程检索失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"流程检索失败: {str(e)[:200]}"
        )


@router.get("/schedule-debug", response_model=ScheduleDebugResponse, summary="甘特日程结构化调试")
async def schedule_debug(
    query: str = Query(default="", description="可选：过滤关键词（任务名/说明）"),
    file_md5: str = Query(default="", description="可选：指定文件MD5"),
    topK: int = Query(default=100, description="返回条数", ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    查看 Excel 甘特/日程结构化识别结果：
    - 数据来源：table_rows(source_parser=xlsx_schedule)
    - 用于快速检查 task/period/confidence 是否提取正确
    """
    try:
        selected_profile = await profile_service.get_selected_profile(db)
        if not selected_profile:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="先初始化知识库场景后再查询",
            )

        file_meta = await search_service._load_accessible_file_metadata(db, current_user)
        allowed_md5 = {k for k in file_meta.keys() if k}
        if not allowed_md5:
            return ScheduleDebugResponse(code=200, message="无可访问文件", data=[])

        if file_md5:
            if file_md5 not in allowed_md5:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无该文件访问权限")
            target_md5 = {file_md5}
        else:
            target_md5 = allowed_md5

        stmt = (
            select(
                TableRow.file_md5,
                TableRow.sheet,
                TableRow.row_no,
                TableRow.row_json,
                FileUpload.file_name,
            )
            .join(FileUpload, FileUpload.file_md5 == TableRow.file_md5)
            .where(TableRow.file_md5.in_(target_md5))
            .where(TableRow.source_parser == "xlsx_schedule")
            .order_by(TableRow.file_md5.asc(), TableRow.row_no.asc())
            .limit(max(topK * 4, 200))
        )
        rows = (await db.execute(stmt)).all()
        if not rows:
            return ScheduleDebugResponse(code=200, message="未找到日程结构化数据", data=[])

        keywords = []
        query_norm = (query or "").strip().lower()
        if query_norm:
            keywords.extend(re.findall(r"[\u3040-\u30ff\u3400-\u9fffA-Za-z0-9_/.-]{2,32}", query_norm))

        items = []
        for row in rows:
            f_md5, sheet, row_no, row_json, file_name = row
            data = {}
            try:
                data = json.loads(row_json) if isinstance(row_json, str) else {}
            except Exception:
                data = {}
            task = str(data.get("task") or "")
            detail = str(data.get("task_detail") or "")
            start = str(data.get("period_start") or "")
            end = str(data.get("period_end") or "")
            confidence = float(data.get("confidence") or 0.0)

            match_score = 0.0
            if keywords:
                hay = f"{task} {detail} {sheet or ''}".lower()
                match_score = float(sum(1 for k in keywords if k in hay))
                if match_score <= 0:
                    continue

            profile_bonus = 0.2 if (file_meta.get(f_md5) and file_meta[f_md5].kb_profile == selected_profile) else 0.0
            items.append(
                {
                    "file_md5": f_md5,
                    "file_name": file_name or "未知文件",
                    "sheet": sheet,
                    "row_no": row_no,
                    "task": task or None,
                    "period_start": start or None,
                    "period_end": end or None,
                    "task_detail": detail or None,
                    "confidence": round(confidence, 3),
                    "match_score": round(match_score + profile_bonus, 3),
                }
            )

        items.sort(key=lambda x: (x["match_score"], x["confidence"]), reverse=True)
        data = [ScheduleDebugItem(**x) for x in items[:topK]]
        return ScheduleDebugResponse(code=200, message="调试数据获取成功", data=data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"甘特调试接口失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"甘特调试接口失败: {str(e)[:200]}",
        )
